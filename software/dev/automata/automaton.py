from europi import *
import math, time, random

class CyberneticAutomaton:
    def __init__(self):
        self.gate1 = cv4
        self.gate2 = cv5
        self.gate3 = cv6
        self.charge = 0.0
        self.charge_threshold = 0.5
        self.markov_bias = 0.2
        self.markov_memory = []
        self.prev_b1_state = b1.value()
        self.prev_b2_state = b2.value()
        self.b1_press_time = 0
        self.b2_press_time = 0
        self.b1_fell = False
        self.b2_fell = False
        self.b1_held = False
        self.b2_held = False
        self.hold_threshold = 1000
        self.last_clock_time = time.ticks_ms()
        self.min_clock_period = 50
        self.max_clock_period = 1000
        self.clock_pulse_duration = 5
        self.last_display_time = time.ticks_ms()
        self.display_interval = 100
        self.ain_scale_mode = False
        self.b1_long_hold_toggled = False

    def update_buttons(self):
        now = time.ticks_ms()
        current_b1 = b1.value()
        current_b2 = b2.value()
        if current_b1 == HIGH and self.prev_b1_state == LOW:
            self.b1_fell = True
            self.b1_press_time = now
        else:
            self.b1_fell = False
        if current_b1 == HIGH and time.ticks_diff(now, self.b1_press_time) > self.hold_threshold:
            self.b1_held = True
        else:
            self.b1_held = False
        if current_b2 == HIGH and self.prev_b2_state == LOW:
            self.b2_fell = True
            self.b2_press_time = now
        else:
            self.b2_fell = False
        if current_b2 == HIGH and time.ticks_diff(now, self.b2_press_time) > self.hold_threshold:
            self.b2_held = True
        else:
            self.b2_held = False
        self.prev_b1_state = current_b1
        self.prev_b2_state = current_b2

    def adjust_params(self):
        self.charge_threshold = k2.read_position() / 100.0

    def button_events(self):
        self.update_buttons()
        if self.b1_fell:
            self.charge += 0.1
            if self.charge > 1.0:
                self.charge = 1.0
        if self.b2_fell:
            self.markov_bias *= 1.1
        if self.b2_held:
            self.charge = 0.0
        if self.b1_held and not self.b1_long_hold_toggled:
            self.ain_scale_mode = not self.ain_scale_mode
            self.b1_long_hold_toggled = True
        if not self.b1_held:
            self.b1_long_hold_toggled = False
        if self.b1_held and self.b2_held:
            self.markov_memory.clear()
            self.markov_bias = 0.2

    def update_charge(self):
        scale = 5.0 if self.ain_scale_mode else 10.0
        ain_value = ain.read_voltage() / scale
        din_state = din.value()
        if len(self.markov_memory) > 10:
            avg = sum(self.markov_memory) / len(self.markov_memory)
            self.markov_bias = avg * 0.3
            self.markov_memory.pop(0)
        base_attack = 0.03
        base_discharge = 0.02
        k1_val = k1.read_position()
        if k1_val >= 50:
            effective_attack = base_attack * (1 + (k1_val - 50) / 50.0)
            effective_discharge = base_discharge * (1 - (k1_val - 50) / 50.0)
        else:
            effective_attack = base_attack * (1 - (50 - k1_val) / 50.0)
            effective_discharge = base_discharge * (1 + (50 - k1_val) / 50.0)
        if din_state == HIGH:
            diff = ain_value - self.charge
            self.charge += effective_attack * diff
            self.markov_memory.append(self.charge)
        else:
            self.charge -= effective_discharge * self.charge
        if self.charge < 0.0:
            self.charge = 0.0
        if self.charge > 1.0:
            self.charge = 1.0
        if self.charge > self.charge_threshold:
            self.gate1.on()
        else:
            self.gate1.off()
        if self.charge > self.charge_threshold * 1.2 and random.uniform(0, 1) < self.markov_bias:
            self.gate2.on()
            time.sleep(0.01)
            self.gate2.off()
        if self.charge < 0.05:
            self.gate3.on()
            time.sleep(0.01)
            self.gate3.off()
        cv1.voltage(self.charge * 5.0)
        cv2.voltage(math.log(1.0 + self.charge) * 5.0)
        cv3.voltage((self.charge ** 2) * 5.0)

    def update_clock(self):
        now = time.ticks_ms()
        clock_period = self.max_clock_period - int(self.charge * (self.max_clock_period - self.min_clock_period))
        if time.ticks_diff(now, self.last_clock_time) >= clock_period:
            self.gate3.on()
            time.sleep_ms(self.clock_pulse_duration)
            self.gate3.off()
            self.last_clock_time = now

    def update_display(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_display_time) >= self.display_interval:
            oled.fill(0)
            charge_voltage = self.charge * (5.0 if self.ain_scale_mode else 10.0)
            ain_voltage = ain.read_voltage()
            din_state = "H" if din.value() == HIGH else "L"
            k1_val = k1.read_position()
            k2_val = k2.read_position()
            oled.text("c:{:.2f}".format(charge_voltage), 0, 0)
            oled.text("A:{:.2f}".format(ain_voltage), 64, 0)
            oled.text("D:{}".format(din_state), 0, 12)
            oled.text("k1:{}".format(k1_val), 36, 12)
            oled.text("k2:{}".format(k2_val), 84, 12)
            oled.text("S:{}".format("5V" if self.ain_scale_mode else "10V"), 0, 24)
            oled.text("b:{:.2f}".format(self.markov_bias), 64, 24)
            oled.show()
            self.last_display_time = now

    def run(self):
        while True:
            self.adjust_params()
            self.button_events()
            self.update_charge()
            self.update_clock()
            self.update_display()
            time.sleep(0.01)

if __name__ == "__main__":
    automaton = CyberneticAutomaton()
    automaton.run()
