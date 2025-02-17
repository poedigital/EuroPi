import sys
import json
from europi import *
from math import sin, pi, floor
from time import sleep_us, sleep_ms, ticks_ms, ticks_diff
from europi_script import EuroPiScript
import _thread, gc
from machine import Pin, I2C
import ssd1306

# ===== CONFIGURATION PARAMETERS =====
LONG_PRESS_DURATION = 500  # ms
MIN_FREQ = 0.01             # Hz
MAX_FREQ = 2                # Hz
DISP_W = 128                # OLED width in pixels
DISP_H = 32                 # OLED height in pixels
CV_RATE = 48000             # CV update rate (samples per second)

MAX_MORPH_SINE = 1.0        # Sine and other amplitude-modulated equations
MAX_MORPH_LOGISTIC = 4.0    # For Logistic, controls the 'r' parameter (will be remapped)
INTERP_STEP = 0.1           # Increment for waveform interpolation per main-loop
TGT_TOL = 0.175             # Tolerance for morph change to trigger recompute
CACHE_MAX = 10              # Maximum number of cached waveforms
SLEEP_MS = 10               # Sleep time (ms) in the main loop

# Display indicator squares
SQ1 = (0, 0, 4, 4)          # DIN activity
SQ2 = (6, 0, 4, 4)          # AIN activity
SQ3 = (12, 0, 4, 4)         # Wave morph/redraw activity

# Initialize OLED
i2c = I2C(0, scl=Pin(17), sda=Pin(16))  # Adjust pins as needed
oled = ssd1306.SSD1306_I2C(DISP_W, DISP_H, i2c)

