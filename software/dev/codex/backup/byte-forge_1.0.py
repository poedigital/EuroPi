import tkinter as tk
from tkinter import ttk
import json
import os
import copy

###############################################################################
# If you have luma / pygame installed, you could import them. For now, we'll
# keep a placeholder approach for the "draw_preview" function.
# from luma.core.render import canvas
# from luma.core.legacy import text
# from luma.emulator.device import pygame
###############################################################################

CODEX_FILE = "codex.txt"
MARGIN = 2
MAX_DIM = 12
CELL_SIZE = 16
CANVAS_SIZE = 256
SUPPORTED_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789=+*-/()[]{}^%.,<> ")

equation_dict = []
byte_array_dict = {}
undo_stack = []
redo_stack = []
pixel_data = []
current_byte_key = None
grid_size_var = None

def load_codex():
    print("[DEBUG] Loading codex file...")
    if os.path.exists(CODEX_FILE):
        with open(CODEX_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                print("[DEBUG] codex file loaded successfully.")
                return data.get("equation_dict", []), data.get("byte_array_dict", {})
            except Exception as e:
                print("[ERROR] JSON load error:", e)
                return [], {}
    print("[DEBUG] No codex file found; returning empty structures.")
    return [], {}

def save_codex():
    print("[DEBUG] Saving codex file...")
    with open(CODEX_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "equation_dict": equation_dict,
            "byte_array_dict": byte_array_dict
        }, f, indent=4)
    print("[DEBUG] codex file saved successfully.")

def get_snapshot():
    return {
        "equation_dict": copy.deepcopy(equation_dict),
        "byte_array_dict": copy.deepcopy(byte_array_dict),
        "pixel_data": copy.deepcopy(pixel_data),
        "current_byte_key": current_byte_key,
        "grid_size": grid_size_var.get()
    }

def set_snapshot(snap):
    print("[DEBUG] set_snapshot called. Restoring from snapshot.")
    equation_dict.clear()
    equation_dict.extend(snap["equation_dict"])
    byte_array_dict.clear()
    byte_array_dict.update(snap["byte_array_dict"])
    for r in range(MAX_DIM):
        for c in range(MAX_DIM):
            pixel_data[r][c] = snap["pixel_data"][r][c]
    global current_byte_key
    current_byte_key = snap["current_byte_key"]
    grid_size_var.set(snap["grid_size"])
    refresh_equation_tree()
    refresh_byte_tree()
    update_display()
    update_byte_array()

def push_snapshot():
    print("[DEBUG] push_snapshot called. Clearing redo_stack and pushing current state.")
    redo_stack.clear()
    undo_stack.append(get_snapshot())

def pop_undo():
    print("[DEBUG] pop_undo called.")
    if not undo_stack:
        print("[DEBUG] No undo snapshots available.")
        return
    current_state = get_snapshot()
    previous_state = undo_stack.pop()
    redo_stack.append(current_state)
    set_snapshot(previous_state)
    save_codex()

def pop_redo():
    print("[DEBUG] pop_redo called.")
    if not redo_stack:
        print("[DEBUG] No redo snapshots available.")
        return
    current_state = get_snapshot()
    next_state = redo_stack.pop()
    undo_stack.append(current_state)
    set_snapshot(next_state)
    save_codex()

def validate_equation(equation, byte_tokens):
    unsupported = []
    i = 0
    while i < len(equation):
        matched = False
        for token in byte_tokens:
            if equation.startswith(token, i):
                matched = True
                i += len(token)
                break
        if not matched:
            if equation[i] not in SUPPORTED_CHARS and equation[i] not in byte_array_dict:
                unsupported.append(equation[i])
            i += 1
    return unsupported

equation_dict, byte_array_dict = load_codex()
pixel_data = [[0]*MAX_DIM for _ in range(MAX_DIM)]
current_byte_key = None

root = tk.Tk()
root.title("Byte-Forge Editor")
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
    new_id = max(e["id"] for e in equation_dict) + 1 if equation_dict else 1
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

btn_eq_add = tk.Button(eq_btn_frame, text="+", command=add_equation)
btn_eq_add.pack(side="left", padx=5)

btn_eq_del = tk.Button(eq_btn_frame, text="-", command=remove_equation)
btn_eq_del.pack(side="left", padx=5)

btn_eq_undo = tk.Button(eq_btn_frame, text="Undo", command=pop_undo)
btn_eq_undo.pack(side="left", padx=5)

btn_eq_redo = tk.Button(eq_btn_frame, text="Redo", command=pop_redo)
btn_eq_redo.pack(side="left", padx=5)

eq_status_canvas = tk.Canvas(eq_btn_frame, width=128, height=32,
                             bg="black", highlightthickness=1,
                             highlightbackground="#888")
eq_status_canvas.pack(side="left", padx=15)

eq_cols = ("ID", "Title", "Equation", "Vars", "Byte")
eq_tree = ttk.Treeview(left_frame, columns=eq_cols, show="headings",
                       selectmode="browse")

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
    # This toggles a "popup" that shows all bytes, with a + or ✓ if present.
    # Clicking one toggles presence in the equation's byte list.
    idx = eq_tree.index(iid)
    eq_data = equation_dict[idx]
    active_list = set(eq_data["byte"])

    win = tk.Toplevel(eq_tree)
    win.title("Select Byte(s)")
    win.geometry(f"+{bbox[0]+eq_tree.winfo_rootx()}+{bbox[1]+eq_tree.winfo_rooty()+50}")
    win.wm_overrideredirect(True)

    frame = ttk.Frame(win)
    frame.pack(fill="both", expand=True)

    def close_popup():
        win.destroy()

    row_num = 0
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
                print(f"[DEBUG] Toggled byte '{key}'. New list:", eq_data["byte"])
            return toggle
        row_label = tk.Label(frame, text=row_str, fg="white", bg="black", anchor="w")
        row_label.grid(row=row_num, column=0, sticky="w", padx=5, pady=3)
        row_btn = tk.Button(frame, text=sign, command=toggle_factory(byte_key), width=2)
        row_btn.grid(row=row_num, column=1, sticky="e")
        row_num += 1

    close_btn = tk.Button(frame, text="Close", command=close_popup)
    close_btn.grid(row=row_num, column=0, columnspan=2, pady=5)

