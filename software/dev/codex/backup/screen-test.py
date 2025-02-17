from luma.core.render import canvas
from luma.core.legacy import text
from luma.emulator.device import pygame

# OLED Display Constants
WIDTH, HEIGHT = 128, 32
MARGIN = 4  # Top and bottom margin
CHAR_WIDTH = 8  # Character width in pixels
CHAR_HEIGHT = 8  # Character height in pixels
MAX_CHARS_PER_LINE = 16  # Max characters per row

# Virtual OLED Display
device = pygame(width=WIDTH, height=HEIGHT)

# Hardcoded Equation Example
TITLE = "Sine Osc"
EQUATION = "================"

def draw_equation_line(draw, text_string, y):
    """Draws a centered equation line."""
    text_width = len(text_string) * CHAR_WIDTH
    x = (WIDTH - text_width) // 2  # Center align
    text(draw, (x, y), text_string, fill="white")

def render_screen():
    """Renders the OLED display with the hardcoded equation."""
    with canvas(device) as draw:
        # Row 1: Title (Centered)
        title_x = (WIDTH - len(TITLE) * CHAR_WIDTH) // 2
        text(draw, (title_x, MARGIN), TITLE, fill="white")

        # Row 2 & Row 3: Equation Wrapping
        if len(EQUATION) > MAX_CHARS_PER_LINE:
            row1, row2 = EQUATION[:MAX_CHARS_PER_LINE], EQUATION[MAX_CHARS_PER_LINE:]
            draw_equation_line(draw, row1, MARGIN + CHAR_HEIGHT)  # Row 2
            draw_equation_line(draw, row2, MARGIN + 2 * CHAR_HEIGHT)  # Row 3
        else:
            draw_equation_line(draw, EQUATION, MARGIN + CHAR_HEIGHT)  # Single-line equation (Row 2)

    input("Press Enter to exit...")

if __name__ == "__main__":
    render_screen()  # Renders once and holds