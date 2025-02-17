from europi import *
from math import sin, pi
from time import sleep, ticks_ms

LONG_PRESS_DURATION = 500

equation_dict = [
    {
        "id": 1,
        "title": "SineOsc",
        "equation": "x(t)=Asin(2πft)",
        "vars": ["a", "b", "c"],
        "settings": {},
        "byte": ["sin"]
    },
    {
        "id": 2,
        "title": "Logistic",
        "equation": "x(n+1) = r*x(n)*(1-x(n))",
        "vars": ["r", "x"],
        "settings": {},
        "byte": []
    },
    {
        "id": 3,
        "title": "GoldenOsc",
        "equation": "x = a * cos(2 * π * φ * t)",
        "vars": ["a", "φ", "t"],
        "settings": {"φ": "1.61803", "t": "time var"},
        "byte": ["cos", "π", "φ"]
    },
    {
        "id": 4,
        "title": "QuantumInt",
        "equation": "x = (a*sin(ωt)+b*cos(ωt))^2",
        "vars": ["a", "b", "ω"],
        "settings": {},
        "byte": ["sin", "cos", "ω"]
    }
]

byte_array_dict = {
    "sin": [
        60, 126, 96, 120, 12, 102, 60, 0,  # 's'
        24, 60, 24, 24, 24, 24, 60, 0,     # 'i'
        60, 102, 6, 12, 24, 126, 0, 0      # 'n'
    ],
    "cos": [
        60, 102, 96, 96, 96, 60, 0, 0,
        60, 96, 96, 96, 96, 60, 0, 0,
        60, 102, 6, 12, 24, 126, 0, 0
    ],
    "π": [254, 254, 24, 24, 24, 24, 24, 24],
    "φ": [126, 66, 66, 126, 18, 18, 30, 0],
    "ω": [62, 34, 62, 42, 34, 42, 62, 0],
    "·": [0, 0, 0, 24, 24, 0, 0, 0]
}

