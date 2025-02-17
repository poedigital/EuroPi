from europi import *
from math import sin, pi
from time import sleep, ticks_ms

LONG_PRESS_DURATION = 500

class Codex:
    def __init__(self):
        self.screen = 1
        self.b1_press_time = None
        self.b1_long_press_triggered = False
        self.b2_press_time = None
        self.b2_long_press_triggered = False
        self.equations = ["x = a * sin(b)", "x(n+1) = r*x*(1-x)", "Lorenz"]
        self.equation_index = 0
        self.assignments = {"AIN": "a", "k1": "b", "k2": None}
        self.controls = ["AIN", "k1", "k2"]
        self.variables = ["a", "b", "r", "x", "y"]
        self.ctrl_index = 0
        self.var_index = 0

    #----------------------------------------------------------------------
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

    #----------------------------------------------------------------------
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

    #----------------------------------------------------------------------
    def on_b1_short_press(self):
        if self.screen == 1:
            self.equation_index = (self.equation_index - 1) % len(self.equations)
        elif self.screen == 2:
            self.ctrl_index = (self.ctrl_index + 1) % len(self.controls)

    #----------------------------------------------------------------------
    def on_b2_short_press(self):
        if self.screen == 1:
            self.equation_index = (self.equation_index + 1) % len(self.equations)
        elif self.screen == 2:
            self.assign_variable()

    #----------------------------------------------------------------------
    def on_b1_long_press(self):
        self.screen -= 1
        if self.screen < 1:
            self.screen = 3
        self.saveSettings()

    #----------------------------------------------------------------------
    def on_b2_long_press(self):
        self.screen += 1
        if self.screen > 3:
            self.screen = 1
        self.saveSettings()

    #----------------------------------------------------------------------
    def assign_variable(self):
        c = self.controls[self.ctrl_index]
        v = self.variables[self.var_index]
        oldv = self.assignments[c]
        if oldv:
            for cc, vv in self.assignments.items():
                if vv == v:
                    self.assignments[cc] = oldv
                    break
        self.assignments[c] = v
        self.var_index = (self.var_index + 1) % len(self.variables)

    #----------------------------------------------------------------------
    def saveSettings(self):
        pass

    #----------------------------------------------------------------------
    def display_home_screen(self):
        oled.fill(0)
        eq_name = self.equations[self.equation_index]
        x_pos = (128 - len(eq_name)*8)//2
        oled.text(eq_name, x_pos, 10, 1)
        if ain.read_voltage() > 0.1:
            oled.fill_rect(0, 0, 4, 4, 1)
        oled.show()

    #----------------------------------------------------------------------
    def display_assignment_screen(self):
        oled.fill(0)
        for i, c in enumerate(self.controls):
            y = i*10
            t = f"{c}: {self.assignments[c] or 'None'}"
            if i == self.ctrl_index:
                oled.fill_rect(0, y, 128, 10, 1)
                oled.text(t, 4, y+2, 0)
            else:
                oled.text(t, 4, y+2, 1)
        y2 = len(self.controls)*10 + 2
        oled.text("b1 cycle", 4, y2, 1)
        oled.text("b2 var", 64, y2, 1)
        oled.show()

    #----------------------------------------------------------------------
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
