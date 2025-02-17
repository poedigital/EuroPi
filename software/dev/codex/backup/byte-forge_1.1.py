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
    print("[DEBUG] load_codex called.")
    if os.path.exists(CODEX_FILE):
        with open(CODEX_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                print("[DEBUG] Codex file loaded successfully.")
                return data.get("equation_dict", []), data.get("byte_array_dict", {})
            except Exception as e:
                print("[ERROR] JSON load error:", e)
                return [], {}
    print("[DEBUG] No codex file found; returning empty structures.")
    return [], {}

def save_codex():
    print("[DEBUG] save_codex called.")
    with open(CODEX_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "equation_dict": equation_dict,
            "byte_array_dict": byte_array_dict
        }, f, indent=4)
    print("[DEBUG] Codex file saved successfully.")

def refresh_byte_tree():
    print("[DEBUG] refresh_byte_tree called.")
    byte_tree.delete(*byte_tree.get_children())
    for k in byte_array_dict:
        s = byte_array_dict[k]["size"]
        arr = byte_array_dict[k]["data"]
        byte_tree.insert("", "end", values=(k, s, str(arr)))

def get_snapshot():
    return {
        "equation_dict": copy.deepcopy(equation_dict),
        "byte_array_dict": copy.deepcopy(byte_array_dict),
        "pixel_data": copy.deepcopy(pixel_data),
        "current_byte_key": current_byte_key,
        "grid_size": grid_size_var.get()
    }

def set_snapshot(snap, push_to_stack=False):
    print("[DEBUG] set_snapshot called. Restoring from snapshot.")
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
    """
    Pushes the current state onto the undo stack.
    Optionally clears the redo stack (default: True).
    """
    print("[DEBUG] push_snapshot called.")
    if clear_redo:
        redo_stack.clear()
    undo_stack.append(get_snapshot())

def pop_undo():
    print("[DEBUG] pop_undo called.")
    if not undo_stack:
        print("[DEBUG] No undo snapshots available.")
        return
    current_state = get_snapshot()
    previous_state = undo_stack.pop()
    redo_stack.append(current_state)  # Push the current state to redo stack
    set_snapshot(previous_state, push_to_stack=False)  # Don't push to undo stack
    save_codex()

def pop_redo():
    print("[DEBUG] pop_redo called.")
    if not redo_stack:
        print("[DEBUG] No redo snapshots available.")
        return
    current_state = get_snapshot()
    next_state = redo_stack.pop()
    undo_stack.append(current_state)  # Push the current state back to undo stack
    set_snapshot(next_state, push_to_stack=False)  # Don't push to redo stack
    save_codex()

def update_oled_equation():
    """
    Updates the OLED emulator and preview with the selected equation.
    """
    sel = eq_tree.selection()
    if not sel:
        print("[DEBUG] No equation selected. Not updating emulator.")
        return
    idx = eq_tree.index(sel[0])
    if idx < 0 or idx >= len(equation_dict):
        return
    data = equation_dict[idx]
    title = data.get("title", "")
    eqn = data.get("equation", "")
    print(f"[DEBUG] update_oled_equation => Rendering: Title='{title}', Equation='{eqn}'")
    update_oled_canvas(title, eqn)  # Updates the main OLED display

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
    print("[DEBUG] add_equation called.")
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
    print("[DEBUG] remove_equation called.")
    sel = eq_tree.selection()
    if not sel:
        print("[DEBUG] No equation row selected.")
        return
    push_snapshot()
    iid = sel[0]
    idx = eq_tree.index(iid)
    print(f"[DEBUG] Removing equation at index {idx}.")
    eq_tree.delete(iid)
    del equation_dict[idx]
    save_codex()
    update_oled_equation()

def refresh_all():
    """
    Refresh the equation tree, byte tree, OLED display, and other components.
    """
    print("[DEBUG] refresh_all called.")
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

