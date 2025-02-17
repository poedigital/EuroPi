import tkinter as tk 
from tkinter import ttk
from oled_emulator import draw_equation
from PIL import Image, ImageTk
from tkinter import Canvas
import json
import os
import copy

CODEX_FILE = "codex.txt"
MARGIN = 2
MAX_DIM = 12
CELL_SIZE = 18
CANVAS_SIZE = 256
emulator_width, emulator_height = 128, 32
edit_mode = False 

equation_dict = []
byte_array_dict = {}
undo_stack = []
redo_stack = []
pixel_data = []
current_byte_key = None
grid_size_var = None

def load_codex():
    if os.path.exists(CODEX_FILE):
        with open(CODEX_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data.get("equation_dict", []), data.get("byte_array_dict", {})
            except Exception as e:
                return [], {}
    return [], {}

def save_codex():
    with open(CODEX_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "equation_dict": equation_dict,
            "byte_array_dict": byte_array_dict
        }, f, indent=4)

def refresh_byte_tree():
    byte_tree.delete(*byte_tree.get_children())  # Clear the tree
    for byte_id, entry in byte_array_dict.items():
        name = entry["name"]
        size = entry["size"]
        data = entry["data"]
        byte_tree.insert("", "end", values=(byte_id, name, size, data))  # Insert with ID
    # Optionally highlight the current selection
    if current_byte_key in byte_array_dict:
        for iid in byte_tree.get_children():
            if byte_tree.item(iid, "values")[0] == current_byte_key:
                byte_tree.selection_set(iid)
                break


def get_snapshot():
    return {
        "equation_dict": copy.deepcopy(equation_dict),
        "byte_array_dict": copy.deepcopy(byte_array_dict),
        "pixel_data": copy.deepcopy(pixel_data),
        "current_byte_key": current_byte_key,
        "grid_size": grid_size_var.get()
    }

def set_snapshot(snap, push_to_stack=False):
    if push_to_stack:
        push_snapshot(clear_redo=False)  # Save the current state before overwriting

    # Temporarily disable grid_size_var trace
    grid_size_var.trace_vdelete("write", grid_size_var.trace_id)

    equation_dict.clear()
    equation_dict.extend(snap["equation_dict"])
    byte_array_dict.clear()
    byte_array_dict.update(snap["byte_array_dict"])
    for r in range(MAX_DIM):
        for c in range(MAX_DIM):
            pixel_data[r][c] = snap["pixel_data"][r][c]
    global current_byte_key
    current_byte_key = snap["current_byte_key"]
    grid_size_var.set(snap["grid_size"])  # Update without triggering `on_grid_size_change`

    # Rebind the trace after setting the value
    grid_size_var.trace_id = grid_size_var.trace_add("write", on_grid_size_change)

    refresh_equation_tree()
    refresh_byte_tree()
    update_display()
    update_byte_array()
    update_oled_equation()

def push_snapshot(clear_redo=True):
    if clear_redo:
        redo_stack.clear()
    undo_stack.append(get_snapshot())

def pop_undo():
    if not undo_stack:
        return
    current_state = get_snapshot()
    previous_state = undo_stack.pop()
    redo_stack.append(current_state)  # Push the current state to redo stack
    set_snapshot(previous_state, push_to_stack=False)  # Don't push to undo stack
    save_codex()

def pop_redo():
    if not redo_stack:
        return
    current_state = get_snapshot()
    next_state = redo_stack.pop()
    undo_stack.append(current_state)  # Push the current state back to undo stack
    set_snapshot(next_state, push_to_stack=False)  # Don't push to redo stack
    save_codex()

def update_oled_equation():
    sel = eq_tree.selection()
    if not sel:
        return
    idx = eq_tree.index(sel[0])
    if idx < 0 or idx >= len(equation_dict):
        return
    data = equation_dict[idx]
    title = data.get("title", "")
    eqn = data.get("equation", "")
    update_oled_canvas(title, eqn)

# Initialize Data
##########################################################
equation_dict, byte_array_dict = load_codex()
pixel_data = [[0]*MAX_DIM for _ in range(MAX_DIM)]
current_byte_key = None

