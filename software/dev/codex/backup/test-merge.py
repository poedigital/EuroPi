from europi import *
from math import sin, pi, floor
from time import sleep_ms, sleep_us, ticks_ms
from europi_script import EuroPiScript
import _thread, gc

# =============================================================================
# CONFIGURATION PARAMETERS
# =============================================================================
MIN_FREQ    = 0.01      # Hz
MAX_FREQ    = 2         # Hz
DISP_W      = 128       # OLED width
DISP_H      = 32        # OLED height
CV_RATE     = 48000     # CV update rate

MAX_MORPH_SINE     = 1.0    # For sine and similar equations
MAX_MORPH_LOGISTIC = 4.0    # For Logistic (maps to the 'r' parameter)
INTERP_STEP        = 0.1    # Increment for waveform interpolation
TGT_TOL            = 0.175  # Tolerance for morph change to trigger recompute
CACHE_MAX          = 10     # Maximum cached waveforms

# Display indicator squares
SQ1 = (0, 0, 4, 4)         # Always drawn
SQ2 = (6, 0, 4, 4)         # Drawn only during interpolation

SLEEP_MS = 10              # Main-loop sleep time (ms)

# For Codex (matrix) module:
LONG_PRESS_DURATION = 500  # milliseconds for a long press

# =============================================================================
# GLOBAL DATA: Equation Dictionary & Assignments
# =============================================================================
equation_dict = [
    {
        "id": 1,
        "title": "SineOsc",
        "equation": "x(t) = sin(2πft)",
        "vars": ["f", "amp"],
        "settings": {},
        "byte": []  # (Could be used to draw symbols)
    },
    {
        "id": 2,
        "title": "SawOsc",
        "equation": "x(t) = 2*(t*f - floor(0.5 + t*f))",
        "vars": ["f", "amp"],
        "settings": {},
        "byte": []
    },
    {
        "id": 3,
        "title": "SquareOsc",
        "equation": "x(t) = 1.0 if sin(2πft) >= 0 else -1.0",
        "vars": ["f", "amp"],
        "settings": {},
        "byte": []
    },
    {
        "id": 4,
        "title": "Logistic",
        "equation": "x(n+1) = r*x(n)*(1-x(n))",
        "vars": ["r", "x", "n"],
        "settings": {},
        "byte": []
    }
]

assignments = {
    'k1': 'f',    # Map k1 to frequency or, for Logistic, to 'r'
    'k2': 'amp'   # Map k2 to amplitude (or to 'x' for Logistic)
}

# =============================================================================
# MODULE: EquationEngine (for computing/caching waveforms)
# =============================================================================
class EquationEngine:
    def __init__(self, disp_width, disp_height):
        self.width = disp_width
        self.height = disp_height
        # Precompute theta for one full cycle.
        self.theta_lookup = [(x / self.width) * 2 * pi for x in range(self.width)]
        self.cache = {}  # Cache keyed by (equation_id, round(morph, 3))
    
    def clear_cache_if_needed(self):
        if len(self.cache) >= CACHE_MAX:
            self.cache.clear()
    
    def fold(self, s, th=1.0):
        """Fold sample value into [-th, th] to avoid overflow artifacts."""
        i = 0
        while (s > th or s < -th) and i < 10:
            s = th - (s - th) if s > th else -th - (s + th)
            i += 1
        return s
    
    def compute_waveform(self, eq, morph, freq):
        """
        Compute a full-cycle waveform (as a tuple of (x, y) pixels).
        Caches results based on (eq id, rounded morph).
        """
        key = (eq["id"], round(morph, 3))
        if key in self.cache:
            return self.cache[key]
        self.clear_cache_if_needed()
        wf = []
        if eq["title"] == "Logistic":
            r = morph  # Assume morph is already mapped (see update_morph_initial)
            x_val = 0.5  # initial value
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
                if eq["title"] == "SineOsc":
                    s = self.fold(sin(theta) * morph, th=1.0)
                elif eq["title"] == "SawOsc":
                    t = theta / (2 * pi)
                    s = 2 * (t * freq - floor(0.5 + t * freq)) * morph
                elif eq["title"] == "SquareOsc":
                    s = (1.0 if sin(theta) >= 0 else -1.0) * morph
                else:
                    s = 0.0
                y = int((s * 0.5 + 0.5) * (self.height - 1))
                wf.append((i, y))
        wf = tuple(wf)
        self.cache[key] = wf
        return wf
    
    def interp_waveform(self, w1, w2, f):
        """Interpolate between two waveforms by fraction f (0..1)."""
        return tuple((x, int(y1 * (1-f) + y2 * f))
                     for (x, y1), (_, y2) in zip(w1, w2))

