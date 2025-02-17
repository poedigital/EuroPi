from europi import *
from europi_script import EuroPiScript
from experimental.rtc import clock
from framebuf import FrameBuffer, MONO_HLSB
import math
import time
import random

class WindEngine:
    def __init__(self):
        self.intensity = 0     # 0..9
        self.value = 0.0       # current wind value in [0..1]
        self.target = 0.0      # random target in [0..1]
        self.last_target_time = time.ticks_ms()
        self.base_interval = 4000  # slower at intensity=0
        self.alpha_min = 0.005
        self.alpha_max = 0.15
        self.downward_bias_base = 1.5
        self.downward_bias_range = 1.0
        self.modulation_amount = 0.3

    def set_intensity(self, val: int):
        self.intensity = max(0, min(9, val))

    def update(self, mod_val=0.5):
        """Generate and slew a random target with downward bias and optional mod push."""
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self.last_target_time)

        # Interval shortens with intensity
        dynamic_interval = self.base_interval - 200*self.intensity
        if dynamic_interval < 500:
            dynamic_interval = 500

        if elapsed >= dynamic_interval:
            self.last_target_time = now

            # Limit the max random target at low intensity
            max_rand_range = 0.3 + 0.7*(self.intensity/9.0)

            # Downward bias
            exponent = self.downward_bias_base + self.downward_bias_range*(self.intensity/9.0)
            raw = (random.random()**exponent)*max_rand_range

            # Nudged by mod
            nudge = (mod_val - 0.5)*self.modulation_amount
            candidate = raw + nudge
            self.target = max(0.0, min(1.0, candidate))

        # Slew
        alpha = self.alpha_min + (self.alpha_max - self.alpha_min)*(self.intensity/9.0)
        self.value += alpha*(self.target - self.value)
        self.value = max(0.0, min(1.0, self.value))

        return self.value

    def gate_threshold(self):
        """
        At intensity=0 => ~0.95 => rarely triggers gates
        At intensity=9 => ~0.40 => triggers more often
        """
        return 0.95 - 0.055*self.intensity

    def gate_on(self):
        return (self.value > self.gate_threshold())


