#!/usr/bin/env python3
import os
import json
import threading
import traceback
import subprocess  # Added for opening folders
import sys         # Added for detecting the operating system
from tkinter import Tk, Label, BOTH, filedialog
from tkinter import ttk  # For the progress bar, treeview, and frame
from tkinterdnd2 import DND_FILES, TkinterDnD
from pydub import AudioSegment

# ---------------- Configuration Handling ----------------

# Set the configuration directory to the user's Documents/mbcorp folder.
config_dir = os.path.join(os.path.expanduser("~"), "Documents", "mbcorp")
os.makedirs(config_dir, exist_ok=True)
config_path = os.path.join(config_dir, "config.json")

# Default configuration values
default_config = {
    "destination_folder": os.path.join(os.path.expanduser("~"), "Dropbox", "bibi-ambi")
}

# If no config file exists, write the default config to disk.
if not os.path.exists(config_path):
    with open(config_path, "w") as f:
        json.dump(default_config, f, indent=4)
    print(f"Created default config file at: {config_path}")

# Load configuration from the file.
with open(config_path, "r") as f:
    config = json.load(f)

# Use the destination folder from the config.
DESTINATION_FOLDER = config.get("destination_folder", default_config["destination_folder"])
os.makedirs(DESTINATION_FOLDER, exist_ok=True)
print(f"Destination folder set to: {DESTINATION_FOLDER}")

# ---------------- Application Code ----------------

# Global flag to ensure only one processing thread is running at a time
processing = False

def convert_file(file_path):
    try:
        # Clean up the file path (remove extraneous braces)
        file_path = file_path.strip("{}")
        print(f"Processing file: {file_path}")

        base, ext = os.path.splitext(os.path.basename(file_path))
        ext = ext.lower()
        # Only support AIFF/AIF/WAV files
        if ext not in ['.aif', '.aiff', '.wav']:
            print(f"Unsupported file type: {ext}")
            return False

        # Load audio file
        audio = AudioSegment.from_file(file_path)
        # Define output file path based on the config destination folder
        output_path = os.path.join(DESTINATION_FOLDER, f"{base}.mp3")
        print(f"Converting to: {output_path}")

        # Export as MP3 with 320kbps bitrate
        audio.export(output_path, format="mp3", bitrate="320k")
        print(f"Successfully converted '{file_path}' to '{output_path}' at 320kbps.")
        return True

    except Exception as e:
        print("Error during conversion:")
        traceback.print_exc()
        return False

def process_queue():
    """
    Process each queued file by iterating over the items in the treeview.
    This runs in a background thread.
    """
    global processing
    processing = True
    # Start the progress bar (must be called from the main thread)
    root.after(0, lambda: progress.start(10))
    # Get all queued items from the table
    items = tree.get_children()
    for item in items:
        # Retrieve the file path (first column) from the item values
        file_path = tree.item(item, "values")[0]
        print(f"Processing queued file: {file_path}")
        # Update status to "Converting"
        root.after(0, lambda it=item: tree.set(it, "Status", "Converting"))
        if os.path.isfile(file_path):
            success = convert_file(file_path)
            if success:
                root.after(0, lambda it=item: tree.set(it, "Status", "MUNCH MUNCH MUNCH"))
            else:
                root.after(0, lambda it=item: tree.set(it, "Status", "Error: Conversion failed"))
        else:
            root.after(0, lambda it=item: tree.set(it, "Status", "Error: File not found"))
    # When done, stop the progress bar and clear the processing flag
    root.after(0, lambda: progress.stop())
    processing = False

def drop(event):
    """
    When files are dropped into the window, add them to the queue table.
    Then, if not already processing, start a background thread to process the queue.
    """
    files = root.tk.splitlist(event.data)
    print(f"Received drop event with files: {files}")
    for file in files:
        cleaned_file = file.strip("{}")
        print(f"Adding file to queue: {cleaned_file}")
        # Insert a new row: first column is file path, second column is the status.
        tree.insert("", "end", values=(cleaned_file, "Queued"))
    # Update the instruction label
    label.config(text="Files queued for conversion...")
    # If not already processing, start processing the queue in a new thread.
    global processing
    if not processing:
        threading.Thread(target=process_queue, daemon=True).start()

def choose_destination():
    """
    Open a directory chooser dialog to let the user select a new destination folder.
    Update the global DESTINATION_FOLDER variable and save the new config.
    """
    global DESTINATION_FOLDER  # Declare global at the top of the function
    new_path = filedialog.askdirectory(initialdir=DESTINATION_FOLDER, title="Select Destination Folder")
    if new_path:
        DESTINATION_FOLDER = new_path
        os.makedirs(DESTINATION_FOLDER, exist_ok=True)
        # Update the label that displays the path
        path_label.config(text=DESTINATION_FOLDER)
        # Update the config file
        config["destination_folder"] = DESTINATION_FOLDER
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
        print(f"Updated destination folder to: {DESTINATION_FOLDER}")

def open_destination_folder():
    """
    Open the destination folder in the system's file explorer.
    """
    try:
        if sys.platform == "darwin":       # macOS
            subprocess.Popen(["open", DESTINATION_FOLDER])
        elif sys.platform == "win32":      # Windows
            subprocess.Popen(["explorer", DESTINATION_FOLDER])
        else:                              # Linux and others
            subprocess.Popen(["xdg-open", DESTINATION_FOLDER])
        print(f"Opened destination folder: {DESTINATION_FOLDER}")
    except Exception as e:
        print("Failed to open destination folder:")
        traceback.print_exc()

# Create the main application window using tkinterdnd2
root = TkinterDnD.Tk()
root.title("Audio Converter")
root.geometry("600x600")
root.resizable(False, False)

# Create an instruction label (and drop zone)
label = Label(root, text="DROP FILES TO QUEUE FOR 320kbps MP3 CONVERSION",
              font=("Helvetica", 16), bg="black", fg="white")
label.pack(fill="x", padx=10, pady=10)

# --------------- New Row: PATH Button & Labels & Open Button ---------------
path_frame = ttk.Frame(root)
path_frame.pack(fill="x", padx=10, pady=5)

# A button labeled "PATH" that lets you choose a new destination folder
path_button = ttk.Button(path_frame, text="PATH", command=choose_destination)
path_button.pack(side="left")

# A label displaying the current destination folder
path_label = ttk.Label(path_frame, text=DESTINATION_FOLDER)
path_label.pack(side="left", padx=10)

# A button labeled "Open in Finder" to open the destination folder
open_button = ttk.Button(path_frame, text="Open in Folder", command=open_destination_folder)
open_button.pack(side="left", padx=10)
# -----------------------------------------------------------

# Create a Treeview widget to serve as the queue container
tree = ttk.Treeview(root, columns=("File", "Status"), show="headings")
tree.heading("File", text="File")
tree.heading("Status", text="Status")
tree.column("File", width=400)
tree.column("Status", width=150)
tree.pack(expand=True, fill="both", padx=10, pady=10)

# Create an indeterminate progress bar at the bottom
progress = ttk.Progressbar(root, orient="horizontal", mode="indeterminate")
progress.pack(fill="x", side="bottom", padx=20, pady=20)

# Register drop targets on both the label and the treeview
label.drop_target_register(DND_FILES)
label.dnd_bind("<<Drop>>", drop)
tree.drop_target_register(DND_FILES)
tree.dnd_bind("<<Drop>>", drop)

print("Audio Converter ready. Drag and drop files into the window.")
root.mainloop()