# =============================================================================
# MODULE: DisplayController (for drawing waveforms)
# =============================================================================
class DisplayController:
    def __init__(self, disp_width, disp_height):
        self.width = disp_width
        self.height = disp_height
        self.last_wave = None
        self.interp = 1.0  # interpolation factor
    
    def render_waveform(self, waveform, interp_active=False):
        oled.fill(0)
        for x, y in waveform:
            if 0 <= x < self.width and 0 <= y < self.height:
                oled.pixel(x, y, 1)
        oled.fill_rect(SQ1[0], SQ1[1], SQ1[2], SQ1[3], 1)
        if interp_active:
            oled.fill_rect(SQ2[0], SQ2[1], SQ2[2], SQ2[3], 1)
        oled.show()
        self.last_wave = waveform

# =============================================================================
# MODULE: WaveEngine (RealTimeLFOWave refactored for update iteration)
# =============================================================================
class WaveEngine(EuroPiScript):
    def __init__(self):
        super().__init__()
        self.phase = 0.0
        self.freq = MIN_FREQ
        self.morph = 0.0
        self.last_target_morph = 0.0
        
        self.eq_engine = EquationEngine(DISP_W, DISP_H)
        self.display_ctrl = DisplayController(DISP_W, DISP_H)
        
        self.eq_list = equation_dict
        self.eq_index = 0
        self.selected_eq = self.eq_list[self.eq_index]
        
        # Initial mapping for k2 to morph.
        self.update_morph_initial()
        
        init_wave = self.eq_engine.compute_waveform(self.selected_eq, self.morph, self.freq)
        self.prev_waveform = init_wave
        self.target_waveform = init_wave
        self.display_ctrl.last_wave = init_wave
        self.last_target_morph = self.morph
        
        # Start CV update thread
        _thread.start_new_thread(self.cv_update_loop, ())
        
        # Also allow cycling equations via a short button press (optional)
        @b1.handler
        def cycle_equations():
            self.eq_index = (self.eq_index + 1) % len(self.eq_list)
            self.selected_eq = self.eq_list[self.eq_index]
            self.update_morph_initial()
            new_target = self.eq_engine.compute_waveform(self.selected_eq, self.morph, self.freq)
            self.prev_waveform = self.display_ctrl.last_wave or new_target
            self.target_waveform = new_target
            self.display_ctrl.interp = 0.0
            self.last_target_morph = self.morph

    def update_morph_initial(self):
        # Map k2's reading into morph value.
        k2_var = assignments.get('k2')
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
                v = self.eq_engine.fold(sin(self.phase) * self.morph, th=1.0)
                voltage = (v + 1) * 2.5
            cv1.voltage(voltage)
            cv2.voltage(5.0 - voltage)
            sleep_us(120)

    def update(self):
        # One update iteration of the wave engine (to be called from AppManager)
        # Read AIN for frequency
        ain_val = ain.read_voltage()
        ain_norm = min(max(ain_val / 5.0, 0.0), 1.0)
        self.freq = MIN_FREQ + (MAX_FREQ - MIN_FREQ) * ain_norm
        
        # Update morph from k2.
        k2_val = round(k2.read_position(), 2)
        k2_var = assignments.get('k2')
        if self.selected_eq["title"] == "Logistic" and k2_var == "r":
            self.morph = 2.5 + (MAX_MORPH_LOGISTIC - 2.5) * k2_val
        elif k2_var == "amp":
            self.morph = MAX_MORPH_SINE * k2_val
        else:
            self.morph = MAX_MORPH_SINE * k2_val
        
        if abs(self.morph - self.last_target_morph) > TGT_TOL:
            new_target = self.eq_engine.compute_waveform(self.selected_eq, self.morph, self.freq)
            self.prev_waveform = self.display_ctrl.last_wave if self.display_ctrl.last_wave else new_target
            self.target_waveform = new_target
            self.display_ctrl.interp = 0.0
            self.last_target_morph = self.morph
        
        if self.display_ctrl.interp < 1.0:
            self.display_ctrl.interp = min(1.0, self.display_ctrl.interp + INTERP_STEP)
            wave = self.eq_engine.interp_waveform(self.prev_waveform, self.target_waveform, self.display_ctrl.interp)
            self.display_ctrl.render_waveform(wave, interp_active=True)
        else:
            self.display_ctrl.render_waveform(self.target_waveform)
        
        gc.collect()

