import tkinter as tk 
from tkinter import ttk, Canvas, messagebox, filedialog
from oled_emulator import draw_equation
from PIL import Image, ImageTk
import json, os, copy, re, shutil

USER_DOCS = os.path.join(os.path.expanduser("~"), "Documents", "mbcorp")
ARCHIVES_FOLDER = os.path.join(USER_DOCS, "archives")
os.makedirs(USER_DOCS, exist_ok=True)

MARGIN = 2
MAX_DIM = 12
CELL_SIZE = 18
CANVAS_SIZE = 256
emulator_width, emulator_height = 128, 32
expanded_geometry = False

equation_dict = []
byte_array_dict = {}
operator_pool = {}

pixel_data = []
current_byte_key = None
grid_size_var = None
id_to_iid_map = {}

eq_undo_stack = []
eq_redo_stack = []
byte_undo_stack = []
byte_redo_stack = []

config = {}
CODEX_FILE = "codex.txt"
CONFIG_FILE = os.path.join(USER_DOCS, "byte-forge-config.json")

def create_backup():
    os.makedirs(ARCHIVES_FOLDER, exist_ok=True)

    codex_path = CODEX_FILE  # or config["codex_path"] if you prefer
    if os.path.exists(codex_path):
        existing = [f for f in os.listdir(ARCHIVES_FOLDER) if f.startswith("codex-page-") and f.endswith(".txt")]
        highest_num = 0
        for fname in existing:
            parts = fname.replace("codex-page-", "").replace(".txt", "")
            try:
                num = int(parts)
                highest_num = max(highest_num, num)
            except ValueError:
                pass
        new_index = highest_num + 1
        backup_name = f"codex-page-{new_index}.txt"
        backup_path = os.path.join(ARCHIVES_FOLDER, backup_name)

        shutil.copyfile(codex_path, backup_path)
        print(f"[INFO] Created backup: {backup_path}")
    else:
        print("[WARNING] Codex file does not exist, no backup created.")

def load_codex():
    if os.path.exists(CODEX_FILE):
        with open(CODEX_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                global equation_dict, byte_array_dict, operator_pool
                equation_dict = data.get("equation_dict", [])
                byte_array_dict = data.get("byte_array_dict", {})

                # Ensure operator_pool is structured correctly
                operator_pool = data.get("operator_pool", {
                    "operators": [],
                    "functions": [],
                    "constants": {},
                    "groupings": [],
                    "variables": []  # Ensure variables is a list
                })

                # Ensure all required keys in operator_pool are properly initialized
                if not isinstance(operator_pool.get("operators"), list):
                    operator_pool["operators"] = []
                if not isinstance(operator_pool.get("functions"), list):
                    operator_pool["functions"] = []
                if not isinstance(operator_pool.get("constants"), dict):
                    operator_pool["constants"] = {}
                if not isinstance(operator_pool.get("groupings"), list):
                    operator_pool["groupings"] = []
                if not isinstance(operator_pool.get("variables"), list):
                    operator_pool["variables"] = []

                return equation_dict, byte_array_dict, operator_pool
            except Exception as e:
                print(f"[ERROR] Failed to load Codex: {e}")
                return [], {}, {
                    "operators": [],
                    "functions": [],
                    "constants": {},
                    "groupings": [],
                    "variables": []
                }
    return [], {}, {
        "operators": [],
        "functions": [],
        "constants": {},
        "groupings": [],
        "variables": []
    }
def save_codex():
    with open(CODEX_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "equation_dict": equation_dict,
            "byte_array_dict": byte_array_dict,
            "operator_pool": operator_pool
        }, f, indent=4)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {"codex_path": "codex.txt"} 

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

def link_codex():
    file_path = filedialog.askopenfilename(
        title="Select Codex File",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
    )
    if file_path:
        config["codex_path"] = file_path
        save_config(config)

def open_codex():
    file_path = config.get("codex_path")
    if os.path.exists(file_path):
        os.startfile(file_path) if os.name == "nt" else os.system(f"open '{file_path}'")
    else:
        print("[ERROR] Codex file not found!")

def export_codex():
    file_path = filedialog.asksaveasfilename(
        title="Save Exported Codex",
        defaultextension=".txt",
        filetypes=[("JSON Files", "*.txt"), ("All Files", "*.*")]
    )

    if not file_path:
        return

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"equation_dict": equation_dict, "byte_array_dict": byte_array_dict}, f, indent=4)

        messagebox.showinfo("Export Complete", f"Codex exported to:\n{file_path}")

    except Exception as e:
        messagebox.showerror("Export Failed", f"Error exporting Codex:\n{e}")

def get_snapshot(section="byte"):
    """
    Captures the current state of the specified section.
    """
    if section == "byte":
        return {
            "byte_array_dict": copy.deepcopy(byte_array_dict),
            "pixel_data": copy.deepcopy(pixel_data),
            "current_byte_key": current_byte_key,
            "grid_size": grid_size_var.get(),
        }
    elif section == "equation":
        return {
            "equation_dict": copy.deepcopy(equation_dict),
        }

def set_snapshot(snap, section="byte", push_to_stack=False):
    """
    Applies a saved snapshot to restore the state.
    """
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
        update_byte_grid_display()
        update_byte_array()

    elif section == "equation":
        if "equation_dict" in snap:
            equation_dict.clear()
            equation_dict.extend(snap["equation_dict"])

        refresh_equation_tree()
        update_oled_equation()

    save_codex()