root = tk.Tk()
root.title("Byte-Forge")
root.geometry("1000x600")

style = ttk.Style(root)
style.configure("Treeview",
    background="black",
    foreground="white",
    fieldbackground="#212121",
    rowheight=22
)
style.map("Treeview",
    background=[("selected", "#9bbcff")],
    foreground=[("selected", "black")]
)

top_frame = ttk.Frame(root)
top_frame.pack(side="top", fill="x")

main_frame = ttk.Frame(root)
main_frame.pack(side="top", fill="both", expand=True)

left_frame = ttk.Frame(main_frame)
left_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

eq_btn_frame = ttk.Frame(left_frame)
eq_btn_frame.pack(side="top", fill="x")

def add_equation():
    push_snapshot()
    new_id = max(eq["id"] for eq in equation_dict) + 1 if equation_dict else 1
    new_eq = {
        "id": new_id,
        "title": "",
        "equation": "",
        "var": [],
        "settings": {},
        "byte": []
    }
    equation_dict.append(new_eq)
    refresh_equation_tree()
    save_codex()
    update_oled_equation()

def remove_equation():
    sel = eq_tree.selection()
    if not sel:
        return
    push_snapshot()
    iid = sel[0]
    idx = eq_tree.index(iid)
    eq_tree.delete(iid)
    del equation_dict[idx]
    save_codex()
    update_oled_equation()

def refresh_all():
    refresh_equation_tree()
    refresh_byte_tree()
    update_oled_equation()

# Adding buttons to the toolbar
btn_eq_add = tk.Button(eq_btn_frame, text="+", command=add_equation)
btn_eq_add.pack(side="left", padx=5)

btn_eq_del = tk.Button(eq_btn_frame, text="-", command=remove_equation)
btn_eq_del.pack(side="left", padx=5)

btn_refresh = tk.Button(eq_btn_frame, text="⟳", command=refresh_all, font=("Arial", 12))
btn_refresh.pack(side="left", padx=5)

btn_eq_undo = tk.Button(eq_btn_frame, text="Undo", command=pop_undo)
btn_eq_undo.pack(side="left", padx=5)

btn_eq_redo = tk.Button(eq_btn_frame, text="Redo", command=pop_redo)
btn_eq_redo.pack(side="left", padx=5)


# Equation Tree
##########################################################
eq_cols = ("ID", "Title", "Equation", "Vars", "Byte")
eq_tree = ttk.Treeview(left_frame, columns=eq_cols, show="headings", selectmode="browse")
for col in eq_cols:
    eq_tree.heading(col, text=col)
    eq_tree.column(col, width=100, anchor="w")

eq_tree.column("ID", width=40)
eq_tree.column("Title", width=120)
eq_tree.column("Equation", width=180)
eq_tree.column("Vars", width=100)
eq_tree.column("Byte", width=80)
eq_tree.pack(fill="both", expand=True)

eq_edit_entry = tk.Entry(eq_tree)

id_to_iid_map = {}  # Global mapping from `id` to `iid`

def refresh_equation_tree():
    eq_tree.delete(*eq_tree.get_children())
    id_to_iid_map.clear()  # Clear the mapping

    for e in equation_dict:
        i = e.get("id", "")
        t = e.get("title", "")
        f = e.get("equation", "")
        v = ", ".join(e.get("var", []))
        b = ", ".join(e.get("byte", []))
        iid = eq_tree.insert("", "end", values=(i, t, f, v, b))
        id_to_iid_map[i] = iid  # Store the mapping

