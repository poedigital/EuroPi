from europi import *
import time
import random
# Removed deque import
# from collections import deque

MAX_PLANES = 8
MAX_NOTES = 8

voltage_samples = []  # Store voltage readings
MAX_VOLTAGE_SAMPLES = 3  # Maximum number of samples to keep
last_stable_note = None
hysteresis_threshold = 0.5

SCALES = {
    'major': [0, 2, 4, 5, 7, 9, 11],
    'minor': [0, 2, 3, 5, 7, 8, 10],
    'harmonic_major': [0, 2, 4, 5, 7, 8, 11],
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
}

OUTPUT_SCALES = {
    cv1: 'major',
    cv2: 'minor',
    cv4: 'harmonic_major',
    cv5: 'harmonic_minor',
}

PLANE_INTERVALS = {
    2: 7,   # +1 octave (7 scale degrees in major scale)
    3: 4,   # + perfect 5th
    4: -3,  # - perfect 4th
    5: 0,   # Unison
    6: 3,   # + perfect 4th
    7: 7,   # +1 octave
    8: 4,   # + perfect 5th
}

NOTE_NAMES_SHARPS = ['C', 'C#', 'D', 'D#', 'E', 'F',
                     'F#', 'G', 'G#', 'A', 'A#', 'B']

planes = 1
current_step_index = -1
last_note_value = None
# Removed duplicate initialization of voltage_samples with deque
# voltage_samples = deque(maxlen=10)  # Store the last 10 voltage readings

plane1_notes = [None] * MAX_NOTES
plane1_notes[0] = 0
reference_note1_value = plane1_notes[0]
plane_notes = {}    # Dictionary to hold intervals for planes 2 to 8
current_note_index = 0

combo_press_time = 0
combo_press_threshold = 100        # Time in ms to detect combo press
combo_press_display_time = 0       # For displaying feedback
combo_press_feedback_duration = 1000  # Duration to display feedback in ms

b2_long_press_display_time = 0    # For displaying 'x' when sequence is cleared
long_press_threshold = 1000        # Time in ms to detect long press
b1_press_time = 0
b2_press_time = 0
b1_long_press_handled = False      # Flag to prevent multiple triggers
b2_long_press_handled = False      # Flag to prevent multiple triggers

ain_mode = 'ROOT'  # Default to 'ROOT' mode

last_ain_voltage = None
last_root_note = 36  # Default root note
voltage_threshold = 0.05

screensaver_active = False
screensaver_last_update = 0
screensaver_interval = 500
screensaver_timeout = 10000  # Time in ms of inactivity before screensaver activates (10 seconds)
last_activity_time = time.ticks_ms()
screensaver_frames = ['   ', '.  ', '.. ', '...']
screensaver_frame_index = 0

def read_root_note():
    global last_root_note, last_stable_note
    voltage = ain.read_voltage()
    min_voltage = 0.05  # Minimum voltage to consider valid input

    if voltage > min_voltage:
        voltage_samples.append(voltage)
        if len(voltage_samples) > MAX_VOLTAGE_SAMPLES:
            # Remove the oldest sample to maintain the fixed size
            voltage_samples.pop(0)

        if len(voltage_samples) == MAX_VOLTAGE_SAMPLES:
            average_voltage = sum(voltage_samples) / len(voltage_samples)

            if ain_mode == 'ROOT':
                # Map voltage to MIDI notes (60 notes from MIDI 36 to 96)
                midi_note = int((average_voltage / 5.0) * 60) + 36
                midi_note = ((midi_note - 36) % 60) + 36

                # Implement hysteresis
                if last_stable_note is None or abs(midi_note - last_stable_note) >= hysteresis_threshold:
                    last_root_note = midi_note
                    last_stable_note = midi_note
            elif ain_mode == 'DIATONIC':
                # Map voltage to scale degrees
                max_position = 16
                position = int((average_voltage / 5.0) * max_position) % max_position

                # Implement hysteresis
                if last_stable_note is None or abs(position - last_stable_note) >= hysteresis_threshold:
                    plane1_notes[0] = position
                    last_stable_note = position
                    update_display()
        else:
            # Not enough samples yet, keep the previous note
            pass
    else:
        # Voltage too low, reset samples and keep the previous note
        voltage_samples.clear()
    return last_root_note

