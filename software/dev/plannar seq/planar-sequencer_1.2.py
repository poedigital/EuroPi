from europi import *
from europi_script import EuroPiScript  # Assuming EuroPiScript is the base class with state methods
import time
import random
import json

class DebouncedSaver:
    """
    A helper class to handle debounced state saving. 
    If the client code calls `request_save()`, the actual save will 
    occur only after a minimum delay (e.g., 500 ms) of no further save requests.
    """
    def __init__(self, save_callback, debounce_ms=500):
        self.save_callback = save_callback
        self.debounce_ms = debounce_ms
        self.last_request_time = None
        self.next_save_time = None

    def request_save(self, current_time_ms):
        self.last_request_time = current_time_ms
        self.next_save_time = current_time_ms + self.debounce_ms

    def maybe_save(self, current_time_ms):
        if self.next_save_time is not None and current_time_ms >= self.next_save_time:
            # Perform the actual save
            self.save_callback()
            # Clear the request
            self.next_save_time = None

class PlanarSequencer(EuroPiScript):
    def __init__(self):
        super().__init__()  # Initialize the base class for state management

        # --- Constants and lookup tables ---
        self.MAX_PLANES = 8
        self.MAX_NOTES = 8

        self.SCALES = {
            'major': [0, 2, 4, 5, 7, 9, 11],
            'minor': [0, 2, 3, 5, 7, 8, 10],
            'harmonic_major': [0, 2, 4, 5, 7, 8, 11],
            'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
        }

        self.OUTPUT_SCALES = {
            cv1: 'major',
            cv2: 'minor',
            cv4: 'harmonic_major',
            cv5: 'harmonic_minor',
        }

        self.PLANE_INTERVALS = {
            2: 7,   # +1 octave
            3: 4,   # + perfect 5th
            4: 3,  # - perfect 4th
            5: 0,   # Unison
            6: 3,   # + perfect 4th
            7: 7,   # +1 octave
            8: 4,   # + perfect 5th
        }

        self.NOTE_NAMES_SHARPS = ['C', 'C#', 'D', 'D#', 'E', 'F',
                                  'F#', 'G', 'G#', 'A', 'A#', 'B']

        # --- Variables ---
        self.planes = 1
        self.current_step_index = -1
        self.last_note_value = None
        self.sequence_steps = []  # List of (note_index, plane_number) tuples

        self.plane1_notes = [None] * self.MAX_NOTES
        self.plane1_notes[0] = 0
        self.reference_note1_value = self.plane1_notes[0]
        self.plane_notes = {}  # Dictionary to hold intervals for planes 2 to 8
        self.current_note_index = 0
        self.last_active_note_index = 0

        self.combo_press_time = 0
        self.combo_press_threshold = 100
        self.combo_press_display_time = 0
        self.combo_press_feedback_duration = 1000

        self.long_press_threshold = 1000
        self.b1_press_time = 0
        self.b2_press_time = 0
        self.b1_long_press_handled = False
        self.b2_long_press_handled = False

        self.ain_mode = 'ROOT'
        self.last_root_note = 36
        self.voltage_threshold = 0.02
        self.last_ain_voltage = None

        self.screensaver_active = False
        self.screensaver_last_update = 0
        self.screensaver_interval = 500
        self.screensaver_timeout = 10000
        self.last_activity_time = time.ticks_ms()
        self.screensaver_frames = ['   ', '.  ', '.. ', '...']
        self.screensaver_frame_index = 0

        # Additional state for knobs, buttons, gate input
        self.last_k1_value = 0
        self.last_k2_value = 0
        self.last_b1_state = False
        self.last_b2_state = False
        self.last_din_state = False

        # Debounced Saver: pass in the actual save method
        self.debounced_saver = DebouncedSaver(save_callback=self._do_save)

        self.load_saved_state()  # Attempt to load saved state
        self.update_display()

    # --------------------------------------------------
    # Debounced Save Logic
    # --------------------------------------------------
    def _do_save(self):
        """
        The actual method that performs the saving of state to disk.
        Called by `DebouncedSaver` after 500 ms of no new save requests.
        """
        state = {
            'current_note_index': self.current_note_index,
            'plane1_notes': self.plane1_notes,
            'ain_mode': self.ain_mode
        }
        self.save_state_json(state)

    def request_save_current_state(self):
        """
        Public method to request saving state. 
        The actual save is deferred by the `DebouncedSaver`.
        """
        now = time.ticks_ms()
        self.debounced_saver.request_save(now)

    @property
    def _state_filename(self):
        return f"saved_state_{self.__class__.__qualname__}.json"

    def load_saved_state(self):
        state = self.load_state_json()
        if state:
            self.current_note_index = state.get('current_note_index', 0)
            self.plane1_notes = state.get('plane1_notes', [None] * self.MAX_NOTES)
            self.ain_mode = state.get('ain_mode', 'ROOT')
            # Update other dependent variables
            self.update_last_active_note_index()
            self.update_display()

    def save_state_json(self, state: dict):
        super().save_state_json(state)

    def load_state_json(self) -> dict:
        return super().load_state_json()

    def clear_saved_state(self):
        """ Deletes the saved state file to ensure a clean start on next reboot. """
        try:
            with open(self._state_filename, "w") as f:
                f.write("{}")  # Write an empty JSON object
            print("Saved state cleared.")
        except Exception as e:
            print(f"Error clearing saved state: {e}")

    # --------------------------------------------------
    # Sequencer Logic
    # --------------------------------------------------
    def read_root_note(self):
        voltage = ain.read_voltage()
        if self.ain_mode == 'ROOT':
            if self.last_ain_voltage is None or abs(voltage - self.last_ain_voltage) > self.voltage_threshold:
                self.last_ain_voltage = voltage
                midi_note = int((voltage / 5.0) * 60) + 36
                midi_note = ((midi_note - 36) % 48) + 36
                self.last_root_note = midi_note
                self.request_save_current_state()
            return self.last_root_note
        elif self.ain_mode == 'DIATONIC':
            max_position = 16
            position = int((voltage / 5.0) * max_position) % max_position
            self.plane1_notes[0] = position
            self.update_last_active_note_index()
            self.update_display()
            self.request_save_current_state()
            return self.last_root_note
        else:
            midi_note = int((voltage / 5.0) * 60) + 36
            return midi_note

    def get_scale_interval(self, scale_degree, scale_name='major'):
        scale_intervals = self.SCALES[scale_name]
        scale_length = len(scale_intervals)
        index = scale_degree % scale_length
        octave_shift = (scale_degree // scale_length) * 12
        interval = scale_intervals[index] + octave_shift
        return interval

    def update_display(self):
        oled.fill(0)
        current_time = time.ticks_ms()

        if self.screensaver_active:
            self.display_screensaver()
            oled.show()
            return

        self.display_mode_indicator(current_time)
        self.display_note_name()
        self.display_plane_indicators()
        self.display_note_values()
        oled.show()

    def display_screensaver(self):
        frame = self.screensaver_frames[self.screensaver_frame_index]
        text_width = len(frame) * 6
        x_position = (128 - text_width) // 2
        oled.text(frame, x_position, 12)

    def display_mode_indicator(self, current_time):
        if (self.combo_press_display_time != 0 and 
            time.ticks_diff(current_time, self.combo_press_display_time) < self.combo_press_feedback_duration):
            oled.text('*', 119, 2)
        else:
            oled.text('R' if self.ain_mode == 'ROOT' else 'D', 119, 2)
            if (self.combo_press_display_time != 0 and 
                time.ticks_diff(current_time, self.combo_press_display_time) >= self.combo_press_feedback_duration):
                self.combo_press_display_time = 0

    def display_note_name(self):
        note_name = self.NOTE_NAMES_SHARPS[self.last_root_note % 12]
        oled.text(note_name, 2, 2)

    def display_plane_indicators(self):
        planes_y_position = 0
        planes_step_width = 7
        planes_total_width = planes_step_width * self.MAX_PLANES
        planes_margin = (128 - planes_total_width) // 2

        for i in range(self.MAX_PLANES):
            x_position = planes_margin + i * planes_step_width
            square_size = 6
            square_x = x_position + (planes_step_width - square_size) // 2
            y_position = planes_y_position + 2
            if i < self.planes:
                oled.fill_rect(square_x, y_position, square_size, square_size, 1)
            else:
                oled.rect(square_x, y_position, square_size, square_size, 1)

    def display_note_values(self):
        y_position = 17
        x_positions = []
        step_width = 14
        total_steps_width = step_width * self.MAX_NOTES
        margin = (128 - total_steps_width) // 2

        for i in range(self.MAX_NOTES):
            x_position = margin + i * step_width
            x_positions.append(x_position)
            note = self.plane1_notes[i]
            if note is not None:
                degree = note + 1
                degree_str = str(degree)
                char_width = 6 * len(degree_str)
                text_x = x_position + (step_width - char_width) // 2
                oled.text(degree_str, text_x, y_position)
            else:
                text_x = x_position + (step_width - 6) // 2
                oled.text("-", text_x, y_position)

        caret_x = x_positions[self.current_note_index] + (step_width - 6) // 2
        caret_y = y_position + 10
        oled.text("^", caret_x, caret_y)

    def advance_sequence(self):
        if not self.sequence_steps:
            return
        self.current_step_index = (self.current_step_index + 1) % len(self.sequence_steps)
        self.output_notes()
        self.update_display()
        self.last_activity_time = time.ticks_ms()
        self.screensaver_active = False
        self.request_save_current_state()

    def update_last_active_note_index(self):
        active_indices = [i for i, note in enumerate(self.plane1_notes) if note is not None]
        self.last_active_note_index = max(active_indices) if active_indices else -1
        self.generate_sequence_steps()
        self.request_save_current_state()

    def generate_sequence_steps(self, shuffle=False):
        self.sequence_steps = []
        
        for note_index in range(self.last_active_note_index + 1):
            note_value = self.plane1_notes[note_index]
            if note_value is not None:
                # Expand the note across all active planes
                for plane_number in range(1, self.planes + 1):
                    self.sequence_steps.append((note_index, plane_number))
            else:
                # Add a single rest step
                self.sequence_steps.append((note_index, None))  # None indicates a rest
        
        if shuffle and self.sequence_steps:
            first_step = self.sequence_steps[0]
            steps_to_shuffle = self.sequence_steps[1:]
            self.shuffle_list(steps_to_shuffle)
            self.sequence_steps = [first_step] + steps_to_shuffle
    def output_notes(self):
        root_note = self.read_root_note()
        if not self.sequence_steps:
            return

        note_index, plane_number = self.sequence_steps[self.current_step_index]
        note_value = self.plane1_notes[note_index]
        adjusted_note_value = self.calculate_adjusted_note_value(note_index, note_value, plane_number)

        if adjusted_note_value is None:
            for output in self.OUTPUT_SCALES:
                output.voltage(0)
            return

        for output, scale_name in self.OUTPUT_SCALES.items():
            interval = self.get_scale_interval(adjusted_note_value, scale_name)
            note_midi = root_note + interval
            if note_midi < 36:
                note_midi += 12
            elif note_midi > 84:
                note_midi -= 12
            voltage = (note_midi - 36) / 12.0
            output.voltage(voltage)

        self.request_save_current_state()

    def calculate_adjusted_note_value(self, note_index, note_value, plane_number):
        if note_value is not None:
            if note_index == 0:
                adjusted_note_value = note_value
            else:
                difference = self.plane1_notes[0] - self.reference_note1_value
                adjusted_note_value = note_value + difference
            adjusted_note_value += self.get_plane_interval(plane_number)
            adjusted_note_value %= 16
            self.last_note_value = adjusted_note_value
            self.request_save_current_state()
            return adjusted_note_value
        else:
            next_note_exists = any(
                self.plane1_notes[i] is not None for i in range(note_index + 1, self.last_active_note_index + 1)
            )
            if next_note_exists and self.last_note_value is not None:
                self.request_save_current_state()
                return self.last_note_value
            else:
                self.last_note_value = None
                self.request_save_current_state()
                return None

    def get_plane_interval(self, plane_number):
        if plane_number == 1:
            return 0
        return self.plane_notes.get(plane_number, self.PLANE_INTERVALS.get(plane_number, 0))

    def randomize_planes(self, set_display_time=True):
        possible_intervals = [-7, -5, -3, 0, 3, 4, 5, 7, 9, 11]
        for plane_number in range(2, self.MAX_PLANES + 1):
            self.plane_notes[plane_number] = random.choice(possible_intervals)

        self.scramble_notes()
        self.generate_sequence_steps(shuffle=True)

        if set_display_time:
            self.combo_press_display_time = time.ticks_ms()
        self.update_display()
        self.request_save_current_state()

    def scramble_notes(self):
        active_indices = [i for i, note in enumerate(self.plane1_notes) if note is not None and i != 0]
        active_notes = [self.plane1_notes[i] for i in active_indices]
        if not active_notes:
            return

        self.shuffle_list(active_notes)
        for idx, note in zip(active_indices, active_notes):
            self.plane1_notes[idx] = note

        self.reference_note1_value = self.plane1_notes[0] if self.plane1_notes[0] is not None else 0
        self.update_last_active_note_index()
        self.request_save_current_state()

    def shuffle_list(self, lst):
        for i in range(len(lst) - 1, 0, -1):
            j = random.randint(0, i)
            lst[i], lst[j] = lst[j], lst[i]

    # --------------------------------------------------
    # Patch Initialization
    # --------------------------------------------------
    def init_patch(self):
        self.planes = 1
        self.current_step_index = -1
        self.current_note_index = 0
        self.last_note_value = None
        self.plane1_notes = [None] * self.MAX_NOTES
        self.plane1_notes[0] = 0
        self.reference_note1_value = self.plane1_notes[0]
        self.plane_notes = self.PLANE_INTERVALS.copy()

        self.update_last_active_note_index()
        self.generate_sequence_steps()
        self.update_display()
        self.request_save_current_state()

    # --------------------------------------------------
    # Hardware Interaction
    # --------------------------------------------------
    def initialize(self):
        self.last_k1_value = k1.read_position()
        self.last_k2_value = k2.read_position()
        self.last_b1_state = False
        self.last_b2_state = False
        self.last_din_state = din.value()
        self.load_saved_state()
        self.update_display()

    def handle_screensaver(self, current_time):
        if time.ticks_diff(current_time, self.last_activity_time) > self.screensaver_timeout:
            if not self.screensaver_active:
                self.screensaver_active = True
                self.screensaver_frame_index = 0
                self.update_display()
            else:
                if time.ticks_diff(current_time, self.screensaver_last_update) > self.screensaver_interval:
                    self.screensaver_frame_index = (self.screensaver_frame_index + 1) % len(self.screensaver_frames)
                    self.screensaver_last_update = current_time
                    self.update_display()
        else:
            self.screensaver_active = False

    def handle_combo_press(self, current_time, b1_state, b2_state):
        if b1_state and b2_state:
            if self.combo_press_time == 0:
                self.combo_press_time = current_time
            elif time.ticks_diff(current_time, self.combo_press_time) > self.combo_press_threshold:
                self.randomize_planes()
                self.combo_press_time = 0
                self.last_activity_time = current_time
        else:
            self.combo_press_time = 0

    def handle_b1_press(self, current_time, b1_state):
        if b1_state and not self.last_b1_state:
            self.b1_press_time = current_time
            self.b1_long_press_handled = False
        elif b1_state:
            press_duration = time.ticks_diff(current_time, self.b1_press_time)
            if press_duration >= self.long_press_threshold and not self.b1_long_press_handled:
                self.ain_mode = 'DIATONIC' if self.ain_mode == 'ROOT' else 'ROOT'
                self.b1_long_press_handled = True
                self.update_display()
                self.last_activity_time = current_time
                self.request_save_current_state()
        elif not b1_state and self.last_b1_state:
            press_duration = time.ticks_diff(current_time, self.b1_press_time)
            if press_duration < self.long_press_threshold and not self.b1_long_press_handled:
                self.current_note_index = (self.current_note_index - 1) % self.MAX_NOTES
                self.update_display()
                self.last_activity_time = current_time
                self.request_save_current_state()
            self.b1_press_time = 0
            self.b1_long_press_handled = False
        self.last_b1_state = b1_state

    def handle_b2_press(self, current_time, b2_state):
        if b2_state and not self.last_b2_state:
            self.b2_press_time = current_time
            self.b2_long_press_handled = False
        elif b2_state:
            press_duration = time.ticks_diff(current_time, self.b2_press_time)
            if press_duration >= self.long_press_threshold and not self.b2_long_press_handled:
                self.init_patch()  # Reset everything
                self.clear_saved_state()  # Wipe the save file
                self.b2_long_press_handled = True
                self.last_activity_time = current_time
        elif not b2_state and self.last_b2_state:
            press_duration = time.ticks_diff(current_time, self.b2_press_time)
            if press_duration < self.long_press_threshold and not self.b2_long_press_handled:
                self.current_note_index = (self.current_note_index + 1) % self.MAX_NOTES
                self.update_display()
                self.last_activity_time = current_time
                self.request_save_current_state()
            self.b2_press_time = 0
            self.b2_long_press_handled = False
        self.last_b2_state = b2_state
        
    def handle_k1_input(self, k1_value, current_time):
        if abs(k1_value - self.last_k1_value) > 0.5:
            max_position = 16
            position = int((k1_value / 100) * (max_position + 1))
            position = min(position, max_position)
            if self.current_note_index == 0:
                if self.ain_mode != 'DIATONIC':
                    position = max(position, 1)
                    self.plane1_notes[self.current_note_index] = position - 1
            else:
                self.plane1_notes[self.current_note_index] = None if position == 0 else position - 1

            self.update_last_active_note_index()
            self.last_k1_value = k1_value
            self.update_display()
            self.last_activity_time = current_time
            self.request_save_current_state()

    def handle_k2_input(self, k2_value, current_time):
        if abs(k2_value - self.last_k2_value) > 0.5:
            new_planes = int(round((k2_value / 99.0) * (self.MAX_PLANES - 1))) + 1
            new_planes = max(1, min(self.MAX_PLANES, new_planes))
            if new_planes != self.planes:
                self.planes = new_planes
                self.update_display()
                self.last_activity_time = current_time
                self.generate_sequence_steps()
            self.last_k2_value = k2_value
            self.request_save_current_state()

    def handle_din_input(self, din_state, current_time):
        if din_state and not self.last_din_state:
            self.advance_sequence()
            self.last_activity_time = current_time
        self.last_din_state = din_state

    # --------------------------------------------------
    # Main Loop
    # --------------------------------------------------
    def main(self):
        while True:
            current_time = time.ticks_ms()

            # 1) We only read hardware changes
            din_state = din.value()
            b1_state = b1.value()
            b2_state = b2.value()
            k1_value = k1.read_position()
            k2_value = k2.read_position()

            # 2) Handle logic
            self.handle_din_input(din_state, current_time)
            self.handle_screensaver(current_time)
            self.handle_combo_press(current_time, b1_state, b2_state)
            self.handle_b1_press(current_time, b1_state)
            self.handle_b2_press(current_time, b2_state)
            self.handle_k1_input(k1_value, current_time)
            self.handle_k2_input(k2_value, current_time)

            # 3) Check if it's time to do a debounced save
            self.debounced_saver.maybe_save(current_time)

# Usage:
if __name__ == "__main__":
    sequencer = PlanarSequencer()
    sequencer.main()