def show_byte_dropdown(iid, bbox):
    idx = eq_tree.index(iid)
    eq_data = equation_dict[idx]

    def rebuild_dropdown():
        for widget in frame.winfo_children():
            widget.destroy()

        row_num = 0
        active_list = set(eq_data["byte"])
        for byte_key in byte_array_dict:
            row_str = byte_key
            sign = "✓" if byte_key in active_list else "+"

            def toggle_factory(key):
                def toggle():
                    if key in eq_data["byte"]:
                        eq_data["byte"].remove(key)
                    else:
                        eq_data["byte"].append(key)
                    refresh_equation_tree()
                    save_codex()
                    rebuild_dropdown()
                    update_oled_equation()
                return toggle

            lbl = tk.Label(frame, text=row_str, fg="white", bg="black", anchor="w")
            lbl.grid(row=row_num, column=0, sticky="w", padx=5, pady=3)
            row_btn = tk.Button(frame, text=sign, command=toggle_factory(byte_key), width=2)
            row_btn.grid(row=row_num, column=1, sticky="e")
            row_num += 1

        close_btn = tk.Button(frame, text="Close", command=win.destroy)
        close_btn.grid(row=row_num, column=0, columnspan=2, pady=5)

    win = tk.Toplevel(eq_tree)
    win.title("Select Byte(s)")
    win.geometry(f"+{bbox[0]+eq_tree.winfo_rootx()}+{bbox[1]+eq_tree.winfo_rooty()+50}")
    win.wm_overrideredirect(True)

    frame = ttk.Frame(win)
    frame.pack(fill="both", expand=True)

    rebuild_dropdown()

def on_eq_double_click(event):
    """
    Handles double-click events in the equation tree.
    Triggers the byte dropdown when the "Byte" column is double-clicked.
    Enables inline editing for other columns with autosave on click away.
    """
    sel = eq_tree.selection()
    if not sel:
        return

    iid = sel[0]
    idx = eq_tree.index(iid)
    col_id = eq_tree.identify_column(event.x)
    c_index = int(col_id.replace("#", "")) - 1  # Map column to 0-based index

    # Only trigger dropdown for "Byte" column
    if c_index < 0 or c_index >= len(eq_cols):
        return

    if eq_cols[c_index] == "Byte":
        bbox = eq_tree.bbox(iid, column=col_id)
        if bbox:
            show_byte_dropdown(iid, bbox)
        return

    # Handle inline editing for other columns
    bbox = eq_tree.bbox(iid, column=col_id)
    if not bbox:
        return

    x, y, w, h = bbox
    eq_edit_entry.place(x=x, y=y, width=w, height=h, in_=eq_tree)
    current_val = eq_tree.set(iid, eq_cols[c_index])
    eq_edit_entry.delete(0, tk.END)
    eq_edit_entry.insert(0, current_val)
    eq_edit_entry.focus()

    # Pass iid and idx to the save function
    def save_and_exit_edit(event=None):
        """
        Save the new value and exit inline editing mode.
        """
        new_val = eq_edit_entry.get()
        eq_edit_entry.place_forget()

        # Update the equation dictionary directly
        field = eq_cols[c_index].lower()
        if field in ["vars", "byte"]:
            equation_dict[idx][field] = [x.strip() for x in new_val.split(",")] if new_val else []
        elif field != "id":
            equation_dict[idx][field] = new_val

            # Trigger OLED update if "title" or "equation" changes
            if field in ["title", "equation"]:
                data = equation_dict[idx]
                title = data.get("title", "")
                eqn = data.get("equation", "")
                update_oled_canvas(title, eqn)

        save_codex()
        refresh_equation_tree()

    # Bind actions for saving
    eq_edit_entry.bind("<Return>", lambda _: save_and_exit_edit())
    eq_edit_entry.bind("<FocusOut>", save_and_exit_edit)  # Save on losing focus

def on_eq_click(event):
    region = eq_tree.identify_region(event.x, event.y)
    if region in ("nothing", "separator", "heading"):
        eq_tree.selection_remove(*eq_tree.selection())
        return  # Ignore clicks outside rows

    # Force selection update
    iid = eq_tree.identify_row(event.y)
    if iid:
        eq_tree.selection_set(iid)

    # Check if the selection actually changed before updating
    sel = eq_tree.selection()
    if sel:
        idx = eq_tree.index(sel[0])
        if idx != getattr(on_eq_click, "last_index", None):  # Compare with the last rendered index
            on_eq_click.last_index = idx  # Update the last rendered index
            update_oled_equation()

