import tkinter as tk 
from tkinter import ttk
from tkinter import filedialog
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

equation_dict = []
byte_array_dict = {}
pixel_data = []
current_byte_key = None
grid_size_var = None
id_to_iid_map = {}

eq_undo_stack = []
eq_redo_stack = []
byte_undo_stack = []
byte_redo_stack = []
CONFIG_FILE = "config.json"

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
# Load the saved config or create a default config
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {"codex_path": "codex.txt"}  # Default to "codex.txt"

# Save the updated config
def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

# Open and link a codex file
def link_codex():
    file_path = filedialog.askopenfilename(
        title="Select Codex File",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
    )
    if file_path:
        config["codex_path"] = file_path
        save_config(config)
        print(f"[INFO] Linked to codex file: {file_path}")

# Open the linked codex file in the default text editor
def open_codex():
    file_path = config.get("codex_path")
    if os.path.exists(file_path):
        os.startfile(file_path) if os.name == "nt" else os.system(f"open '{file_path}'")
    else:
        print("[ERROR] Codex file not found!")

config = load_config()
def refresh_byte_tree():
    byte_tree.delete(*byte_tree.get_children())
    for k in byte_array_dict:
        s = byte_array_dict[k]["size"]
        arr = byte_array_dict[k]["data"]
        byte_tree.insert("", "end", values=(k, s, str(arr)))

def get_snapshot(section="byte"):
    if section == "byte":
        return {
            "byte_array_dict": copy.deepcopy(byte_array_dict),
            "pixel_data": copy.deepcopy(pixel_data),
            "current_byte_key": current_byte_key,
            "grid_size": grid_size_var.get()
        }
    elif section == "equation":
        return {
            "equation_dict": copy.deepcopy(equation_dict)
        }

def set_snapshot(snap, section="byte", push_to_stack=False):
    if push_to_stack:
        push_snapshot(section, clear_redo=False)

    if section == "byte":
        if "byte_array_dict" in snap:
            byte_array_dict.clear()
            byte_array_dict.update(snap["byte_array_dict"])
        if "pixel_data" in snap:
            for r in range(MAX_DIM):
                for c in range(MAX_DIM):
                    pixel_data[r][c] = snap["pixel_data"][r][c]
        if "current_byte_key" in snap:
            global current_byte_key
            current_byte_key = snap["current_byte_key"]
        if "grid_size" in snap:
            grid_size_var.set(snap["grid_size"])

        refresh_byte_tree()
        update_display()
        update_byte_array()

    elif section == "equation":
        if "equation_dict" in snap:
            equation_dict.clear()
            equation_dict.extend(snap["equation_dict"])

        refresh_equation_tree()
        update_oled_equation()

    save_codex()

def push_snapshot(section="byte", clear_redo=True):
    if section == "byte":
        if clear_redo:
            byte_redo_stack.clear()
        snapshot = get_snapshot("byte")
        byte_undo_stack.append(snapshot)
    elif section == "equation":
        if clear_redo:
            eq_redo_stack.clear()
        snapshot = get_snapshot("equation")
        eq_undo_stack.append(snapshot)

def pop_undo(section="byte"):
    if section == "byte":
        if not byte_undo_stack:
            return
        current_state = get_snapshot("byte")
        previous_state = byte_undo_stack.pop()
        byte_redo_stack.append(current_state)
        set_snapshot(previous_state, section="byte", push_to_stack=False)

