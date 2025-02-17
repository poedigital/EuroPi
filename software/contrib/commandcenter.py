from time import ticks_ms, ticks_diff, sleep_ms
import math
from europi import (
    oled, b1, b2,
    cv1, cv2, cv4, cv5, cv3, cv6,
    k1, k2, din, ain
)
from europi_script import EuroPiScript

class CommandCenter(EuroPiScript):
    def __init__(self):
        super().__init__()
        
        # Initialize variables
        self.current_page = 0  # 0: Offsets, 1: Release Times, 2: AIN Amplifiers
        self.total_pages = 2   # Pages 0, 1, and 2

        # Initialize channel settings
        self.channels = {
            1: {
                'cv_offset': 0.0,
                'release_duration': 0.0,  # Default to 1 second
                'voltage_from_offset': 0.0,
                'transition_active': False,
                'transition_start_time': 0,
                'transition_start_value': 0.0,
                'ain_amplifier': 0.0,
                'target_offset': 0.0,
            },
            2: {
                'cv_offset': 0.0,
                'release_duration': 0.0,
                'voltage_from_offset': 0.0,
                'transition_active': False,
                'transition_start_time': 0,
                'transition_start_value': 0.0,
                'ain_amplifier': 0.0,
                'target_offset': 0.0,
            },
        }

        # Initialize knob active flags for soft takeover
        self.k1_active = False
        self.k2_active = False

        # Assign button handlers
        b1.handler(self.prev_page)
        b2.handler(self.next_page)

        # Initialize previous din value
        self.previous_din_value = 0  # For detecting rising edge

        # Initial display update
        self.update_display()
    
    @classmethod
    def display_name(cls):
        return "Command Center"

    def prev_page(self):
        """Select the previous page."""
        self.current_page -= 1
        if self.current_page < 0:
            self.current_page = self.total_pages  # Wrap around to last page
        # Reset knob active flags
        self.k1_active = False
        self.k2_active = False
        self.update_display()
    
    def next_page(self):
        """Select the next page."""
        self.current_page += 1
        if self.current_page > self.total_pages:
            self.current_page = 0  # Wrap around to first page
        # Reset knob active flags
        self.k1_active = False
        self.k2_active = False
        self.update_display()
    
    def update_display(self):
        """Update the OLED display with the current page and parameter values."""
        oled.fill(0)
        if self.current_page == 0:
            # Page 0: Offsets
            oled.text("Offsets", 0, 0)
            # Display values above parameter names
            # Left column (k1)
            oled.text(f"{self.channels[1]['cv_offset']:.2f}V", 0, 10)
            oled.text("1 & 2", 0, 20)
            # Right column (k2)
            oled.text(f"{self.channels[2]['cv_offset']:.2f}V", 64, 10)
            oled.text("4 & 5", 64, 20)
        elif self.current_page == 1:
            # Page 1: Release Times
            oled.text("Release Times", 0, 0)
            # Left column (k1)
            oled.text(f"{self.channels[1]['release_duration']:.2f}s", 0, 10)
            oled.text("1 & 2", 0, 20)
            # Right column (k2)
            oled.text(f"{self.channels[2]['release_duration']:.2f}s", 64, 10)
            oled.text("4 & 5", 64, 20)
        elif self.current_page == 2:
            # Page 2: AIN Amplifiers
            oled.text("ain Amps", 0, 0)
            # Left column (k1)
            oled.text(f"{self.channels[1]['ain_amplifier']*100:.0f}%", 0, 10)
            oled.text("1 & 2", 0, 20)
            # Right column (k2)
            oled.text(f"{self.channels[2]['ain_amplifier']*100:.0f}%", 64, 10)
            oled.text("4 & 5", 64, 20)
        oled.show()
    
    def main(self):
        threshold = 5  # Threshold for knob pickup (soft takeover)
        max_duration = 4.0  # Maximum release duration in seconds

        while True:
            # Read din value
            din_value = din.value()  # Get din value (0 or 1)

            # Process triggers for cv3 and cv6
            if din_value == 1 and self.previous_din_value == 0:
                # Rising edge detected, send triggers to cv3 and cv6
                cv3.on()
                cv6.on()
                sleep_ms(10)  # Adjust the duration as needed
                cv3.off()
                cv6.off()

            # Update previous din value
            self.previous_din_value = din_value

            # Adjust parameters based on current page
            if self.current_page == 0:
                # Page 0: Adjust cv_offset for channels 1 and 2
                k1_value = k1.read_position(1000)
                k2_value = k2.read_position(1000)
                # Channel 1
                if not self.k1_active:
                    stored_knob_position = (self.channels[1]['cv_offset'] / 5.0) * 1000
                    if abs(k1_value - stored_knob_position) < threshold:
                        self.k1_active = True
                if self.k1_active:
                    self.channels[1]['cv_offset'] = (k1_value / 1000) * 5.0  # Map to 0-5V
                # Channel 2
                if not self.k2_active:
                    stored_knob_position = (self.channels[2]['cv_offset'] / 5.0) * 1000
                    if abs(k2_value - stored_knob_position) < threshold:
                        self.k2_active = True
                if self.k2_active:
                    self.channels[2]['cv_offset'] = (k2_value / 1000) * 5.0  # Map to 0-5V
                self.update_display()

            elif self.current_page == 1:
                # Page 1: Adjust release_duration for channels 1 and 2
                k1_value = k1.read_position(1000)
                k2_value = k2.read_position(1000)
                # Channel 1
                if not self.k1_active:
                    stored_knob_position = (self.channels[1]['release_duration'] / max_duration) * 1000
                    if abs(k1_value - stored_knob_position) < threshold:
                        self.k1_active = True
                if self.k1_active:
                    self.channels[1]['release_duration'] = (k1_value / 1000) * max_duration  # Map to 0-4s
                # Channel 2
                if not self.k2_active:
                    stored_knob_position = (self.channels[2]['release_duration'] / max_duration) * 1000
                    if abs(k2_value - stored_knob_position) < threshold:
                        self.k2_active = True
                if self.k2_active:
                    self.channels[2]['release_duration'] = (k2_value / 1000) * max_duration  # Map to 0-4s
                self.update_display()

            elif self.current_page == 2:
                # Page 2: Adjust ain_amplifier for channels 1 and 2
                k1_value = k1.read_position(1000)
                k2_value = k2.read_position(1000)
                # Channel 1
                if not self.k1_active:
                    stored_knob_position = self.channels[1]['ain_amplifier'] * 1000
                    if abs(k1_value - stored_knob_position) < threshold:
                        self.k1_active = True
                if self.k1_active:
                    self.channels[1]['ain_amplifier'] = k1_value / 1000  # Map to 0.0 - 1.0
                # Channel 2
                if not self.k2_active:
                    stored_knob_position = self.channels[2]['ain_amplifier'] * 1000
                    if abs(k2_value - stored_knob_position) < threshold:
                        self.k2_active = True
                if self.k2_active:
                    self.channels[2]['ain_amplifier'] = k2_value / 1000  # Map to 0.0 - 1.0
                self.update_display()

            # Read ain voltage
            try:
                ain_voltage = ain.read_voltage()
            except AttributeError:
                try:
                    ain_voltage = ain.read()  # Fallback method
                except AttributeError:
                    ain_voltage = 0.0  # Default to 0.0V

            # Process channels 1 and 2
            for ch_num in [1, 2]:
                channel = self.channels[ch_num]

                # Check if cv_offset has changed
                if channel['cv_offset'] != channel['target_offset']:
                    # Start transition
                    channel['transition_active'] = True
                    channel['transition_start_time'] = ticks_ms()
                    channel['transition_start_value'] = channel['voltage_from_offset']
                    channel['target_offset'] = channel['cv_offset']

                if channel['transition_active']:
                    elapsed_time = ticks_diff(ticks_ms(), channel['transition_start_time']) / 1000  # in seconds
                    if elapsed_time >= channel['release_duration']:
                        channel['transition_active'] = False
                        channel['voltage_from_offset'] = channel['target_offset']
                    else:
                        # Exponential decay towards target_offset
                        decay_factor = math.exp(-elapsed_time / channel['release_duration']) if channel['release_duration'] > 0 else 0
                        channel['voltage_from_offset'] = channel['target_offset'] + (channel['transition_start_value'] - channel['target_offset']) * decay_factor
                else:
                    # Voltage_from_offset is at target_offset
                    channel['voltage_from_offset'] = channel['target_offset']

                # Compute final voltage
                ain_contribution = ain_voltage * channel['ain_amplifier']
                total_voltage = channel['voltage_from_offset'] + ain_contribution
                total_voltage = min(max(total_voltage, 0.0), 5.0)  # Clamp to 0-5V
                channel['voltage'] = total_voltage

                # Output voltage to appropriate outputs
                if ch_num == 1:
                    cv1.voltage(channel['voltage'])
                    cv2.voltage(channel['voltage'])
                elif ch_num == 2:
                    cv4.voltage(channel['voltage'])
                    cv5.voltage(channel['voltage'])

            # Small delay to prevent CPU overload
            sleep_ms(10)

if __name__ == "__main__":
    CommandCenter().main()