# =============================================================================
# MODULE: Codex (Equation Codex & Matrix assignment)
# =============================================================================
class Codex:
    def __init__(self):
        # Use an independent copy of equation_dict (or reference the global one)
        self.equations = equation_dict
        self.equation_index = 0
        self.controls = ["AIN", "k1", "k2"]
        self.assignments = {ctrl: None for ctrl in self.controls}
        self.ctrl_index = 0  
        self.var_index = 0  
        self.b1_press_time = None
        self.b1_long_press_triggered = False
        self.b2_press_time = None
        self.b2_long_press_triggered = False
        # screen: 1 = codex home, 2 = matrix assignment
        self.screen = 1

    # -------------------------
    # Button checking utilities
    # -------------------------
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
        # In codex mode, short press on b1 cycles backward.
        if self.screen == 1:
            self.equation_index = (self.equation_index - 1) % len(self.equations)
        elif self.screen == 2:
            self.ctrl_index = (self.ctrl_index + 1) % len(self.controls)

    def on_b2_short_press(self):
        # In codex mode, short press on b2 cycles forward.
        if self.screen == 1:
            self.equation_index = (self.equation_index + 1) % len(self.equations)
        elif self.screen == 2:
            self.assign_variable()

    def on_b1_long_press(self):
        # Long press cycles overall codex screens.
        self.screen -= 1
        if self.screen < 1:
            self.screen = 3
        self.saveSettings()

    def on_b2_long_press(self):
        self.screen += 1
        if self.screen > 3:
            self.screen = 1
        self.saveSettings()

    def assign_variable(self):
        ctrl = self.controls[self.ctrl_index]
        var_list = self.equations[self.equation_index]["vars"]
        if not var_list:
            return  # nothing to assign
        var_name = var_list[self.var_index]
        # Prevent duplicate assignment to both k1 and k2.
        if ctrl in ["k1", "k2"]:
            for c, v in self.assignments.items():
                if c in ["k1", "k2"] and v == var_name:
                    return
        old_var = self.assignments.get(ctrl)
        if old_var:
            for c, v in self.assignments.items():
                if v == old_var:
                    self.assignments[c] = None
                    break
        self.assignments[ctrl] = var_name
        self.var_index = (self.var_index + 1) % len(var_list)

    def saveSettings(self):
        # Here you would write the current assignments (and other settings)
        # to a file (e.g. saved_state_Codex.txt). For now, we leave it as a stub.
        pass

    # -------------------------
    # Display routines
    # -------------------------
    def draw_equation_line(self, text, x, y, tokens):
        # For simplicity, we just draw plain text.
        # (In your full version you’d draw tokens using byte_array_dict.)
        oled.text(text, x, y, 1)

    def display_home_screen(self):
        oled.fill(0)
        eq = self.equations[self.equation_index]
        eq_title = eq["title"][:12]
        eq_equation = eq["equation"]
        # Title centered.
        tx = (DISP_W - len(eq_title)*8) // 2
        oled.text(eq_title, tx, 0, 1)
        # Equation (if long, split into two rows).
        if len(eq_equation) > 16:
            row1 = eq_equation[:16]
            row2 = eq_equation[16:32]
            row1_x = (DISP_W - len(row1)*8) // 2
            row2_x = (DISP_W - len(row2)*8) // 2
            self.draw_equation_line(row1, row1_x, 12, [])
            self.draw_equation_line(row2, row2_x, 24, [])
        else:
            eq_x = (DISP_W - len(eq_equation)*8) // 2
            self.draw_equation_line(eq_equation, eq_x, 12, [])
        # Draw an AIN indicator if voltage exceeds threshold.
        if ain.read_voltage() > 0.1:
            oled.fill_rect(0, 0, 4, 4, 1)
        oled.show()

    def display_assignment_screen(self):
        oled.fill(0)
        row_height = 10
        col_width = 24
        start_x = 32
        start_y = 0
        for i, ctrl in enumerate(self.controls):
            y = start_y + i * row_height
            oled.text(ctrl, 0, y, 1)
            assignment = self.assignments.get(ctrl) or "None"
            oled.text(": " + assignment, start_x, y, 1)
        oled.show()

    def display_waveform_screen(self):
        # In codex mode this is a simple waveform preview.
        oled.fill(0)
        r = k1.percent() * 4
        x = k2.percent()
        data = []
        for i in range(DISP_W):
            x = r * x * (1 - x)
            data.append(x)
        for i, val in enumerate(data):
            y = int(val * 16)
            oled.pixel(i, DISP_H - 1 - y, 1)
        oled.show()

    def update(self):
        # This update method should be called from the AppManager when in codex mode.
        self.check_b1()
        self.check_b2()
        if self.screen == 1:
            self.display_home_screen()
        elif self.screen == 2:
            self.display_assignment_screen()
        elif self.screen == 3:
            self.display_waveform_screen()