eq_tree.bind("<Double-1>", on_eq_double_click)
eq_tree.bind("<Button-1>", on_eq_click)

# Constants for the OLED preview canvas (smaller size for the toolbar)
toolbar_canvas_width, toolbar_canvas_height = emulator_width * 2, emulator_height * 2

# Add OLED Canvas to Toolbar (next to buttons)
oled_canvas = Canvas(eq_btn_frame, width=toolbar_canvas_width, height=toolbar_canvas_height, bg="black", highlightthickness=1)
oled_canvas.pack(side="right", padx=10, pady=5)  # Align it to the right of the toolbar

def update_oled_canvas(title, equation):
    """
    Updates the OLED canvas with the rendered equation.
    """
    try:
        # Render the OLED content
        oled_image = draw_equation(title, equation)

        # Clip excess padding (if any) and resize
        clipped_image = oled_image.crop((0, 0, emulator_width, emulator_height))  # Ensure dimensions are exact
        oled_image_resized = clipped_image.resize((toolbar_canvas_width, toolbar_canvas_height), Image.NEAREST)
        snapshot_tk = ImageTk.PhotoImage(oled_image_resized)

        # Clear the canvas and draw the new image
        oled_canvas.delete("all")
        oled_canvas.create_image(0, 0, anchor="nw", image=snapshot_tk)
        oled_canvas.image = snapshot_tk  # Prevent garbage collection
    except Exception as e:
        print(f"[ERROR] Failed to update OLED canvas: {e}")

# Right-Side Pixel Editor
##########################################################
right_frame = ttk.Frame(main_frame)
right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

byte_cols = ("ID", "Name", "Size", "Data")
byte_tree = ttk.Treeview(right_frame, columns=byte_cols, show="headings", selectmode="browse")
byte_tree.heading("ID", text="ID")
byte_tree.heading("Name", text="Name")
byte_tree.heading("Size", text="Size")
byte_tree.heading("Data", text="Byte Array")
byte_tree.column("ID", width=50, anchor="center")
byte_tree.column("Name", width=90, anchor="w")
byte_tree.column("Size", width=40, anchor="center")
byte_tree.column("Data", width=200, anchor="w")
byte_tree.grid(row=4, column=0, columnspan=3, sticky="nsew")

byte_scroll = ttk.Scrollbar(right_frame, orient="vertical", command=byte_tree.yview)
byte_scroll.grid(row=4, column=3, sticky="ns")
byte_tree.configure(yscrollcommand=byte_scroll.set)

grid_size_var = tk.IntVar(value=8)
canvas = tk.Canvas(right_frame, width=CANVAS_SIZE, height=CANVAS_SIZE, bg="#444444")
canvas.grid(row=0, column=0, columnspan=4, sticky="n", padx=5, pady=5)

def update_display():
    """
    Refreshes the canvas based on `pixel_data` and updates the OLED emulator.
    """
    canvas.delete("all")
    s = grid_size_var.get()
    total_cells = s + 2 * MARGIN
    grid_px = total_cells * CELL_SIZE
    offset_x = (CANVAS_SIZE - grid_px) // 2
    offset_y = (CANVAS_SIZE - grid_px) // 2

    for y in range(MAX_DIM):
        for x in range(MAX_DIM):
            val = pixel_data[y][x]
            in_region = (x >= MARGIN and x < MARGIN + s and y >= MARGIN and y < MARGIN + s)
            color = "white" if (val == 0 and in_region) else "black" if (val == 1 and in_region) else "#777777"

            left = offset_x + x * CELL_SIZE
            top = offset_y + y * CELL_SIZE
            right = left + CELL_SIZE
            bottom = top + CELL_SIZE

            rid = canvas.create_rectangle(left, top, right, bottom, fill=color, outline="black")

            def click_closure(e, cx=x, cy=y):
                push_snapshot()
                pixel_data[cy][cx] = 1 - pixel_data[cy][cx]  # Toggle pixel
                update_display()
                update_byte_array()
                update_oled_equation()  # Trigger OLED redraw dynamically

            if in_region:
                canvas.tag_bind(rid, "<Button-1>", click_closure)

    # Draw bounding box
    act_left = offset_x + MARGIN * CELL_SIZE
    act_top = offset_y + MARGIN * CELL_SIZE
    act_right = act_left + s * CELL_SIZE
    act_bottom = act_top + s * CELL_SIZE
    canvas.create_rectangle(act_left, act_top, act_right, act_bottom, outline="blue", width=2)