def push_snapshot(section="byte", clear_redo=True):
    """
    Saves the current state to the undo stack.
    """
    if section == "byte":
        if clear_redo:
            byte_redo_stack.clear()
        byte_undo_stack.append(get_snapshot("byte"))
    elif section == "equation":
        if clear_redo:
            eq_redo_stack.clear()
        eq_undo_stack.append(get_snapshot("equation"))

def pop_undo(section="byte"):
    """
    Restores the last state from the undo stack.
    """
    if section == "byte":
        if not byte_undo_stack:
            return
        current_state = get_snapshot("byte")
        previous_state = byte_undo_stack.pop()
        byte_redo_stack.append(current_state)
        set_snapshot(previous_state, section="byte", push_to_stack=False)

    elif section == "equation":
        if not eq_undo_stack:
            return
        current_state = get_snapshot("equation")
        previous_state = eq_undo_stack.pop()
        eq_redo_stack.append(current_state)
        set_snapshot(previous_state, section="equation", push_to_stack=False)

def pop_redo(section="byte"):
    """
    Redoes the last undone state.
    """
    if section == "byte":
        if not byte_redo_stack:
            return
        current_state = get_snapshot("byte")
        next_state = byte_redo_stack.pop()
        byte_undo_stack.append(current_state)
        set_snapshot(next_state, section="byte", push_to_stack=False)

    elif section == "equation":
        if not eq_redo_stack:
            return
        current_state = get_snapshot("equation")
        next_state = eq_redo_stack.pop()
        eq_undo_stack.append(current_state)
        set_snapshot(next_state, section="equation", push_to_stack=False)

def refresh_byte_tree():
    byte_tree.delete(*byte_tree.get_children())
    for k in byte_array_dict:
        s = byte_array_dict[k]["size"]
        arr = byte_array_dict[k]["data"]
        byte_tree.insert("", "end", values=(k, s, str(arr)))

def update_oled_equation():
    """
    Updates the OLED preview based on the selected equation.
    """
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

# FIRST ROW & TITLE ————— HERE ———— I KEEP MISSING IT LOL
##########################################################
equation_dict, byte_array_dict, operator_pool = load_codex()
pixel_data = [[0]*MAX_DIM for _ in range(MAX_DIM)]
current_byte_key = None

root = tk.Tk()
root.title("Byte-Forge") # HERE
root.geometry("624x892") # AND HERE

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

def toggle_window_size():
    global expanded_geometry
    
    if not expanded_geometry:
        # Expand
        expanded_geometry = True
        root.geometry("968x892")
        toggle_btn.config(text="<<")  # Update text when expanded
    else:
        # Shrink
        expanded_geometry = False
        root.geometry("624x892")
        toggle_btn.config(text=">>")  # Update text when collapsed

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

    # auto-select the just-added equation
    if new_id in id_to_iid_map:
        eq_tree.selection_set(id_to_iid_map[new_id])
        eq_tree.focus(id_to_iid_map[new_id])

def remove_equation():
    sel = eq_tree.selection()
    if not sel:
        return
    push_snapshot(section="equation")
    iid = sel[0]
    idx = eq_tree.index(iid)

    # delete equation from tree and dictionary
    eq_tree.delete(iid)
    del equation_dict[idx]
    
    # save changes
    save_codex()
    update_oled_equation()

    # ensure tokenizer is cleared
    tokenizer_tree.delete(*tokenizer_tree.get_children())
    tokenizer_entry.delete(0, tk.END)

    # if there's a remaining equation, select it and repopulate tokenizer
    if equation_dict:
        eq_tree.selection_set(eq_tree.get_children()[0])
        eq_tree.focus(eq_tree.get_children()[0])
        tokenize_equation(0)

def refresh_all():
    refresh_equation_tree()
    refresh_byte_tree()
    update_oled_equation()
    
# Add a frame for the button and OLED container
btn_oled_container = ttk.Frame(eq_btn_frame)
btn_oled_container.pack(side="top", fill="x")

# First row of buttons
btn_top_row = ttk.Frame(btn_oled_container)
btn_top_row.pack(side="top", fill="x")

btn_open_codex = tk.Button(btn_top_row, text="Open Codex", command=open_codex)
btn_open_codex.pack(side="left")

btn_link_codex = tk.Button(btn_top_row, text="Link Codex", command=link_codex)
btn_link_codex.pack(side="left")

btn_export = tk.Button(btn_top_row, text="Export", command=export_codex)
btn_export.pack(side="left")

toggle_btn = tk.Button(
    btn_top_row, 
    text=">>", 
    command=toggle_window_size
)
toggle_btn.pack(side="right", padx=5)


# UI Tools
##########################################################