def refresh_equation_tree():
    print("[DEBUG] refresh_equation_tree called.")
    eq_tree.delete(*eq_tree.get_children())
    for e in equation_dict:
        i = e.get("id", "")
        t = e.get("title", "")
        f = e.get("equation", "")
        v = ", ".join(e.get("var", []))
        b = ", ".join(e.get("byte", []))
        eq_tree.insert("", "end", values=(i, t, f, v, b))

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
                    print(f"[DEBUG] Toggled byte '{key}'. New list:", eq_data["byte"])
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

    def save_and_exit_edit(event=None):
        """
        Save the new value and exit inline editing mode.
        """
        global edit_mode, current_iid, current_c_index, edit_bbox
        if not edit_mode:
            return  # Skip if not in edit mode

        new_val = eq_edit_entry.get()
        eq_edit_entry.place_forget()
        eq_tree.set(current_iid, eq_cols[current_c_index], new_val)
        push_snapshot()

        idx = eq_tree.index(current_iid)
        field = eq_cols[current_c_index].lower()  # Get the field name ("title", "equation", etc.)
        
        if field in ["vars", "byte"]:
            equation_dict[idx][field] = [x.strip() for x in new_val.split(",")] if new_val else []
        elif field != "id":
            equation_dict[idx][field] = new_val

            # Force re-selection to ensure update_oled_equation works
            eq_tree.selection_set(current_iid)

            # Debug statement for the field update
            print(f"[DEBUG] Field updated: {field}, Value: {new_val}")
            print("[DEBUG] Forcing re-selection for OLED update.")

            # Refresh the OLED canvas if "title" or "equation" was updated
            if field in ["title", "equation"]:
                update_oled_equation()

        save_codex()
        refresh_equation_tree()

        # Reset edit mode state
        edit_mode = False
        current_iid = None
        current_c_index = -1
        edit_bbox = None

        # Unbind global click handler
        root.unbind("<Button-1>")


    # Bind actions for saving
    eq_edit_entry.bind("<Return>", lambda _: save_and_exit_edit())
    eq_edit_entry.bind("<FocusOut>", save_and_exit_edit)  # Save on losing focus
    global edit_mode, current_iid, current_c_index, edit_bbox  # Track edit state and cell bounds
    if edit_mode:
        return  # Prevent re-entering edit mode

    sel = eq_tree.selection()
    if not sel:
        return

    current_iid = sel[0]  # Save the selected item's ID globally
    col_id = eq_tree.identify_column(event.x)
    current_c_index = int(col_id.replace("#", "")) - 1
    if current_c_index < 0:
        return

    bbox = eq_tree.bbox(current_iid, column=col_id)
    if not bbox:
        return

    # Save the bounding box of the cell being edited
    edit_bbox = bbox  # (x, y, width, height)

    # Enter edit mode
    x, y, w, h = bbox
    eq_edit_entry.place(x=x, y=y, width=w, height=h, in_=eq_tree)
    current_val = eq_tree.set(current_iid, eq_cols[current_c_index])
    eq_edit_entry.delete(0, tk.END)
    eq_edit_entry.insert(0, current_val)
    eq_edit_entry.focus()
    edit_mode = True  # Mark as in edit mode

    def save_and_exit_edit(event=None):
        global edit_mode, current_iid, current_c_index, edit_bbox
        if not edit_mode:
            return  # Skip if not in edit mode

        new_val = eq_edit_entry.get()
        eq_edit_entry.place_forget()
        eq_tree.set(current_iid, eq_cols[current_c_index], new_val)
        push_snapshot()

        idx = eq_tree.index(current_iid)
        field = eq_cols[current_c_index].lower()  # Get the field name ("title", "equation", etc.)
        
        if field == "vars":
            equation_dict[idx]["var"] = [x.strip() for x in new_val.split(",")] if new_val else []
        elif field == "byte":
            equation_dict[idx]["byte"] = [x.strip() for x in new_val.split(",")] if new_val else []
        elif field == "id":
            pass
        else:
            equation_dict[idx][field] = new_val

            # Refresh the OLED canvas if "title" or "equation" was updated
            if field in ["title", "equation"]:
                update_oled_equation()

        save_codex()
        refresh_equation_tree()
        
        # Reset edit mode state
        edit_mode = False
        current_iid = None
        current_c_index = -1
        edit_bbox = None

        # Unbind global click handler
        root.unbind("<Button-1>")

    def handle_external_click(event):
        """
        Check if the click is outside the current edit cell's bounding box.
        """
        global edit_mode, edit_bbox
        if not edit_mode or not edit_bbox:
            return

        # Ignore clicks inside the Entry widget
        if event.widget == eq_edit_entry:
            return

        # Calculate bounds
        x1, y1, w, h = edit_bbox
        x2, y2 = x1 + w, y1 + h
        mouse_x, mouse_y = root.winfo_pointerx(), root.winfo_pointery()

        # Check if the click is outside the bounding box
        if not (x1 <= mouse_x <= x2 and y1 <= mouse_y <= y2):
            save_and_exit_edit()

    # Bind global click to handle external clicks
    root.bind("<Button-1>", handle_external_click)

    # Bind Return key to save and exit edit mode
    eq_edit_entry.bind("<Return>", lambda event: save_and_exit_edit())
    eq_edit_entry.bind("<FocusOut>", save_and_exit_edit)  # Also save when focus is lost

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
        print("[DEBUG] OLED canvas updated successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to update OLED canvas: {e}")

