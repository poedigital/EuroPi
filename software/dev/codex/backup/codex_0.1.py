from europi import *
from math import sin, pi
from time import sleep

class Codex:
    def __init__(self):
        self.equation_template = "x = a * sin(b)"
        self.a_value = 0.50
        self.b_value = 0.50
        self.x_value = 0.00
        self.current_variable_index = 0
        self.b1_last_state = 0

        # Define variables with their metadata (sin is included)
        self.variables = [
            {"name": "a", "start": 4, "length": 1},
            {"name": "sin", "start": 8, "length": 3},
            {"name": "b", "start": 12, "length": 1},
        ]

        self.display_equation()

    def display_equation(self):
        oled.fill(0)
        equation_text = self.equation_template
        equation_length = len(equation_text) * 8
        center_x = (128 - equation_length) // 2
        center_y = 10
        oled.text(equation_text, center_x, center_y, 1)

        char_width = 8
        current_var = self.variables[self.current_variable_index]
        start_x = center_x + current_var["start"] * char_width
        highlight_width = current_var["length"] * char_width
        oled.fill_rect(start_x, center_y - 2, highlight_width, 10, 1)
        oled.text(equation_text[current_var["start"]:current_var["start"] + current_var["length"]], start_x, center_y, 0)

        oled.text("^k1", center_x + (self.variables[0]["start"] * char_width), center_y + 12, 1)
        oled.text("^k2", center_x + (self.variables[2]["start"] * char_width), center_y + 12, 1)

        ain_scaled = ain.read_voltage() / 10.0
        if ain_scaled > 0.01:
            oled.fill_rect(0, 0, 4, 4, 1)
        oled.fill_rect(6, 0, int(12 * ain_scaled), 2, 1)
        oled.show()

    def calculate_x(self):
        self.x_value = self.a_value * sin(self.b_value * pi)
        # Scale x_value to 0–10V range for cv1 output
        scaled_x = max(0.0, min(10.0, self.x_value * 10))
        cv1.voltage(scaled_x)

    def toggle_variable(self):
        self.current_variable_index = (self.current_variable_index + 1) % len(self.variables)

    def handle_button(self):
        current_state = b1.value()
        if current_state == 1 and self.b1_last_state == 0:
            self.toggle_variable()
        self.b1_last_state = current_state

    def main(self):
        while True:
            current_var = self.variables[self.current_variable_index]["name"]
            if current_var == "a":
                self.a_value = k1.percent()
            elif current_var == "b":
                self.b_value = k2.percent()

            self.handle_button()
            self.calculate_x()
            self.display_equation()
            sleep(0.1)

if __name__ == "__main__":
    Codex().main()