def on_eq_double_click(event):
    sel = eq_tree.selection()
    if not sel:
        return
    iid = sel[0]
    col_id = eq_tree.identify_column(event.x)
    c_index = int(col_id.replace("#", "")) - 1
    if c_index < 0:
        return

    if eq_cols[c_index] == "Byte":
        bbox = eq_tree.bbox(iid, column=col_id)
        if bbox:
            show_byte_dropdown(iid, bbox)
        return

    bbox = eq_tree.bbox(iid, column=col_id)
    if not bbox:
        return
    x, y, w, h = bbox
    eq_edit_entry.place(x=x, y=y, width=w, height=h, in_=eq_tree)
    current_val = eq_tree.set(iid, eq_cols[c_index])
    eq_edit_entry.delete(0, tk.END)
    eq_edit_entry.insert(0, current_val)
    eq_edit_entry.focus()

    def on_enter(_):
        new_val = eq_edit_entry.get()
        eq_edit_entry.place_forget()
        idx = eq_tree.index(iid)
        eq_tree.set(iid, eq_cols[c_index], new_val)
        push_snapshot()
        field = eq_cols[c_index].lower()
        if field == "vars":
            equation_dict[idx]["var"] = [x.strip() for x in new_val.split(",")] if new_val else []
        elif field == "byte":
            # We handle byte now with a dropdown, so might not be used
            equation_dict[idx]["byte"] = [x.strip() for x in new_val.split(",")] if new_val else []
        elif field == "id":
            pass
        else:
            equation_dict[idx][field] = new_val
        save_codex()
        refresh_equation_tree()

    eq_edit_entry.bind("<Return>", on_enter)

def on_eq_click(event):
    region = eq_tree.identify_region(event.x, event.y)
    if region in ("nothing", "separator", "heading"):
        eq_tree.selection_remove(*eq_tree.selection())

eq_tree.bind("<Double-1>", on_eq_double_click)
eq_tree.bind("<Button-1>", on_eq_click)

right_frame = ttk.Frame(main_frame)
right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

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
            if in_region:
                color = "white" if val == 0 else "black"
            else:
                color = "#777777"

            cell_left   = offset_x + x * CELL_SIZE
            cell_top    = offset_y + y * CELL_SIZE
            cell_right  = cell_left + CELL_SIZE
            cell_bottom = cell_top  + CELL_SIZE

            rid = canvas.create_rectangle(
                cell_left, cell_top, cell_right, cell_bottom,
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

    active_left   = offset_x + MARGIN*CELL_SIZE
    active_top    = offset_y + MARGIN*CELL_SIZE
    active_right  = active_left + s*CELL_SIZE
    active_bottom = active_top + s*CELL_SIZE
    canvas.create_rectangle(active_left, active_top,
                            active_right, active_bottom,
                            outline="blue", width=2)

def update_byte_array():
    print("[DEBUG] update_byte_array called.")
    s = grid_size_var.get()
    arr = []
    for row in range(s):
        b = 0
        for col in range(s):
            if pixel_data[row + MARGIN][col + MARGIN] == 1:
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

clear_btn["command"] = on_clear_canvas

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

btn_byte_add = tk.Button(byte_entry_frame, text="+", command=on_add_byte)
btn_byte_add.pack(side="left", padx=5)

btn_byte_del = tk.Button(byte_entry_frame, text="-", command=on_remove_byte)
btn_byte_del.pack(side="left", padx=5)

byte_cols = ("Name", "Size", "Data")
byte_tree = ttk.Treeview(right_frame, columns=byte_cols, show="headings",
                         selectmode="browse")

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

byte_edit_entry = tk.Entry(byte_tree)

def refresh_byte_tree():
    print("[DEBUG] refresh_byte_tree called.")
    byte_tree.delete(*byte_tree.get_children())
    for k in byte_array_dict:
        s = byte_array_dict[k]["size"]
        arr = byte_array_dict[k]["data"]
        byte_tree.insert("", "end", values=(k, s, str(arr)))

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

        if c_index == 0:  # Rename the byte key
            if new_val in byte_array_dict and new_val != old_name:
                print(f"[DEBUG] Key '{new_val}' already exists in dict. Skipping rename.")
                return
            print(f"[DEBUG] Renaming byte '{old_name}' -> '{new_val}'")
            data = byte_array_dict[old_name]
            del byte_array_dict[old_name]
            byte_array_dict[new_val] = data
            refresh_byte_tree()
            save_codex()
            return

        if c_index == 1:  # Edit size
            try:
                new_s = int(new_val)
                byte_array_dict[old_name]["size"] = new_s
                print(f"[DEBUG] Updated size for '{old_name}' -> {new_s}")
            except ValueError:
                print("[DEBUG] Invalid integer for size, ignoring.")
                pass

        if c_index == 2:  # Edit data array
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
    print("[DEBUG] on_byte_tree_select triggered.")
    sel = byte_tree.selection()
    if not sel:
        print("[DEBUG] Nothing selected in byte_tree.")
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

###############################################################################
# Final Initialization
###############################################################################
def init():
    refresh_equation_tree()
    refresh_byte_tree()
    update_display()

init()
root.mainloop()