class ExpandableSection(tk.Frame):
    def __init__(self, parent, title="Section", config_key=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.config_key = config_key  # unique key to store expanded/collapsed state

        # load initial expanded/collapsed state
        self.is_expanded = load_config().get("section_states", {}).get(self.config_key, True)

        # header frame (contains +/- button, title, and optional buttons)
        self.header = tk.Frame(self)
        self.header.pack(fill="x", expand=True, pady=(5, 2))

        # expand/collapse button
        self.toggle_btn = tk.Button(self.header, text="x" if self.is_expanded else "o", width=2, command=self.toggle_section)
        self.toggle_btn.pack(side="left", padx=(5, 2))

        # section title
        self.title_label = tk.Label(self.header, text=title, font=("Arial", 12, "bold"), anchor="w")
        self.title_label.pack(side="left", padx=5, pady=2)

        # optional button frame for additional buttons
        self.button_frame = tk.Frame(self.header)
        self.button_frame.pack(side="right", padx=5)

        # main content frame
        self.content = tk.Frame(self)
        if self.is_expanded:
            self.content.pack(fill="x", expand=True)

    def toggle_section(self):
        """expands or collapses the section and saves its state"""
        if self.is_expanded:
            self.content.pack_forget()
            self.toggle_btn.config(text="o")
        else:
            self.content.pack(fill="x", expand=True)
            self.toggle_btn.config(text="x")

        self.is_expanded = not self.is_expanded  # toggle state
        self.save_state()

    def save_state(self):
        """save expanded/collapsed state to config"""
        config = load_config()
        if "section_states" not in config:
            config["section_states"] = {}
        config["section_states"][self.config_key] = self.is_expanded
        save_config(config)

def center_window(width=624, height=892):
    """ Centers the window on the screen based on given width and height. """
    root.update_idletasks()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    
    root.geometry(f"{width}x{height}+{x}+{y}")

# Equation Tree
##########################################################
# Second row of buttons
btn_bottom_row = ttk.Frame(btn_oled_container)
btn_bottom_row.pack(side="left", pady=2)  # Buttons aligned left

btn_eq_add = tk.Button(btn_bottom_row, text="+Eq", command=add_equation)
btn_eq_add.pack(side="left")

btn_eq_del = tk.Button(btn_bottom_row, text="-Eq", command=remove_equation)
btn_eq_del.pack(side="left")

btn_refresh = tk.Button(btn_bottom_row, text="⟳", command=refresh_all)
btn_refresh.pack(side="left")

btn_eq_undo = tk.Button(btn_bottom_row, text="Undo", command=lambda: pop_undo(section="equation"))
btn_eq_undo.pack(side="left")

btn_eq_redo = tk.Button(btn_bottom_row, text="Redo", command=lambda: pop_redo(section="equation"))
btn_eq_redo.pack(side="left")

# OLED Display on the right
toolbar_canvas_width, toolbar_canvas_height = emulator_width * 2, emulator_height * 2
oled_canvas = Canvas(btn_oled_container, width=toolbar_canvas_width, height=toolbar_canvas_height, bg="black", highlightthickness=1)
oled_canvas.pack(side="right", padx=10, pady=5)  # Align OLED to the right with padding

eq_cols = ("ID", "Title", "Equation", "Vars", "Byte")
eq_tree = ttk.Treeview(left_frame, columns=eq_cols, show="headings", selectmode="browse")
for col in eq_cols:
    eq_tree.heading(col, text=col)
    eq_tree.column(col, width=100, anchor="w")

eq_tree.column("ID", width=0, stretch=False)
eq_tree.column("Title", width=120)
eq_tree.column("Equation", width=200)
eq_tree.column("Vars", width=100)
eq_tree.column("Byte", width=100)
eq_tree.pack(fill="both", expand=True)
eq_edit_entry = tk.Entry(eq_tree)

def update_equation_bytes():
    for eq in equation_dict:
        equation_text = eq.get("equation", "")
        used_chars = set(equation_text)  # Extract unique characters from the equation
        valid_bytes = [char for char in used_chars if char in byte_array_dict]  # Filter to only valid bytes
        eq["byte"] = valid_bytes  # Update the 'byte' field

def refresh_equation_tree():
    update_equation_bytes()
    eq_tree.delete(*eq_tree.get_children())
    id_to_iid_map.clear()

    for e in equation_dict:
        i = e.get("id", "")
        t = e.get("title", "")
        f = parse_exceptions(e.get("equation", ""))
        v = ", ".join(e.get("vars", []))
        b = ", ".join(e.get("byte", []))  # Bytes are now keys
        iid = eq_tree.insert("", "end", values=(i, t, f, v, b))
        id_to_iid_map[i] = iid  # Store the mapping

def on_eq_double_click(event):
    sel = eq_tree.selection()
    if not sel:
        return

    iid = sel[0]
    idx = eq_tree.index(sel[0])
    col_id = eq_tree.identify_column(event.x)
    c_index = int(col_id.replace("#", "")) - 1  # Convert column ID to index

    # only allow inline editing for "title", prevent editing "vars"
    if c_index < 0 or eq_cols[c_index] != "Title":
        return

    # Handle inline editing for Title
    bbox = eq_tree.bbox(iid, column=col_id)
    if not bbox:
        return

    x, y, w, h = bbox
    eq_edit_entry.place(x=x, y=y, width=w, height=h, in_=eq_tree)

    # Prepare the current value for editing
    current_val = eq_tree.set(iid, eq_cols[c_index])
    eq_edit_entry.delete(0, tk.END)
    eq_edit_entry.insert(0, current_val)
    eq_edit_entry.focus()

    def save_and_exit_edit(event=None):
        """
        Save the new value and exit inline editing mode.
        """
        new_val = eq_edit_entry.get().strip()
        eq_edit_entry.place_forget()

        # update only the "title" field
        equation_dict[idx]["title"] = new_val

        save_codex()
        refresh_equation_tree()

    # Bind actions for saving
    eq_edit_entry.bind("<Return>", save_and_exit_edit)
    eq_edit_entry.bind("<FocusOut>", save_and_exit_edit)

def on_eq_click(event):
    region = eq_tree.identify_region(event.x, event.y)
    if region in ("nothing", "separator", "heading"):
        eq_tree.selection_remove(*eq_tree.selection())
        return
    
    iid = eq_tree.identify_row(event.y)
    if iid:
        eq_tree.selection_set(iid)

    sel = eq_tree.selection()
    if not sel:
        return

    new_index = eq_tree.index(sel[0])
    old_index = getattr(on_eq_click, "last_index", None)

    if new_index != old_index:
        on_eq_click.last_index = new_index
        update_oled_equation()
        refresh_ranges_tree()
        populate_tokenizer_from_eq(new_index)  # Populate tokenizer

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

# tokenizer
##########################################################
tokenizer_section = ExpandableSection(left_frame, title="Tokenizer", config_key="tokenizer")
tokenizer_section.pack(fill="x", padx=5, pady=5)

tokenizer_input_frame = ttk.Frame(tokenizer_section.content)
tokenizer_input_frame.pack(fill="x", padx=5, pady=5)

tokenizer_entry = tk.Entry(tokenizer_input_frame, width=40)
tokenizer_entry.pack(side="left", fill="x", expand=True, padx=5)

tokenizer_btn_frame = ttk.Frame(tokenizer_input_frame)
tokenizer_btn_frame.pack(side="right")

tokenizer_cols = ("Raw Text", "Category", "Assigned Token")
tokenizer_tree = ttk.Treeview(
    tokenizer_section.content, columns=tokenizer_cols, show="headings", height=8
)
for col in tokenizer_cols:
    tokenizer_tree.heading(col, text=col)
    tokenizer_tree.column(col, anchor="w")
tokenizer_tree.pack(fill="both", expand=True)

def populate_tokenizer_from_eq(eq_idx):
    """Populates the tokenizer tree and autofills the tokenizer entry field from the selected equation."""
    tokenizer_tree.delete(*tokenizer_tree.get_children())

    if eq_idx < 0 or eq_idx >= len(equation_dict):
        tokenizer_entry.delete(0, tk.END)
        return

    eq_data = equation_dict[eq_idx]
    equation_text = eq_data.get("equation", "").strip()

    if not equation_text:
        tokenizer_entry.delete(0, tk.END)
        return  # No equation, keep tokenizer empty

    # Apply exception parsing before displaying in the text field
    parsed_eq = parse_exceptions(equation_text)
    print(f"[debug] parsed equation: '{parsed_eq}'")

    # Autofill the tokenizer entry field
    tokenizer_entry.delete(0, tk.END)
    tokenizer_entry.insert(0, parsed_eq)

    # Tokenize the parsed equation
    raw_tokens = parsed_eq.split(" ")

    for token in raw_tokens:
        category = "unknown"
        if token in operator_pool.get("functions", []):
            category = "function"
        elif token in operator_pool.get("operators", []):
            category = "operator"
        elif token in operator_pool.get("constants", {}):
            category = "constant"
        elif token in operator_pool.get("groupings", []):
            category = "grouping"
        elif token in operator_pool.get("variables", []):
            category = "variable"

        tokenizer_tree.insert("", "end", values=(token, category, token if category != "unknown" else "???"))
        print(f"[debug] inserting token: '{token}', category: '{category}'")
def tokenize_equation(eq_idx):
    """Tokenizes the equation while ensuring exception parsing and updating the backend."""
    if eq_idx < 0 or eq_idx >= len(equation_dict):
        print("[debug] invalid equation index.")
        return

    eq_data = equation_dict[eq_idx]

    # Ensure the equation is saved to the dictionary before parsing
    eq_data["equation"] = tokenizer_entry.get().strip()

    eq = eq_data["equation"]
    print(f"[debug] raw equation before parsing: '{eq}'")

    # Apply exception parsing before tokenizing
    parsed_eq = parse_exceptions(eq)
    print(f"[debug] parsed equation: '{parsed_eq}'")

    raw_tokens = parsed_eq.split(" ")
    tokenizer_tree.delete(*tokenizer_tree.get_children())

    tokens = []  # Collect new tokens for updating equation_dict
    variables = []  # Store extracted variables

    for token in raw_tokens:
        category = "unknown"
        if token in operator_pool.get("functions", []):
            category = "function"
        elif token in operator_pool.get("operators", []):
            category = "operator"
        elif token in operator_pool.get("constants", {}):
            category = "constant"
        elif token in operator_pool.get("groupings", []):
            category = "grouping"
        elif token in operator_pool.get("variables", []):
            category = "variable"
            variables.append(token)  # Store variable for `vars` field

        print(f"[debug] inserting token: '{token}', category: '{category}'")

        tokenizer_tree.insert("", "end", values=(token, category, token if category != "unknown" else "???"))
        tokens.append(token)

    # Immediately update equation_dict with new tokenized version
    eq_data["equation"] = " ".join(tokens)
    eq_data["vars"] = list(set(variables))  # Remove duplicates

    # Save immediately to ensure persistence
    save_codex()

    # Refresh the UI and restore selection
    refresh_equation_tree()
    eq_tree.selection_set(eq_tree.get_children()[eq_idx])  # Restore focus

tk.Button(tokenizer_input_frame, text="Tokenize", command=lambda: tokenize_equation(eq_tree.index(eq_tree.selection()[0]))).pack(side="left", padx=2)

def move_token(direction):
    sel = tokenizer_tree.selection()
    if not sel:
        return

    iid = sel[0]
    index = tokenizer_tree.index(iid)
    tokens = list(tokenizer_tree.get_children())

    if direction == "up" and index > 0:
        tokenizer_tree.move(iid, "", index - 1)
    elif direction == "down" and index < len(tokens) - 1:
        tokenizer_tree.move(iid, "", index + 1)
    else:
        return

    # update equation_dict with new token order
    eq_sel = eq_tree.selection()
    if not eq_sel:
        return

    eq_idx = eq_tree.index(eq_sel[0])
    if eq_idx < 0 or eq_idx >= len(equation_dict):
        return

    # rebuild equation from reordered tokens
    new_tokens = [
        tokenizer_tree.item(token_id, "values")[0] for token_id in tokenizer_tree.get_children()
    ]

    equation_dict[eq_idx]["equation"] = " ".join(new_tokens)

    # save and refresh everything
    save_codex()
    refresh_equation_tree()
    update_oled_equation()

    # reselect the equation to avoid UI flickering
    eq_tree.selection_set(eq_tree.get_children()[eq_idx])

tk.Button(tokenizer_input_frame, text="↑", command=lambda: move_token("up")).pack(side="left", padx=2)
tk.Button(tokenizer_input_frame, text="↓", command=lambda: move_token("down")).pack(side="left", padx=2)

def on_tokenizer_select(event):
    """ handles token selection but does not modify the tokenizer entry. """
    sel = tokenizer_tree.selection()
    if not sel:
        return

    iid = sel[0]
    values = tokenizer_tree.item(iid, "values")

    # just log selection for debugging but do not autofill the tokenizer entry
    raw_text = values[0]
    print(f"[DEBUG] Selected token: {raw_text}")  

tokenizer_tree.bind("<<TreeviewSelect>>", on_tokenizer_select)

def on_tokenizer_double_click(event):
    """Triggers the 'Add Operator' form if the selected token has '???' as assigned."""
    sel = tokenizer_tree.selection()
    if not sel:
        return

    iid = sel[0]
    values = tokenizer_tree.item(iid, "values")
    raw_text, category, assigned_token = values

    # Only trigger 'Add Operator' if the token is unknown ('???')
    if assigned_token == "???":
        add_operator(pre_filled_symbol=raw_text)

tokenizer_tree.bind("<Double-1>", on_tokenizer_double_click)

# Operator Pool
##########################################################
operator_section = ExpandableSection(left_frame, title="Operator Pool", config_key="operator_pool")
operator_section.pack(fill="x", padx=5, pady=5)

operator_cols = ("Category", "Symbol/Key", "Value")
operator_tree = ttk.Treeview(
    operator_section.content, columns=operator_cols, show="headings", height=8
)
for col in operator_cols:
    operator_tree.heading(col, text=col)
    operator_tree.column(col, anchor="w")
operator_tree.pack(fill="both", expand=True)

def refresh_operator_tree():
    operator_tree.delete(*operator_tree.get_children())
    for category, items in operator_pool.items():
        if category == "constants" and isinstance(items, dict):
            for symbol, value in items.items():
                operator_tree.insert("", "end", values=(category, symbol, value))
        elif isinstance(items, list):
            for symbol in items:
                operator_tree.insert("", "end", values=(category, symbol, ""))

def add_operator(pre_filled_symbol=None):
    """Opens a pop-up to add a new operator to the pool, positioning the dropdown menu exactly at the cursor."""
    add_window = tk.Toplevel(root)
    add_window.title("Add Operator")

    # Get cursor position
    cursor_x, cursor_y = root.winfo_pointerxy()
    add_window.geometry(f"+{cursor_x}+{cursor_y}")

    tk.Label(add_window, text="Category:").grid(row=0, column=0, padx=5, pady=5)
    category_var = tk.StringVar(value="operators")
    category_dropdown = ttk.Combobox(
        add_window, textvariable=category_var,
        values=["operators", "functions", "constants", "groupings", "variables"],
        state="readonly"
    )
    category_dropdown.grid(row=0, column=1, padx=5, pady=5)

    tk.Label(add_window, text="Symbol/Key:").grid(row=1, column=0, padx=5, pady=5)
    symbol_entry = tk.Entry(add_window)
    symbol_entry.grid(row=1, column=1, padx=5, pady=5)

    if pre_filled_symbol:
        symbol_entry.insert(0, pre_filled_symbol)

    tk.Label(add_window, text="Value (Optional):").grid(row=2, column=0, padx=5, pady=5)
    value_entry = tk.Entry(add_window)
    value_entry.grid(row=2, column=1, padx=5, pady=5)

    def confirm_add():
        category = category_var.get()
        symbol = symbol_entry.get().strip()
        value = value_entry.get().strip()

        if not symbol:
            messagebox.showerror("Error", "Symbol cannot be empty.")
            return

        # Normalize symbol (e.g., "*" → "⋅")
        symbol = parse_exceptions(symbol)

        # Ensure category exists
        if category not in operator_pool:
            if category == "constants":
                operator_pool[category] = {}
            else:
                operator_pool[category] = []

        # Handle addition for each category
        if category == "constants":
            # Constants need a dictionary
            if not isinstance(operator_pool[category], dict):
                operator_pool[category] = {}

            if symbol in operator_pool[category]:
                messagebox.showerror("Error", f"'{symbol}' already exists in {category}.")
                return

            try:
                numeric_value = float(value) if value else 0.0
            except ValueError:
                messagebox.showerror("Error", f"Value for '{symbol}' must be a number.")
                return

            operator_pool[category][symbol] = numeric_value

        elif category == "variables":
            # Variables are stored in a list
            if not isinstance(operator_pool[category], list):
                operator_pool[category] = []

            if symbol in operator_pool[category]:
                messagebox.showerror("Error", f"'{symbol}' already exists in {category}.")
                return

            operator_pool[category].append(symbol)

        else:
            # All other categories are lists
            if not isinstance(operator_pool[category], list):
                operator_pool[category] = []

            if symbol in operator_pool[category]:
                messagebox.showerror("Error", f"'{symbol}' already exists in {category}.")
                return

            operator_pool[category].append(symbol)

        # Save changes
        save_codex()
        refresh_operator_tree()

        # Re-tokenize the current equation
        eq_sel = eq_tree.selection()
        if eq_sel:
            eq_idx = eq_tree.index(eq_sel[0])
            tokenize_equation(eq_idx)

        add_window.destroy()

    tk.Button(add_window, text="Add", command=confirm_add).grid(row=5, column=0, columnspan=2, pady=10)
operator_tree.bind("<Button-3>", add_operator)

def remove_operator():
    sel = operator_tree.selection()
    if sel:
        for iid in sel:
            values = operator_tree.item(iid, "values")
            category, symbol, _ = values
            if category in operator_pool:
                if category == "constants" and isinstance(operator_pool[category], dict):
                    operator_pool[category].pop(symbol, None)
                elif isinstance(operator_pool[category], list):
                    try:
                        operator_pool[category].remove(symbol)
                    except ValueError:
                        messagebox.showerror("Error", f"'{symbol}' not found in {category}.")
        save_codex()
        refresh_operator_tree()

        # Refresh the tokenizer tree to update token categories
        sel_eq = eq_tree.selection()
        if sel_eq:
            eq_idx = eq_tree.index(sel_eq[0])
            tokenize_equation(eq_idx)  # Re-tokenize the selected equation to reflect changes

tk.Button(operator_section.button_frame, text="+", command=add_operator).pack(side="left", padx=2)
tk.Button(operator_section.button_frame, text="-", command=remove_operator).pack(side="left", padx=2)

def on_operator_double_click(event):
    """Allows inline editing of operator pool entries on double-click."""
    sel = operator_tree.selection()
    if not sel:
        return

    iid = sel[0]
    col_id = operator_tree.identify_column(event.x)
    c_index = int(col_id.replace("#", "")) - 1  # Convert column ID to index

    if c_index < 1:  # Only allow editing for Symbol/Key and Value columns
        return

    # Get bounding box for inline editing
    bbox = operator_tree.bbox(iid, column=col_id)
    if not bbox:
        return
    x, y, w, h = bbox

    # Create an Entry widget for inline editing
    edit_entry = tk.Entry(operator_tree)
    values = operator_tree.item(iid, "values")
    edit_entry.insert(0, values[c_index])
    edit_entry.place(x=x, y=y, width=w, height=h)
    edit_entry.focus()

    def save_edit(event=None):
        """Saves the edited operator and updates the table."""
        new_value = edit_entry.get().strip()
        edit_entry.place_forget()

        category, symbol, value = values

        # Ensure category exists
        if category not in operator_pool:
            messagebox.showerror("Error", f"Category '{category}' not found in operator pool.")
            return

        if category == "constants":
            # Editing a constant (symbol or value)
            if c_index == 1:  # Editing Symbol/Key
                if symbol == new_value:
                    return  # No change, exit early
                if new_value in operator_pool[category]:
                    messagebox.showerror("Error", f"'{new_value}' already exists in {category}.")
                    return
                operator_pool[category][new_value] = operator_pool[category].pop(symbol)  # Rename key

            elif c_index == 2:  # Editing Value
                try:
                    numeric_value = float(new_value)  # Convert to float
                except ValueError:
                    messagebox.showerror("Error", f"Value for '{symbol}' must be a number.")
                    return
                operator_pool[category][symbol] = numeric_value  # Update the value
                operator_tree.item(iid, values=(category, symbol, numeric_value))  # Update Treeview row

        else:
            # Editing non-constant categories (operators, functions, groupings, variables)
            operator_list = operator_pool[category]

            if c_index == 1:  # Editing Symbol/Key
                if symbol == new_value:
                    return  # No change, exit early

                try:
                    operator_list.remove(symbol)  # Remove old value first
                except ValueError:
                    messagebox.showerror("Error", f"'{symbol}' not found in {category}.")
                    return

                if new_value in operator_list:
                    messagebox.showerror("Error", f"'{new_value}' already exists in {category}.")
                    operator_list.append(symbol)  # Restore old value
                    return

                operator_list.append(new_value)  # Add new value
                operator_tree.item(iid, values=(category, new_value, value))  # Update Treeview row

            elif c_index == 2:  # Editing Value (for non-constants, should not exist)
                messagebox.showerror("Error", "Values are only editable for constants.")
                return

        save_codex()
        refresh_operator_tree()


    edit_entry.bind("<Return>", save_edit)
    edit_entry.bind("<FocusOut>", save_edit)

operator_tree.bind("<Double-1>", on_operator_double_click)

# Ranges Tree
##########################################################
ranges_section = ExpandableSection(left_frame, title="Variable Ranges", config_key="variable_ranges")
ranges_section.pack(fill="x", padx=5, pady=5)

ranges_frame = ttk.Frame(ranges_section.content)
ranges_frame.pack(fill="x", padx=5, pady=5)

ranges_cols = ("Var", "Min", "Max")
ranges_tree = ttk.Treeview(ranges_frame, columns=ranges_cols, show="headings", selectmode="browse", height=5)
for col in ranges_cols:
    ranges_tree.heading(col, text=col)
    ranges_tree.column(col, width=80, anchor="w")

ranges_tree.pack(side="left", fill="x", expand=True)

ranges_scroll = ttk.Scrollbar(ranges_frame, orient="vertical", command=ranges_tree.yview)
ranges_tree.configure(yscrollcommand=ranges_scroll.set)
ranges_scroll.pack(side="right", fill="y")

def refresh_ranges_tree():
    # Clear out the old rows
    ranges_tree.delete(*ranges_tree.get_children())

    sel = eq_tree.selection()
    if not sel:
        return  # No equation selected

    idx = eq_tree.index(sel[0])
    if idx < 0 or idx >= len(equation_dict):
        return

    eq_data = equation_dict[idx]

    # Make sure we have a 'settings' and a 'ranges' dict
    if "settings" not in eq_data:
        eq_data["settings"] = {}
    if "ranges" not in eq_data["settings"]:
        eq_data["settings"]["ranges"] = {}

    vars_list = eq_data.get("vars", [])
    for v in vars_list:
        # If we don't have a stored range for this var, give it a default
        if v not in eq_data["settings"]["ranges"]:
            eq_data["settings"]["ranges"][v] = [0.0, 1.0]  # or whatever defaults you prefer

        var_min, var_max = eq_data["settings"]["ranges"][v]
        # Insert a row into the tree
        ranges_tree.insert("", "end", values=(v, var_min, var_max))

def on_ranges_double_click(event):
    sel = ranges_tree.selection()
    if not sel:
        return
    
    iid = sel[0]
    col_id = ranges_tree.identify_column(event.x)  # e.g. "#1", "#2", "#3"
    row_vals = ranges_tree.item(iid, "values")     # (var_name, var_min, var_max)
    if not row_vals:
        return

    c_index = int(col_id.replace("#","")) - 1
    if c_index < 0:
        return  # Out of range

    # BBox for inline editing
    bbox = ranges_tree.bbox(iid, column=col_id)
    if not bbox:
        return
    x, y, w, h = bbox

    var_name, old_min, old_max = row_vals

    # We only want to let them edit min or max, i.e. columns #1 or #2 in 0-based
    if c_index == 0:
        # "Var" column -- typically read-only. Let's do nothing or we can rename var if you like.
        return

    # Create an Entry for editing
    editor = tk.Entry(ranges_tree)
    current_val = row_vals[c_index]
    editor.insert(0, str(current_val))
    editor.place(x=x, y=y, width=w, height=h)
    editor.focus()

    def save_edit(event=None):
        new_val_str = editor.get().strip()
        editor.place_forget()

        # Convert to float
        try:
            new_val = float(new_val_str)
        except ValueError:
            new_val = float(current_val)  # fallback if invalid

        # Update eq_data
        eq_sel = eq_tree.selection()
        if not eq_sel:
            return
        eq_idx = eq_tree.index(eq_sel[0])
        if eq_idx < 0 or eq_idx >= len(equation_dict):
            return

        eq_data = equation_dict[eq_idx]
        var_ranges = eq_data["settings"]["ranges"][var_name]

        # c_index == 1 -> 'Min'
        # c_index == 2 -> 'Max'
        if c_index == 1:
            var_ranges[0] = new_val  # min
        elif c_index == 2:
            var_ranges[1] = new_val  # max

        # Save back to the row & persist to codex
        updated_row = list(row_vals)
        updated_row[c_index] = new_val
        ranges_tree.item(iid, values=tuple(updated_row))
        save_codex()

    # Bind Return/FocusOut to save
    editor.bind("<Return>", save_edit)
    editor.bind("<FocusOut>", save_edit)

ranges_tree.bind("<Double-1>", on_ranges_double_click)

# Exceptions Tree
##########################################################
exceptions_section = ExpandableSection(left_frame, title="Parsing Exceptions", config_key="parsing_exceptions")
exceptions_section.pack(fill="x", padx=5, pady=5)

# add/remove buttons inside the exception header
btn_add_exception = tk.Button(exceptions_section.button_frame, text="+", command=lambda: add_exception())
btn_remove_exception = tk.Button(exceptions_section.button_frame, text="-", command=lambda: remove_exception())

btn_remove_exception.pack(side="right", padx=3)
btn_add_exception.pack(side="right", padx=3)

exceptions_tree_frame = ttk.Frame(exceptions_section.content)
exceptions_tree_frame.pack(fill="both", expand=False)

exceptions_cols = ("Initial Char", "Parsed Char")
exceptions_tree = ttk.Treeview(
    exceptions_tree_frame,
    columns=exceptions_cols,
    show="headings",
    selectmode="browse",
    height=3  # Adjust the number of visible rows
)
for col in exceptions_cols:
    exceptions_tree.heading(col, text=col)
    exceptions_tree.column(col, anchor="w")

exceptions_scrollbar = ttk.Scrollbar(exceptions_tree_frame, orient="vertical", command=exceptions_tree.yview)
exceptions_tree.configure(yscrollcommand=exceptions_scrollbar.set)

exceptions_tree.pack(side="left", fill="both", expand=True)
exceptions_scrollbar.pack(side="right", fill="y")

def load_exceptions():
    config = load_config()
    return config.get("exceptions", {})

def save_exceptions(exceptions):
    config = load_config()
    config["exceptions"] = exceptions
    save_config(config)

def parse_exceptions(equation):
    """
    Replace exceptions in the equation text with desired symbols dynamically.
    """
    exceptions = load_exceptions()

    # Remove empty-string exceptions
    exceptions = {k: v for k, v in exceptions.items() if k.strip()}

    if not exceptions:
        return equation  # Return unchanged if no exceptions exist

    pattern = re.compile("|".join(re.escape(k) for k in exceptions))
    return pattern.sub(lambda match: exceptions.get(match.group(0), ""), equation)

def add_exception():
    exceptions = load_exceptions()
    if "" not in exceptions:  # Avoid duplicate blank entries
        exceptions[""] = ""  # Default blank entry
        save_exceptions(exceptions)
        refresh_exceptions_tree()

def remove_exception():
    sel = exceptions_tree.selection()
    if not sel:
        return
    old_value = exceptions_tree.item(sel[0], "values")[0]
    exceptions = load_exceptions()
    if old_value in exceptions:
        del exceptions[old_value]
        save_exceptions(exceptions)
        refresh_exceptions_tree()

def refresh_exceptions_tree():
    exceptions_tree.delete(*exceptions_tree.get_children())
    exceptions = load_exceptions()
    for old, new in exceptions.items():
        exceptions_tree.insert("", "end", values=(old, new))

def on_exceptions_double_click(event):
    sel = exceptions_tree.selection()
    if not sel:
        return

    iid = sel[0]
    col_id = exceptions_tree.identify_column(event.x)
    c_index = int(col_id.replace("#", "")) - 1  # Map column to 0-based index
    if c_index < 0 or c_index >= len(exceptions_cols):
        return

    # Inline editing setup
    bbox = exceptions_tree.bbox(iid, column=col_id)
    if not bbox:
        return
    x, y, w, h = bbox
    edit_entry = tk.Entry(exceptions_tree)
    edit_entry.place(x=x, y=y, width=w, height=h)
    current_val = exceptions_tree.set(iid, exceptions_cols[c_index])
    edit_entry.insert(0, current_val)
    edit_entry.focus()

    def save_and_exit_edit(event=None):
        new_val = edit_entry.get().strip()
        edit_entry.place_forget()

        sel = exceptions_tree.selection()
        if not sel:
            return

        iid = sel[0]
        values = exceptions_tree.item(iid, "values")

        if not values:  # Prevent the "Item Not Found" error
            return

        old_value, new_value = values
        exceptions = load_exceptions()

        if c_index == 0:  # Editing the "Initial Char" column
            if old_value in exceptions:
                del exceptions[old_value]
            exceptions[new_val] = new_value
        elif c_index == 1:  # Editing the "Parsed Char" column
            exceptions[old_value] = new_val

        save_exceptions(exceptions)
        refresh_exceptions_tree()


    edit_entry.bind("<Return>", save_and_exit_edit)
    edit_entry.bind("<FocusOut>", save_and_exit_edit)

exceptions_tree.bind("<Double-1>", on_exceptions_double_click)

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

def update_byte_grid_display():
    """
    Update the display of the byte grid
    """
    canvas.delete("all")  # Clear the canvas
    s = grid_size_var.get()  # Current grid size
    total_cells = MAX_DIM  # Always use MAX_DIM to keep the container consistent
    grid_px = total_cells * CELL_SIZE

    # Calculate fixed offsets to center the grid
    offset_x = (CANVAS_SIZE - grid_px) // 2
    offset_y = (CANVAS_SIZE - grid_px) // 2

    for y in range(MAX_DIM):
        for x in range(MAX_DIM):
            # Determine if the cell is within the active region
            in_region = MARGIN <= x < MARGIN + s and MARGIN <= y < MARGIN + s
            color = (
                "white" if in_region and pixel_data[y][x] == 0 else
                "black" if in_region and pixel_data[y][x] == 1 else
                "#777777"
            )

            # Compute cell coordinates
            left = offset_x + x * CELL_SIZE
            top = offset_y + y * CELL_SIZE
            right = left + CELL_SIZE
            bottom = top + CELL_SIZE

            # Draw the cell
            rid = canvas.create_rectangle(left, top, right, bottom, fill=color, outline="black")

            # Bind click interaction for cells within the active region
            if in_region:
                def click_closure(e, cx=x, cy=y):
                    push_snapshot()
                    pixel_data[cy][cx] = 1 - pixel_data[cy][cx]
                    update_byte_grid_display()
                    update_byte_array()

                canvas.tag_bind(rid, "<Button-1>", click_closure)

    # Draw bounding box for the active region
    act_left = offset_x + MARGIN * CELL_SIZE
    act_top = offset_y + MARGIN * CELL_SIZE
    act_right = act_left + s * CELL_SIZE
    act_bottom = act_top + s * CELL_SIZE
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

    byte_array_dict[current_byte_key]["size"] = s
    byte_array_dict[current_byte_key]["data"] = arr

    save_codex()
    refresh_byte_tree()
    update_oled_equation()
    
def on_grid_size_change(*_):
    push_snapshot()
    update_byte_grid_display()
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

    update_byte_grid_display()
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
size_values = list(range(5, 11))
size_om = ttk.OptionMenu(byte_op_frame, grid_size_var, 8, *size_values)
size_om.pack(side="left")

def on_clear_canvas():
    push_snapshot()
    for yy in range(MAX_DIM):
        for xx in range(MAX_DIM):
            pixel_data[yy][xx] = 0
    update_byte_grid_display()
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
        show_error_in_textfield("NAME CANNOT BE EMPTY!")
        return

    # Check for duplicate names directly as dictionary keys
    if typed_name in byte_array_dict:
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
        return
    for iid in sel:
        row_vals = byte_tree.item(iid, "values")
        byte_id = row_vals[0]
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

    global current_byte_key
    if current_byte_key == byte_id:
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

            update_byte_grid_display()
        finally:
            # Re-enable grid size change trace
            grid_size_var.trace_id = grid_size_var.trace_add("write", on_grid_size_change)

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
    center_window()

    global config, CODEX_FILE, operator_pool

    config = load_config()
    CODEX_FILE = config.get("codex_path", "codex.txt")  # Set CODEX_FILE before using it
    print(f"[INFO] Current Codex File Location: {CODEX_FILE}")

    create_backup()

    # Now load the codex AFTER CODEX_FILE has been set correctly
    global equation_dict, byte_array_dict
    equation_dict, byte_array_dict, operator_pool = load_codex()
    print("[DEBUG] operator_pool contents on load:", json.dumps(operator_pool, indent=4))

    refresh_equation_tree()
    refresh_byte_tree()
    update_byte_grid_display()
    update_oled_equation()
    refresh_exceptions_tree()
    refresh_operator_tree()

create_backup()
init()
root.mainloop()

