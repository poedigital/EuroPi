from europi import *
from europi_script import EuroPiScript
from experimental.rtc import clock
from framebuf import FrameBuffer, MONO_HLSB
import math
import time
import random

class SolarLFO(EuroPiScript):
    def __init__(self):
        super().__init__()

        # ----- Existing Setup -----
        self.ain_samples = []
        self.last_ain_update = time.ticks_ms()
        self.ain_average = 0.0
        self.ain_connected = False  # Flag for AIN connection state
        self.current_pitch = 1.0  # Used if you want a center frequency
        self.ain_filtered = 0.0  # Initialize the filtered value

        self.last_din_state = 0  # For detecting DIN edges
        self.last_din_rising_edge = time.ticks_ms()
        self.din_period = 2000.0  # Default DIN clock period in ms (0.5 Hz => 30 BPM)
        self.last_din_time = time.ticks_ms()  # Track last time we saw a DIN rising edge

        # For the internal LFO phase
        self.lfo_phase = 0.0
        self.lfo_freq_hz = 0.1   # Default slow freq if no DIN and k2=0
        self.last_lfo_update = time.ticks_ms()

        # Initialize RTC
        if not clock.source:
            print("RTC not initialized, setting fallback time...")
            clock.source.set_time(year=2025, month=1, day=13, hour=12, minute=0, second=0)

        # Internal variables
        self.current_hourly_voltage = 0.0  # Voltage for Out2
        self.current_daily_voltage = 0.0   # Voltage for Out1
        self.going_down = False           # Direction flag for hourly LFO
        self.last_minute = None           # Last processed minute for hourly LFO
        self.last_daily_voltage = 0.0
        self.last_hour = None
        self.voltage_scale = 10  # Default scale is 10V
        self.b2_pressed_time = None

        # Load settings
        state = self.load_state_json()
        self.voltage_scale = state.get("voltage_scale", 10)

        # Framebuffer for the OLED
        self.buffer = bytearray(OLED_WIDTH * OLED_HEIGHT // 8)
        self.frame = FrameBuffer(self.buffer, OLED_WIDTH, OLED_HEIGHT, MONO_HLSB)


    # -----------------------------------------------------------------------
    # 1) HELPER FUNCTIONS
    # -----------------------------------------------------------------------

    def get_current_time(self):
        """Safe RTC time read."""
        try:
            dt = clock.source.datetime()
            return dt[:6]  # (year, month, day, hour, minute, second)
        except Exception as e:
            print(f"Error reading RTC: {e}")
            return None, None, None, None, None, None

    def save_settings(self):
        """Save user preferences (like voltage scaling)."""
        state = {"voltage_scale": self.voltage_scale}
        self.save_state_json(state)

    def get_sun_times(self, month):
        """
        Return (sunrise, sunset) in local time for the given month.
        Times are decimal hours from midnight. E.g., 7.5 => 7:30 AM.
        """
        data = self.MONTREAL.get(month, {"sunrise": 6.0, "sunset": 18.0})
        return (data["sunrise"], data["sunset"])

    MONTREAL = {
        1:  {"sunrise": 7.5,  "sunset": 16.6},   
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

    # -----------------------------------------------------------------------
    # 2) RING-MOD & FOLDBACK
    # -----------------------------------------------------------------------

    def ring_mod(self, base, mod, depth):
        """
        Multiplicative approach around 'base'.
        We treat mod ∈ [0..1], shift it to [-1..+1], then multiply by depth.
        final = base * [1 + depth*(2*mod - 1)]
        """
        # Make sure depth is in [0..1]
        d = max(0.0, min(1.0, depth))
        # Shift mod from [0..1] => [-1..+1]
        bipolar_mod = 2.0 * mod - 1.0

        # Now scale by 'd'
        factor = 1.0 + d * bipolar_mod

        # Multiply
        out = base * factor
        return out

    def foldback(self, value, max_value=10.0):
        """
        If 'value' goes below 0, fold it back up (mirror).
        If it goes above max_value, fold it down.
        This is a simple one-pass fold. If it exceeds the range by more than 10,
        you'd need multiple folds or a loop.
        """
        if value < 0.0:
            folded = -value  # mirror around 0
            # if still > max_value, do another pass
            if folded > max_value:
                folded = 2.0 * max_value - folded
            return folded

        elif value > max_value:
            folded = 2.0 * max_value - value  # mirror around max_value
            if folded < 0.0:
                folded = -folded
            return folded

        return value

    # -----------------------------------------------------------------------
    # 3) INTERNAL LFO FOR SCENARIO 1
    # -----------------------------------------------------------------------

    def check_din_rising_edge(self):
        """Detect rising edges on the DIN input."""
        current_din_state = din.value()  # Get the current state of DIN
        if current_din_state == 1 and self.last_din_state == 0:
            # Rising edge detected
            now = time.ticks_ms()
            elapsed = time.ticks_diff(now, self.last_din_rising_edge)
            self.last_din_rising_edge = now

            # Update the DIN period if elapsed time is reasonable
            if elapsed > 10:  # Ignore absurdly short periods
                self.din_period = elapsed
            self.last_din_time = now

        # Update the last state
        self.last_din_state = current_din_state


    def update_internal_lfo(self):
        """
        Called each loop.  
        1) Decide LFO frequency based on:
           - If DIN pulses come in regularly, interpret that as BPM.
           - Else revert to free-run freq from K2.
        2) Advance phase and produce mod ∈ [0..1].
        """
        now = time.ticks_ms()
        dt_ms = time.ticks_diff(now, self.last_lfo_update)
        self.last_lfo_update = now

        # Check if DIN has gone silent for >2 seconds => fallback to free-run
        silence_ms = time.ticks_diff(now, self.last_din_time)
        din_active = (silence_ms < 2000)

        # K2 reading => 0..100. Map to freq range. (0.1Hz to ~1200Hz)
        k2_val = k2.read_position() / 100.0
        # We’ll do a rough exponential mapping:
        # freq = 10^(log10(0.1) + k2_val*(log10(1200) - log10(0.1)))
        # or simpler approach:
        freq_min = 0.01
        freq_max = 1200.0
        # Log approach:
        freq = freq_min * (freq_max / freq_min) ** k2_val

        if din_active:
            # Convert din_period (ms) to frequency: freq_din = 1000 / din_period
            freq_din = 1000.0 / max(self.din_period, 1.0)
            # We can combine freq_din and freq if you want:
            # e.g. treat K2 as a clock multiplier: freq = freq_din * (some factor)
            # For simplicity: freq = freq_din * (1 + 2*k2_val)
            # or something like that. Let’s do a simple approach:
            multiplier = 1.0 + 4.0 * k2_val  # up to 5x faster
            freq = freq_din * multiplier

        # ensure freq is not insane
        freq = min(freq, 2000.0)

        # Update the phase
        dt_sec = dt_ms / 1000.0
        self.lfo_phase += 2.0 * math.pi * freq * dt_sec
        # keep phase in check
        if self.lfo_phase > 2.0 * math.pi:
            self.lfo_phase -= 2.0 * math.pi

        # output = unipolar wave
        mod_val = 0.5 * (1.0 + math.sin(self.lfo_phase))
        return mod_val
        

    # -----------------------------------------------------------------------
    # 4) SCENARIO DETECTION & AIN READING
    # -----------------------------------------------------------------------

    def read_ain(self):
        """
        Read raw AIN voltage (0–10V).
        If >0.01 => assume something is plugged.
        Normalize to 0–1.
        """
        ain_value = ain.read_voltage()  # Read raw voltage (0–10V)
        if ain_value > 0.01:
            self.ain_connected = True
            return ain_value / self.voltage_scale  # Normalize to 0–1
        self.ain_connected = False
        return 0.0

    def update_ain_average(self):
        raw_v = ain.read_voltage()
        self.ain_connected = (raw_v > 0.01)

        alpha = 0.1  # smaller alpha => more smoothing (less stepping)
        self.ain_filtered = (1 - alpha) * self.ain_filtered + alpha * raw_v
        self.ain_average = self.ain_filtered / self.voltage_scale


    def get_mod_source_value(self):
        """
        If we are in scenario 2 (AIN connected):
          - scale AIN by K2
        Otherwise (scenario 1):
          - use internal LFO
        Returns mod ∈ [0..1].
        """
        if self.ain_connected:
            # Scenario 2: AIN is present
            atten = k2.read_position() / 100.0  # 0..1
            mod_val = self.ain_average * atten
        else:
            # Scenario 1: internal LFO
            mod_val = self.update_internal_lfo()

        return max(0.0, min(1.0, mod_val))

    # -----------------------------------------------------------------------
    # 5) MAIN OUTPUTS (DAILY & HOURLY) + HOUR TRIGGER
    # -----------------------------------------------------------------------

    def calculate_daily_lfo(self):
        """
        Generate base daily wave from [0..voltage_scale].
        Then ring-mod it with whichever scenario.
        Then foldback, then output to CV1.
        """
        year, month, day, hour, minute, second = self.get_current_time()
        if hour is None:
            return 0

        # Determine base wave
        sunrise, sunset = self.get_sun_times(month)
        current_time = hour + minute/60 + second/3600
        if sunrise <= current_time <= sunset:
            day_length = sunset - sunrise
            day_phase = (current_time - sunrise) / max(day_length, 0.001)
            # Sine wave from 0..voltage_scale
            base = max(0, math.sin(math.pi * day_phase) * self.voltage_scale)
        else:
            # Nighttime => base=0
            base = 0.0

        # ring-mod with mod source
        mod_val = self.get_mod_source_value()
        depth = k1.read_position() / 100.0  # 0..1
        out = self.ring_mod(base, mod_val, depth)

        # foldback
        final = self.foldback(out, max_value=self.voltage_scale)

        # Log changes on minute boundary
        if self.last_minute != minute:
            print(f"[Out1 - Daily LFO] RawBase={base:.2f} RingMod-> {final:.3f} (mod={mod_val:.3f}, depth={depth:.2f}) Time={hour:02}:{minute:02}")
            self.last_daily_voltage = final
            self.last_minute = minute

        cv1.voltage(final)
        self.current_daily_voltage = final
        return final
    
    def minute_to_base(self, m):
        if m < 30:
            return (m / 30.0) * self.voltage_scale
        else:
            return (1.0 - (m - 30)/30.0) * self.voltage_scale

    def interpolate_hourly_base(self, minute, second):
        prev_minute = (minute - 1) % 60
        prev_base = self.minute_to_base(prev_minute)
        curr_base = self.minute_to_base(minute)

        frac = second / 60.0  # 0..1
        return prev_base + (curr_base - prev_base) * frac

    def calculate_hourly_lfo(self):
        _, _, _, hour, minute, second = self.get_current_time()
        if minute is None or second is None:
            return 0

        # 1) Ramped base
        base = self.interpolate_hourly_base(minute, second)

        # 2) Ring mod
        mod_val = self.get_mod_source_value()
        depth = k1.read_position() / 100.0
        out = self.ring_mod(base, mod_val, depth)

        # 3) Foldback
        final = self.foldback(out, max_value=self.voltage_scale)

        # 4) Send to CV2
        cv2.voltage(final)
        self.current_hourly_voltage = final

        # Logging (e.g. once per new minute)
        if minute != self.last_minute:
            print(f"[Out2 - Hourly LFO] base={base:.2f}, mod={mod_val:.2f}, final={final:.2f}, min={minute}, sec={second}")
            self.last_minute = minute

        return final

    def handle_hour_trigger(self):
        """
        At the start of each hour (minute=0, second=0), emit a short pulse on CV3.
        """
        _, _, _, hour, minute, second = self.get_current_time()
        if hour is not None and minute == 0 and second == 0:
            # Only trigger once per hour
            if hour != self.last_hour:
                cv3.voltage(8)   # or whatever pulse voltage you prefer
                time.sleep(0.02) # 20ms pulse
                cv3.voltage(0)
                self.last_hour = hour
                print(f"[Out3 - Hourly Trigger] Hour={hour} at {hour:02}:00:00")


    # -----------------------------------------------------------------------
    # 6) INTERFACE: B2 LONG PRESS, ETC.
    # -----------------------------------------------------------------------

    def handle_b2_long_press(self):
        """
        Toggle between 5V / 10V range on long-press.
        """
        if b2.value() == 1:
            if self.b2_pressed_time is None:
                self.b2_pressed_time = time.ticks_ms()
            else:
                press_duration = time.ticks_diff(time.ticks_ms(), self.b2_pressed_time)
                if press_duration >= 600:
                    self.toggle_voltage_scale()
                    self.b2_pressed_time = None
        else:
            self.b2_pressed_time = None

    def toggle_voltage_scale(self):
        self.voltage_scale = 5 if self.voltage_scale == 10 else 10
        print(f"Voltage scaling toggled to {self.voltage_scale}V")
        self.save_settings()

    # -----------------------------------------------------------------------
    # 7) OLED DISPLAY
    # -----------------------------------------------------------------------

    def update_oled(self):
        """Update OLED display with current state."""
        year, month, day, hour, minute, second = self.get_current_time()
        self.frame.fill(0)  # Clear

        # Show time
        if hour is not None:
            self.frame.text(f"{hour:02}:{minute:02}", 86, 0, 1)
        else:
            self.frame.text("rtc err", 0, 0, 1)

        # Display averaged AIN if > 0
        if self.ain_average > 0:
            # show e.g. "2.45v"
            disp = f"{self.ain_average:.2f}v"
            self.frame.text(disp, 86, 12, 1)

        # Show an arrow for daily LFO rising/falling
        daily_arrow = "-"
        if self.current_daily_voltage > self.last_daily_voltage:
            daily_arrow = "+"
        # Hourly arrow
        hourly_arrow = "-" if self.going_down else "+"

        # Draw LFO bars 
        scale_factor = 24 / self.voltage_scale
        daily_bar_height = int(self.current_daily_voltage * scale_factor)
        hourly_bar_height = int(self.current_hourly_voltage * scale_factor)

        daily_bar_x = 8
        daily_bar_y = 24 - daily_bar_height
        self.frame.fill_rect(daily_bar_x, daily_bar_y, 8, daily_bar_height, 1)
        self.frame.text(f"1{daily_arrow}", 8, 25, 1)

        hourly_bar_x = 28
        hourly_bar_y = 24 - hourly_bar_height
        self.frame.fill_rect(hourly_bar_x, hourly_bar_y, 8, hourly_bar_height, 1)
        self.frame.text(f"2{hourly_arrow}", 28, 25, 1)

        # Show scaling factor
        txt = f"v{self.voltage_scale}"
        if self.voltage_scale == 5:
            self.frame.text(txt, 110, 24, 1)
        else:
            self.frame.text(txt, 102, 24, 1)

        oled.blit(self.frame, 0, 0)
        oled.show()

    def main(self):
        while True:
            self.check_din_rising_edge()  # Poll DIN for rising edges
            self.update_ain_average()    # Update AIN and scenario detection
            self.update_oled()           # Update the OLED display
            self.handle_b2_long_press()  # Handle long press for voltage scaling
            self.calculate_daily_lfo()   # Calculate and output daily LFO
            self.calculate_hourly_lfo()  # Calculate and output hourly LFO
            self.handle_hour_trigger()   # Handle hourly trigger
            time.sleep(0.01)             # Main loop delay for responsiveness


if __name__ == "__main__":
    SolarLFO().main()