def get_scale_interval(scale_degree, scale_name='major'):
    scale_intervals = SCALES[scale_name]
    scale_length = len(scale_intervals)
    index = scale_degree % scale_length
    octave_shift = (scale_degree // scale_length) * 12
    interval = scale_intervals[index] + octave_shift
    return interval

def update_display():
    global combo_press_display_time, b2_long_press_display_time
    oled.fill(0)

    current_time = time.ticks_ms()
    if screensaver_active:
        frame = screensaver_frames[screensaver_frame_index]
        text_width = len(frame) * 6
        x_position = (128 - text_width) // 2
        oled.text(frame, x_position, 12)
        oled.show()
        return

    if combo_press_display_time != 0 and time.ticks_diff(current_time, combo_press_display_time) < combo_press_feedback_duration:
        # Display '*' in place of 'R' or 'D'
        oled.text('*', 119, 2)
    else:
        # Display 'R' or 'D' as usual
        if ain_mode == 'ROOT':
            oled.text('R', 119, 2)
        else:
            oled.text('D', 119, 2)
        # Reset combo_press_display_time if expired
        if combo_press_display_time != 0 and time.ticks_diff(current_time, combo_press_display_time) >= combo_press_feedback_duration:
            combo_press_display_time = 0


    note_name = NOTE_NAMES_SHARPS[last_root_note % 12]
    note_name_with_octave = f"{note_name}"
    oled.text(note_name_with_octave, 2, 2)  # Adjust x and y as needed

    planes_y_position = 0  # Adjusted height position for plane indicators
    planes_step_width = 7  # Width per plane indicator
    planes_total_width = planes_step_width * MAX_PLANES
    planes_margin = (128 - planes_total_width) // 2

    for i in range(MAX_PLANES):
        x_position = planes_margin + i * planes_step_width
        square_size = 6
        square_x = x_position + (planes_step_width - square_size) // 2
        if i < planes:
            oled.fill_rect(square_x, planes_y_position + 2, square_size, square_size, 1)
        else:
            oled.rect(square_x, planes_y_position + 2, square_size, square_size, 1)

    y_position = planes_y_position + 17  # Adjusted height position for the note values
    x_positions = []

    step_width = 14  # Adjusted width per step
    total_steps_width = step_width * MAX_NOTES
    margin = (128 - total_steps_width) // 2  # Center the steps on the screen

    for i in range(MAX_NOTES):
        x_position = margin + i * step_width
        x_positions.append(x_position)
        note = plane1_notes[i]
        if note is not None:
            degree = note + 1  # Degrees range from 1 to 16
            degree_str = str(degree)
            degree_len = len(degree_str)
            char_width = 6 * degree_len
            text_x = x_position + (step_width - char_width) // 2
            oled.text(degree_str, text_x, y_position)
        else:
            text_x = x_position + (step_width - 6) // 2
            oled.text("-", text_x, y_position)
    caret_x = x_positions[current_note_index] + (step_width - 6) // 2
    caret_y = y_position + 10  # Position of the caret under the numbers
    oled.text("^", caret_x, caret_y)

    oled.show()  # Refresh the display

def advance_sequence():
    global current_step_index, sequence_length, last_active_note_index
    global last_activity_time
    last_active_note_index = 0
    for i in range(MAX_NOTES - 1, -1, -1):
        if plane1_notes[i] is not None:
            last_active_note_index = i
            break
    else:
        return

    sequence_length = (last_active_note_index + 1) * planes
    current_step_index = (current_step_index + 1) % sequence_length
    output_notes()
    update_display()
    last_activity_time = time.ticks_ms()
    screensaver_active = False

def output_notes():
    global last_note_value
    root_note = read_root_note()
    note_index = (current_step_index // planes) % (last_active_note_index + 1)
    plane_number = (current_step_index % planes) + 1

    note_value = plane1_notes[note_index]

    if note_value is not None:
        if note_index == 0:
            adjusted_note_value = plane1_notes[0]
        else:
            difference = plane1_notes[0] - reference_note1_value
            adjusted_note_value = note_value + difference

        plane_interval = get_plane_interval(plane_number)
        adjusted_note_value += plane_interval

        max_position = 16  # Degrees 0 to 15
        adjusted_note_value = adjusted_note_value % max_position

        last_note_value = adjusted_note_value
    else:
        next_note_exists = False
        for i in range(note_index + 1, last_active_note_index + 1):
            if plane1_notes[i] is not None:
                next_note_exists = True
                break
        if next_note_exists and last_note_value is not None:
            adjusted_note_value = last_note_value
        else:
            adjusted_note_value = None
            last_note_value = None

    if adjusted_note_value is None:
        for output in OUTPUT_SCALES:
            output.voltage(0)
        return

    for output, scale_name in OUTPUT_SCALES.items():
        interval = get_scale_interval(adjusted_note_value, scale_name)
        note_midi = root_note + interval
        if note_midi < 36:
            note_midi += 12  # Shift up an octave if too low
        elif note_midi > 84:
            note_midi -= 12  # Shift down an octave if too high
        voltage = (note_midi - 36) / 12.0  # Assuming C2 (MIDI 36) is 0V
        output.voltage(voltage)

def get_plane_interval(plane_number):
    if plane_number == 1:
        return 0  # Plane 1 is the base
    else:
        return plane_notes.get(plane_number, PLANE_INTERVALS.get(plane_number, 0))

def randomize_planes(set_display_time=True):
    global plane_notes, combo_press_display_time
    possible_intervals = [-7, -5, -3, 0, 3, 4, 5, 7, 9, 12]  # Possible scale degree intervals
    for plane_number in range(2, MAX_PLANES + 1):
        plane_notes[plane_number] = random.choice(possible_intervals)
    if set_display_time:
        combo_press_display_time = time.ticks_ms()
    update_display()

def handle_combo_press():
    randomize_planes()

def init_patch():
    global planes, current_step_index, current_note_index, plane1_notes, plane_notes, last_note_value, reference_note1_value, b2_long_press_display_time
    planes = 1
    current_step_index = -1
    current_note_index = 0
    last_note_value = None
    plane1_notes = [None] * MAX_NOTES
    plane1_notes[0] = 0
    reference_note1_value = plane1_notes[0]
    plane_notes = {}
    randomize_planes()
    b2_long_press_display_time = time.ticks_ms()
    update_display()

def main():
    global planes, current_step_index, current_note_index, reference_note1_value
    global combo_press_time, b1_press_time, b2_press_time, b1_long_press_handled, b2_long_press_handled
    global ain_mode
    global screensaver_active, screensaver_last_update, screensaver_frame_index, last_activity_time

    last_k1_value = k1.read_position()
    last_k2_value = k2.read_position()
    last_b1_state = False
    last_b2_state = False

    last_din_state = din.value()
    current_step_index = -1

    randomize_planes(set_display_time=False)

    update_display()

    while True:
        b1_state = b1.value()
        b2_state = b2.value()
        k1_value = k1.read_position()
        k2_value = k2.read_position()

        current_time = time.ticks_ms()

        if time.ticks_diff(current_time, last_activity_time) > screensaver_timeout:
            if not screensaver_active:
                screensaver_active = True
                screensaver_frame_index = 0
                update_display()
            else:
                if time.ticks_diff(current_time, screensaver_last_update) > screensaver_interval:
                    screensaver_frame_index = (screensaver_frame_index + 1) % len(screensaver_frames)
                    screensaver_last_update = current_time
                    update_display()
        else:
            screensaver_active = False

        if b1_state and b2_state:
            if combo_press_time == 0:
                combo_press_time = current_time
            elif time.ticks_diff(current_time, combo_press_time) > combo_press_threshold:
                handle_combo_press()
                combo_press_time = 0  # Reset combo press time
                last_activity_time = current_time  # Update activity time
        else:
            combo_press_time = 0  # Reset if buttons are not both pressed

        if b1_state and not last_b1_state:
            b1_press_time = current_time
            b1_long_press_handled = False
        elif b1_state:
            press_duration = time.ticks_diff(current_time, b1_press_time)
            if press_duration >= long_press_threshold and not b1_long_press_handled:
                ain_mode = 'DIATONIC' if ain_mode == 'ROOT' else 'ROOT'
                b1_long_press_handled = True
                update_display()
                last_activity_time = current_time  # Update activity time
        elif not b1_state and last_b1_state:
            press_duration = time.ticks_diff(current_time, b1_press_time)
            if press_duration < long_press_threshold and not b1_long_press_handled:
                current_note_index = (current_note_index - 1) % MAX_NOTES
                update_display()
                last_activity_time = current_time  # Update activity time
            b1_press_time = 0  # Reset press time
            b1_long_press_handled = False
        last_b1_state = b1_state

        if b2_state and not last_b2_state:
            b2_press_time = current_time
            b2_long_press_handled = False
        elif b2_state:
            press_duration = time.ticks_diff(current_time, b2_press_time)
            if press_duration >= long_press_threshold and not b2_long_press_handled:
                init_patch()
                b2_long_press_handled = True
                last_activity_time = current_time  # Update activity time
        elif not b2_state and last_b2_state:
            press_duration = time.ticks_diff(current_time, b2_press_time)
            if press_duration < long_press_threshold and not b2_long_press_handled:
                current_note_index = (current_note_index + 1) % MAX_NOTES
                update_display()
                last_activity_time = current_time  # Update activity time
            b2_press_time = 0  # Reset press time
            b2_long_press_handled = False
        last_b2_state = b2_state

        if abs(k1_value - last_k1_value) > 0.5:
            max_position = 16  # Positions 0 to 16 (17 positions)
            position = int((k1_value / 100) * (max_position + 1))
            if position > max_position:
                position = max_position

            if current_note_index == 0:
                if ain_mode == 'DIATONIC':
                    pass  # Do nothing, K1 does not affect plane1_notes[0] in 'DIATONIC' mode
                else:
                    # Ensure position is at least 1
                    if position < 1:
                        position = 1
                    plane1_notes[current_note_index] = position - 1  # Values 0 to 15
            else:
                if position == 0:
                    plane1_notes[current_note_index] = None  # Represents '-'
                else:
                    plane1_notes[current_note_index] = position - 1  # Values 0 to 15

            last_k1_value = k1_value
            update_display()
            last_activity_time = current_time  # Update activity time
            
        if abs(k2_value - last_k2_value) > 0.5:
            new_planes = int(round((k2_value / 99.0) * (MAX_PLANES - 1))) + 1
            if new_planes < 1:
                new_planes = 1
            elif new_planes > MAX_PLANES:
                new_planes = MAX_PLANES
            if new_planes != planes:
                planes = new_planes
                update_display()
                last_activity_time = current_time  # Update activity time
            last_k2_value = k2_value

        din_state = din.value()
        if din_state and not last_din_state:
            advance_sequence()
            last_activity_time = current_time  # Update activity time
        last_din_state = din_state

main()