def update_byte_array():
    """
    Updates the `byte_array_dict` for the currently selected byte based on `pixel_data`.
    """
    s = grid_size_var.get()
    arr = []
    for row in range(s):
        b = 0
        for col in range(s):
            if pixel_data[row + MARGIN][col + MARGIN] == 1:
                b |= (1 << (s - 1 - col))  # Bitwise set for each cell
        arr.append(b)

    if current_byte_key:
        byte_array_dict[current_byte_key]["size"] = s
        byte_array_dict[current_byte_key]["data"] = arr
    save_codex()
    refresh_byte_tree()


def on_byte_tree_select(event):
    """
    Handles selection in the byte tree, updating the grid and loading `pixel_data`.
    """
    sel = byte_tree.selection()
    if not sel:
        return
    iid = sel[0]
    row_vals = byte_tree.item(iid, "values")
    byte_id = int(row_vals[0])  # First column is now ID

    global current_byte_key
    current_byte_key = byte_id

    # Reset `pixel_data` to match the selected byte
    for yy in range(MAX_DIM):
        for xx in range(MAX_DIM):
            pixel_data[yy][xx] = 0  # Clear the grid

    if byte_id in byte_array_dict:
        byte_data = byte_array_dict[byte_id]
        grid_size_var.set(byte_data["size"])
        for rr in range(byte_data["size"]):
            row_data = byte_data["data"][rr]
            for cc in range(byte_data["size"]):
                bit = (row_data >> (byte_data["size"] - 1 - cc)) & 1
                pixel_data[rr + MARGIN][cc + MARGIN] = bit

        update_display()
        update_oled_equation()  # Trigger redraw for OLED

byte_tree.bind("<<TreeviewSelect>>", on_byte_tree_select)


def on_byte_tree_double_click(event):
    """
    Handles double-click events in the byte tree for renaming the selected byte.
    """
    sel = byte_tree.selection()
    if not sel:
        return
    iid = sel[0]
    col_id = byte_tree.identify_column(event.x)
    if col_id != "#2":  # Only allow renaming in the "Name" column
        return
    byte_id = int(byte_tree.item(iid)["values"][0])  # ID is now in the first column
    bbox = byte_tree.bbox(iid, column=1)
    if not bbox:
        return

    byte_edit_entry = tk.Entry(byte_tree)
    x, y, w, h = bbox
    byte_edit_entry.place(x=x, y=y, width=w, height=h, in_=byte_tree)
    byte_edit_entry.delete(0, tk.END)
    byte_edit_entry.insert(0, byte_array_dict[byte_id]["name"])
    byte_edit_entry.focus()

    def on_rename(_):
        new_name = byte_edit_entry.get().strip()
        byte_edit_entry.place_forget()
        if any(entry["name"] == new_name for entry in byte_array_dict.values()):
            print(f"[DEBUG] Name '{new_name}' already exists. Skipping rename.")
            return
        byte_array_dict[byte_id]["name"] = new_name
        refresh_byte_tree()
        save_codex()

    byte_edit_entry.bind("<Return>", on_rename)

byte_tree.bind("<Double-1>", on_byte_tree_double_click)

def update_byte_array():
    """
    Updates the `byte_array_dict` for the currently selected byte based on `pixel_data`.
    """
    s = grid_size_var.get()
    arr = []
    for row in range(s):
        b = 0
        for col in range(s):
            if pixel_data[row + MARGIN][col + MARGIN] == 1:
                b |= (1 << (s - 1 - col))  # Bitwise set for each cell
        arr.append(b)

    if current_byte_key:
        byte_array_dict[current_byte_key]["size"] = s
        byte_array_dict[current_byte_key]["data"] = arr
    save_codex()
    refresh_byte_tree()
    
