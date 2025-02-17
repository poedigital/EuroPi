import sys
import math
import json
import re
import gc
from time import sleep_us, sleep_ms
from math import sin, pi
from europi import *
from europi_script import EuroPiScript
import _thread

# 1) Import your EquationEngine and loading function from test-equation-3.py
from test-equation3 import EquationEngine, load_saved_state

# ===== CONFIGURATION PARAMETERS =====
MIN_FREQ    = 0.01      # Hz
MAX_FREQ    = 2         # Hz
DISP_W      = 128       # OLED width in pixels
DISP_H      = 32        # OLED height in pixels
CV_RATE     = 48000     # CV update rate (samples per second)

MAX_MORPH_SINE     = 1.0
MAX_MORPH_LOGISTIC = 4.0  # logistic 'r' parameter max
INTERP_STEP = 0.1       # Waveform interpolation increment
TGT_TOL     = 0.175     # If morph changes by more than this => recompute
CACHE_MAX   = 10        # Max waveforms to cache
SLEEP_MS    = 10        # Sleep time in main loop

# Display indicator squares
SQ1 = (0, 0, 4, 4)  # always drawn (decoy)
SQ2 = (6, 0, 4, 4)  # drawn while interpolating waveforms

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
        # Draw squares (indicator)
        oled.fill_rect(SQ1[0], SQ1[1], SQ1[2], SQ1[3], 1)
        if interp_active:
            oled.fill_rect(SQ2[0], SQ2[1], SQ2[2], SQ2[3], 1)
        oled.show()
        self.last_wave = waveform