def pop_redo(section="byte"):
    if section == "byte":
        if not byte_redo_stack:
            return
        current_state = get_snapshot("byte")
        next_state = byte_redo_stack.pop()
        byte_undo_stack.append(current_state)  # Push current state to undo stack
        set_snapshot(next_state, section="byte", push_to_stack=False)
    elif section == "equation":
        if not eq_redo_stack:
            return
        current_state = get_snapshot("equation")
        next_state = eq_redo_stack.pop()
        eq_undo_stack.append(current_state)
        set_snapshot(next_state, section="equation", push_to_stack=False)

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
    push_snapshot(section="equation")
    new_id = max(eq["id"] for eq in equation_dict) + 1 if equation_dict else 1
    new_eq = {
        "id": new_id,
        "title": "",
        "equation": "",
        "vars": [],
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
    push_snapshot(section="equation")
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
    
# Add a frame for the first row of buttons
btn_top_row = ttk.Frame(eq_btn_frame)
btn_top_row.pack(side="top", fill="x", pady=2)

btn_open_codex = tk.Button(btn_top_row, text="Open Codex", command=open_codex)
btn_open_codex.pack(side="left", padx=5)

btn_link_codex = tk.Button(btn_top_row, text="Link Codex", command=link_codex)
btn_link_codex.pack(side="left", padx=5)

# Add a frame for the second row of buttons
btn_bottom_row = ttk.Frame(eq_btn_frame)
btn_bottom_row.pack(side="top", fill="x", pady=2)

btn_eq_add = tk.Button(btn_bottom_row, text="+", command=add_equation)
btn_eq_add.pack(side="left", padx=5)

btn_eq_del = tk.Button(btn_bottom_row, text="-", command=remove_equation)
btn_eq_del.pack(side="left", padx=5)

btn_refresh = tk.Button(btn_bottom_row, text="⟳", command=refresh_all)
btn_refresh.pack(side="left", padx=5)

btn_eq_undo = tk.Button(btn_bottom_row, text="Undo", command=lambda: pop_undo(section="equation"))
btn_eq_undo.pack(side="left", padx=5)

btn_eq_redo = tk.Button(btn_bottom_row, text="Redo", command=lambda: pop_redo(section="equation"))
btn_eq_redo.pack(side="left", padx=5)

# Add a frame for the OLED emulator
oled_frame = ttk.Frame(eq_btn_frame)
oled_frame.pack(side="top", fill="x", pady=10)  # Add some vertical padding for spacing

# Center the OLED canvas within the new frame
toolbar_canvas_width, toolbar_canvas_height = emulator_width * 2, emulator_height * 2

oled_canvas = Canvas(oled_frame, width=toolbar_canvas_width, height=toolbar_canvas_height, bg="black", highlightthickness=1)
oled_canvas.pack(anchor="center", pady=5)  # Center-align the canvas


# Equation Tree
##########################################################
eq_cols = ("ID", "Title", "Equation", "Vars", "Byte")
eq_tree = ttk.Treeview(left_frame, columns=eq_cols, show="headings", selectmode="browse")
for col in eq_cols:
    eq_tree.heading(col, text=col)
    eq_tree.column(col, width=100, anchor="w")

eq_tree.column("ID", width=0, stretch=False)
eq_tree.column("Title", width=120)
eq_tree.column("Equation", width=180)
eq_tree.column("Vars", width=100)
eq_tree.column("Byte", width=100)
eq_tree.pack(fill="both", expand=True)
eq_edit_entry = tk.Entry(eq_tree)

def refresh_equation_tree():
    eq_tree.delete(*eq_tree.get_children())
    id_to_iid_map.clear()  # Clear the mapping

    for e in equation_dict:
        i = e.get("id", "")
        t = e.get("title", "")
        f = e.get("equation", "")
        v = ", ".join(e.get("vars", []))
        b = ", ".join(e.get("byte", []))  # Bytes are now keys
        iid = eq_tree.insert("", "end", values=(i, t, f, v, b))
        id_to_iid_map[i] = iid  # Store the mapping

def show_byte_dropdown(iid, bbox):
    idx = eq_tree.index(iid)
    eq_data = equation_dict[idx]

    def rebuild_dropdown():
        for widget in frame.winfo_children():
            widget.destroy()
        row_num = 0
        active_list = set(eq_data["byte"])  # Get currently selected bytes

        for byte_key in byte_array_dict.keys():  # Iterate over keys
            row_str = byte_key  # The key is now the name
            sign = "✓" if byte_key in active_list else "+"

            def toggle_factory(key):
                def toggle():
                    push_snapshot(section="equation")

                    if key in eq_data["byte"]:
                        eq_data["byte"].remove(key)
                    else:
                        eq_data["byte"].append(key)

                    refresh_equation_tree()
                    save_codex()
                    rebuild_dropdown()
                    update_oled_equation()
                return toggle

            # UI row: label + toggle button
            lbl = tk.Label(frame, text=row_str, fg="white", bg="black", anchor="w")
            lbl.grid(row=row_num, column=0, sticky="w", padx=5, pady=3)

            row_btn = tk.Button(frame, text=sign, command=toggle_factory(byte_key), width=2)
            row_btn.grid(row=row_num, column=1, sticky="e")
            row_num += 1

        # Finally, a simple "Close" button
        close_btn = tk.Button(frame, text="Close or freeze!",
                              command=lambda: destroy_dropdown("[DEBUG] Close button pressed"))
        close_btn.grid(row=row_num, column=0, columnspan=2, pady=5)

    def destroy_dropdown(reason):
        print(f"{reason}")
        if win.winfo_exists():
            print(f"[DEBUG] Destroying dropdown window with title: {win.title()}")
            win.destroy()
        else:
            print("[DEBUG] Dropdown window already destroyed.")

    win = tk.Toplevel(eq_tree)
    win.title("Select Byte(s)")
    win.geometry(f"+{bbox[0] + eq_tree.winfo_rootx()}+{bbox[1] + eq_tree.winfo_rooty() + 50}")
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
        return

    iid = eq_tree.identify_row(event.y)
    if iid:
        eq_tree.selection_set(iid)

    col_id = eq_tree.identify_column(event.x)
    c_index = int(col_id.replace("#", "")) - 1

    if c_index >= 0 and c_index < len(eq_cols) and eq_cols[c_index] == "Byte":
        bbox = eq_tree.bbox(iid, column=col_id)
        if bbox:
            show_byte_dropdown(iid, bbox)
        return

    sel = eq_tree.selection()
    if sel:
        idx = eq_tree.index(sel[0])
        if idx != getattr(on_eq_click, "last_index", None):
            on_eq_click.last_index = idx
            print("[DEBUG] Selection changed. Updating OLED equation.")
            update_oled_equation()

eq_tree.bind("<Button-1>", on_eq_click)
eq_tree.bind("<Double-1>", on_eq_double_click)



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

byte_scroll = ttk.Scrollbar(right_frame, orient="vertical", command=byte_tree.yview)
byte_scroll.grid(row=4, column=3, sticky="ns")
byte_tree.configure(yscrollcommand=byte_scroll.set)

grid_size_var = tk.IntVar(value=8)
canvas = tk.Canvas(right_frame, width=CANVAS_SIZE, height=CANVAS_SIZE, bg="#444444")
canvas.grid(row=0, column=0, columnspan=4, sticky="n", padx=5, pady=5)

def update_display():
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
    # Check if we are in a "load" state; skip saving if true
    if current_byte_key is None:
        return

    # Convert pixel_data back into byte array format
    s = grid_size_var.get()
    arr = []
    for row in range(s):
        b = 0
        for col in range(s):
            if pixel_data[row + MARGIN][col + MARGIN] == 1:
                b |= (1 << (s - 1 - col))
        arr.append(b)

    print(f"[DEBUG] Updating byte_array_dict for key={current_byte_key}")
    byte_array_dict[current_byte_key]["size"] = s
    byte_array_dict[current_byte_key]["data"] = arr

    save_codex()
    refresh_byte_tree()
    update_oled_equation()
    
def on_grid_size_change(*_):
    push_snapshot()
    update_display()
    update_byte_array()

grid_size_var.trace_id = grid_size_var.trace_add("write", on_grid_size_change)

# SHIFT Arrow Buttons
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

def on_add_byte():
    typed_name = byte_text.get().strip()
    if not typed_name:
        print("[DEBUG] Name is empty. Skipping.")
        show_error_in_textfield("NAME CANNOT BE EMPTY!")
        return

    # Check for duplicate names directly as dictionary keys
    if typed_name in byte_array_dict:
        print(f"[DEBUG] Name '{typed_name}' already exists. Skipping.")
        show_error_in_textfield("NAME ALREADY TAKEN!")
        return

    # Get the current grid size
    s = grid_size_var.get()
    arr = []
    # Convert pixel_data to the byte array format
    for row in range(s):
        b = 0
        for col in range(s):
            if pixel_data[row + MARGIN][col + MARGIN] == 1:
                b |= (1 << (s - 1 - col))
        arr.append(b)

    # Add the new byte using the typed name as the dictionary key
    byte_array_dict[typed_name] = {
        "size": s,
        "data": arr
    }

    # Set the current byte key to the newly added byte
    global current_byte_key
    current_byte_key = typed_name

    # Refresh the UI and save changes
    refresh_byte_tree()
    save_codex()
    byte_text.delete(0, tk.END)  # Clear the text field
    print(f"[DEBUG] Added new byte with name '{typed_name}'")

def show_error_in_textfield(error_message):
    byte_text.delete(0, tk.END)  # Clear the current text
    byte_text.insert(0, error_message)  # Insert the error message
    byte_text.config(fg="red")  # Set the text color to red
    # After 2 seconds, clear the text field and reset font color
    byte_text.after(2000, lambda: byte_text.delete(0, tk.END))
    byte_text.after(2000, lambda: byte_text.config(fg="white"))
    
btn_byte_add = tk.Button(byte_entry_frame, text="+", command=on_add_byte)
btn_byte_add.pack(side="left", padx=5)

def on_remove_byte():
    sel = byte_tree.selection()
    if not sel:
        print("[DEBUG] No byte row selected.")
        return
    for iid in sel:
        row_vals = byte_tree.item(iid, "values")
        byte_id = row_vals[0]
        print(f"[DEBUG] Removing byte ID={byte_id}")
        if byte_id in byte_array_dict:
            del byte_array_dict[byte_id]
        byte_tree.delete(iid)
    save_codex()
    refresh_byte_tree()

btn_byte_del = tk.Button(byte_entry_frame, text="-", command=on_remove_byte)
btn_byte_del.pack(side="left", padx=5)
byte_edit_entry = tk.Entry(byte_tree)

def on_byte_tree_select(event):
    sel = byte_tree.selection()
    if not sel:
        return

    iid = sel[0]
    row_vals = byte_tree.item(iid, "values")
    byte_id = row_vals[0]  # The dictionary key

    byte_text.delete(0, tk.END)  # Populate the text field with the key
    byte_text.insert(0, byte_id)

    print(f"[DEBUG] Selected Byte ID={byte_id}")

    global current_byte_key
    if current_byte_key == byte_id:
        print("[DEBUG] Skipping re-selection")
        return

    current_byte_key = byte_id

    # Load grid data
    if byte_id in byte_array_dict:
        entry = byte_array_dict[byte_id]
        s = entry["size"]
        arr = entry["data"]

        # Temporarily disable the trace to prevent infinite loops
        if hasattr(grid_size_var, 'trace_id') and grid_size_var.trace_id is not None:
            grid_size_var.trace_remove("write", grid_size_var.trace_id)

        try:
            grid_size_var.set(s)
            # Clear and populate pixel_data
            for yy in range(MAX_DIM):
                for xx in range(MAX_DIM):
                    pixel_data[yy][xx] = 0

            for rr in range(s):
                b = arr[rr]
                for cc in range(s):
                    bit = (b >> (s - 1 - cc)) & 1
                    pixel_data[rr + MARGIN][cc + MARGIN] = bit

            update_display()
        finally:
            # Re-enable grid size change trace
            grid_size_var.trace_id = grid_size_var.trace_add("write", on_grid_size_change)

    else:
        print(f"[DEBUG] Byte ID={byte_id} not found in byte_array_dict")

byte_tree.bind("<<TreeviewSelect>>", on_byte_tree_select)

def on_byte_tree_double_click(event):
    sel = byte_tree.selection()
    if not sel:
        return

    iid = sel[0]
    col_id = byte_tree.identify_column(event.x)

    if col_id != "#1":  # Only allow renaming for the first column (Name/Key)
        return

    row_vals = byte_tree.item(iid, "values")
    byte_id = row_vals[0]  # Use the key as the name

    # Get bounding box of the first column
    bbox = byte_tree.bbox(iid, column=0)
    if not bbox:
        return

    # Create an Entry for inline editing
    edit_entry = tk.Entry(byte_tree)
    x, y, w, h = bbox
    edit_entry.place(x=x, y=y, width=w, height=h)
    edit_entry.insert(0, byte_id)
    edit_entry.focus()

    def save_rename(*args):
        new_name = edit_entry.get().strip()
        edit_entry.place_forget()
        if not new_name or new_name == byte_id:
            return
        if new_name in byte_array_dict:
            print(f"[DEBUG] Key '{new_name}' already exists. Skipping rename.")
            return

        byte_array_dict[new_name] = byte_array_dict.pop(byte_id)  # Rename the key
        refresh_byte_tree()
        save_codex()

    edit_entry.bind("<Return>", save_rename)
    edit_entry.bind("<FocusOut>", save_rename)

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