def on_grid_size_change(*_):
    push_snapshot()
    update_display()
    update_byte_array()

grid_size_var.trace_add("write", on_grid_size_change)

# SHIFT Buttons
##########################################################
shift_frame = ttk.Frame(right_frame)
shift_frame.grid(row=1, column=0, columnspan=4, sticky="n", pady=3)

def shift_pixels(direction):
    push_snapshot()
    temp = copy.deepcopy(pixel_data)

    if direction == "left":
        for yy in range(MAX_DIM):
            for xx in range(1, MAX_DIM):
                pixel_data[yy][xx-1] = temp[yy][xx]
            pixel_data[yy][MAX_DIM-1] = 0
    elif direction == "right":
        for yy in range(MAX_DIM):
            for xx in range(MAX_DIM-1):
                pixel_data[yy][xx+1] = temp[yy][xx]
            pixel_data[yy][0] = 0
    elif direction == "up":
        for yy in range(1, MAX_DIM):
            for xx in range(MAX_DIM):
                pixel_data[yy-1][xx] = temp[yy][xx]
        for xx in range(MAX_DIM):
            pixel_data[MAX_DIM-1][xx] = 0
    elif direction == "down":
        for yy in range(MAX_DIM-1):
            for xx in range(MAX_DIM):
                pixel_data[yy+1][xx] = temp[yy][xx]
        for xx in range(MAX_DIM):
            pixel_data[0][xx] = 0

    update_display()
    update_byte_array()

tk.Button(shift_frame, text="←", width=3, command=lambda: shift_pixels("left")).pack(side="left", padx=2)
tk.Button(shift_frame, text="→", width=3, command=lambda: shift_pixels("right")).pack(side="left", padx=2)
tk.Button(shift_frame, text="↑", width=3, command=lambda: shift_pixels("up")).pack(side="left", padx=2)
tk.Button(shift_frame, text="↓", width=3, command=lambda: shift_pixels("down")).pack(side="left", padx=2)

# Byte Editor (top-level controls for Undo/Redo, Clear, etc.)
##########################################################
byte_op_frame = ttk.Frame(right_frame)
byte_op_frame.grid(row=2, column=0, columnspan=4, sticky="n", pady=3)

btn_byte_undo = tk.Button(byte_op_frame, text="Undo", command=pop_undo)
btn_byte_undo.pack(side="left", padx=5)

btn_byte_redo = tk.Button(byte_op_frame, text="Redo", command=pop_redo)
btn_byte_redo.pack(side="left", padx=5)

clear_btn = tk.Button(byte_op_frame, text="Clear")
clear_btn.pack(side="left", padx=5)

lbl_size = tk.Label(byte_op_frame, text="Size:")
lbl_size.pack(side="left", padx=5)
size_values = list(range(5, 12))
size_om = ttk.OptionMenu(byte_op_frame, grid_size_var, 8, *size_values)
size_om.pack(side="left")

def on_clear_canvas():
    push_snapshot()
    for yy in range(MAX_DIM):
        for xx in range(MAX_DIM):
            pixel_data[yy][xx] = 0
    update_display()
    update_byte_array()

clear_btn.config(command=on_clear_canvas)

# Byte Entry (Add / Remove Bytes)
##########################################################
byte_entry_frame = ttk.Frame(right_frame)
byte_entry_frame.grid(row=3, column=0, columnspan=4, sticky="n", pady=3)

byte_text = tk.Entry(byte_entry_frame)
byte_text.pack(side="left", padx=5)

# Global ID counter
next_byte_id = 1

def get_next_byte_id():
    global next_byte_id
    while next_byte_id in byte_array_dict:
        next_byte_id += 1
    return next_byte_id