# ===== MODULE: RealTimeLFOWave =====
class RealTimeLFOWave(EuroPiScript):
    def __init__(self):
        super().__init__()
        self.phase = 0.0
        self.freq  = MIN_FREQ
        self.morph = 0.0
        self.last_target_morph = 0.0

        # 2) Load equations & operator pool from saved_state_Codex
        (
            self.equations,
            self.byte_array_dict,
            self.operator_pool,
            self.global_settings
        ) = load_saved_state("saved_state_Codex.txt")

        # 3) Create an EquationEngine instance from test_equation_3.py
        self.eq_engine = EquationEngine(self.operator_pool)

        # Basic caching for waveforms
        self._wave_cache = {}

        # 4) Create display controller
        self.display_ctrl = DisplayController(DISP_W, DISP_H)

        # Choose which equation to start with
        self.eq_index = self.global_settings.get("last_equation", 0) % len(self.equations)
        self.selected_eq = self.equations[self.eq_index]

        # Set initial morph
        self.update_morph_initial()

        # 5) Precompute the initial waveform
        init_wave = self.compute_waveform(self.selected_eq, self.morph, self.freq)
        self.prev_waveform   = init_wave
        self.target_waveform = init_wave
        self.display_ctrl.render_waveform(init_wave, interp_active=False)
        self.last_target_morph = self.morph

        # 6) Start a second thread for CV updating
        _thread.start_new_thread(self.cv_update_loop, ())

        # 7) Assign button for cycling equations
        @b1.handler
        def cycle_equations():
            self.eq_index = (self.eq_index + 1) % len(self.equations)
            self.selected_eq = self.equations[self.eq_index]
            self.update_morph_initial()
            new_target = self.compute_waveform(self.selected_eq, self.morph, self.freq)
            self.prev_waveform = self.display_ctrl.last_wave or new_target
            self.target_waveform = new_target
            self.display_ctrl.interp = 0.0
            self.last_target_morph = self.morph

    def load_variable_context(self, eq_dict, morph, freq, pixel_x=None):
        """
        Creates a local context dictionary for evaluating RPN tokens.
        If 'pixel_x' is provided, we treat 't' as pixel_x / DISP_W.
        You can also handle eq_dict["vars"] if you want dynamic ranges.
        """
        local_ctx = {}
        # Common variables
        local_ctx["freq"]  = freq
        local_ctx["morph"] = morph

        # If we want to treat 't' as a fraction along the display:
        if pixel_x is not None:
            local_ctx["t"] = pixel_x / DISP_W
        else:
            local_ctx["t"] = 0.0

        # Optionally handle eq_dict["vars"] + eq_dict["settings"]["ranges"]
        # e.g. set each var to min_val or a knob-based value
        varz = eq_dict.get("vars", [])
        rngs = eq_dict.get("settings", {}).get("ranges", {})
        for v in varz:
            (vmin, vmax) = rngs.get(v, (0.0, 1.0))
            # For now, just pick min value or something:
            local_ctx[v] = vmin

        return local_ctx

    def compute_waveform(self, eq_dict, morph, freq):
        """
        Builds a list of (x, y) points for the display using eq_dict["rpn"] tokens.
        Calls self.eq_engine.evaluate_rpn(...) for each pixel in the display width.
        """
        eq_id = eq_dict.get("id", "no_id")
        rpn   = eq_dict.get("rpn", [])
        if not rpn:
            print(f"[WARNING] {eq_dict.get('title','?')} has no RPN tokens!")
            return []

        # Use a cache to avoid recomputing
        cache_key = (eq_id, round(morph, 3), round(freq, 3))
        if cache_key in self._wave_cache:
            return self._wave_cache[cache_key]

        waveform = []
        for x in range(DISP_W):
            local_ctx = self.load_variable_context(eq_dict, morph, freq, pixel_x=x)
            try:
                val = self.eq_engine.evaluate_rpn(rpn, local_ctx)
            except Exception as e:
                print(f"[ERROR] RPN eval failed for eq_id={eq_id}: {e}")
                val = 0.0

            # Normalize val from -1..+1 => 0..(DISP_H - 1), or adapt as needed
            y_scaled = int(((val + 1.0) * 0.5) * (DISP_H - 1))
            waveform.append((x, y_scaled))

        self._wave_cache[cache_key] = waveform
        return waveform

    def interp_waveform(self, w1, w2, fraction):
        """Linear interpolation of two waveforms by fraction [0..1]."""
        return [
            (x1, int(y1*(1.0 - fraction) + y2*fraction))
            for ((x1, y1), (x2, y2)) in zip(w1, w2)
        ]

    def update_morph_initial(self):
        """
        Example logic to read a knob assignment from global_settings
        and map it to 'morph'. Adjust as you like.
        """
        k2_var = self.global_settings.get("assignments", {}).get('k2', 'amp')
        k2_val = round(k2.read_position(), 2)

        # If "Logistic" is a known eq title, and 'k2' is "r" => do something special
        if self.selected_eq.get("title") == "Logistic" and k2_var == "r":
            self.morph = 2.5 + (MAX_MORPH_LOGISTIC - 2.5) * k2_val
        else:
            self.morph = MAX_MORPH_SINE * k2_val

    def cv_update_loop(self):
        """Runs on a second thread: produce a simple LFO voltage on cv1/cv2."""
        while True:
            # Advance phase
            self.phase = (self.phase + (self.freq / CV_RATE) * 2.0 * pi) % (2.0*pi)

            # Example sine-based output
            if self.selected_eq.get("title") == "Logistic":
                voltage = 0.0
            else:
                voltage = (sin(self.phase) * self.morph + 1.0) * 2.5

            cv1.voltage(voltage)
            cv2.voltage(5.0 - voltage)
            sleep_us(120)

    def main(self):
        while True:
            # Read input for frequency
            ain_val = ain.read_voltage()
            self.freq = MIN_FREQ + (MAX_FREQ - MIN_FREQ)*(ain_val/5.0)

            # Recompute morph from knobs
            k2_val = round(k2.read_position(), 2)
            k2_var = self.global_settings.get("assignments", {}).get('k2', 'amp')
            if self.selected_eq.get("title") == "Logistic" and k2_var == "r":
                self.morph = 2.5 + (MAX_MORPH_LOGISTIC - 2.5)*k2_val
            else:
                self.morph = MAX_MORPH_SINE*k2_val

            # If morph changed enough, compute a new waveform
            if abs(self.morph - self.last_target_morph) > TGT_TOL:
                new_target = self.compute_waveform(self.selected_eq, self.morph, self.freq)
                self.prev_waveform = self.display_ctrl.last_wave or new_target
                self.target_waveform = new_target
                self.display_ctrl.interp = 0.0
                self.last_target_morph = self.morph

            # Waveform interpolation
            if self.display_ctrl.interp < 1.0:
                self.display_ctrl.interp = min(1.0, self.display_ctrl.interp + INTERP_STEP)
                wave = self.interp_waveform(self.prev_waveform, self.target_waveform, self.display_ctrl.interp)
                self.display_ctrl.render_waveform(wave, interp_active=True)
            else:
                self.display_ctrl.render_waveform(self.target_waveform, interp_active=False)

            gc.collect()
            sleep_ms(SLEEP_MS)


# ===== Main Entry Point =====
if __name__ == "__main__":
    RealTimeLFOWave().main()
