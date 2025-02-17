"""
SolarLFO Example
Author: [Your Name or Handle]
Description: Demonstrates a generative "Solar LFO" with wind-based chaos,
             seasonal day length, and DIN sync behavior.

Hardware assumptions:
- 6 CV outs -> cv1..cv6, each capable of 0-10 V
- 2 digital ins: DIN (16th tick clock) on pin din, a second digital in unused or re-purposed
- 1 analog in (ain) for external audio/CV
- 2 knobs: k1, k2
- 2 buttons: b1 (dec wind), b2 (inc wind + long-press for output-range toggle)
- 1 small 128x32 OLED
- Real-time clock (I2C)
- Non-volatile storage (optional)
"""

import math
import time
import json
import random

# ---------------------
# PLACEHOLDER: adapt these to your hardware
# ---------------------
try:
    from my_europi_lib import (
        cv1, cv2, cv3, cv4, cv5, cv6,
        din, b1, b2, k1, k2, ain, oled, rtc,
        ticks_ms, ticks_diff, sleep_ms
    )
except ImportError:
    # For pseudo-testing on a desktop / placeholder
    class FakeCV:
        def __init__(self, name): self.name = name
        def voltage(self, v): pass
        def value(self, *args): return 0
        def on(self): pass
        def off(self): pass
    cv1=cv2=cv3=cv4=cv5=cv6 = FakeCV("cvX")

    class FakeDigitalIn:
        def __init__(self, name): self.name=name
        def value(self): return 0
    din=FakeDigitalIn("din")

    class FakeButton:
        def __init__(self, name): self.name=name
        def value(self): return 0
    b1=FakeButton("b1")
    b2=FakeButton("b2")

    class FakeKnob:
        def read_position(self): return 0
    k1=k2=FakeKnob()

    class FakeAIN:
        def read_voltage(self): return 0
    ain = FakeAIN()

    class FakeOled:
        def fill(self, c): pass
        def text(self, msg, x, y, c=1): pass
        def show(self): pass
    oled = FakeOled()

    class FakeRTC:
        def now(self):
            # returns a time.struct_time
            return time.localtime()
    rtc = FakeRTC()

    ticks_ms = lambda: int(time.time()*1000)
    def ticks_diff(a,b): return a-b
    def sleep_ms(ms): time.sleep(ms/1000)


# ~~~~~~~~~~~~~~~~~~~~~~~~~
# Seasonal data placeholder
# ~~~~~~~~~~~~~~~~~~~~~~~~~
# Approximate average sunrise & sunset times for Montreal by month (UTC-5 or UTC-4 in DST).
# Times in decimal hours from midnight (e.g., 5.5 = 5:30 AM).
# This is just an example; you can refine it or store it in an external file.
MONTREAL_SUN_TABLE = {
    1:  {"sunrise": 7.5,  "sunset": 16.6},   # January
    2:  {"sunrise": 7.0,  "sunset": 17.2},
    3:  {"sunrise": 6.2,  "sunset": 18.0},
    4:  {"sunrise": 5.3,  "sunset": 19.0},
    5:  {"sunrise": 4.6,  "sunset": 19.8},
    6:  {"sunrise": 4.3,  "sunset": 20.3},
    7:  {"sunrise": 4.5,  "sunset": 20.2},
    8:  {"sunrise": 5.0,  "sunset": 19.6},
    9:  {"sunrise": 5.6,  "sunset": 18.7},
    10: {"sunrise": 6.2,  "sunset": 17.6},
    11: {"sunrise": 6.9,  "sunset": 16.8},
    12: {"sunrise": 7.4,  "sunset": 16.2},
}

def get_sun_times(month):
    """
    Return (sunrise, sunset) in local time for the given month.
    Times are decimal hours from midnight. E.g. 7.5 => 7:30 AM
    """
    data = MONTREAL_SUN_TABLE.get(month, {"sunrise": 6.0, "sunset": 18.0})
    return (data["sunrise"], data["sunset"])


# -------------
# User settings
# -------------
SETTINGS_FILE = "solar_lfo_settings.json"

def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            return data
    except:
        return {
            "wind_intensity": 0,   # 0..9
            "output_scale": 1.0,   # 1.0 for 0-10v, 0.5 for 0-5v
        }

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
    except:
        pass  # If filesystem not available or error => skip