def on_add_byte():
    push_snapshot()
    key = byte_text.get().strip()
    if not key:
        print("[DEBUG] No name provided for new byte.")
        return
    if any(entry["name"] == key for entry in byte_array_dict.values()):
        print(f"[DEBUG] Name '{key}' already exists. Skipping add.")
        return
    s = grid_size_var.get()
    arr = []
    for row in range(s):
        b = 0
        for col in range(s):
            if pixel_data[row + MARGIN][col + MARGIN] == 1:
                b |= (1 << (s - 1 - col))
        arr.append(b)
    byte_id = get_next_byte_id()
    byte_array_dict[byte_id] = {"name": key, "size": s, "data": arr}
    global current_byte_key
    current_byte_key = byte_id  # Ensure the newly added byte is selected
    refresh_byte_tree()
    save_codex()
    print(f"[DEBUG] Added byte with ID {byte_id}, name '{key}'.")

btn_byte_add = tk.Button(byte_entry_frame, text="+", command=on_add_byte)
btn_byte_add.pack(side="left", padx=5)

def on_remove_byte():
    sel = byte_tree.selection()
    if not sel:
        print("[DEBUG] No byte row selected.")
        return
    push_snapshot()
    for iid in sel:
        vals = byte_tree.item(iid, "values")
        byte_id = int(vals[0])  # ID is now in the first column
        if byte_id in byte_array_dict:
            del byte_array_dict[byte_id]
        byte_tree.delete(iid)
    save_codex()
    refresh_byte_tree()

btn_byte_del = tk.Button(byte_entry_frame, text="-", command=on_remove_byte)
btn_byte_del.pack(side="left", padx=5)

def on_byte_tree_select(event):
    """
    Handles selection in the byte tree, updating the grid and loading `pixel_data`.
    """
    sel = byte_tree.selection()
    if not sel:
        return
    iid = sel[0]
    row_vals = byte_tree.item(iid, "values")
    byte_id = int(row_vals[0])  # First column is now ID

    global current_byte_key
    current_byte_key = byte_id

    # Reset `pixel_data` to match the selected byte
    for yy in range(MAX_DIM):
        for xx in range(MAX_DIM):
            pixel_data[yy][xx] = 0  # Clear the grid

    if byte_id in byte_array_dict:
        byte_data = byte_array_dict[byte_id]
        grid_size_var.set(byte_data["size"])
        for rr in range(byte_data["size"]):
            row_data = byte_data["data"][rr]
            for cc in range(byte_data["size"]):
                bit = (row_data >> (byte_data["size"] - 1 - cc)) & 1
                pixel_data[rr + MARGIN][cc + MARGIN] = bit

        update_display()
        update_oled_equation()  # Trigger redraw for OLED

byte_tree.bind("<<TreeviewSelect>>", on_byte_tree_select)

def on_byte_tree_double_click(event):
    """
    Handles double-click events in the byte tree for renaming the selected byte.
    """
    sel = byte_tree.selection()
    if not sel:
        return
    iid = sel[0]
    col_id = byte_tree.identify_column(event.x)
    if col_id != "#2":  # Only allow renaming in the "Name" column
        return
    byte_id = int(byte_tree.item(iid)["values"][0])  # ID is now in the first column
    bbox = byte_tree.bbox(iid, column=1)
    if not bbox:
        return

    byte_edit_entry = tk.Entry(byte_tree)
    x, y, w, h = bbox
    byte_edit_entry.place(x=x, y=y, width=w, height=h, in_=byte_tree)
    byte_edit_entry.delete(0, tk.END)
    byte_edit_entry.insert(0, byte_array_dict[byte_id]["name"])
    byte_edit_entry.focus()

    def on_rename(_):
        new_name = byte_edit_entry.get().strip()
        byte_edit_entry.place_forget()
        if any(entry["name"] == new_name for entry in byte_array_dict.values()):
            print(f"[DEBUG] Name '{new_name}' already exists. Skipping rename.")
            return
        byte_array_dict[byte_id]["name"] = new_name
        refresh_byte_tree()
        save_codex()

    byte_edit_entry.bind("<Return>", on_rename)

byte_tree.bind("<Double-1>", on_byte_tree_double_click)




# Final Init + mainloop
##########################################################
def init():
    refresh_equation_tree()
    refresh_byte_tree()
    update_display()
    update_oled_equation()

init()
root.mainloop()