class Codex:
    def __init__(self):
        self.screen = 1
        self.b1_press_time = None
        self.b1_long_press_triggered = False
        self.b2_press_time = None
        self.b2_long_press_triggered = False

        self.equations = equation_dict
        self.equation_index = 0

        self.controls = ["AIN", "k1", "k2"]
        self.assignments = {control: None for control in self.controls}

        self.ctrl_index = 0  
        self.var_index = 0  

    # -----------------------------------------------------------------------
    # utilities
    # -----------------------------------------------------------------------

    def check_b1(self):
        if b1.value() == 1:
            if self.b1_press_time is None:
                self.b1_press_time = ticks_ms()
            else:
                d = ticks_ms() - self.b1_press_time
                if d >= LONG_PRESS_DURATION and not self.b1_long_press_triggered:
                    self.b1_long_press_triggered = True
                    self.on_b1_long_press()
        else:
            if self.b1_press_time is not None:
                d = ticks_ms() - self.b1_press_time
                if d < LONG_PRESS_DURATION and not self.b1_long_press_triggered:
                    self.on_b1_short_press()
                self.b1_press_time = None
                self.b1_long_press_triggered = False

    def check_b2(self):
        if b2.value() == 1:
            if self.b2_press_time is None:
                self.b2_press_time = ticks_ms()
            else:
                d = ticks_ms() - self.b2_press_time
                if d >= LONG_PRESS_DURATION and not self.b2_long_press_triggered:
                    self.b2_long_press_triggered = True
                    self.on_b2_long_press()
        else:
            if self.b2_press_time is not None:
                d = ticks_ms() - self.b2_press_time
                if d < LONG_PRESS_DURATION and not self.b2_long_press_triggered:
                    self.on_b2_short_press()
                self.b2_press_time = None
                self.b2_long_press_triggered = False

    def on_b1_short_press(self):
        if self.screen == 1:
            self.equation_index = (self.equation_index - 1) % len(self.equations)
        elif self.screen == 2:
            self.ctrl_index = (self.ctrl_index + 1) % len(self.controls)

    def on_b2_short_press(self):
        if self.screen == 1:
            self.equation_index = (self.equation_index + 1) % len(self.equations)
        elif self.screen == 2:
            self.assign_variable()

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
    # logic
    # -----------------------------------------------------------------------

    def assign_variable(self):
        ctrl = self.controls[self.ctrl_index]
        var_name = self.current_vars[self.var_index]
        
        if ctrl in ["k1", "k2"]:
            for c, v in self.assignments.items():
                if c in ["k1", "k2"] and v == var_name:
                    return
        
        old_var = self.assignments[ctrl]
        if old_var:
            for c, v in self.assignments.items():
                if v == old_var:
                    self.assignments[c] = None
                    break
        
        self.assignments[ctrl] = var_name
        self.var_index = (self.var_index + 1) % len(self.current_vars)


    @property
    def current_vars(self):
        return self.equations[self.equation_index]["vars"]

    def saveSettings(self):
        pass
    
    # -----------------------------------------------------------------------
    # visual helpers 
    # -----------------------------------------------------------------------

    def draw_8x8(self, oled, sprite_bytes, x, y):
        for row in range(8):
            row_data = sprite_bytes[row]
            for col in range(8):
                bit = (row_data >> (7 - col)) & 1
                if bit == 1:
                    oled.pixel(x + col, y + row, 1)

    def draw_token(self, oled, token, x, y):
        sprite = byte_array_dict[token]
        chars = len(sprite) // 8
        cx = x
        for c in range(chars):
            chunk = sprite[c*8 : (c+1)*8]
            self.draw_8x8(oled, chunk, cx, y)
            cx += 8
        return cx

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
    # state engine / screen rendering 
    # -----------------------------------------------------------------------
    
    def display_home_screen(self):
        oled.fill(0)
        eq_data = self.equations[self.equation_index]
        eq_title = eq_data["title"][:12]
        eq_equation = eq_data["equation"]
        eq_tokens = eq_data["byte"]

        # Title
        tx = (128 - len(eq_title)*8)//2
        oled.text(eq_title, tx, 0, 1)

        # Equation
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

        # AIN Dot
        if ain.read_voltage() > 0.1:
            oled.fill_rect(0, 0, 4, 4, 1)

        oled.show()

    def display_assignment_screen(self):
        oled.fill(0)
        row_height = 10
        col_width = 24
        byte_width = 8
        start_x = 32
        start_y = 0

        extra_byte = [12, 18, 37, 41, 18, 12]

        for i, c in enumerate(self.controls):
            y = start_y + i * row_height
            oled.text(f"{c}", 0, y, 1)

            for row in range(6):
                row_data = extra_byte[row]
                for col in range(8):
                    bit = (row_data >> (7 - col)) & 1
                    if bit == 1:
                        oled.pixel(24 + col, y + row, 1)

            selected_var = self.assignments[c]
            for j, var in enumerate(self.current_vars):
                x = start_x + byte_width + j * col_width
                is_selected = (var == selected_var)
                if is_selected:
                    oled.fill_rect(x - 1, y - 1, col_width, row_height, 1)
                    oled.text(var, x, y, 0)
                else:
                    oled.text(var, x, y, 1)
        
        footer_y = start_y + len(self.controls) * row_height + 2
        oled.show()

    def display_waveform_screen(self):
        oled.fill(0)
        r = k1.percent() * 4
        x = k2.percent()
        data = []
        for i in range(128):
            x = r*x*(1 - x)
            data.append(x)
        for i, val in enumerate(data):
            y = int(val * 16)
            oled.pixel(i, 24 - y, 1)
        oled.show()
        
    # -----------------------------------------------------------------------
    # main
    # ----------------------------------------------------------------------- 

    def main(self):
        while True:
            self.check_b1()
            self.check_b2()

            if self.screen == 1:
                self.display_home_screen()
            elif self.screen == 2:
                self.display_assignment_screen()
            elif self.screen == 3:
                self.display_waveform_screen()

            sleep(0.1)

if __name__ == "__main__":
    Codex().main()

