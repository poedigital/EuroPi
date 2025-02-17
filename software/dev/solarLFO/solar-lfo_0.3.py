from europi import *
from europi_script import EuroPiScript
from experimental.rtc import clock
from framebuf import FrameBuffer, MONO_HLSB
import math
import time


class SolarLFO(EuroPiScript):
    def __init__(self):
        super().__init__()
        self.ain_samples = []
        self.last_ain_update = time.ticks_ms()
        self.ain_average = 0.0
        self.ain_modulation = 0.0  # Current modulation from AIN
        self.ain_connected = False  # Flag for AIN connection state
        self.current_pitch = 1.0  # Center frequency

        self.last_din_state = 0  # For detecting DIN edges
        self.last_din_rising_edge = time.ticks_ms()
        self.din_period = 1.0  # Default DIN clock period (1 second)


        # Initialize RTC
        if not clock.source:
            print("RTC not initialized, setting fallback time...")
            clock.source.set_time(year=2025, month=1, day=13, hour=12, minute=0, second=0)

        # Internal variables
        self.current_hourly_voltage = 0.0  # Voltage for Out2
        self.current_daily_voltage = 0.0  # Voltage for Out1
        self.going_down = False  # Direction flag for hourly LFO
        self.last_minute = None  # Last processed minute for hourly LFO
        self.last_daily_voltage = 0.0  # Default to 0.0 for safe comparison
        self.last_hour = None  # Track last hour for hourly trigger on Out3
        self.voltage_scale = 10  # Default scale is 10V
        self.b2_pressed_time = None  # Track the time when b2 is pressed
        
        # Load settings
        state = self.load_state_json()
        self.voltage_scale = state.get("voltage_scale", 10)  # Default to 10V

        # Framebuffer for the OLED
        self.buffer = bytearray(OLED_WIDTH * OLED_HEIGHT // 8)
        self.frame = FrameBuffer(self.buffer, OLED_WIDTH, OLED_HEIGHT, MONO_HLSB)

    def get_current_time(self):
        try:
            datetime = clock.source.datetime()
            return datetime[:6]  # year, month, day, hour, minute, second
        except Exception as e:
            print(f"Error reading RTC: {e}")
            return None, None, None, None, None, None
 
    def save_settings(self):
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


    """
    ======
    INPUTS
    ======
    """
        
    def read_ain(self):
        """Read and normalize AIN value."""
        ain_value = ain.read_voltage()  # Read AIN voltage (0-10V)
        if ain_value > 0.01:  # Threshold to detect if something is plugged in
            self.ain_connected = True
            return ain_value / self.voltage_scale  # Normalize to 0-1
        self.ain_connected = False
        return 0.0

    def update_ain_average(self):
        now = time.ticks_ms()
        ain_value = self.read_ain()
        self.ain_samples.append(ain_value)

        if time.ticks_diff(now, self.last_ain_update) >= 500:
            if self.ain_samples:
                self.ain_average = sum(self.ain_samples) / len(self.ain_samples)
                self.ain_samples.clear()  # Clear samples for the next second
            else:
                self.ain_average = 0.0  # No data, default to 0
            self.last_ain_update = now  # Update the last update time



        """
        =========
        INTERFACE
        =========
        """

    def handle_b2_long_press(self):
        if b2.value() == 1:
            if self.b2_pressed_time is None:
                self.b2_pressed_time = time.ticks_ms()
            else:
                press_duration = time.ticks_diff(time.ticks_ms(), self.b2_pressed_time)
                if press_duration >= 600:  # Long press threshold (600ms)
                    self.toggle_voltage_scale()
                    self.b2_pressed_time = None
        else:
            self.b2_pressed_time = None

    def toggle_voltage_scale(self):
        self.voltage_scale = 5 if self.voltage_scale == 10 else 10
        print(f"Voltage scaling toggled to {self.voltage_scale}V")
        self.save_settings()


        """
        =======
        OUTPUTS
        =======
        """

        """out1"""
    def calculate_daily_lfo(self):
        year, month, day, hour, minute, second = self.get_current_time()

        if hour is not None:
            # Get sunrise and sunset for the current month
            sunrise, sunset = self.get_sun_times(month)

            # Convert current time to decimal hours
            current_time = hour + (minute / 60) + (second / 3600)

            if sunrise <= current_time <= sunset:
                # Normalize time within the daylight period
                day_length = sunset - sunrise
                day_phase = (current_time - sunrise) / day_length  # 0.0 to 1.0

                # Sinusoidal waveform: Peak at solar noon
                daily_voltage = max(0, math.sin(math.pi * day_phase) * self.voltage_scale)

                # Log and update only when the minute changes
                if self.last_minute != minute:
                    print(f"[Out1 - Daily LFO] Voltage: {daily_voltage:.5f}V, Time: {hour:02}:{minute:02}")
                    self.last_daily_voltage = daily_voltage
                    self.last_minute = minute

                # Update CV1
                cv1.voltage(daily_voltage)
                self.current_daily_voltage = daily_voltage
                return daily_voltage
            else:
                # Outside daylight hours, voltage is 0
                if self.current_daily_voltage != 0:
                    print(f"[Out1 - Daily LFO] Voltage: 0.00000V (Nighttime), Time: {hour:02}:{minute:02}")
                self.current_daily_voltage = 0
                cv1.voltage(0)
                return 0

        return 0


        """out2"""
    def calculate_hourly_lfo(self):
        _, _, _, _, minute, _ = self.get_current_time()

        if minute is not None:
            increment_value = self.voltage_scale / 30.0  # Increment per minute
            if minute < 30:
                self.going_down = False
                self.current_hourly_voltage = round(minute * increment_value, 5)
            else:
                self.going_down = True
                self.current_hourly_voltage = round(self.voltage_scale - ((minute - 30) * increment_value), 5)

            # Ensure voltage stays in range [0, voltage_scale]
            self.current_hourly_voltage = max(0, min(self.voltage_scale, self.current_hourly_voltage))

            # Print voltage on minute change
            if self.last_minute != minute:
                print(f"[Out2 - Hourly LFO] Voltage: {self.current_hourly_voltage:.5f}V, Minute: {minute:02}")
                self.last_minute = minute

            # Update CV2
            cv2.voltage(self.current_hourly_voltage)
            return self.current_hourly_voltage

        return 0

        """out3"""
    def handle_hour_trigger(self):
        _, _, _, hour, minute, second = self.get_current_time()
        if minute == 0 and second == 0:  # Trigger only at the start of the hour
            if hour != self.last_hour:  # Ensure the trigger is only fired once per hour
                cv3.voltage(8)  # 8V pulse
                time.sleep(0.02)  # Pulse duration: 20ms
                cv3.voltage(0)  # Reset CV3 to 0V
                self.last_hour = hour
                print(f"[Out3 - Hourly Trigger] Hour: {hour} Triggered at {hour:02}:00:00")

        """
        =======
        DISPLAY
        =======
        """

    def update_oled(self):
        """Update OLED display with current state."""
        year, month, day, hour, minute, second = self.get_current_time()
        self.frame.fill(0)  # Clear OLED content

        # Display current time (hh:mm)
        if hour is not None:
            self.frame.text(f"{hour:02}:{minute:02}", 86, 0, 1)
        else:
            self.frame.text("rtc error", 0, 0, 1)

        # Display averaged AIN value below the clock only if it's non-zero
        if self.ain_average > 0:
            ain_display = f"{self.ain_average:.2f}v"
            self.frame.text(ain_display, 86, 12, 1)

        # Determine arrows for daily and hourly LFOs
        daily_arrow = "+" if self.current_daily_voltage > self.last_daily_voltage else "-"
        hourly_arrow = "+" if not self.going_down else "-"


        # Draw LFO bars (existing logic for daily/hourly LFO visualization)
        scale_factor = 24 / self.voltage_scale  # Normalize height to fit display (24px max)
        daily_bar_height = int(self.current_daily_voltage * scale_factor)
        hourly_bar_height = int(self.current_hourly_voltage * scale_factor)

        daily_bar_height = int(self.current_daily_voltage * scale_factor)
        daily_bar_x = 8  # Left bar position
        daily_bar_y = 24 - daily_bar_height
        self.frame.fill_rect(daily_bar_x, daily_bar_y, 8, daily_bar_height, 1)
        self.frame.text(f"1{daily_arrow}", 8, 25, 1)

        # Out2 (hourly cycle) - Right bar
        hourly_bar_height = int(self.current_hourly_voltage * scale_factor)
        hourly_bar_x = 28  # Right bar position (8px gap)
        hourly_bar_y = 24 - hourly_bar_height
        self.frame.fill_rect(hourly_bar_x, hourly_bar_y, 8, hourly_bar_height, 1)
        self.frame.text(f"2{hourly_arrow}", 28, 25, 1)

        # Display the scaling factor
        if self.voltage_scale == 10:
            self.frame.text(f"v{self.voltage_scale}", 102, 24, 1)  # Position for 10V
        else:
            self.frame.text(f"v{self.voltage_scale}", 110, 24, 1)  # Position for 5V

        # Show the OLED buffer
        oled.blit(self.frame, 0, 0)
        oled.show()

    def main(self):
        while True:
            self.update_ain_average()  # Update AIN average
            self.update_oled()  # Update OLED
            self.calculate_daily_lfo()  # Update CV1 (daily cycle)
            self.calculate_hourly_lfo()  # Update CV2 (hourly cycle)
            self.handle_hour_trigger()  # Check and trigger hourly pulse on CV3
            self.handle_b2_long_press()  # Detect and handle b2 long press
            time.sleep(0.01)  # Main loop delay for responsiveness


if __name__ == "__main__":
    SolarLFO().main()