# =============================================================================
# APP MANAGER: Switches among the three pages
# =============================================================================
class AppManager:
    def __init__(self):
        # Global state: 1 = Equation Codex, 2 = Matrix Engine, 3 = Waveform Engine
        self.state = 1
        self.codex = Codex()
        self.wave_engine = WaveEngine()  # Already starts its CV update thread.
    
    def cycle_state(self, direction):
        # Change overall app mode.
        self.state += direction
        if self.state < 1:
            self.state = 3
        elif self.state > 3:
            self.state = 1
    
    def update(self):
        if self.state in [1, 2]:
            # In codex mode, we delegate update to the Codex module.
            self.codex.update()
        elif self.state == 3:
            # In wave engine mode, call one update iteration.
            self.wave_engine.update()
    
    def render(self):
        # In this framework the render methods are included in update().
        # We assume each update call does the drawing.
        pass

# =============================================================================
# BUTTON HANDLERS for Global State Switching
# =============================================================================
# These handlers override any per-module long press behavior.
app_manager = AppManager()

@b1.handler
def global_b1_handler():
    # On a long press, cycle the overall state backward.
    # (You might add logic to detect long press here if desired.)
    app_manager.cycle_state(-1)

@b2.handler
def global_b2_handler():
    # On a long press, cycle the overall state forward.
    app_manager.cycle_state(1)

# =============================================================================
# MAIN LOOP
# =============================================================================
while True:
    # Update the currently active module based on app_manager.state:
    # State 1 & 2: Codex (which handles home and assignment screens)
    # State 3: Waveform engine
    app_manager.update()
    sleep_ms(10)