# ~~~~~~~~~~~~~~~~~~~~~~~
# LFO / wave calculations
# ~~~~~~~~~~~~~~~~~~~~~~~
def smooth_sine(phase):
    """Simple sine wave from 0..1 (not -1..1). Input phase is 0..1."""
    return 0.5 + 0.5 * math.sin(2*math.pi*phase)

def half_wave_rectified_sine(phase):
    """Example half-wave rect: returns 0..1, zero for negative portion of sine."""
    s = math.sin(2*math.pi*phase)
    return max(0, s)

def ring_mod(base_val, mod_val, depth):
    """
    Example ring-mod style function: 
    base_val, mod_val in [0..1], 
    depth in [0..1].
    """
    # e.g. combine the signals
    # scale mod_val to ±1 => (mod_val*2 -1)
    # apply ring mod => base_val * (1 + depth*(mod_val*2 -1))
    return base_val * (1.0 + depth * ((mod_val*2.0)-1.0))

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Example "wind" generator: chaotic random bursts
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class WindEngine:
    def __init__(self):
        self.intensity = 0   # 0..9
        self.last_update = ticks_ms()
        self.clocked = False
        self.clock_interval = 200  # default ms if free
        self.value = 0.0     # main random-ish value
        self.gate = False
        self.gate_threshold = 0.7  # can vary with intensity

    def set_intensity(self, val):
        self.intensity = max(0, min(9, val))

    def update_clocked(self, interval_ms):
        """When DIN is active, we have a known interval (or guess an interval)."""
        self.clocked = True
        self.clock_interval = interval_ms

    def update_free(self):
        self.clocked = False

    def tick(self):
        """
        Called often in the main loop. 
        - If clocked, update slightly every 'clock_interval'.
        - If free, we can update every 200ms or random intervals.
        """
        now = ticks_ms()
        ms_since = ticks_diff(now, self.last_update)
        
        target_interval = self.clock_interval if self.clocked else 250
        if ms_since >= target_interval:
            self.last_update = now

            # "Wind" logic: bigger intensity => more/faster random changes
            # We'll do a random walk, plus bursts.
            step_size = 0.02 * (1 + self.intensity)  # bigger with intensity
            # random walk:
            r = (random.random()*2 -1)*step_size
            new_val = self.value + r
            # clamp to 0..1
            new_val = max(0, min(1, new_val))

            # chance of sudden burst if intensity>0
            burst_chance = 0.005 * self.intensity
            if random.random() < burst_chance:
                # big jump
                new_val = random.random()

            self.value = new_val
            
            # Gate logic: threshold depends on intensity:
            # high intensity => threshold is lower => gate triggers more easily
            # min threshold ~0.8, max threshold ~0.2
            thr = 0.9 - 0.07*self.intensity  # 0.9 down to ~0.27
            self.gate = (self.value > thr)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main SolarLFO class (example only)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class SolarLFO:
    def __init__(self):
        # State variables
        self.settings = load_settings()
        self.wind = WindEngine()
        self.wind.set_intensity(self.settings["wind_intensity"])
        self.output_scale = self.settings["output_scale"]  # 1.0 or 0.5
        self.last_b2_press_time = 0
        self.b2_long_press_handled = False
        self.long_press_threshold = 800  # ms

        # For detecting DIN presence
        self.din_active = False
        self.last_din_tick = 0

        # For hourly trigger
        self.last_hour_tick = -1

        # Additional illusions of phase
        self.start_time = time.time()  # Used for free-run phases

    def main_loop(self):
        try:
            # Existing main loop logic
            self.check_buttons()
            self.check_din()
            self.check_knobs()
            self.check_ain()

            # Update wind engine
            self.wind.tick()

            # Calculate LFOs
            now_tuple = rtc.now()
            year, month, day, hour, minute, second = now_tuple[:6]

            sun_val = self.calc_sun_lfo(hour, minute, second, month)
            hour_phase = (minute * 60 + second) / 3600.0
            hour_lfo = hour_phase

            do_hour_trigger = False
            if not self.din_active and minute == 0 and self.last_hour_tick != hour:
                self.last_hour_tick = hour
                do_hour_trigger = True

            day_phase = self.calc_day_phase(hour, minute, second)
            out4_val = smooth_sine((2 * day_phase) % 1.0)

            t = time.time() - self.start_time
            base_freq = 0.02
            if self.din_active:
                base_freq = 0.1
            raw5 = 0.5 + 0.5 * math.sin(2 * math.pi * base_freq * t)
            out5_val = raw5 * self.wind.value

            wind_gate = self.wind.gate

            ain_v = ain.read_voltage()
            ain_norm = min(1.0, ain_v / 5.0)
            rm_depth = self.read_k1()
            mod_sun_val = ring_mod(sun_val, ain_norm, rm_depth)

            out1_voltage = self.clamp10(mod_sun_val * 10 * self.output_scale)
            out2_voltage = self.clamp10(hour_lfo * 10 * self.output_scale)
            out4_voltage = self.clamp10(out4_val * 10 * self.output_scale)
            out5_voltage = self.clamp10(out5_val * 10 * self.output_scale)

            cv1.voltage(out1_voltage)
            cv2.voltage(out2_voltage)
            if do_hour_trigger:
                cv3.on()
                sleep_ms(20)
                cv3.off()
            else:
                cv3.off()
            cv4.voltage(out4_voltage)
            cv5.voltage(out5_voltage)
            if wind_gate:
                cv6.on()
            else:
                cv6.off()

            self.update_oled(
                (year, month, day, hour, minute, second),
                sun_val, hour_lfo, out5_val, wind_gate
            )
        except Exception as e:
            oled.fill(0)
            oled.text("Error:", 0, 0)
            oled.text(str(e), 0, 10)
            oled.show()
            time.sleep(1)


    def calc_sun_lfo(self, hour, minute, second, month):
        """
        Return a 0..1 value for the 'sun' intensity across 24h,
        taking into account a flattening from ~3 AM to dawn.
        You can incorporate monthly sunrise/sunset from MONTREAL_SUN_TABLE
        for a more accurate seasonal approach.
        """
        # Basic approach:
        day_phase = self.calc_day_phase(hour, minute, second)

        # Get sunrise & sunset from table:
        sunrise, sunset = get_sun_times(month)

        # Convert hour+minute+second => decimal hours
        current_h = hour + minute/60.0 + second/3600.0

        # We'll do a custom function:
        # If current < 3 or between 3..sunrise => near zero
        # Peak near middle of sunrise..sunset (use a sine or half-cos).
        # Then back to zero after sunset, or small tail near midnight.

        # For demonstration, do a rough approach:
        if current_h < 3.0:
            return 0.0  # "late night" quiet
        if current_h < sunrise:
            # smoothly rise from 3 AM => sunrise
            frac = (current_h - 3.0) / (sunrise - 3.0)
            return 0.2 * smooth_sine(0.5*frac)  # partial
        if current_h > sunset:
            # smoothly go to zero by midnight
            # let's say we fade from sunset => 24
            frac = (current_h - sunset) / (24.0 - sunset)
            return 0.2*(1.0 - frac)
        # else: we are in daylight
        # day length = sunset - sunrise
        day_frac = (current_h - sunrise)/(sunset - sunrise)
        # push it through a sine for a "zenith"
        return smooth_sine(day_frac)

    def calc_day_phase(self, hour, minute, second):
        """Return fraction of the 24-hour day: 0.0..1.0."""
        sec_total = hour*3600 + minute*60 + second
        return (sec_total / 86400.0) % 1.0

    def check_buttons(self):
        """Handle button logic for wind intensity and output scale toggle."""
        b1_state = b1.value()  # 1 if pressed
        b2_state = b2.value()
        now_ms = ticks_ms()

        # b1 short press => wind--
        if b1_state:
            # on press, decrement wind right away:
            self.wind.set_intensity(self.wind.intensity - 1)
            # optional: add small debounce / or detect release
            sleep_ms(200)  # quick and dirty
        # b2 short press => wind++
        # b2 long press => toggle scale
        if b2_state and not self.b2_long_press_handled:
            press_duration = 0
            self.last_b2_press_time = now_ms
            while b2.value():
                press_duration = ticks_diff(ticks_ms(), self.last_b2_press_time)
                if press_duration > self.long_press_threshold:
                    # long press recognized
                    self.toggle_scale()
                    self.b2_long_press_handled = True
                    break
                sleep_ms(20)
            # If we exit loop and press_duration < threshold => short press
            if press_duration < self.long_press_threshold:
                # short
                self.wind.set_intensity(self.wind.intensity + 1)
        elif not b2_state:
            self.b2_long_press_handled = False

        # clamp intensity
        self.wind.set_intensity(self.wind.intensity)
        # store new setting
        self.settings["wind_intensity"] = self.wind.intensity
        save_settings(self.settings)

    def toggle_scale(self):
        """Toggle between 1.0 and 0.5 scaling for outputs."""
        if abs(self.output_scale - 1.0) < 0.01:
            self.output_scale = 0.5
        else:
            self.output_scale = 1.0
        self.settings["output_scale"] = self.output_scale
        save_settings(self.settings)

    def check_din(self):
        """
        If DIN pulses are detected, consider DIN active.
        If no pulses for 30s => inactive.
        """
        # Basic edge detect
        din_state = din.value()
        now_ms = ticks_ms()
        if din_state == 1:
            # just assume we got a pulse
            self.last_din_tick = now_ms
            if not self.din_active:
                # begin fade-in or do something
                self.din_active = True

        # check if we lost pulses for 30s
        if self.din_active and ticks_diff(now_ms, self.last_din_tick) > 30000:
            self.din_active = False
            self.wind.update_free()

        # Example: if we do detect pulses, we might measure BPM or interval
        # For demonstration, let's just pass a fixed interval to wind.
        if self.din_active:
            # pretend 16th note at 120bpm => 125ms
            self.wind.update_clocked(125)
        else:
            self.wind.update_free()

    def check_knobs(self):
        # knob positions in [0..100] or whatever your environment uses
        # map them to [0..1]
        pass

    def read_k1(self):
        """Return a 0..1 value from knob k1."""
        pos = k1.read_position()  # 0..100?
        return min(1.0, pos/100.0)

    def read_k2(self):
        """Return a 0..1 value from knob k2."""
        pos = k2.read_position()
        return min(1.0, pos/100.0)

    def check_ain(self):
        # might do smoothing if needed
        pass

    def clamp10(self, v):
        """Clamp voltage to 0..10 just in case."""
        return max(0, min(10, v))

    def update_oled(self, tm, sun_val, hour_val, wind_val, wind_gate):
        """
        Minimal screen update.  
        tm: tuple-like object (year, month, day, hour, minute, second)  
        sun_val, hour_val, wind_val in 0..1  
        wind_gate: bool  
        """
        # Unpack the tuple for clarity
        year, month, day, hour, minute, second = tm

        oled.fill(0)
        # show wind intensity
        oled.text(f"W:{self.wind.intensity}", 0, 0)
        # show scale
        sc_txt = "10V" if abs(self.output_scale - 1.0) < 0.01 else "5V"
        oled.text(sc_txt, 40, 0)
        # show time
        oled.text(f"{hour:02}:{minute:02}", 80, 0)

        # Draw small bars:
        # sun bar => y=10..some value
        bar_len = int(sun_val * 20)  # up to 20 px
        oled.text("Sun", 0, 10)
        for i in range(bar_len):
            oled.text("|", 30, 29 - i)  # vertical bar from bottom up

        # hour bar
        bar_len_h = int(hour_val * 20)
        oled.text("Hr", 50, 10)
        for i in range(bar_len_h):
            oled.text("|", 70, 29 - i)

        # wind bar => from wind_val
        bar_len_w = int(wind_val * 20)
        oled.text("Wnd", 90, 10)
        for i in range(bar_len_w):
            oled.text("|", 120, 29 - i)

        # wind gate indicator
        if wind_gate:
            oled.text("G", 120, 0)

        # DIN indicator
        if self.din_active:
            oled.text("CLK", 0, 25)

        oled.show()



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Example usage in your main script
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main():
    slfo = SolarLFO()
    while True:
        slfo.main_loop()
        sleep_ms(5)  # ~20 Hz update (tweak as needed)



if __name__ == "__main__":
    main()

