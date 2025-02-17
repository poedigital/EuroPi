from europi import *
from time import ticks_ms, ticks_diff, sleep_ms
from europi_script import EuroPiScript

class Nebulaid(EuroPiScript):
    def __init__(self):
        super().__init__()

        # Initialize variables
        self.step = 0  # Current step in the sequence
        self.arm_record = False  # Whether recording is armed
        self.recording = False  # Tracks if recording is in progress
        self.loop_size = 16  # Default loop size (number of triggers)
        self.reset_requested = False  # Tracks if reset was requested

        # Initialize trigger timing variables
        self.reset_triggers_on_time = None
        self.reset_triggers_duration = 6  # in milliseconds
        self.cv1_trigger_on_time = None
        self.cv1_trigger_duration = 10  # in milliseconds

        # Define possible loop sizes in triggers (2 triggers per beat)
        self.loop_sizes = [8, 16, 32, 64, 128]  # Corresponds to 2, 4, 8, 16, 32 beats

        # Display initial "Awaiting clock in" message
        self.display_awaiting_clock()

        # Assign input handlers inside __init__ to have access to 'self'
        b1.handler(self.arm_recording)
        b2.handler(self.reset_sequence)
        din.handler(self.clock_input)

    def display_awaiting_clock(self):
        """Display 'Awaiting clock in' message on the OLED during boot."""
        oled.fill(0)
        oled.text("Awaiting", 10, 10)
        oled.text("Clock In", 10, 20)
        oled.show()

    def arm_recording(self):
        """Toggle recording arm status when b1 is pressed."""
        self.arm_record = not self.arm_record
        self.update_oled_display()

    def reset_sequence(self):
        """Reset the sequence and send reset triggers when b2 is pressed."""
        self.reset_requested = True
        self.reset_sequence_action()

    def clock_input(self):
        """Advance step and update the OLED when a clock trigger is received."""
        self.advance_step()
        self.update_oled_display()

    def update_oled_display(self):
        """Update the OLED display based on the current state."""
        oled.fill(0)

        # Build and display progress bar on first line
        progress_bar_length = 16  # Number of characters in progress bar
        if self.loop_size > 0:
            position = int((self.step / self.loop_size) * progress_bar_length)
            if position >= progress_bar_length:
                position = progress_bar_length - 1
        else:
            position = 0

        progress_bar = ['.' for _ in range(progress_bar_length)]
        progress_bar[position] = '|'
        progress_bar_str = ''.join(progress_bar)
        oled.text(progress_bar_str, 0, 0)

        # Display middle line
        if self.arm_record and not self.recording:
            oled.text("Arm for Rec", 0, 10)  # Middle line, y=10
        elif self.recording:
            oled.text("Recording", 0, 10)
        else:
            # Display sequence length on the left side of row 2
            loop_size_beats = self.loop_size // 2  # Convert triggers to beats
            seq_length_text = f"Len: {loop_size_beats}"
            oled.text(seq_length_text, 0, 10)  # Left-aligned, x=0

        # Display bottom line with 'Arm' on left and 'Reset' on right
        oled.text("Arm", 0, 20)  # Bottom left, y=20
        reset_text = "Reset"
        text_width = len(reset_text) * 8  # Assuming 8 pixels per character
        x_reset = oled.width - text_width
        oled.text(reset_text, x_reset, 20)

        oled.show()

    def reset_sequence_action(self):
        """Reset the sequence and send reset triggers when b2 is pressed."""
        self.arm_record = False
        self.recording = False
        self.step = 0
        self.reset_requested = False

        # Send reset triggers for outputs 2-5 immediately
        cv2.on()
        cv3.on()
        cv4.on()
        cv5.on()
        # Record the time when triggers were turned on
        self.reset_triggers_on_time = ticks_ms()

        # Update the OLED display
        self.update_oled_display()

    def advance_step(self):
        """Handle advancing the sequence on each clock tick."""
        # Update loop size based on knob 1 (k1)
        self.loop_size = self.loop_sizes[k1.read_position(len(self.loop_sizes))]

        # Send a trigger at the beginning of the loop (step 0)
        if self.step == 0:
            # If armed and not recording, start recording and send trigger via cv1
            if self.arm_record and not self.recording:
                self.recording = True
                cv1.on()  # Trigger CV1 on recording start
                self.cv1_trigger_on_time = ticks_ms()

            # Send reset triggers for outputs 2-5 as well
            cv2.on()
            cv3.on()
            cv4.on()
            cv5.on()
            self.reset_triggers_on_time = ticks_ms()  # Record reset trigger time

        # Advance step and check for loop completion
        self.step += 1
        if self.step >= self.loop_size:
            # End of loop; if recording, stop and trigger CV1 again
            if self.recording:
                self.recording = False
                cv1.on()  # Trigger CV1 on recording stop
                self.cv1_trigger_on_time = ticks_ms()
                self.arm_record = False  # Disarm recording after stop

            self.step = 0  # Reset step count at loop end

        # Update the OLED display with each step
        self.update_oled_display()

    def main(self):
        """Main loop with small delay to avoid CPU overload."""
        self.reset_triggers_on_time = None
        self.cv1_trigger_on_time = None

        while True:
            current_time = ticks_ms()

            # Check for incoming clock triggers
            if din.value() == 1:  # If a clock pulse is received
                self.advance_step()  # Advance the step in response

            # Check for trigger timeouts and reset logic
            if self.reset_triggers_on_time is not None:
                if ticks_diff(current_time, self.reset_triggers_on_time) >= self.reset_triggers_duration:
                    cv2.off()
                    cv3.off()
                    cv4.off()
                    cv5.off()
                    self.reset_triggers_on_time = None

            if self.cv1_trigger_on_time is not None:
                if ticks_diff(current_time, self.cv1_trigger_on_time) >= self.cv1_trigger_duration:
                    cv1.off()
                    self.cv1_trigger_on_time = None

            sleep_ms(4)  # Minimal delay to prevent CPU overload

if __name__ == "__main__":
    nebulaid = Nebulaid()
    nebulaid.main()
