from europi import *
from time import ticks_diff, ticks_ms, sleep_ms
from europi_script import EuroPiScript
import struct
from array import array


class ToasterMessage:
    def __init__(self, text, duration_ms):
        self.text = text
        self.display_until = ticks_ms() + duration_ms

class ButtonHandler:
    """
    Handles button press events, distinguishing between short and long presses.
    Long presses trigger the callback on release after holding the button down for the specified duration.
    """
    def __init__(self, pin, short_press_callback=None, long_press_callback=None, long_press_duration=1000):
        self.pin = pin
        self.short_press_callback = short_press_callback
        self.long_press_callback = long_press_callback
        self.long_press_duration = long_press_duration

        self.last_state = self.pin.value()
        self.pressed_time = None

    def update(self):
        current_state = self.pin.value()
        current_time = ticks_ms()

        if current_state != self.last_state:
            # State changed
            if current_state == 1:
                # Button pressed
                self.pressed_time = current_time
            else:
                # Button released
                if self.pressed_time is not None:
                    press_duration = ticks_diff(current_time, self.pressed_time)
                    if press_duration >= self.long_press_duration:
                        if self.long_press_callback:
                            self.long_press_callback()
                    else:
                        if self.short_press_callback:
                            self.short_press_callback()
                self.pressed_time = None

        self.last_state = current_state


