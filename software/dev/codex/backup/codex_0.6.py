import sys  # Import sys to use sys.exit()
import json
from europi import *
from math import sin, pi
from time import sleep, ticks_ms

LONG_PRESS_DURATION = 500  # Duration in milliseconds for a long press

def load_saved_state(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (
            data.get("equation_dict", []), 
            data.get("byte_array_dict", {})
        )
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        sys.exit(1)  # Terminate if file is missing or invalid

class Codex:
    def __init__(self):
        # Load the saved state
        loaded_equations, loaded_bytes = load_saved_state("saved_state_Codex.txt")

        self.equations = loaded_equations
        self.byte_arrays = loaded_bytes

        # Screens
        self.screen = 1
        self.equation_index = 0

        # Controls and assignments
        self.controls = ["AIN", "k1", "k2"]
        self.variables = ["a", "b", "c", "z", "w"]  # from test-matrix
        self.assignments = {c: None for c in self.controls}
        self.ctrl_index = 0
        self.var_index = 0  # 0 means "None", 1..len(variables) means a variable index

        # Button states / handlers
        self.buttons = {
            'b1': {
                'pin': b1,
                'press_time': None,
                'long_press_triggered': False,
                'short_press_handler': self.on_b1_short_press,
                'long_press_handler': self.on_b1_long_press
            },
            'b2': {
                'pin': b2,
                'press_time': None,
                'long_press_triggered': False,
                'short_press_handler': self.on_b2_short_press,
                'long_press_handler': self.on_b2_long_press
            }
        }

        # Assets for assignment screen
        self.none_symbol = [12, 18, 37, 41, 18, 12]
        self.inverted_none_symbol = [243, 237, 218, 214, 237, 243]

        # Layout constants (from test-matrix)
        self.ROW_HEIGHT = 12
        self.COL_WIDTH = 18
        self.START_X = 30
        self.START_Y = 1

    # -----------------------------------------------------------------------
    # Generic Button Checker
    # -----------------------------------------------------------------------
    def check_button(self, button_id):
        button = self.buttons[button_id]
        pin = button['pin']
        press_time = button['press_time']
        long_press_triggered = button['long_press_triggered']
        short_press_handler = button['short_press_handler']
        long_press_handler = button['long_press_handler']

        if pin.value() == 1:  # Button is pressed
            if press_time is None:
                button['press_time'] = ticks_ms()
            else:
                d = ticks_ms() - press_time
                if d >= LONG_PRESS_DURATION and not long_press_triggered:
                    button['long_press_triggered'] = True
                    long_press_handler()
                    self.refresh_needed = True  # Mark screen as needing refresh
        else:  # Button is released
            if press_time is not None:
                d = ticks_ms() - press_time
                if d < LONG_PRESS_DURATION and not long_press_triggered:
                    short_press_handler()
                    self.refresh_needed = True  # Mark screen as needing refresh

                button['press_time'] = None
                button['long_press_triggered'] = False


    # -----------------------------------------------------------------------
    # Button Handlers
    # -----------------------------------------------------------------------
    def on_b1_short_press(self):
        if self.screen == 1:
            self.equation_index = (self.equation_index - 1) % len(self.equations)
        elif self.screen == 2:
            # From test-matrix: b1 cycles to the next control
            self.ctrl_index = (self.ctrl_index + 1) % len(self.controls)
            assigned_var = self.assignments[self.controls[self.ctrl_index]]
            # If assigned_var is not None, set var_index to that variable
            if assigned_var in self.variables:
                self.var_index = self.variables.index(assigned_var) + 1
            else:
                self.var_index = 0

    def on_b2_short_press(self):
        if self.screen == 1:
            self.equation_index = (self.equation_index + 1) % len(self.equations)
        elif self.screen == 2:
            # From test-matrix: b2 cycles the var_index, assigns var
            while True:
                self.var_index = (self.var_index + 1) % (len(self.variables) + 1)
                new_assignment = None if self.var_index == 0 else self.variables[self.var_index - 1]
                # Prevent assignment conflicts between k1 and k2
                ctrl = self.controls[self.ctrl_index]
                if ctrl == "k1" and self.assignments["k2"] == new_assignment and new_assignment:
                    continue
                if ctrl == "k2" and self.assignments["k1"] == new_assignment and new_assignment:
                    continue
                break
            self.assignments[ctrl] = new_assignment

    def on_b1_long_press(self):
        self.screen -= 1
        if self.screen < 1:
            self.screen = 3
        self.saveSettings()

    def on_b2_long_press(self):
        self.screen += 1
        if self.screen > 3:
            self.screen = 1
        self.saveSettings()

    # -----------------------------------------------------------------------
    # Logic for Equations
    # -----------------------------------------------------------------------

    def saveSettings(self):
        # Save any changes if desired
        pass

    # -----------------------------------------------------------------------
    # Visual Helpers for the Assignment Screen
    # -----------------------------------------------------------------------
    def draw_none_symbol(self, x, y, highlight=False):
        s = self.inverted_none_symbol if highlight else self.none_symbol
        for row, row_data in enumerate(s):
            for col in range(6):
                bit = (row_data >> (5 - col)) & 1
                oled.pixel(x + col, y + row, bit)

    def draw_inverted_text(self, text, x, y, box_width=None, box_height=10):
        if box_width is None:
            box_width = len(text) * 6
        oled.fill_rect(x - 2, y - 2, box_width, box_height, 1)
        oled.text(text, x, y, 0)

    # -----------------------------------------------------------------------
    # state 1 // homescreen
    # -----------------------------------------------------------------------
    def display_home_screen(self):
        oled.fill(0)
        eq_data = self.equations[self.equation_index]
        eq_title = eq_data["title"][:12]  
        eq_equation = eq_data["equation"]
        eq_tokens = eq_data["byte"]  

        tx = (128 - len(eq_title)*8)//2
        oled.text(eq_title, tx, 0, 1)

        if len(eq_equation) > 16:
            row1 = eq_equation[:16]
            row2 = eq_equation[16:]
            row1_x = (128 - len(row1)*8)//2
            row2_x = (128 - len(row2)*8)//2
            self.draw_equation_line(oled, row1, row1_x, 12, eq_tokens)
            self.draw_equation_line(oled, row2, row2_x, 24, eq_tokens)
        else:
            eq_x = (128 - len(eq_equation)*8)//2
            self.draw_equation_line(oled, eq_equation, eq_x, 12, eq_tokens)

        if ain.read_voltage() > 0.1:
            oled.fill_rect(0, 0, 4, 4, 1)

        oled.show()


        
    def draw_glyph(self, oled, glyph_info, x, y):
        height = glyph_info["size"]
        row_data_list = glyph_info["data"]

        for row in range(height):
            row_data = row_data_list[row]
            for col in range(8):
                bit = (row_data >> (7 - col)) & 1
                if bit == 1:
                    oled.pixel(x + col, y + row, 1)

        return x + 8


    def draw_token(self, oled, token, x, y):
        glyph_info = self.byte_arrays.get(token)

        if not glyph_info:
            return x

        x_new = self.draw_glyph(oled, glyph_info, x, y)
        return x_new


    def draw_equation_line(self, oled, text, x, y, tokens):
        pos_x = x
        i = 0
        while i < len(text):
            matched = False
            for t in tokens:
                if text.startswith(t, i):
                    pos_x = self.draw_token(oled, t, pos_x, y)
                    i += len(t)
                    matched = True
                    break

            if not matched:
                oled.text(text[i], pos_x, y, 1)
                pos_x += 8
                i += 1
            
    # -----------------------------------------------------------------------
    # state 2 // assignement matrix
    # -----------------------------------------------------------------------

    def display_assignment_screen(self):
        oled.fill(0)
        for i, control in enumerate(self.controls):
            y = self.START_Y + i * self.ROW_HEIGHT

            if i == self.ctrl_index:
                self.draw_inverted_text(control, 2, y, box_width=self.COL_WIDTH + 10)
            else:
                oled.text(control, 2, y, 1)

            assigned_var = self.assignments[control]
            none_highlight = (assigned_var is None) or (
                i == self.ctrl_index and self.var_index == 0
            )
            self.draw_none_symbol(self.START_X + 5, y + 2, highlight=none_highlight)

            for j, var in enumerate(self.variables):
                x = self.START_X + (j + 1) * self.COL_WIDTH
                if i == self.ctrl_index and (self.var_index == j + 1):
                    self.draw_inverted_text(var, x, y, box_width=self.COL_WIDTH - 2, box_height=self.ROW_HEIGHT - 2)
                elif assigned_var == var:
                    oled.fill_rect(x - 2, y - 2, self.COL_WIDTH - 2, self.ROW_HEIGHT - 2, 1)
                    oled.text(var, x, y, 0)
                else:
                    oled.text(var, x, y, 1)

        oled.show()
        
    # -----------------------------------------------------------------------
    # state 3 // wave engine
    # -----------------------------------------------------------------------

    def display_waveform_screen(self):
        oled.fill(0)
        r = k1.percent() * 4
        x = k2.percent()
        data = []
        for i in range(128):
            x = r * x * (1 - x)
            data.append(x)
        for i, val in enumerate(data):
            y = int(val * 16)
            oled.pixel(i, 24 - y, 1)
        oled.show()

    # -----------------------------------------------------------------------
    # Main Loop
    # -----------------------------------------------------------------------
    def main(self):
        self.refresh_needed = True

        while True:
            for button_id in self.buttons:
                self.check_button(button_id)

            if self.refresh_needed:
                if self.screen == 1:
                    self.display_home_screen()
                elif self.screen == 2:
                    self.display_assignment_screen()
                elif self.screen == 3:
                    self.display_waveform_screen()

                self.refresh_needed = False 

            sleep(0.1)

if __name__ == "__main__":
    Codex().main()