# Right-Side Pixel Editor
##########################################################
right_frame = ttk.Frame(main_frame)
right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

byte_cols = ("Name", "Size", "Data")
byte_tree = ttk.Treeview(right_frame, columns=byte_cols, show="headings", selectmode="browse")
byte_tree.heading("Name", text="Name")
byte_tree.heading("Size", text="Size")
byte_tree.heading("Data", text="Byte Array")
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
    print("[DEBUG] update_display called.")
    canvas.delete("all")
    s = grid_size_var.get()
    total_cells = s + 2*MARGIN
    grid_px = total_cells * CELL_SIZE
    offset_x = (CANVAS_SIZE - grid_px) // 2
    offset_y = (CANVAS_SIZE - grid_px) // 2

    for y in range(MAX_DIM):
        for x in range(MAX_DIM):
            val = pixel_data[y][x]
            in_region = (x >= MARGIN and x < MARGIN+s and y >= MARGIN and y < MARGIN+s)
            color = "white" if (val == 0 and in_region) else "black" if (val == 1 and in_region) else "#777777"

            left   = offset_x + x * CELL_SIZE
            top    = offset_y + y * CELL_SIZE
            right  = left + CELL_SIZE
            bottom = top + CELL_SIZE

            rid = canvas.create_rectangle(
                left, top, right, bottom,
                fill=color, outline="black"
            )

            def click_closure(e, cx=x, cy=y):
                print(f"[DEBUG] Pixel clicked at {cx},{cy}")
                push_snapshot()
                pixel_data[cy][cx] = 1 - pixel_data[cy][cx]
                update_display()
                update_byte_array()

            if in_region:
                canvas.tag_bind(rid, "<Button-1>", click_closure)

    # Draw bounding box
    act_left = offset_x + MARGIN*CELL_SIZE
    act_top = offset_y + MARGIN*CELL_SIZE
    act_right = act_left + s*CELL_SIZE
    act_bottom = act_top + s*CELL_SIZE
    canvas.create_rectangle(act_left, act_top, act_right, act_bottom, outline="blue", width=2)

def update_byte_array():
    print("[DEBUG] update_byte_array called.")
    s = grid_size_var.get()
    arr = []
    for row in range(s):
        b = 0
        for col in range(s):
            if pixel_data[row+MARGIN][col+MARGIN] == 1:
                b |= (1 << (s - 1 - col))
        arr.append(b)

    if current_byte_key:
        print(f"[DEBUG] Updating byte_array_dict for key={current_byte_key}")
        byte_array_dict[current_byte_key]["size"] = s
        byte_array_dict[current_byte_key]["data"] = arr
    else:
        print("[DEBUG] No current_byte_key selected.")
    save_codex()
    refresh_byte_tree()

def on_grid_size_change(*_):
    print("[DEBUG] on_grid_size_change called.")
    push_snapshot()
    update_display()
    update_byte_array()

grid_size_var.trace_add("write", on_grid_size_change)

# SHIFT Buttons
##########################################################
shift_frame = ttk.Frame(right_frame)
shift_frame.grid(row=1, column=0, columnspan=4, sticky="n", pady=3)

def shift_pixels(direction):
    print(f"[DEBUG] shift_pixels called with direction={direction}")
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
    print("[DEBUG] on_clear_canvas called.")
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

def on_add_byte():
    print("[DEBUG] on_add_byte called.")
    push_snapshot()
    key = byte_text.get().strip()
    if not key:
        print("[DEBUG] No name provided for new byte.")
        return
    if key in byte_array_dict:
        print(f"[DEBUG] Key '{key}' already in dict. Skipping add.")
        return
    s = grid_size_var.get()
    arr = []
    for row in range(s):
        b = 0
        for col in range(s):
            if pixel_data[row+MARGIN][col+MARGIN] == 1:
                b |= (1 << (s - 1 - col))
        arr.append(b)
    byte_array_dict[key] = {"size": s, "data": arr}
    global current_byte_key
    current_byte_key = key
    refresh_byte_tree()
    save_codex()

btn_byte_add = tk.Button(byte_entry_frame, text="+", command=on_add_byte)
btn_byte_add.pack(side="left", padx=5)