def load_saved_state(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (data.get("equation_dict", []), data.get("byte_array_dict", {}), data.get("global_settings", {}))
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        sys.exit(1)

# ===== MODULE: EquationEngine =====
class EquationEngine:
    def __init__(self, disp_width, disp_height, equations):
        self.width = disp_width
        self.height = disp_height
        self.theta_lookup = [(x / self.width) * 2 * pi for x in range(self.width)]
        self.cache = {}
        self.equations = equations  # Reference to SOT equations

    def clear_cache_if_needed(self):
        if len(self.cache) >= CACHE_MAX:
            self.cache.clear()

    def compute_waveform(self, eq_data, morph, freq):
        key = (eq_data["id"], round(morph, 3))
        if key in self.cache:
            return self.cache[key]
        self.clear_cache_if_needed()
        wf = []
        if eq_data["title"] == "Logistic":
            r = morph
            x_val = 0.5  # starting value
            for i in range(self.width):
                try:
                    x_val = r * x_val * (1.0 - x_val)
                except Exception:
                    x_val = 0.0
                x_val = max(0.0, min(1.0, x_val))
                y = int(x_val * (self.height - 1))
                wf.append((i, y))
        else:
            for i, theta in enumerate(self.theta_lookup):
                if eq_data["title"] == "SineOsc":
                    s = sin(theta) * morph  # Direct computation without fold
                elif eq_data["title"] == "SawOsc":
                    t = theta / (2 * pi)
                    s = 2 * (t * freq - floor(0.5 + t * freq))
                    s *= morph
                elif eq_data["title"] == "SquareOsc":
                    s = 1.0 if sin(theta) >= 0 else -1.0
                    s *= morph
                else:
                    s = 0.0
                y = int(((s * 0.5) + 0.5) * (self.height - 1))
                wf.append((i, y))
        wf = tuple(wf)
        self.cache[key] = wf
        return wf

    def interp_waveform(self, w1, w2, f):
        """Interpolate between two waveforms (tuples of (x,y)) by fraction f."""
        return tuple((x, int(y1 * (1 - f) + y2 * f))
                     for (x, y1), (_, y2) in zip(w1, w2))

# ===== MODULE: DisplayController =====
class DisplayController:
    def __init__(self, disp_width, disp_height):
        self.width = disp_width
        self.height = disp_height
        self.last_wave = None
        self.interp = 1.0

    def render_waveform(self, waveform, interp_active=False):
        oled.fill(0)
        for x, y in waveform:
            if 0 <= x < self.width and 0 <= y < self.height:
                oled.pixel(x, y, 1)
        oled.fill_rect(*SQ1, 1)  # DIN activity indicator
        if interp_active:
            oled.fill_rect(*SQ2, 1)  # AIN activity indicator
        oled.show()
        self.last_wave = waveform

# ===== MODULE: RealTimeLFOWave =====
class RealTimeLFOWave(EuroPiScript):
    def __init__(self, equations, assignments):
        super().__init__()
        self.phase = 0.0
        self.freq = MIN_FREQ
        self.morph = 0.0  # current morph parameter from controls
        self.last_target_morph = 0.0

        self.eq_engine = EquationEngine(DISP_W, DISP_H, equations)
        self.display_ctrl = DisplayController(DISP_W, DISP_H)

        self.eq_list = equations
        self.equation_index = 0
        self.selected_eq = self.eq_list[self.equation_index]
        self.assignments = assignments
        self.update_morph_initial()

        init_wave = self.eq_engine.compute_waveform(self.selected_eq, self.morph, self.freq)
        self.prev_waveform = init_wave
        self.target_waveform = init_wave
        self.display_ctrl.last_wave = init_wave  # initial displayed waveform
        self.last_target_morph = self.morph

        _thread.start_new_thread(self.cv_update_loop, ())

        @b1.handler
        def cycle_equations():
            self.equation_index = (self.equation_index + 1) % len(self.eq_list)
            self.selected_eq = self.eq_list[self.equation_index]
            self.update_morph_initial()
            new_target = self.eq_engine.compute_waveform(self.selected_eq, self.morph, self.freq)
            self.prev_waveform = self.display_ctrl.last_wave or new_target
            self.target_waveform = new_target
            self.display_ctrl.interp = 0.0
            self.last_target_morph = self.morph

    def update_morph_initial(self):
        k2_var = self.assignments.get('k2')
        k2_val = round(k2.read_position(), 2)
        if self.selected_eq["title"] == "Logistic" and k2_var == "r":
            self.morph = 2.5 + (MAX_MORPH_LOGISTIC - 2.5) * k2_val
        elif k2_var == "amp":
            self.morph = MAX_MORPH_SINE * k2_val
        else:
            self.morph = MAX_MORPH_SINE * k2_val

    def cv_update_loop(self):
        while True:
            self.phase = (self.phase + (self.freq / CV_RATE) * 2 * pi) % (2 * pi)
            if self.selected_eq["title"] == "Logistic":
                voltage = 0.0
            else:
                # Removed fold function usage
                v = sin(self.phase) * self.morph
                voltage = (v + 1) * 2.5
            cv1.voltage(voltage)
            cv2.voltage(5.0 - voltage)
            sleep_us(120)  # ~48000 Hz update rate

    def wave_engine_loop(self):
        if not self.eq_list:
            return
        while self.screen == 3:
            for b in self.buttons:
                self.check_button(b)

            eqd = self.eq_list[self.equation_index]
            if eqd != self.selected_eq:
                self.selected_eq = eqd
                self.phase = 0.0
                self.prev_waveform = []
                self.target_waveform = []
                self.display_ctrl.interp = 1.0

            ain_val = ain.read_voltage()
            ain_norm = 0.0 if ain_val < 0 else (1.0 if ain_val > 5 else (ain_val / 5.0))
            self.freq = MIN_FREQ + (MAX_FREQ - MIN_FREQ) * ain_norm

            k2_var = self.assignments.get('k2')
            kv = round(k2.read_position(), 2)
            if eqd["title"] == "Logistic" and k2_var == "r":
                self.morph = 2.5 + (MAX_MORPH_LOGISTIC - 2.5) * kv
            elif k2_var == "amp":
                self.morph = MAX_MORPH_SINE * kv
            else:
                self.morph = MAX_MORPH_SINE * kv

            # Determine if morphing is active
            morph_active = False
            if abs(self.morph - self.last_target_morph) > TGT_TOL:
                nwf = self.eq_engine.compute_waveform(eqd, self.morph, self.freq)
                self.prev_waveform = self.display_ctrl.last_wave or nwf
                self.target_waveform = nwf
                self.display_ctrl.interp = 0.0
                self.last_target_morph = self.morph
                morph_active = True  # Morphing started

            # Interpolation
            if self.display_ctrl.interp < 1.0:
                self.display_ctrl.interp = min(1.0, self.display_ctrl.interp + INTERP_STEP)
                wv = self.eq_engine.interp_waveform(self.prev_waveform, self.target_waveform, self.display_ctrl.interp)
                morph_active = True  # Still morphing
                din_active = self.buttons['b1']['pin'].value() or self.buttons['b2']['pin'].value()
                ain_active = ain_val > 0.01
                self.display_ctrl.render_waveform(
                    wv,
                    interp_active=True
                )
                # Update DisplayController indicators externally if needed
            else:
                if not self.target_waveform:
                    self.target_waveform = self.eq_engine.compute_waveform(eqd, self.morph, self.freq)
                din_active = self.buttons['b1']['pin'].value() or self.buttons['b2']['pin'].value()
                ain_active = ain_val > 0.01
                self.display_ctrl.render_waveform(
                    self.target_waveform,
                    interp_active=False
                )

            gc.collect()
            sleep_ms(SLEEP_MS)

    def main(self):
        while True:
            if self.screen == 3:
                self.wave_engine_loop()
                self.refresh_needed = True
                continue
            for b in self.buttons:
                self.check_button(b)
            if self.refresh_needed:
                {1: self.display_home_screen, 2: self.display_assignment_screen}.get(self.screen, lambda: None)()
                self.refresh_needed = False

# ===== MAIN SCRIPT =====
if __name__ == "__main__":
    # Load SOT data
    eq_list, byte_map, global_set = load_saved_state("saved_state_Codex.txt")
    
    # Initialize Codex
    codex = RealTimeLFOWave(eq_list, assignments)
    codex.main()
