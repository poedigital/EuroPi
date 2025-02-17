#!/usr/bin/env python3
import os
import json
import threading
import traceback
from tkinter import Tk, Label, BOTH, filedialog, messagebox
from tkinter import ttk  # For the progress bar, treeview, and frame
from tkinterdnd2 import DND_FILES, TkinterDnD
from pdf2image import convert_from_path
from PIL import Image, ImageOps
import subprocess
import platform

# ---------------- Configuration Handling ----------------

# Set the configuration directory to the user's Documents/mbcorp folder.
config_dir = os.path.join(os.path.expanduser("~"), "Documents", "mbcorp")
os.makedirs(config_dir, exist_ok=True)
config_path = os.path.join(config_dir, "negative-config.json")

# Default configuration values
default_config = {
    "destination_folder": os.path.join(os.path.expanduser("~"), "Dropbox", "pdf_negatives"),
    "poppler_path": ""  # Set your Poppler path here if necessary
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

# Poppler path from config (if needed)
POPLER_PATH = config.get("poppler_path", default_config["poppler_path"])

# ---------------- Application Code ----------------

# Global flag to ensure only one processing thread is running at a time
processing = False

def convert_pdf_to_negative(file_path):
    try:
        # Clean up the file path (remove extraneous braces)
        file_path = file_path.strip("{}")
        print(f"Processing file: {file_path}")

        base, ext = os.path.splitext(os.path.basename(file_path))
        ext = ext.lower()
        # Only support PDF files
        if ext != '.pdf':
            print(f"Unsupported file type: {ext}")
            return False

        # Convert PDF pages to images
        pages = convert_from_path(file_path, poppler_path=POPLER_PATH)
        print(f"Converted PDF to {len(pages)} images.")

        inverted_images = []
        for i, page in enumerate(pages):
            # Invert colors
            inverted_page = ImageOps.invert(page.convert('RGB'))
            inverted_images.append(inverted_page)
            print(f"Inverted colors for page {i + 1}.")

        # Define output PDF path
        output_pdf_path = os.path.join(DESTINATION_FOLDER, f"{base}_negative.pdf")
        # Save inverted images as a single PDF
        inverted_images[0].save(output_pdf_path, save_all=True, append_images=inverted_images[1:])
        print(f"Successfully saved negative PDF to '{output_pdf_path}'.")
        return True

    except Exception as e:
        print("Error during PDF processing:")
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
            success = convert_pdf_to_negative(file_path)
            if success:
                root.after(0, lambda it=item: tree.set(it, "Status", "Completed"))
            else:
                root.after(0, lambda it=item: tree.set(it, "Status", "Error"))
        else:
            root.after(0, lambda it=item: tree.set(it, "Status", "Error: File not found"))
    # When done, stop the progress bar and clear the processing flag
    root.after(0, lambda: progress.stop())
    processing = False
    messagebox.showinfo("Processing Complete", "All files have been processed.")

def drop(event):
    """
    When files are dropped into the window, add them to the queue table.
    Then, if not already processing, start a background thread to process the queue.
    """
    files = root.tk.splitlist(event.data)
    print(f"Received drop event with files: {files}")
    for file in files:
        cleaned_file = file.strip("{}")
        base, ext = os.path.splitext(cleaned_file)
        if ext.lower() != '.pdf':
            messagebox.showwarning("Unsupported File", f"'{cleaned_file}' is not a PDF file and will be skipped.")
            continue
        print(f"Adding file to queue: {cleaned_file}")
        # Insert a new row: first column is file path, second column is the status.
        tree.insert("", "end", values=(cleaned_file, "Queued"))
    # Update the instruction label
    label.config(text="Files queued for processing...")
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
    if os.path.exists(DESTINATION_FOLDER):
        if platform.system() == "Windows":
            os.startfile(DESTINATION_FOLDER)
        elif platform.system() == "Darwin":  # macOS
            subprocess.Popen(["open", DESTINATION_FOLDER])
        else:  # Linux and others
            subprocess.Popen(["xdg-open", DESTINATION_FOLDER])
    else:
        messagebox.showerror("Error", "Destination folder does not exist.")

def clear_queue():
    """
    Clear all items from the queue.
    """
    if messagebox.askyesno("Clear Queue", "Are you sure you want to clear the queue?"):
        for item in tree.get_children():
            tree.delete(item)
        label.config(text="DROP PDF FILES TO QUEUE FOR NEGATIVE CONVERSION")

# Create the main application window using tkinterdnd2
root = TkinterDnD.Tk()
root.title("PDF Negative Converter")
root.geometry("700x500")
root.resizable(False, False)

# Create an instruction label (and drop zone)
label = Label(root, text="DROP PDF FILES TO QUEUE FOR NEGATIVE CONVERSION",
              font=("Helvetica", 14), bg="#2E2E2E", fg="white")
label.pack(fill="x", padx=10, pady=10)

# --------------- Buttons Frame ---------------
buttons_frame = ttk.Frame(root)
buttons_frame.pack(fill="x", padx=10, pady=5)

# A button labeled "PATH" that lets you choose a new destination folder
path_button = ttk.Button(buttons_frame, text="Choose Destination", command=choose_destination)
path_button.pack(side="left")

# A button to open the destination folder
open_button = ttk.Button(buttons_frame, text="Open Destination Folder", command=open_destination_folder)
open_button.pack(side="left", padx=5)

# A button to clear the queue
clear_button = ttk.Button(buttons_frame, text="Clear Queue", command=clear_queue)
clear_button.pack(side="left", padx=5)

# A label displaying the current destination folder
path_label = ttk.Label(buttons_frame, text=DESTINATION_FOLDER, foreground="blue", cursor="hand2")
path_label.pack(side="left", padx=10)

# -----------------------------------------------------------

# Create a Treeview widget to serve as the queue container
tree = ttk.Treeview(root, columns=("File", "Status"), show="headings")
tree.heading("File", text="File")
tree.heading("Status", text="Status")
tree.column("File", width=500)
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

print("PDF Negative Converter ready. Drag and drop PDF files into the window.")
root.mainloop()