class CVSeq(EuroPiScript):

    def __init__(self):
        super().__init__()

        # Initialize current_time to prevent AttributeError
        self.current_time = ticks_ms()
        self.clock_event = False  # Initialize the clock event flag
        self.last_activity_time = ticks_ms()  # Track the last time of activity

        # Define CV output channels in the desired order: 1, 2, 4, 5, 3, 6
        self.output_channels = [1, 2, 4, 5, 3, 6]  # Channels 3 and 6 added
        self.cv_channels = [cv1, cv2, cv4, cv5, cv3, cv6]  # Corresponding CV outputs

        self.numCVR = 6       # Updated to 6 channels
        self.numCVRBanks = 6  # Number of CV recording channel banks (0-5)

        # Define Trigger CV outputs 3 & 6
        self.trigger_duration = 22  # in milliseconds
        self.cv3_trigger_on_time = None  # Initialize cv6_trigger_on_time
        self.cv6_trigger_on_time = None  # Initialize cv6_trigger_on_time
        self.next_trigger_time_cv6 = None  # Schedule time for CV6 reset trigger

        self.arm_record = False
        self.recording = False

        # Initialize Seqs
        self.clockStep = 0
        self.ActiveCvr = 0
        self.ActiveBank = 0
        self.resetTimeout = 512  # in milliseconds
        self.CvIn = 0
        self.bankToSave = 0
        self.MAX_STEPS = 256  # Maximum number of steps (32 bars * 8 steps)
        self.sequence_lengths = [16, 32, 48, 64, 128]  # Corresponds to 1,2,3,4,8
        self.ch6_reset_enabled = True  # Initialize channel 6 reset as enabled

        # Initialize CV recordings and recording flags for 6 channels
        self.CVR = [
            [
                array('f', [0.0] * self.MAX_STEPS) for _ in range(self.numCVR)
            ] for _ in range(self.numCVRBanks)
        ]
        
        self.CvRecording = [['false'] * self.numCVR
                            for _ in range(self.numCVRBanks)]


        # Initialize buttons using the ButtonHandler class
        self.button1 = ButtonHandler(
            pin=b1,
            short_press_callback=self.toggle_recording,
            long_press_callback=self.reset_sequence,
            long_press_duration=444  # milliseconds
        )
        self.button2 = ButtonHandler(
            pin=b2,
            short_press_callback=self.increment_channel_length,
            long_press_callback=self.confirmDelete,
            long_press_duration=444  # milliseconds
        )
        
        self.last_knob_read_time = 0
        self.knob_read_interval = 64  # milliseconds
        
        self.current_message = None
        self.channel_lengths = [16] * self.numCVR  # Default length for each channel
        self.channel_steps = [0] * self.numCVR    # Step counter for each channel

        # Initialize display update flags
        self.static_display_needs_update = True
        self.dynamic_display_needs_update = True
        self.last_display_update = ticks_ms()
        self.display_update_interval = 22  # Approximately 30 updates per second

        # Screensaver variables
        self.screensaver_active = False
        self.screensaver_last_update = ticks_ms()
        self.screensaver_interval = 512  # milliseconds between frames
        self.screensaver_frames = [' ', ' ', '.', '..', '...']
        self.screensaver_frame_index = 0
        self.screensaver_timeout = 10000  # milliseconds (10 seconds of inactivity)
        self.last_activity_time = ticks_ms()

        self.voltage_ranges = [
            (0.1, '.'),
            (1.4, ','),
            (2.9, 'o'),
            (5.0, 'O'),
            (6.5, '0'),
            (9.5, '@')
        ]

        din.handler(self.dInput)

        self.loadState(self.ActiveBank)

    def dInput(self, *args):
        """Handle digital input triggers."""
        self.clock_event = True
        self.last_activity_time = ticks_ms()  # Update activity time
        self.screensaver_active = False  # Deactivate screensaver

    def reset_sequence(self):
        """Reset the sequence counters to 0 and send a trigger to cv6."""
        for i in range(self.numCVR):
            self.channel_steps[i] = 0  # Reset step counters for all channels
        self.clockStep = 0
        current_time = ticks_ms()  # Fetch current time
        self.triggerCV6(current_time)  # Pass current_time
        self.show_message('seq. reset', duration_ms=256)
        self.last_activity_time = current_time  # Update activity time
        self.screensaver_active = False  # Deactivate screensaver

    def triggerCV3(self, current_time):
        """Send a trigger out of CV3 for a short duration."""
        if self.cv3_trigger_on_time is None:
            self.cv3_trigger_on_time = current_time  # Record the time the trigger was turned on
            self.cv_channels[4].voltage(5)  # Set CV3 voltage to 5V (index 4 corresponds to CV3)

    def triggerCV6(self, current_time):
        """Send a trigger out of CV6 for a short duration."""
        if self.cv6_trigger_on_time is None:
            self.cv6_trigger_on_time = current_time  # Record the time the trigger was turned on
            self.cv_channels[5].voltage(5)  # Set CV6 voltage to 5V (index 5 corresponds to CV6)

    def handleClock(self, current_time):
        """Handle incoming clock triggers, manage CV recordings, and trigger CV6 when appropriate."""
        self.CvIn = round(ain.read_voltage(), 5)  # Sample CV input with high precision

        # Start recording if armed and at the first step
        if self.channel_steps[self.ActiveCvr] == 0 and self.CvRecording[self.ActiveBank][self.ActiveCvr] == 'pending':
            self.CvRecording[self.ActiveBank][self.ActiveCvr] = 'true'

        # Pre-create a zero array for efficiency
        zero_array = array('f', [0.0] * self.MAX_STEPS)

        # Iterate through all CV channels (1,2,4,5,3,6)
        for i in range(self.numCVR):
            channel_number = self.output_channels[i]

            # **1. Record or Playback CV Values BEFORE advancing the step**
            if self.CvRecording[self.ActiveBank][i] == 'true':
                self.CVR[self.ActiveBank][i][self.channel_steps[i]] = self.CvIn  # Store CV input
                self.cv_channels[i].voltage(self.CvIn)  # Output CV
            else:
                self.cv_channels[i].voltage(self.CVR[self.ActiveBank][i][self.channel_steps[i]])  # Playback stored CV

            # **2. Handle Triggers Based on the Current Step**
            if self.channel_steps[i] == self.channel_lengths[i] - 1:
                if channel_number == 6 and self.ch6_reset_enabled:
                    self.next_trigger_time_cv6 = current_time + 20  # 20 ms delay

                # **CV3 Code Remains Unchanged**
                if channel_number == 3:
                    if self.arm_record and not self.recording:
                        self.recording = True
                        self.triggerCV3(current_time)  # Activate CV3 Trigger
                        self.arm_record = False  # Disarm after first trigger
                    elif self.recording:
                        self.triggerCV3(current_time)  # Activate CV3 Trigger
                        self.recording = False  # End recording state

            # **3. Advance the Step Counter AFTER triggers**
            self.channel_steps[i] = (self.channel_steps[i] + 1) % self.channel_lengths[i]

            # **4. Stop Recording if Active**
            if self.channel_steps[i] == 0 and self.CvRecording[self.ActiveBank][i] == 'true':
                self.CvRecording[self.ActiveBank][i] = 'false'
                self.saveState(bank=self.ActiveBank)

    def get_bar_length(self):
        """Convert current loop length in triggers to bars."""
        triggers_per_bar = 16
        bars = self.channel_lengths[self.ActiveCvr] // triggers_per_bar
        return bars

    def increment_channel_length(self):
        """Cycle the length of the currently selected channel through 1,2,3,4,8 bars."""
        current_length = self.channel_lengths[self.ActiveCvr]
        sequence = self.sequence_lengths
        try:
            current_index = sequence.index(current_length)
            next_index = (current_index + 1) % len(sequence)
        except ValueError:
            next_index = 0

        self.channel_lengths[self.ActiveCvr] = sequence[next_index]
        self.static_display_needs_update = True
        self.dynamic_display_needs_update = True
        self.saveState(self.ActiveBank)
        self.last_activity_time = ticks_ms()  # Update activity time
        self.screensaver_active = False  # Deactivate screensaver
        
    def toggle_recording(self):
        """Toggle recording for the current CV channel, and handle channel 6 reset toggle."""
        active_channel = self.output_channels[self.ActiveCvr]

        self.last_activity_time = ticks_ms()  # Update activity time
        self.screensaver_active = False  # Deactivate screensaver

        if active_channel == 6:
            # Toggle ch6 reset
            self.ch6_reset_enabled = not self.ch6_reset_enabled
            if self.ch6_reset_enabled:
                self.show_message("ch6 reset on", duration_ms=512)
            else:
                self.show_message("ch6 reset off", duration_ms=512)
            return

        if active_channel == 3:
            # Existing code for channel 3
            if not self.arm_record:
                self.arm_record = True  # Arm for recording
                self.recording = False  # Ensure we're not already in recording state
            else:
                self.arm_record = False  # Disarm if already armed
            self.static_display_needs_update = True
            self.dynamic_display_needs_update = True
            # Immediate state saving
            self.saveState(self.ActiveBank)
            return

        # Else, handle normal CV channel recording
        current_status = self.CvRecording[self.ActiveBank][self.ActiveCvr]
        if current_status == 'false':
            self.CvRecording[self.ActiveBank][self.ActiveCvr] = 'pending'
        elif current_status == 'pending':
            self.CvRecording[self.ActiveBank][self.ActiveCvr] = 'false'
        self.static_display_needs_update = True
        self.dynamic_display_needs_update = True
        # Immediate state saving
        self.saveState(self.ActiveBank)


    def saveState(self, bank):
        """Save CVR data and channel loop lengths for a specific bank to a binary file."""
        outputFile = f"saved_state_CVSeq2_bank_{bank}.bin"
        try:
            with open(outputFile, 'wb') as file:
                for c in range(self.numCVR):
                    # Pack loop length as unsigned short (little-endian)
                    loop_length = self.channel_lengths[c]
                    file.write(struct.pack('<H', loop_length))

                    # Write CVR data per float
                    cvr_data_array = self.CVR[bank][c][:loop_length]
                    for voltage in cvr_data_array:
                        file.write(struct.pack('<f', voltage))
        except Exception as e:
            self.show_message(f"Save Error: {str(e)}", duration_ms=500)
            print(f"Error saving bank {bank}: {e}")

    def loadState(self, bank):
        """Load CVR data and channel loop lengths for a specific bank from a binary file."""
        outputFile = f"saved_state_CVSeq2_bank_{bank}.bin"

        try:
            with open(outputFile, 'rb') as file:
                for c in range(self.numCVR):
                    # Unpack loop length
                    loop_length_bytes = file.read(2)
                    if not loop_length_bytes or len(loop_length_bytes) != 2:
                        raise ValueError("Unexpected end of file when reading loop length.")
                    loop_length = struct.unpack('<H', loop_length_bytes)[0]
                    self.channel_lengths[c] = loop_length

                    # Read CVR data per float
                    cvr_data_array = array('f')
                    for _ in range(loop_length):
                        voltage_bytes = file.read(4)
                        if not voltage_bytes or len(voltage_bytes) != 4:
                            raise ValueError("Unexpected end of file when reading CVR data.")
                        voltage = struct.unpack('<f', voltage_bytes)[0]
                        cvr_data_array.append(voltage)

                    # Assign to the array slice
                    self.CVR[bank][c][:loop_length] = cvr_data_array
        except (OSError, ValueError):
            # Initialize default states if the file is not found or is incomplete
            self.initializeDefaultStates(bank)
        except Exception as e:
            self.show_message(f"Load Error: {str(e)}", duration_ms=500)
            print(f"Error loading bank {bank}: {e}")

    def initializeDefaultStates(self, bank=None):
        """Initialize all CVR data and loop lengths to default values for a specific bank or all banks."""
        if bank is not None:
            # Initialize default values for a specific bank
            for i in range(self.numCVR):
                self.CvRecording[bank][i] = 'false'  # Reset recording status
                self.CVR[bank][i] = array('f', [0.0] * self.MAX_STEPS)  # Reset CV values as array
                self.channel_lengths[i] = 16  # Set default length to 16 steps (1 bar)
                self.channel_steps[i] = 0  # Reset step counters
            self.saveState(bank)  # Save the initialized default states for this bank
        else:
            # Initialize defaults for all banks
            self.CVR = [
                [array('f', [0.0] * self.MAX_STEPS) for _ in range(self.numCVR)]
                for _ in range(self.numCVRBanks)
            ]
            self.CvRecording = [['false'] * self.numCVR for _ in range(self.numCVRBanks)]
            self.channel_lengths = [16] * self.numCVR  # Set to 1 bar (16 steps)
            self.channel_steps = [0] * self.numCVR    # Reset step counters

            for bank in range(self.numCVRBanks):
                self.saveState(bank)  # Save default states for each bank

    def increment_channel(self):
        """Increment the active CV channel, cycling through 1,2,4,5,3,6"""
        self.ActiveCvr = (self.ActiveCvr + 1) % len(self.output_channels)  # cycles 0-5
        self.static_display_needs_update = True
        self.dynamic_display_needs_update = True
        self.saveState(self.ActiveBank)
        self.last_activity_time = ticks_ms()  # Update activity time
        self.screensaver_active = False  # Deactivate screensaver

    def getCvBank(self):
        self.ActiveBank = k2.read_position(self.numCVRBanks)

    def confirmDelete(self):
        """Clear the current bank and display a confirmation message."""
        # Clear the active bank
        self.clearCvrs(self.ActiveBank)

        # Display confirmation message using the toaster system
        self.show_message('bank cleared', duration_ms=400)
        self.last_activity_time = ticks_ms()  # Update activity time
        self.screensaver_active = False  # Deactivate screensaver

    def clearCvrs(self, bank):
        """Clear CV recordings for the specified bank without resetting sequence timing."""
        for i in range(self.numCVR):
            self.CvRecording[bank][i] = 'false'  # Reset recording status
            # Efficiently reset all CV values in the channel
            self.CVR[bank][i] = array('f', [0.0] * self.MAX_STEPS)
            
        self.bankToSave = bank
        self.saveState(bank)
        self.last_activity_time = ticks_ms()  # Update activity time
        self.screensaver_active = False  # Deactivate screensaver

    def updateScreen(self, current_time):
        """
        Update the OLED display. If the screensaver is active, display the animation.
        Otherwise, display the normal UI elements.
        """
        if self.screensaver_active:
            # Update screensaver animation
            if ticks_diff(current_time, self.screensaver_last_update) >= self.screensaver_interval:
                oled.fill(0)  # Clear the screen
                frame = self.screensaver_frames[self.screensaver_frame_index]
                text_width = len(frame) * 6  # Approximate width (6px per character)
                x_position = max((128 - text_width) // 2, 0)  # Centered
                oled.text(frame, x_position, 12, 1)  # y=12 for vertical centering
                oled.show()
                self.screensaver_frame_index = (self.screensaver_frame_index + 1) % len(self.screensaver_frames)
                self.screensaver_last_update = current_time
        else:
            if self.current_message:
                self.updateToasterMessage(current_time)
            else:
                if self.static_display_needs_update:
                    self.updateStaticDisplay()
                if self.dynamic_display_needs_update:
                    self.updateDynamicDisplay()

    def updateToasterMessage(self, current_time):
        if self.current_message and current_time < self.current_message.display_until:
            oled.fill(0)  # Clear the screen
            message = self.current_message.text
            text_width = len(message) * 6  # Approximate width (6px per character)
            x_position = max((128 - text_width) // 2 - 10, 0)  # Centered with left adjustment
            oled.text(message, x_position, 12, 1)  # y=12 for vertical centering
            oled.show()
        else:
            self.current_message = None  # Clear the message
            self.static_display_needs_update = True
            self.dynamic_display_needs_update = True

    def show_message(self, text, duration_ms=1024):
        """Display a toaster message for a specified duration."""
        self.current_message = ToasterMessage(text, duration_ms)
        self.static_display_needs_update = True
        self.dynamic_display_needs_update = True
        self.last_activity_time = ticks_ms()  # Reset inactivity timer
        self.screensaver_active = False  # Deactivate screensaver

    def updateStaticDisplay(self):
        """
        Update the static parts of the display (e.g., labels and outlines).
        """
        oled.fill(0)  # Clear the screen

        y_bottom = 25  # y position for bottom row

        # **i. Bank Indicator**
        oled.text("ba", 91, y_bottom, 1)  # Normal "ba" text
        # Draw background rectangle for bank number
        oled.fill_rect(110, y_bottom - 1, 10, 12, 1)  # White background

        # **ii. Channel Indicator**
        oled.text("ch", 3, y_bottom, 1)  # Normal "ch" text
        # Draw background rectangle for channel number
        oled.fill_rect(22, y_bottom - 1, 10, 12, 1)  # White background

        # **iii. Progress Bar Outline**
        progress_bar_x = 40
        progress_bar_y = y_bottom + 2
        progress_bar_width = 48
        progress_bar_height = 4

        # Draw progress bar outline
        oled.rect(progress_bar_x, progress_bar_y, progress_bar_width, progress_bar_height, 1)  # Outline

        self.static_display_needs_update = False

    def updateDynamicDisplay(self):
        """
        Update the dynamic parts of the display (e.g., active channel, progress bar, voltage symbols).
        """
        if self.current_message or self.screensaver_active:
            return  # Toaster message or screensaver is being displayed

        y_bottom = 25  # y position for bottom row
        progress_bar_x = 40
        progress_bar_y = y_bottom + 2
        progress_bar_width = 48
        progress_bar_height = 4

        # Update Bank Indicator - value
        oled.fill_rect(110, y_bottom - 1, 10, 12, 1)  # White background
        oled.text(f"{self.ActiveBank + 1}", 111, y_bottom, 0)  # Black text for the bank number

        # Update Channel Indicator - value
        oled.fill_rect(22, y_bottom - 1, 10, 12, 1)  # White background
        oled.text(f"{self.output_channels[self.ActiveCvr]}", 23, y_bottom, 0)  # Black text for the channel number

        # Update Progress Bar
        active_channel_loop_length = self.channel_lengths[self.ActiveCvr]
        active_channel_step = self.channel_steps[self.ActiveCvr]
        progress_width = int((active_channel_step / active_channel_loop_length) * progress_bar_width) if active_channel_loop_length else 0

        # Clear previous progress bar area
        oled.fill_rect(progress_bar_x + 1, progress_bar_y + 1, progress_bar_width - 2, progress_bar_height - 2, 0)  # Clear inside the outline
        # Draw filled portion
        oled.fill_rect(progress_bar_x + 1, progress_bar_y + 1, progress_width - 2, progress_bar_height - 2, 1)  # Filled portion

        # Update Voltage Symbols
        symbol_positions = [4, 18, 32, 46, 64, 78]
        y_dot = 3  # y position for the dots

        for i in range(self.numCVR):
            voltage = self.CVR[self.ActiveBank][i][self.channel_steps[i]] if self.channel_steps[i] < len(self.CVR[self.ActiveBank][i]) else 0.0
            is_recording = (self.CvRecording[self.ActiveBank][i] == 'true' and self.ActiveCvr == i)
            symbol = self.map_voltage_to_symbol(voltage, is_recording, i)

            # Invert color for the active channel (white background, black text)
            if i == self.ActiveCvr:
                oled.fill_rect(symbol_positions[i] - 2, 0, 14, 12, 1)  # White background for active channel
                oled.text(symbol, symbol_positions[i], y_dot, 0)  # Inverted (black text on white background)
            else:
                # Clear previous symbol
                oled.fill_rect(symbol_positions[i], y_dot, 8, 8, 0)
                oled.text(symbol, symbol_positions[i], y_dot, 1)  # Normal (white text on black background)

        # Update Loop Length Counters
        y_counter = 14  # y position for loop lengths

        for i in range(self.numCVR):
            loop_length_bars = self.channel_lengths[i] // 16  # Assuming 16 triggers per bar
            # Clear previous loop length
            oled.fill_rect(symbol_positions[i], y_counter, 8, 8, 0)
            oled.text(f"{loop_length_bars}", symbol_positions[i], y_counter, 1)

        # Update REC/ARM Indicators
        rec_arm_x = 100
        y_rec_arm_row1 = 13  # Align with y_dot

        channel_rec_status = self.CvRecording[self.ActiveBank][self.ActiveCvr]

        # Clear previous status
        oled.fill_rect(rec_arm_x, y_rec_arm_row1, 30, 12, 0)

        if self.recording:
            oled.text('NEB', rec_arm_x, y_rec_arm_row1, 1)  # Nebulae is recording
        elif self.arm_record:
            oled.text('arm', rec_arm_x, y_rec_arm_row1, 1)  # Nebulae is armed
        elif channel_rec_status == 'true':
            oled.text('REC', rec_arm_x, y_rec_arm_row1, 1)  # Channel is recording
        elif channel_rec_status == 'pending':
            oled.text('arm', rec_arm_x, y_rec_arm_row1, 1)  # Channel is armed
        else:
            oled.text('---', rec_arm_x, y_rec_arm_row1, 1)  # No status

        # Update Voltage Reading
        ain_voltage = round(ain.read_voltage(), 1)  # Read and round the voltage to one decimal place

        # Clear previous voltage reading
        oled.fill_rect(rec_arm_x - 3, 0, 30, 10, 0)
        oled.text(f"{ain_voltage}v", rec_arm_x - 3, 0, 1)  # Adjust x=rec_arm_x - 3

        # Show the updated display
        oled.show()


    def map_voltage_to_symbol(self, voltage, is_recording, channel_index):
        if channel_index == 4:
            return 'n'
        elif channel_index == 5:
            return self.get_ch6_symbol()
        else:
            if is_recording:
                return 'x'
            for threshold, symbol in self.voltage_ranges:
                if voltage <= threshold:
                    return symbol
            return '!'
            
    def get_ch6_symbol(self):
        """Return the current bar number for ch6's display."""
        if self.channel_lengths[5] == 0:
            return '1/1'  # Default if length is zero

        current_bar = (self.channel_steps[5] // 16) + 1  # Assuming 16 triggers per bar
        total_bars = self.channel_lengths[5] // 16 if self.channel_lengths[5] >= 16 else 1

        if total_bars == 1:
            return '1'  # Single bar
        else:
            return str(current_bar)  # Display current bar number

    def main(self):
        # Set initial active channel and bank based on knob positions
        self.ActiveCvr = k1.read_position(len(self.output_channels))  # Set active channel based on k1 position
        self.ActiveBank = k2.read_position(self.numCVRBanks)  # Set active bank based on k2 position
        self.static_display_needs_update = True
        self.dynamic_display_needs_update = True

        # Initialize knob positions
        prev_k1_pos = self.ActiveCvr
        prev_k2_pos = self.ActiveBank

        while True:
            current_time = ticks_ms()
            self.current_time = current_time  # Update current_time for callbacks

            # Handle clock events
            if self.clock_event:
                self.clockStep += 1
                self.handleClock(current_time)  # Pass current_time
                self.dynamic_display_needs_update = True
                self.clock_event = False

            # **Handle CV6 Trigger Activation**
            if self.next_trigger_time_cv6 and current_time >= self.next_trigger_time_cv6:
                self.triggerCV6(current_time)
                self.next_trigger_time_cv6 = None

            # **Handle CV6 Trigger Deactivation**
            if self.cv6_trigger_on_time is not None:
                elapsed_time = ticks_diff(current_time, self.cv6_trigger_on_time)
                if elapsed_time >= self.trigger_duration:
                    self.cv_channels[5].voltage(0)  # Turn off CV6
                    self.cv6_trigger_on_time = None

            # **Handle CV3 Trigger Deactivation**
            if self.cv3_trigger_on_time is not None:
                elapsed_time = ticks_diff(current_time, self.cv3_trigger_on_time)
                if elapsed_time >= self.trigger_duration:
                    self.cv_channels[4].voltage(0)  # Turn off CV3
                    self.cv3_trigger_on_time = None

                    
            # Check for inactivity to activate screensaver
            if not self.screensaver_active and ticks_diff(current_time, self.last_activity_time) >= self.screensaver_timeout:
                self.screensaver_active = True
                self.screensaver_frame_index = 0  # Reset animation

            # Handle clock reset timeout for the active channel only
            if self.clockStep != 0 and ticks_diff(current_time, din.last_triggered()) > self.resetTimeout:
                if self.output_channels[self.ActiveCvr] != 6 and self.CvRecording[self.ActiveBank][self.ActiveCvr] != 'true':
                    self.channel_steps[self.ActiveCvr] = 0  # Reset only the active channel
                    self.clockStep = 0

            # Update buttons
            self.button1.update()
            self.button2.update()

            # Since long_press_callback is triggered on release, we assume any button state change is activity
            if self.button1.last_state != self.button1.pin.value() or self.button2.last_state != self.button2.pin.value():
                self.last_activity_time = current_time
                self.screensaver_active = False  # Deactivate screensaver

            # Read knobs at intervals
            if current_time - self.last_knob_read_time >= self.knob_read_interval:
                self.last_knob_read_time = current_time
                # Read knobs
                current_k1_pos = k1.read_position(len(self.output_channels))
                if current_k1_pos != prev_k1_pos:
                    prev_k1_pos = current_k1_pos
                    self.ActiveCvr = current_k1_pos  # Update active channel index
                    self.static_display_needs_update = True
                    self.dynamic_display_needs_update = True
                    self.last_activity_time = current_time  # Update activity time
                    self.screensaver_active = False  # Deactivate screensaver

                current_k2_pos = k2.read_position(self.numCVRBanks)
                if current_k2_pos != prev_k2_pos:
                    prev_k2_pos = current_k2_pos
                    self.ActiveBank = current_k2_pos  # Update active bank
                    self.static_display_needs_update = True
                    self.dynamic_display_needs_update = True
                    self.last_activity_time = current_time  # Update activity time
                    self.screensaver_active = False  # Deactivate screensaver
                    # Immediate state loading
                    self.loadState(self.ActiveBank)

            # Handle display updates
            if current_time - self.last_display_update >= self.display_update_interval:
                self.updateScreen(current_time)
                self.last_display_update = current_time


if __name__ == '__main__':
    dm = CVSeq()
    dm.main()
