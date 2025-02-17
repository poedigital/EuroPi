import sys
import json
from europi import *
from math import sin, pi, floor
from time import sleep, sleep_ms, ticks_ms

LONG_PRESS_DURATION = 500

def load_saved_state(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (data.get("equation_dict", []), data.get("byte_array_dict", {}), data.get("global_settings", {}))
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        sys.exit(1)
        
class Codex:
    def __init__(self):
        eq_list, byte_map, global_set = load_saved_state("saved_state_Codex.txt")
        self.equations, self.byte_arrays, self.global_settings = eq_list, byte_map, global_set
        self.screen = self.global_settings.get("last_screen", 1)
        self.equation_index = 0
        self.controls = ["AIN", "k1", "k2"]
        self.assignments = {c: None for c in self.controls}
        self.ctrl_index, self.var_index = 0, 0
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
        self.none_symbol = [12, 18, 37, 41, 18, 12]
        self.inverted_none_symbol = [243, 237, 218, 214, 237, 243]
        self.ROW_HEIGHT, self.COL_WIDTH, self.START_X, self.START_Y = 12, 18, 30, 1
        self.refresh_needed = True

    # -----------------------------------------------------------------------
    # Button Checking
    # -----------------------------------------------------------------------
    def check_button(self, button_id):
        button = self.buttons[button_id]
        pin = button['pin']
        press_time = button['press_time']
        long_press_triggered = button['long_press_triggered']
        short_press_handler = button['short_press_handler']
        long_press_handler = button['long_press_handler']
        if pin.value() == 1:
            if press_time is None:
                button['press_time'] = ticks_ms()
            elif (d := ticks_ms() - press_time) >= LONG_PRESS_DURATION and not long_press_triggered:
                button['long_press_triggered'] = True
                long_press_handler()
                self.refresh_needed = True
        elif press_time is not None:
            if (d := ticks_ms() - press_time) < LONG_PRESS_DURATION and not long_press_triggered:
                short_press_handler()
                self.refresh_needed = True
            button['press_time'] = None
            button['long_press_triggered'] = False

    # -----------------------------------------------------------------------
    # Button Handlers
    # -----------------------------------------------------------------------
    def on_b1_short_press(self):
        if self.screen == 1:
            self.equation_index = (self.equation_index - 1) % len(self.equations)
        elif self.screen == 2:
            self.ctrl_index = (self.ctrl_index + 1) % len(self.controls)
            eq_vars = self.equations[self.equation_index].get("vars", [])
            ctrl = self.controls[self.ctrl_index]
            assigned_var = self.assignments[ctrl]
            self.var_index = eq_vars.index(assigned_var) + 1 if assigned_var in eq_vars else 0

    def on_b2_short_press(self):
        if self.screen == 1:
            self.equation_index = (self.equation_index + 1) % len(self.equations)
        elif self.screen == 2:
            eq_data = self.equations[self.equation_index]
            eq_vars = eq_data.get("vars", [])
            eq_assignments = eq_data.setdefault("settings", {}).setdefault("assignments", {})
            total_slots = len(eq_vars) + 1
            ctrl = self.controls[self.ctrl_index]
            other_ctrl = "k2" if ctrl == "k1" else "k1"
            attempts = 0
            while attempts < total_slots:
                self.var_index = (self.var_index + 1) % total_slots
                new_var = eq_vars[self.var_index - 1] if self.var_index else None
                conflict = ctrl in ["k1", "k2"] and new_var and eq_assignments.get(other_ctrl) == new_var
                if conflict:
                    attempts += 1
                    continue
                break
            self.assignments[ctrl] = new_var
            eq_assignments[ctrl] = new_var
            self.saveSettings()

    def on_b1_long_press(self):
        self.screen = self.screen - 1 if self.screen > 1 else 3
        self.saveSettings()
        
    def on_b2_long_press(self):
        self.screen = self.screen + 1 if self.screen < 3 else 1
        self.saveSettings()

    # -----------------------------------------------------------------------
    # Visual / Equation Helpers
    # -----------------------------------------------------------------------
    def saveSettings(self):
        try:
            with open("saved_state_Codex.txt", "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("global_settings", {})["last_screen"] = self.screen
            eq_list = data.get("equation_dict", [])
            if 0 <= self.equation_index < len(eq_list):
                eq_data = eq_list[self.equation_index]
                eq_assignments = eq_data.setdefault("settings", {}).setdefault("assignments", {})
                eq_assignments.update({ctrl: self.assignments[ctrl] for ctrl in self.controls})
            with open("saved_state_Codex.txt", "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            print("[ERROR] Failed to save settings:", e)

    def draw_none_symbol(self, x, y, highlight=False):
        s = self.inverted_none_symbol if highlight else self.none_symbol
        for row, row_data in enumerate(s):
            for col in range(6):
                oled.pixel(x + col, y + row, (row_data >> (5 - col)) & 1)

    def draw_inverted_text(self, text, x, y, box_width=None, box_height=10):
        box_width = len(text) * 6 if box_width is None else box_width
        oled.fill_rect(x - 2, y - 2, box_width, box_height, 1)
        oled.text(text, x, y, 0)

    def draw_glyph(self, oled, glyph_info, x, y):
        for row, row_data in enumerate(glyph_info["data"][:glyph_info["size"]]):
            for col in range(8):
                if (row_data >> (7 - col)) & 1:
                    oled.pixel(x + col, y + row, 1)
        return x + 8

    def draw_token(self, oled, token, x, y):
        glyph_info = self.byte_arrays.get(token)
        return self.draw_glyph(oled, glyph_info, x, y) if glyph_info else x

    def draw_equation_line(self, oled, text, x, y, tokens):
        pos_x, i = x, 0
        while i < len(text):
            for t in tokens:
                if text.startswith(t, i):
                    pos_x = self.draw_token(oled, t, pos_x, y)
                    i += len(t)
                    break
            else:
                oled.text(text[i], pos_x, y, 1)
                pos_x += 8
                i += 1

    # -----------------------------------------------------------------------
    # State 1 // Home Screen
    # -----------------------------------------------------------------------
    def display_home_screen(self):
        oled.fill(0)
        eq_data = self.equations[self.equation_index]
        eq_title = eq_data["title"][:12]
        eq_equation = eq_data["equation"]
        eq_tokens = eq_data["byte"]
        tx = (128 - len(eq_title) * 8) // 2
        oled.text(eq_title, tx, 0, 1)
        if len(eq_equation) > 16:
            for idx, row in enumerate([eq_equation[:16], eq_equation[16:]]):
                x = (128 - len(row) * 8) // 2
                self.draw_equation_line(oled, row, x, 12 + idx * 12, eq_tokens)
        else:
            eq_x = (128 - len(eq_equation) * 8) // 2
            self.draw_equation_line(oled, eq_equation, eq_x, 12, eq_tokens)
        if ain.read_voltage() > 0.1:
            oled.fill_rect(0, 0, 4, 4, 1)
        oled.show()

    # -----------------------------------------------------------------------
    # State 2 // Assignment Matrix
    # -----------------------------------------------------------------------
    def display_assignment_screen(self):
        oled.fill(0)
        eq_data = self.equations[self.equation_index]
        eq_vars = eq_data.get("vars", [])
        eq_assignments = eq_data.get("settings", {}).get("assignments", {})
        self.assignments.update({c: eq_assignments[c] for c in self.controls if c in eq_assignments})

        for i, control in enumerate(self.controls):
            y = self.START_Y + i * self.ROW_HEIGHT
            if i == self.ctrl_index:
                self.draw_inverted_text(control, 2, y, box_width=self.COL_WIDTH + 10)
            else:
                oled.text(control, 2, y, 1)
            assigned_var = self.assignments[control]
            self.draw_none_symbol(self.START_X + 5, y + 2, highlight=(assigned_var is None or (i == self.ctrl_index and self.var_index == 0)))

            for j, var in enumerate(eq_vars):
                x = self.START_X + (j + 1) * self.COL_WIDTH
                if i == self.ctrl_index and self.var_index == j + 1:
                    self.draw_inverted_text(var, x, y, box_width=self.COL_WIDTH - 2, box_height=self.ROW_HEIGHT - 2)
                elif assigned_var == var:
                    oled.fill_rect(x - 2, y - 2, self.COL_WIDTH - 2, self.ROW_HEIGHT - 2, 1)
                    oled.text(var, x, y, 0)
                else:
                    oled.text(var, x, y, 1)
        oled.show()

    # -----------------------------------------------------------------------
    # State 3 // Wave Engine
    # -----------------------------------------------------------------------
    def wave_engine_loop(self):
        while self.screen == 3:
            # Check buttons each iteration so user can exit state 3
            for button_id in self.buttons:
                self.check_button(button_id)

            # Example: logistic map
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

            # Example small delay
            sleep(0.05)

    # -----------------------------------------------------------------------
    # Main Loop
    # -----------------------------------------------------------------------
    def main(self):
        self.refresh_needed = True
        while True:
            if self.screen == 3:
                self.wave_engine_loop()
                self.refresh_needed = True
                continue
            for button_id in self.buttons:
                self.check_button(button_id)
            if self.refresh_needed:
                {1: self.display_home_screen, 2: self.display_assignment_screen}.get(self.screen, lambda: None)()
                self.refresh_needed = False

if __name__ == "__main__":
    Codex().main()
