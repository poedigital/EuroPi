from europi import *
from time import ticks_ms, ticks_diff, sleep_ms
from europi_script import EuroPiScript

import time
import random

class PlanarSequencer(EuroPiScript):
    MAX_PLANES = 8
    MAX_NOTES = 8

    SCALES = {
        'major': [0, 2, 4, 5, 7, 9, 11],
        'minor': [0, 2, 3, 5, 7, 8, 10],
        'harmonic_major': [0, 2, 4, 5, 7, 8, 11],
        'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
        'custom': [0, 2, 4, 5, 7, 8, 10],
    }

    OUTPUT_SCALES = {
        cv1: 'major',
        cv2: 'minor',
        cv4: 'custom',
        cv5: 'harmonic_minor',
    }

    PLANE_INTERVALS = {
        2: 7,   # +1 octave (7 scale degrees in major scale)
        3: 4,   # + perfect 5th
        4: 3,   # - perfect 4th
        5: 0,   # Unison
        6: 3,   # + perfect 4th
        7: 7,   # +1 octave
        8: 4,   # + perfect 5th
    }

    NOTE_NAMES_SHARPS = ['C', 'C#', 'D', 'D#', 'E', 'F',
                         'F#', 'G', 'G#', 'A', 'A#', 'B']

    def __init__(self):
        super().__init__()
        self.planes = 1
        self.current_step_index = -1
        self.last_note_value = None
        self.sequence_steps = []  # List of (note_index, plane_number) tuples

        self.plane1_notes = [None] * self.MAX_NOTES
        self.plane1_notes[0] = 0
        self.reference_note1_value = self.plane1_notes[0]
        self.plane_notes = self.PLANE_INTERVALS.copy()
        self.current_note_index = 0
        self.last_active_note_index = 0

        self.combo_press_time = 0
        self.combo_press_threshold = 100        # Time in ms to detect combo press
        self.combo_press_display_time = 0       # For displaying feedback
        self.combo_press_feedback_duration = 1000  # Duration to display feedback in ms

        self.long_press_threshold = 1000        # Time in ms to detect long press
        self.b1_press_time = 0
        self.b2_press_time = 0
        self.b1_long_press_handled = False
        self.b2_long_press_handled = False

        self.ain_mode = 'ROOT'  # Default to 'ROOT' mode

        self.last_root_note = 36  # Default root note
        self.voltage_threshold = 0.05
        self.last_ain_voltage = None  # Initialize last AIN voltage

        self.screensaver_active = False
        self.screensaver_last_update = 0
        self.screensaver_interval = 500
        self.screensaver_timeout = 10000  # Time in ms of inactivity before screensaver activates (10 seconds)
        self.last_activity_time = time.ticks_ms()
        self.screensaver_frames = ['   ', '.  ', '.. ', '...']
        self.screensaver_frame_index = 0

        # Initialize input states
        self.last_k1_value = k1.read_position()
        self.last_k2_value = k2.read_position()
        self.last_b1_state = False
        self.last_b2_state = False
        self.last_din_state = din.value()
        self.cv6_last_voltage = None  # Add this line

        # Initialize the patch
        self.init_patch()
        self.update_display()

    def read_root_note(self):
        voltage = ain.read_voltage()

        if self.ain_mode == 'ROOT':
            if self.last_ain_voltage is None or abs(voltage - self.last_ain_voltage) > self.voltage_threshold:
                self.last_ain_voltage = voltage
                midi_note = round(voltage * 12) + 36  # Use round for better accuracy
                self.last_root_note = midi_note
            return self.last_root_note

        elif self.ain_mode == 'DIATONIC':
            if self.last_root_note is None:
                self.last_root_note = 60

            if self.last_ain_voltage is None or abs(voltage - self.last_ain_voltage) > self.voltage_threshold:
                self.last_ain_voltage = voltage

                midi_note = round(voltage * 12) + 36  # Use round for better accuracy

                scale_name = self.OUTPUT_SCALES[cv1]
                scale_intervals = self.SCALES[scale_name]
                scale_length = len(scale_intervals)

                semitone_distance = midi_note - self.last_root_note

                max_scale_degrees = 32
                scale_semitones = []
                for degree in range(max_scale_degrees):
                    octave = degree // scale_length
                    index = degree % scale_length
                    semitone = octave * 12 + scale_intervals[index]
                    scale_semitones.append(semitone)

                closest_degree = min(range(len(scale_semitones)), key=lambda x: abs(scale_semitones[x] - semitone_distance))

                self.plane1_notes[0] = closest_degree

                self.update_last_active_note_index()
                self.update_display()
            return self.last_root_note

        else:
            midi_note = round(voltage * 12) + 36  # Use round for better accuracy
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
        oled.show()

    def display_mode_indicator(self, current_time):
        if self.combo_press_display_time != 0 and time.ticks_diff(current_time, self.combo_press_display_time) < self.combo_press_feedback_duration:
            oled.text('*', 119, 2)
        else:
            oled.text('R' if self.ain_mode == 'ROOT' else 'D', 119, 2)
            if self.combo_press_display_time != 0 and time.ticks_diff(current_time, self.combo_press_display_time) >= self.combo_press_feedback_duration:
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
            return  # No steps to advance

        self.current_step_index = (self.current_step_index + 1) % len(self.sequence_steps)

        self.output_notes()
        self.update_display()
        self.last_activity_time = time.ticks_ms()
        self.screensaver_active = False

    def update_last_active_note_index(self):
        active_indices = [i for i, note in enumerate(self.plane1_notes) if note is not None]
        if active_indices:
            self.last_active_note_index = max(active_indices)
        else:
            self.last_active_note_index = -1  # Indicates no active notes

        self.generate_sequence_steps()

    def generate_sequence_steps(self, shuffle=False):
        self.sequence_steps = []

        for note_index in range(self.last_active_note_index + 1):
            note_value = self.plane1_notes[note_index]
            if note_value is not None:
                for plane_number in range(1, self.planes + 1):
                    self.sequence_steps.append((note_index, plane_number))
            else:
                # Handle gaps differently when planes > 1
                self.sequence_steps.append((note_index, 1))  # Only one rest step

        if shuffle:
            if self.sequence_steps:
                first_step = self.sequence_steps[0]  # Save the first step
                steps_to_shuffle = self.sequence_steps[1:]  # Steps to be shuffled

                self.shuffle_list(steps_to_shuffle)

                # Reconstruct the sequence_steps list
                self.sequence_steps = [first_step] + steps_to_shuffle

    def output_notes(self):
        self.last_note_value = None

        root_note = self.read_root_note()

        if not self.sequence_steps:
            return  # No steps to output

        note_index, plane_number = self.sequence_steps[self.current_step_index]

        note_value = self.plane1_notes[note_index]

        adjusted_note_value = self.calculate_adjusted_note_value(note_index, note_value, plane_number)

        # Handle cv3 to output the root note (Plane 1, Note 1)
        root_note_value = self.plane1_notes[0]
        if root_note_value is not None:
            adjusted_root_note_value = self.calculate_adjusted_note_value(0, root_note_value, 1)
            cv3_scale_name = 'major'  # Or any scale you prefer
            interval_cv3 = self.get_scale_interval(adjusted_root_note_value, scale_name=cv3_scale_name)
            note_midi_cv3 = root_note + interval_cv3

            # Ensure note_midi_cv3 is within the desired range
            while note_midi_cv3 < 36:
                note_midi_cv3 += 12
            while note_midi_cv3 > 84:
                note_midi_cv3 -= 12

            voltage_cv3 = (note_midi_cv3 - 36) / 12.0
            cv3.voltage(voltage_cv3)
        else:
            cv3.voltage(0)  # Output 0V if root note is not set

        # Handle cv6 to output the root note adjusted by the current plane interval
        if root_note_value is not None:
            adjusted_root_note_value_cv6 = self.calculate_adjusted_note_value(0, root_note_value, plane_number)
            cv6_scale_name = 'major'  # Or any scale you prefer
            interval_cv6 = self.get_scale_interval(adjusted_root_note_value_cv6, scale_name=cv6_scale_name)
            note_midi_cv6 = root_note + interval_cv6

            # Ensure note_midi_cv6 is within the desired range
            while note_midi_cv6 < 36:
                note_midi_cv6 += 12
            while note_midi_cv6 > 84:
                note_midi_cv6 -= 12

            voltage_cv6 = (note_midi_cv6 - 36) / 12.0
            # Update cv6 only if the voltage has changed
            if self.cv6_last_voltage != voltage_cv6:
                cv6.voltage(voltage_cv6)
                self.cv6_last_voltage = voltage_cv6  # Store the last voltage
        else:
            # No new note, hold the last voltage
            if self.cv6_last_voltage is not None:
                cv6.voltage(self.cv6_last_voltage)
            else:
                cv6.voltage(0)  # If no last voltage, output 0

        # Handle other CV outputs as before
        for output, scale_name in self.OUTPUT_SCALES.items():
            if adjusted_note_value is not None:
                interval = self.get_scale_interval(adjusted_note_value, scale_name)
                note_midi = root_note + interval
                # Ensure note_midi is within the desired range
                while note_midi < 36:
                    note_midi += 12
                while note_midi > 84:
                    note_midi -= 12
                voltage = (note_midi - 36) / 12.0
                output.voltage(voltage)
            else:
                output.voltage(0)

    def calculate_adjusted_note_value(self, note_index, note_value, plane_number):
        if note_value is not None:
            if note_index == 0:
                adjusted_note_value = note_value
            else:
                difference = self.plane1_notes[0] - self.reference_note1_value
                adjusted_note_value = note_value + difference
            adjusted_note_value += self.get_plane_interval(plane_number)
            adjusted_note_value %= 16  # Ensure within 0-15
            self.last_note_value = adjusted_note_value

            return adjusted_note_value
        else:
            # Handle rests and hold-over notes
            next_note_exists = any(
                self.plane1_notes[i] is not None for i in range(note_index + 1, self.last_active_note_index + 1)
            )
            if next_note_exists and self.last_note_value is not None:
                return self.last_note_value
            else:
                self.last_note_value = None
                return None

    def get_plane_interval(self, plane_number):
        if plane_number == 1:
            return 0  # Plane 1 is the base
        else:
            return self.plane_notes.get(plane_number, self.PLANE_INTERVALS.get(plane_number, 0))

    def randomize_planes(self, set_display_time=True):
        possible_intervals = [-7, -5, -3, 0, 3, 4, 5, 7, 9, 11]  # Possible scale degree intervals

        # Randomize plane intervals
        for plane_number in range(2, self.MAX_PLANES + 1):
            self.plane_notes[plane_number] = random.choice(possible_intervals)

        self.scramble_notes()

        self.generate_sequence_steps(shuffle=True)

        if set_display_time:
            self.combo_press_display_time = time.ticks_ms()
        self.update_display()

    def scramble_notes(self):
        # Identify indices of active notes, excluding index 0
        active_indices = [i for i, note in enumerate(self.plane1_notes) if note is not None and i != 0]

        active_notes = [self.plane1_notes[i] for i in active_indices]

        if not active_notes:
            return  # No active notes to scramble

        self.shuffle_list(active_notes)

        for idx, note in zip(active_indices, active_notes):
            self.plane1_notes[idx] = note

        self.reference_note1_value = self.plane1_notes[0] if self.plane1_notes[0] is not None else 0

        self.update_last_active_note_index()

    def shuffle_list(self, lst):
        for i in range(len(lst) - 1, 0, -1):
            j = random.randint(0, i)  # Get a random index from 0 to i
            lst[i], lst[j] = lst[j], lst[i]  # Swap elements

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
        elif not b1_state and self.last_b1_state:
            press_duration = time.ticks_diff(current_time, self.b1_press_time)
            if press_duration < self.long_press_threshold and not self.b1_long_press_handled:
                self.current_note_index = (self.current_note_index - 1) % self.MAX_NOTES
                self.update_display()
                self.last_activity_time = current_time
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
                self.init_patch()
                self.b2_long_press_handled = True
                self.last_activity_time = current_time
        elif not b2_state and self.last_b2_state:
            press_duration = time.ticks_diff(current_time, self.b2_press_time)
            if press_duration < self.long_press_threshold and not self.b2_long_press_handled:
                self.current_note_index = (self.current_note_index + 1) % self.MAX_NOTES
                self.update_display()
                self.last_activity_time = current_time
            self.b2_press_time = 0
            self.b2_long_press_handled = False
        self.last_b2_state = b2_state

    def handle_k1_input(self, k1_value, current_time):
        if abs(k1_value - self.last_k1_value) > 0.5:
            max_position = 16
            position = int((k1_value / 100) * (max_position + 1))
            position = min(position, max_position)  # Ensure position does not exceed max_position

            if self.current_note_index == 0:
                if self.ain_mode != 'DIATONIC':
                    position = max(position, 1)  # Ensure position is at least 1
                    self.plane1_notes[self.current_note_index] = position - 1
            else:
                self.plane1_notes[self.current_note_index] = None if position == 0 else position - 1

            self.update_last_active_note_index()

            self.last_k1_value = k1_value
            self.update_display()
            self.last_activity_time = current_time

    def handle_k2_input(self, k2_value, current_time):
        if abs(k2_value - self.last_k2_value) > 0.5:
            new_planes = int(round((k2_value / 99.0) * (self.MAX_PLANES - 1))) + 1
            if new_planes < 1:
                new_planes = 1
            elif new_planes > self.MAX_PLANES:
                new_planes = self.MAX_PLANES
            if new_planes != self.planes:
                self.planes = new_planes
                self.update_display()
                self.last_activity_time = current_time
                # Regenerate sequence steps without shuffling
                self.generate_sequence_steps()
            self.last_k2_value = k2_value

    def handle_din_input(self, din_state, current_time):
        if din_state and not self.last_din_state:
            self.advance_sequence()
            self.last_activity_time = current_time
        self.last_din_state = din_state

    def main(self):
        while True:
            current_time = time.ticks_ms()
            b1_state = b1.value()
            b2_state = b2.value()
            k1_value = k1.read_position()
            k2_value = k2.read_position()
            din_state = din.value()

            self.handle_screensaver(current_time)
            self.handle_combo_press(current_time, b1_state, b2_state)
            self.handle_b1_press(current_time, b1_state)
            self.handle_b2_press(current_time, b2_state)
            self.handle_k1_input(k1_value, current_time)
            self.handle_k2_input(k2_value, current_time)
            self.handle_din_input(din_state, current_time)

if __name__ == "__main__":
    PlanarSequencer().main()