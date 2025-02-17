from europi import *
from math import sin, pi
from time import sleep, ticks_ms

class Codex:
    def __init__(self):
        self.equation_template = "x = a * sin(b)"
        self.a_value = 0.50
        self.b_value = 0.50
        self.x_value = 0.00

        # Variable assignments
        self.assignments = {"k1": "a", "k2": "b", "AIN": None}
        self.controls = list(self.assignments.keys())  # k1, k2, AIN
        self.variables = ["a", "b"]  # Variables available for assignment

        # State tracking
        self.in_assignment_mode = False
        self.current_control_index = 0
        self.current_variable_index = 0
        self.b1_press_time = None  # Track time for long press
        self.b2_last_state = 0
        self.long_press_duration = 500  # Long press threshold in milliseconds

        self.display_equation()

    def display_equation(self):
        oled.fill(0)
        equation_text = self.equation_template
        equation_length = len(equation_text) * 8
        center_x = (128 - equation_length) // 2
        center_y = 10
        oled.text(equation_text, center_x, center_y, 1)

        char_width = 8
        for control, variable in self.assignments.items():
            if variable:
                var_index = self.variables.index(variable)
                var_pos = 4 + var_index * 8
                oled.text(f"^{control}", center_x + var_pos * char_width, center_y + 12, 1)

        ain_scaled = ain.read_voltage() / 10.0
        if ain_scaled > 0.01:
            oled.fill_rect(0, 0, 4, 4, 1)
        oled.fill_rect(6, 0, int(12 * ain_scaled), 2, 1)
        oled.show()

    def display_assignment_menu(self):
        oled.fill(0)
        for i, control in enumerate(self.controls):
            line_y = 10 + i * 10
            assign_text = f"{control}: {self.assignments[control] or 'None'}"
            if i == self.current_control_index:
                oled.fill_rect(0, line_y - 2, 128, 10, 1)
                oled.text(assign_text, 4, line_y, 0)
            else:
                oled.text(assign_text, 4, line_y, 1)

        oled.text("b1: cycle", 4, 30, 1)
        oled.text("b2: assign", 64, 30, 1)
        oled.show()

    def handle_assignment(self):
        if self.b1_press_time is None:  # Track when the button is first pressed
            if b1.value() == 1:
                self.b1_press_time = ticks_ms()
        else:
            if b1.value() == 0:  # Button released
                press_duration = ticks_ms() - self.b1_press_time
                self.b1_press_time = None
                if press_duration >= self.long_press_duration:
                    self.in_assignment_mode = False
                    self.display_equation()
                else:  # Short press
                    self.current_control_index = (self.current_control_index + 1) % len(self.controls)

        if b2.value() == 1 and self.b2_last_state == 0:
            current_control = self.controls[self.current_control_index]
            new_var = self.variables[self.current_variable_index]
            current_var = self.assignments[current_control]

            if current_var:
                for ctrl, var in self.assignments.items():
                    if var == new_var:
                        self.assignments[ctrl] = current_var
                        break

            self.assignments[current_control] = new_var
            self.current_variable_index = (self.current_variable_index + 1) % len(self.variables)

        self.b2_last_state = b2.value()

    def toggle_assignment_mode(self):
        if self.b1_press_time is None:  # Start tracking button press time
            if b1.value() == 1:
                self.b1_press_time = ticks_ms()
        else:
            if b1.value() == 0:  # Button released
                press_duration = ticks_ms() - self.b1_press_time
                self.b1_press_time = None
                if press_duration >= self.long_press_duration:
                    self.in_assignment_mode = not self.in_assignment_mode
                    if not self.in_assignment_mode:
                        self.display_equation()
                    else:
                        self.display_assignment_menu()

    def main(self):
        while True:
            if self.in_assignment_mode:
                self.display_assignment_menu()
                self.handle_assignment()
            else:
                self.toggle_assignment_mode()
                self.display_equation()
            sleep(0.1)

if __name__ == "__main__":
    Codex().main()
