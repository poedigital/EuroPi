import json
import os
from PIL import Image, ImageDraw, ImageFont

# Constants for the emulator dimensions
emulator_width, emulator_height = 128, 32
margin_top = 2  # Top margin
char_width = 6  # Width of each character
char_height = 8  # Height of each character
max_chars_per_line = 16  # Maximum characters per line
row_height = char_height  # Height of each row
font = ImageFont.load_default()  # Default monospaced pixel font
CODEX_FILE = "codex.txt"  # Path to the codex file
SUPPORTED_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789=+*-/()[]{}^%.,<> ")
USER_DOCS = os.path.join(os.path.expanduser("~"), "Documents", "mbcorp")
CONFIG_FILE = os.path.join(USER_DOCS, "byte-forge-config.json")

def load_config():
    """loads configuration file to retrieve codex path"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {"codex_path": "codex.txt"}  # default fallback

# retrieve codex path from config
config = load_config()
CODEX_FILE = config.get("codex_path", "codex.txt")

def load_codex():
    """
    Load the contents of the codex file.
    Returns the byte_array_dict from the file.
    """
    if not os.path.exists(CODEX_FILE):
        print(f"[WARNING] Codex file does not exist: {CODEX_FILE}")
        return {}
    try:
        with open(CODEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("byte_array_dict", {})
    except Exception as e:
        print(f"[ERROR] Failed to load codex: {e}")
        return {}
    
def _draw_byte_map(draw, x, y, byte_map):
    """
    Renders a byte map at a specific position on the canvas.
    Adjusts positioning for proper centering relative to text.
    """
    size = byte_map.get("size", 8)
    data = byte_map.get("data", [])

    # Center the byte map within the character height and adjust for the baseline
    byte_map_y = y + (char_height - size) // 2 + 2  # Adjust by +2 for baseline alignment
    for row, byte in enumerate(data):
        for col in range(size):
            pixel = (byte >> (size - 1 - col)) & 1
            if pixel:
                draw.point((x + col, byte_map_y + row), fill="white")

def _process_equation(draw, equation, y, byte_array_dict):
    """
    Process and render the equation line by centering it and replacing special tokens.
    """
    tokens = equation.split()

    # Calculate the total width
    line_width = 0
    for token in tokens:
        if token in byte_array_dict:
            line_width += byte_array_dict[token]["size"] + char_width  # Byte map size + space
        else:
            line_width += len(token) * char_width + char_width  # Text width + space

    # Calculate starting x position for centering
    x = max(0, (emulator_width - line_width) // 2)

    # Render each token
    for token in tokens:
        if token in byte_array_dict:  # Render byte map
            byte_map = byte_array_dict[token]
            byte_map_size = byte_map["size"]
            byte_map_y = y + (char_height - byte_map_size) // 2 + 2  # Adjust by +2 for baseline alignment
            _draw_byte_map(draw, x, byte_map_y, byte_map)
            x += byte_map_size + char_width  # Move cursor by byte map size + space
        else:  # Render text
            draw.text((x, y), token, fill="white", font=font)
            x += len(token) * char_width + char_width  # Move cursor by text width + space

def _draw_centered_line(draw, text_string, y, width=emulator_width):
    """
    Helper to draw a single line of text, centered horizontally based on actual pixel width.
    """
    text_width = draw.textlength(text_string, font=font)
    x = max(0, (width - text_width) // 2)  # Ensure it doesn't go negative
    draw.text((x, y), text_string, fill="white", font=font)

def draw_equation(title, equation):
    """
    Render `title` and `equation` to a virtual OLED image.
    Special characters are replaced with corresponding byte maps if found in the codex.
    Unsupported characters are replaced with `!`.
    """
    # Load the byte_array_dict from codex.txt
    byte_array_dict = load_codex()

    # Create a blank image for the OLED
    img = Image.new("1", (emulator_width, emulator_height), "black")
    draw = ImageDraw.Draw(img)

    # Draw the title on Row 1
    _draw_centered_line(draw, title[:max_chars_per_line], margin_top)

    # Calculate y-coordinates for the equation rows
    row_2_y = margin_top + row_height  # Row 2 starts after Row 1
    row_3_y = row_2_y + row_height  # Row 3 starts after Row 2

    # Wrap and render the equation across up to two lines
    if len(equation) > max_chars_per_line:
        row1 = equation[:max_chars_per_line]
        row2 = equation[max_chars_per_line:max_chars_per_line * 2]
        _process_equation(draw, row1, row_2_y, byte_array_dict)  # Row 2
        _process_equation(draw, row2, row_3_y, byte_array_dict)  # Row 3
    else:
        _process_equation(draw, equation, row_2_y, byte_array_dict)  # Single-line equation (Row 2)

    # Clip the image to ensure no unintended padding
    img = img.crop((0, 0, emulator_width, emulator_height))
    return img