def on_remove_byte():
    print("[DEBUG] on_remove_byte called.")
    sel = byte_tree.selection()
    if not sel:
        print("[DEBUG] No byte row selected.")
        return
    push_snapshot()
    for iid in sel:
        vals = byte_tree.item(iid, "values")
        name = vals[0]
        print(f"[DEBUG] Deleting byte '{name}' from dictionary and tree.")
        if name in byte_array_dict:
            del byte_array_dict[name]
        byte_tree.delete(iid)
    save_codex()

btn_byte_del = tk.Button(byte_entry_frame, text="-", command=on_remove_byte)
btn_byte_del.pack(side="left", padx=5)
byte_edit_entry = tk.Entry(byte_tree)

def on_byte_tree_double_click(event):
    sel = byte_tree.selection()
    if not sel:
        return
    iid = sel[0]
    col_id = byte_tree.identify_column(event.x)
    c_index = int(col_id.replace("#", "")) - 1
    if c_index < 0:
        return
    bbox = byte_tree.bbox(iid, column=col_id)
    if not bbox:
        return
    x, y, w, h = bbox
    byte_edit_entry.place(x=x, y=y, width=w, height=h, in_=byte_tree)
    val = byte_tree.set(iid, byte_cols[c_index])
    byte_edit_entry.delete(0, tk.END)
    byte_edit_entry.insert(0, val)
    byte_edit_entry.focus()

    def on_enter(_):
        new_val = byte_edit_entry.get()
        byte_edit_entry.place_forget()
        row_vals = list(byte_tree.item(iid, "values"))
        old_name = row_vals[0]
        row_vals[c_index] = new_val
        byte_tree.item(iid, values=row_vals)
        push_snapshot()

        if old_name not in byte_array_dict:
            print(f"[DEBUG] old_name '{old_name}' not found in dict. Aborting rename.")
            return

        if c_index == 0:
            if new_val in byte_array_dict and new_val != old_name:
                print(f"[DEBUG] Key '{new_val}' already exists. Skipping rename.")
                return
            print(f"[DEBUG] Renaming byte '{old_name}' -> '{new_val}'")
            data = byte_array_dict[old_name]
            del byte_array_dict[old_name]
            byte_array_dict[new_val] = data
            refresh_byte_tree()
            save_codex()
            return

        if c_index == 1:
            try:
                new_s = int(new_val)
                byte_array_dict[old_name]["size"] = new_s
                print(f"[DEBUG] Updated size for '{old_name}' -> {new_s}")
            except ValueError:
                print("[DEBUG] Invalid integer for size, ignoring.")

        if c_index == 2:
            try:
                arr_e = eval(new_val)
                if isinstance(arr_e, list):
                    byte_array_dict[old_name]["data"] = arr_e
                    print(f"[DEBUG] Updated data array for '{old_name}' -> {arr_e}")
            except Exception as e:
                print("[DEBUG] Exception parsing new data array:", e)

        save_codex()

    byte_edit_entry.bind("<Return>", on_enter)

def on_byte_tree_click(event):
    region = byte_tree.identify_region(event.x, event.y)
    if region in ("nothing", "separator", "heading"):
        byte_tree.selection_remove(*byte_tree.selection())

def on_byte_tree_select(event):
    sel = byte_tree.selection()
    if not sel:
        return
    iid = sel[0]
    row_vals = byte_tree.item(iid, "values")
    name = row_vals[0]
    byte_text.delete(0, tk.END)
    byte_text.insert(0, name)
    print(f"[DEBUG] Byte '{name}' selected. Loading into pixel_data.")
    if name not in byte_array_dict:
        print("[DEBUG] Byte not in dict, ignoring.")
        return
    push_snapshot()
    for yy in range(MAX_DIM):
        for xx in range(MAX_DIM):
            pixel_data[yy][xx] = 0

    d = byte_array_dict[name]
    s = d["size"]
    arr = d["data"]
    global current_byte_key
    current_byte_key = name
    grid_size_var.set(s)
    for rr in range(s):
        b = arr[rr]
        for cc in range(s):
            bit = (b >> (s - 1 - cc)) & 1
            pixel_data[rr + MARGIN][cc + MARGIN] = bit

    update_display()
    update_byte_array()

byte_tree.bind("<Double-1>", on_byte_tree_double_click)
byte_tree.bind("<Button-1>", on_byte_tree_click)
byte_tree.bind("<<TreeviewSelect>>", on_byte_tree_select)

# Final Init + mainloop
##########################################################
def init():
    refresh_equation_tree()
    refresh_byte_tree()
    update_display()
    update_oled_equation()

init()
root.mainloop()
