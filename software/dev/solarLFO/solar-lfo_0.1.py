from europi import *
from europi_script import EuroPiScript
from experimental.rtc import clock
from framebuf import FrameBuffer, MONO_HLSB
import math
import time


class SolarLFO(EuroPiScript):
    def __init__(self):
        super().__init__()

        # Initialize RTC
        if not clock.source:
            print("RTC not initialized, setting fallback time...")
            clock.source.set_time(year=2025, month=1, day=13, hour=12, minute=0, second=0)

        # Internal variables
        self.current_hourly_voltage = 0.0  # Voltage for Out2
        self.current_daily_voltage = 0.0  # Voltage for Out1
        self.going_down = False  # Direction flag for hourly LFO
        self.last_minute = None  # Last processed minute for hourly LFO
        self.last_daily_voltage = None  # Track last daily voltage for logging

        # Framebuffer for the OLED
        self.buffer = bytearray(OLED_WIDTH * OLED_HEIGHT // 8)
        self.frame = FrameBuffer(self.buffer, OLED_WIDTH, OLED_HEIGHT, MONO_HLSB)

    def get_current_time(self):
        """Retrieve the current time from RTC."""
        try:
            datetime = clock.source.datetime()
            return datetime[:6]  # year, month, day, hour, minute, second
        except Exception as e:
            print(f"Error reading RTC: {e}")
            return None, None, None, None, None, None

    def calculate_daily_lfo(self):
        """Calculate the daily voltage for a 24-hour cycle (0–10V)."""
        year, month, day, hour, minute, second = self.get_current_time()

        if hour is not None:
            # Total seconds elapsed in the day
            total_seconds = (hour * 3600) + (minute * 60) + second
            day_phase = total_seconds / (24 * 3600.0)  # Normalize to 24-hour cycle

            # Sinusoidal daily waveform: Peak at 12:00, 0 at 0:00 and 24:00
            daily_voltage = max(0, math.sin(2 * math.pi * day_phase) * 5 + 5)

            # Print only when the voltage changes
            if self.last_daily_voltage is None or daily_voltage != self.last_daily_voltage:
                print(f"[Out1 - Daily LFO] Voltage: {daily_voltage:.5f}V, Time: {hour:02}:{minute:02}:{second:02}")
                self.last_daily_voltage = daily_voltage

            # Update CV1
            cv1.voltage(daily_voltage)
            self.current_daily_voltage = daily_voltage  # Store for OLED update
            return daily_voltage

        return 0

    def calculate_hourly_lfo(self):
        """Calculate a 30-minute linear transition (0–10V, up and down)."""
        _, _, _, _, minute, _ = self.get_current_time()

        if minute is not None:
            increment_value = 10.0 / 30.0  # Increment per minute
            if minute < 30:
                self.going_down = False
                self.current_hourly_voltage = round(minute * increment_value, 5)
            else:
                self.going_down = True
                self.current_hourly_voltage = round(10.0 - ((minute - 30) * increment_value), 5)

            # Ensure voltage stays in range [0, 10]
            self.current_hourly_voltage = max(0, min(10.0, self.current_hourly_voltage))

            # Print voltage on minute change
            if self.last_minute != minute:
                print(f"[Out2 - Hourly LFO] Voltage: {self.current_hourly_voltage:.5f}V, Minute: {minute:02}")
                self.last_minute = minute

            # Update CV2
            cv2.voltage(self.current_hourly_voltage)
            return self.current_hourly_voltage

        return 0

    def handle_hour_trigger(self):
        """Trigger output on CV3 at the top of every hour."""
        _, _, _, hour, minute, _ = self.get_current_time()

        if minute == 0 and self.last_minute != 0:  # Trigger only if we're at m=0 and it's a new hour
            print(f"[Out3 - Hourly Trigger] Hourly Trigger Activated: {hour:02}:00")
            cv3.voltage(5)  # Send a 5V pulse
            time.sleep(0.02)  # Pulse duration: 20ms
            cv3.voltage(0)  # Reset CV3 to 0V

        self.last_minute = minute  # Update last processed minute

    def update_oled(self):
        """Update OLED display with current state."""
        year, month, day, hour, minute, second = self.get_current_time()
        self.frame.fill(0)  # Clear OLED content

        # Display current time (hh:mm)
        if hour is not None:
            self.frame.text(f"{hour:02}:{minute:02}", 86, 0, 1)
        else:
            self.frame.text("rtc error", 0, 0, 1)

        # Draw vertical bars for Out1 (daily) and Out2 (hourly)
        # Out1 (daily cycle) - Left bar
        daily_bar_height = int((self.current_daily_voltage / 10.0) * 24)
        daily_bar_x = 0  # Left bar position
        daily_bar_y = 24 - daily_bar_height
        self.frame.fill_rect(daily_bar_x, daily_bar_y, 8, daily_bar_height, 1)
        self.frame.rect(daily_bar_x, 0, 8, 24, 1)
        self.frame.text(f"1", 0, 25, 1)

        # Out2 (hourly cycle) - Right bar
        hourly_bar_height = int((self.current_hourly_voltage / 10.0) * 24)
        hourly_bar_x = 16  # Right bar position (8px gap)
        hourly_bar_y = 24 - hourly_bar_height
        self.frame.fill_rect(hourly_bar_x, hourly_bar_y, 8, hourly_bar_height, 1)
        self.frame.rect(hourly_bar_x, 0, 8, 24, 1)
        self.frame.text(f"2", 16, 25, 1)

        # Show the OLED buffer
        oled.blit(self.frame, 0, 0)
        oled.show()

    def main(self):
        """Main loop to update outputs and OLED display."""
        while True:
            self.update_oled()  # Update OLED
            self.calculate_daily_lfo()  # Update CV1 (daily cycle)
            self.calculate_hourly_lfo()  # Update CV2 (hourly cycle)
            self.handle_hour_trigger()  # Check and trigger hourly pulse on CV3
            time.sleep(1)  # Main loop delay


if __name__ == "__main__":
    SolarLFO().main()