class SolarLFO(EuroPiScript):
    def __init__(self):
        super().__init__()

        # AIN smoothing
        self.ain_filtered = 0.0
        self.ain_average = 0.0
        self.ain_connected = False

        # DIN
        self.last_din_state = 0
        self.last_din_rising_edge = time.ticks_ms()
        self.din_period = 2000.0
        self.last_din_time = time.ticks_ms()
        self.lfo_phase = 0.0
        self.last_lfo_update = time.ticks_ms()

        # RTC fallback
        if not clock.source:
            print("RTC not initialized, fallback time...")
            clock.source.set_time(year=2025, month=1, day=13,
                                  hour=12, minute=0, second=0)

        # Variables for daily, hourly, and dawn/dusk LFO
        self.current_daily_voltage = 0.0
        self.last_daily_voltage = 0.0

        self.current_hourly_voltage = 0.0
        self.last_hourly_voltage = 0.0

        self.current_dawn_dusk_voltage = 0.0
        self.last_dawn_dusk_voltage = 0.0

        self.current_out5 = 0.0  # wind output level
        self.going_down = False

        # Logging
        self.last_minute = None
        self.last_minute_out4 = None
        self.last_hour = None

        self.voltage_scale = 10
        self.b2_pressed_time = None

        # Load settings
        state = self.load_state_json()
        self.voltage_scale = state.get("voltage_scale", 10)

        # Framebuffer for OLED
        self.buffer = bytearray(OLED_WIDTH * OLED_HEIGHT // 8)
        self.frame = FrameBuffer(self.buffer, OLED_WIDTH, OLED_HEIGHT, MONO_HLSB)

        # Wind
        self.wind = WindEngine()
        self.wind.set_intensity(0)

        # For short-press detection
        self.b1_pressed = False
        self.b1_press_time = 0
        self.b2_pressed = False
        self.b2_press_time = 0
        self.b2_handled_long = False

    # -----------------------------------------------------------------------
    # RTC / Utility
    # -----------------------------------------------------------------------
    def get_current_time(self):
        try:
            dt = clock.source.datetime()
            return dt[:6]
        except:
            return None, None, None, None, None, None

    def save_settings(self):
        state = {"voltage_scale": self.voltage_scale}
        self.save_state_json(state)

    def get_sun_times(self, month):
        data = self.MONTREAL.get(month, {"sunrise": 6.0, "sunset": 18.0})
        return data["sunrise"], data["sunset"]

    MONTREAL = {
        1:  {"sunrise": 7.5, "sunset": 16.6},
        2:  {"sunrise": 7.0, "sunset": 17.2},
        3:  {"sunrise": 6.2, "sunset": 18.0},
        4:  {"sunrise": 5.3, "sunset": 19.0},
        5:  {"sunrise": 4.6, "sunset": 19.8},
        6:  {"sunrise": 4.3, "sunset": 20.3},
        7:  {"sunrise": 4.5, "sunset": 20.2},
        8:  {"sunrise": 5.0, "sunset": 19.6},
        9:  {"sunrise": 5.6, "sunset": 18.7},
        10: {"sunrise": 6.2, "sunset": 17.6},
        11: {"sunrise": 6.9, "sunset": 16.8},
        12: {"sunrise": 7.4, "sunset": 16.2},
    }

    # -----------------------------------------------------------------------
    # DIN
    # -----------------------------------------------------------------------
    def check_din_rising_edge(self):
        current = din.value()
        if current == 1 and self.last_din_state == 0:
            now = time.ticks_ms()
            elapsed = time.ticks_diff(now, self.last_din_rising_edge)
            self.last_din_rising_edge = now
            if elapsed > 10:
                self.din_period = elapsed
            self.last_din_time = now
        self.last_din_state = current

    # -----------------------------------------------------------------------
    # ring_mod & foldback
    # -----------------------------------------------------------------------
    def ring_mod(self, base, mod, depth):
        d = max(0.0, min(1.0, depth))
        bipolar_mod = 2.0*mod - 1.0
        factor = 1.0 + d*bipolar_mod
        return base*factor

    def foldback(self, value, max_value=10.0):
        if value < 0.0:
            folded = -value
            if folded>max_value:
                folded = 2.0*max_value - folded
            return folded
        elif value>max_value:
            folded = 2.0*max_value - value
            if folded<0.0:
                folded = -folded
            return folded
        return value

    # -----------------------------------------------------------------------
    # Internal LFO if no AIN
    # -----------------------------------------------------------------------
    def update_internal_lfo(self):
        now = time.ticks_ms()
        dt_ms = time.ticks_diff(now, self.last_lfo_update)
        self.last_lfo_update = now

        silence_ms = time.ticks_diff(now, self.last_din_time)
        din_active = (silence_ms<2000)

        k2_val = k2.read_position()/100.0
        freq_min, freq_max = 0.01, 1200.0
        freq = freq_min*((freq_max/freq_min)**k2_val)

        if din_active:
            freq_din = 1000.0/max(self.din_period, 1.0)
            multiplier = 1.0+4.0*k2_val
            freq = freq_din*multiplier

        freq = min(freq, 2000.0)

        dt_sec = dt_ms/1000.0
        self.lfo_phase += 2.0*math.pi*freq*dt_sec
        if self.lfo_phase>2.0*math.pi:
            self.lfo_phase -= 2.0*math.pi

        return 0.5*(1.0+math.sin(self.lfo_phase))

    # -----------------------------------------------------------------------
    # AIN
    # -----------------------------------------------------------------------
    def read_ain(self):
        val = ain.read_voltage()
        if val>0.01:
            self.ain_connected = True
            return val/self.voltage_scale
        self.ain_connected = False
        return 0.0

    def update_ain_average(self):
        raw_v = ain.read_voltage()
        self.ain_connected = (raw_v>0.01)
        alpha = 0.1
        self.ain_filtered = (1-alpha)*self.ain_filtered + alpha*raw_v
        self.ain_average = self.ain_filtered/self.voltage_scale

    def get_mod_source_value(self):
        if self.ain_connected:
            atten = k2.read_position()/100.0
            mod_val = self.ain_average*atten
        else:
            mod_val = self.update_internal_lfo()
        return max(0.0, min(1.0, mod_val))

    # -----------------------------------------------------------------------
    # minute_to_base + interpolate_hourly_base for the Hourly LFO
    # -----------------------------------------------------------------------
    def minute_to_base(self, mm):
        """Convert the minute into a 0..voltage_scale range."""
        if mm<30:
            return (mm/30.0)*self.voltage_scale
        else:
            return (1.0 - ((mm-30)/30.0))*self.voltage_scale

    def interpolate_hourly_base(self, mm, ss):
        """Linear interpolation across one minute."""
        prev_m = (mm-1) % 60
        prev_b = self.minute_to_base(prev_m)
        curr_b = self.minute_to_base(mm)
        frac = ss/60.0
        return prev_b + (curr_b - prev_b)*frac

    # -----------------------------------------------------------------------
    # Out1 => daily LFO
    # -----------------------------------------------------------------------
    def calculate_daily_lfo(self):
        y, mo, d, h, m, s = self.get_current_time()
        if h is None:
            return 0

        sunrise, sunset = self.get_sun_times(mo)
        current_time = h+(m/60)+(s/3600)
        if sunrise <= current_time <= sunset:
            day_length = max((sunset-sunrise), 0.001)
            day_phase = (current_time - sunrise)/day_length
            base = max(0, math.sin(math.pi*day_phase)*self.voltage_scale)
        else:
            base = 0.0

        mod_val = self.get_mod_source_value()
        depth = k1.read_position()/100.0
        out = self.ring_mod(base, mod_val, depth)
        final_out = self.foldback(out, self.voltage_scale)

        cv1.voltage(final_out)
        self.last_daily_voltage = self.current_daily_voltage
        self.current_daily_voltage = final_out

        if self.last_minute != m:
            print(f"[Out1 - Daily] base={base:.2f} => {final_out:.3f}, {h:02}:{m:02}")
            self.last_minute = m

        return final_out

    # -----------------------------------------------------------------------
    # Out2 => Dawn/Dusk LFO
    # -----------------------------------------------------------------------
    def calculate_dawn_dusk_lfo(self):
        y, mo, d, h, m, s = self.get_current_time()
        if h is None:
            return 0

        sunrise, sunset = self.get_sun_times(mo)
        current_time = h + (m/60) + (s/3600)
        if current_time<sunrise:
            current_time+=24

        day_length = max(0.001, (sunset - sunrise))
        double_day_phase = ((current_time - sunrise)/(day_length/2)) % 2.0
        wave_phase = double_day_phase%1.0

        base = max(0, math.sin(math.pi*wave_phase)*self.voltage_scale)

        mod_val = self.get_mod_source_value()
        depth = k1.read_position()/100.0
        out = self.ring_mod(base, mod_val, depth)
        final_out = self.foldback(out, self.voltage_scale)

        cv2.voltage(final_out)
        self.last_dawn_dusk_voltage = self.current_dawn_dusk_voltage
        self.current_dawn_dusk_voltage = final_out

        if self.last_minute_out4!=m:
            print(f"[Out2 - DawnDusk] base={base:.2f} => {final_out:.3f}, {h:02}:{m:02} phase={wave_phase:.3f}")
            self.last_minute_out4 = m

        return final_out

    # -----------------------------------------------------------------------
    # Out3 => Hour Trigger
    # -----------------------------------------------------------------------
    def handle_hour_trigger(self):
        y, mo, d, hh, mm, ss = self.get_current_time()
        if hh is not None and mm==0 and ss==0:
            if hh!=self.last_hour:
                cv3.voltage(8)
                time.sleep(0.02)
                cv3.voltage(0)
                self.last_hour = hh
                print(f"[Out3 - HourTrigger] {hh}:00:00")

    # -----------------------------------------------------------------------
    # Out4 => Hourly LFO
    # -----------------------------------------------------------------------
    def calculate_hourly_lfo(self):
        y, mo, d, h, m, s = self.get_current_time()
        if m is None or s is None:
            return 0

        base = self.interpolate_hourly_base(m, s)
        self.going_down = (m>=30)

        mod_val = self.get_mod_source_value()
        depth = k1.read_position()/100.0
        out = self.ring_mod(base, mod_val, depth)
        final_out = self.foldback(out, self.voltage_scale)
        cv4.voltage(final_out)

        self.last_hourly_voltage = self.current_hourly_voltage
        self.current_hourly_voltage = final_out

        if self.last_minute!=m:
            print(f"[Out4 - Hourly] base={base:.2f} => {final_out:.3f}, {h:02}:{m:02}")
            self.last_minute = m

        return final_out

    # -----------------------------------------------------------------------
    # Wind => Out5, Gate => Out6
    # -----------------------------------------------------------------------
    def update_wind(self):
        mod_val = self.get_mod_source_value()
        wval = self.wind.update(mod_val)
        scaled = wval*self.voltage_scale
        cv5.voltage(scaled)
        self.current_out5 = scaled

        if self.wind.gate_on():
            cv6.voltage(5)
        else:
            cv6.voltage(0)

    # -----------------------------------------------------------------------
    # b1 b2 short and long presses
    # -----------------------------------------------------------------------
    def handle_b1_presses(self):
        """
        B1 short => wind intensity--
        B1 long => show tooltip
        """
        if b1.value() == 1 and not self.b1_pressed:
            self.b1_pressed = True
            self.b1_press_time = time.ticks_ms()
        elif b1.value() == 1 and self.b1_pressed:
            diff = time.ticks_diff(time.ticks_ms(), self.b1_press_time)
            if diff >= 600:  # Long press detected
                self.show_tooltip()
        elif b1.value() == 0 and self.b1_pressed:
            diff = time.ticks_diff(time.ticks_ms(), self.b1_press_time)
            self.b1_pressed = False
            if diff < 600:  # Short press
                new_int = self.wind.intensity - 1
                self.wind.set_intensity(new_int)
                print(f"Wind intensity => {self.wind.intensity}")

    def handle_b2_presses(self):
        """B2 short => wind intensity++ ; B2 long => toggle voltage scale"""
        if b2.value()==1 and not self.b2_pressed:
            self.b2_pressed = True
            self.b2_press_time = time.ticks_ms()
            self.b2_handled_long = False
        elif b2.value()==1 and self.b2_pressed:
            diff = time.ticks_diff(time.ticks_ms(), self.b2_press_time)
            if diff>=600 and not self.b2_handled_long:
                self.toggle_voltage_scale()
                self.b2_handled_long = True
        elif b2.value()==0 and self.b2_pressed:
            diff = time.ticks_diff(time.ticks_ms(), self.b2_press_time)
            self.b2_pressed = False
            if diff<600 and not self.b2_handled_long:
                new_int = self.wind.intensity+1
                self.wind.set_intensity(new_int)
                print(f"Wind intensity => {self.wind.intensity}")

    def toggle_voltage_scale(self):
        self.voltage_scale = 5 if self.voltage_scale==10 else 10
        print(f"Voltage scale => {self.voltage_scale}")
        self.save_settings()

    # -----------------------------------------------------------------------
    # OLED RENDERING
    # -----------------------------------------------------------------------
    def render_oled_bar(self, label, x, voltage, scale_factor, arrow):
        height = int(voltage * scale_factor)
        y = 24 - height
        self.frame.fill_rect(x, y, 7, height, 1)
        self.frame.text(f"{label}{arrow}", x, 25, 1)

    def update_oled(self):
        y, mo, d, h, m, s = self.get_current_time()
        self.frame.fill(0)

        if h is not None:
            self.frame.text(f"{h:02}:{m:02}", 86, 0, 1)
        else:
            self.frame.text("rtc err", 0, 0, 1)

        if self.ain_average>0:
            disp = f"{self.ain_average:.2f}v"
            self.frame.text(disp, 86, 12, 1)

        scale_factor = 24/self.voltage_scale

        daily_arrow = "+"
        if self.current_daily_voltage<self.last_daily_voltage:
            daily_arrow="-"

        dawn_dusk_arrow = "+"
        if self.current_dawn_dusk_voltage<self.last_dawn_dusk_voltage:
            dawn_dusk_arrow="-"

        hourly_arrow = "+"
        if self.going_down:
            hourly_arrow="-"

        self.render_oled_bar("1", 4, self.current_daily_voltage, scale_factor, daily_arrow)
        self.render_oled_bar("2", 24, self.current_dawn_dusk_voltage, scale_factor, dawn_dusk_arrow)
        self.render_oled_bar("4", 44, self.current_hourly_voltage, scale_factor, hourly_arrow)
        self.render_oled_bar("5", 64, self.current_out5, scale_factor, "")

        self.frame.text(f"w{self.wind.intensity}", 86, 24, 1)
        vs_text = f"v{self.voltage_scale}"
        self.frame.text(vs_text, 110 if self.voltage_scale==5 else 102, 24, 1)

        oled.blit(self.frame, 0, 0)
        oled.show()

    def show_tooltip(self):
        """
        Display tooltip on OLED for 3 seconds.
        """
        self.frame.fill(0)  # Clear screen

        # Tooltip content
        tooltip_lines = [
            "1: 24h, 2: 12h",
            "4: 1h, 5: rdm",
            "3: 1h trig",
            "6: rdm gate",
        ]

        # Render lines (each 8 pixels tall)
        for i, line in enumerate(tooltip_lines):
            self.frame.text(line, 0, i * 8, 1)

        oled.blit(self.frame, 0, 0)
        oled.show()

        # Keep showing tooltip while B1 is pressed
        while b1.value() == 1:
            time.sleep(0.01)

        # Update the OLED back to the main screen
        self.update_oled()


    # -----------------------------------------------------------------------
    # MAIN
    # -----------------------------------------------------------------------
    def main(self):
        while True:
            self.check_din_rising_edge()
            self.update_ain_average()

            self.handle_b1_presses()
            self.handle_b2_presses()

            self.calculate_daily_lfo()       # Out1
            self.calculate_hourly_lfo()      # Out4
            self.calculate_dawn_dusk_lfo()   # Out2

            self.handle_hour_trigger()
            self.update_wind()
            self.update_oled()

            time.sleep(0.01)

if __name__=="__main__":
    SolarLFO().main()

