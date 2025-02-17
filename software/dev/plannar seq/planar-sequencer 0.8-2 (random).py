from europi import *
import time
import random

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
sequence_steps = []  # List of (note_index, plane_number) tuples

plane1_notes = [None] * MAX_NOTES
plane1_notes[0] = 0
reference_note1_value = plane1_notes[0]
plane_notes = {}    # Dictionary to hold intervals for planes 2 to 8
current_note_index = 0
last_active_note_index = 0  # Initialize here

combo_press_time = 0
combo_press_threshold = 100        # Time in ms to detect combo press
combo_press_display_time = 0       # For displaying feedback
combo_press_feedback_duration = 1000  # Duration to display feedback in ms

long_press_threshold = 1000        # Time in ms to detect long press
b1_press_time = 0
b2_press_time = 0
b1_long_press_handled = False
b2_long_press_handled = False

ain_mode = 'ROOT'  # Default to 'ROOT' mode

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

                if last_stable_note is None or abs(position - last_stable_note) >= hysteresis_threshold:
                    plane1_notes[0] = position
                    last_stable_note = position
                    update_last_active_note_index()  # Add this line
                    update_display()

    else:
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
    oled.fill(0)
    current_time = time.ticks_ms()

    if screensaver_active:
        display_screensaver()
        return

    display_mode_indicator(current_time)
    display_note_name()
    display_plane_indicators()
    display_note_values()
    oled.show()
    
def display_screensaver():
    frame = screensaver_frames[screensaver_frame_index]
    text_width = len(frame) * 6
    x_position = (128 - text_width) // 2
    oled.text(frame, x_position, 12)
    oled.show()

def display_mode_indicator(current_time):
    global combo_press_display_time
    if combo_press_display_time != 0 and time.ticks_diff(current_time, combo_press_display_time) < combo_press_feedback_duration:
        oled.text('*', 119, 2)
    else:
        oled.text('R' if ain_mode == 'ROOT' else 'D', 119, 2)
        if combo_press_display_time != 0 and time.ticks_diff(current_time, combo_press_display_time) >= combo_press_feedback_duration:
            combo_press_display_time = 0

def display_note_name():
    note_name = NOTE_NAMES_SHARPS[last_root_note % 12]
    oled.text(note_name, 2, 2)

def display_plane_indicators():
    planes_y_position = 0
    planes_step_width = 7
    planes_total_width = planes_step_width * MAX_PLANES
    planes_margin = (128 - planes_total_width) // 2

    for i in range(MAX_PLANES):
        x_position = planes_margin + i * planes_step_width
        square_size = 6
        square_x = x_position + (planes_step_width - square_size) // 2
        y_position = planes_y_position + 2
        if i < planes:
            oled.fill_rect(square_x, y_position, square_size, square_size, 1)
        else:
            oled.rect(square_x, y_position, square_size, square_size, 1)

def display_note_values():
    y_position = 17
    x_positions = []
    step_width = 14
    total_steps_width = step_width * MAX_NOTES
    margin = (128 - total_steps_width) // 2

    for i in range(MAX_NOTES):
        x_position = margin + i * step_width
        x_positions.append(x_position)
        note = plane1_notes[i]
        if note is not None:
            degree = note + 1
            degree_str = str(degree)
            char_width = 6 * len(degree_str)
            text_x = x_position + (step_width - char_width) // 2
            oled.text(degree_str, text_x, y_position)
        else:
            text_x = x_position + (step_width - 6) // 2
            oled.text("-", text_x, y_position)

    # Draw caret under current note
    caret_x = x_positions[current_note_index] + (step_width - 6) // 2
    caret_y = y_position + 10
    oled.text("^", caret_x, caret_y)

def advance_sequence():
    global current_step_index, last_activity_time, screensaver_active

    if not sequence_steps:
        return  # No steps to advance

    current_step_index = (current_step_index + 1) % len(sequence_steps)

    output_notes()
    update_display()
    last_activity_time = time.ticks_ms()
    screensaver_active = False
    
def update_last_active_note_index():
    global last_active_note_index
    active_indices = [i for i, note in enumerate(plane1_notes) if note is not None]
    if active_indices:
        last_active_note_index = max(active_indices)
    else:
        last_active_note_index = -1  # Indicates no active notes

    # Regenerate sequence steps whenever active notes change
    generate_sequence_steps()
    
def generate_sequence_steps():
    global sequence_steps, planes, last_active_note_index
    sequence_steps = []

    # Generate all combinations of note indices and plane numbers
    for note_index in range(last_active_note_index + 1):
        if plane1_notes[note_index] is not None:
            for plane_number in range(1, planes + 1):
                sequence_steps.append((note_index, plane_number))

    # Optional: Exclude the first step from shuffling to keep it immutable
    if sequence_steps:
        first_step = sequence_steps[0]  # Save the first step
        steps_to_shuffle = sequence_steps[1:]  # Steps to be shuffled

        # Shuffle the steps
        shuffle_list(steps_to_shuffle)

        # Reconstruct the sequence_steps list
        sequence_steps = [first_step] + steps_to_shuffle
    else:
        # If no steps, sequence_steps remains empty
        pass

def output_notes():
    global last_note_value

    root_note = read_root_note()

    if not sequence_steps:
        return  # No steps to output

    note_index, plane_number = sequence_steps[current_step_index]

    note_value = plane1_notes[note_index]

    adjusted_note_value = calculate_adjusted_note_value(note_index, note_value, plane_number)

    if adjusted_note_value is None:
        for output in OUTPUT_SCALES:
            output.voltage(0)
        return

    for output, scale_name in OUTPUT_SCALES.items():
        interval = get_scale_interval(adjusted_note_value, scale_name)
        note_midi = root_note + interval
        # Ensure note_midi is within the desired range
        note_midi = ((note_midi - 36) % 48) + 36  # Wrap between MIDI 36 and 84
        voltage = (note_midi - 36) / 12.0
        output.voltage(voltage)
def calculate_adjusted_note_value(note_index, note_value, plane_number):
    global last_note_value
    if note_value is not None:
        if note_index == 0:
            adjusted_note_value = note_value
        else:
            difference = plane1_notes[0] - reference_note1_value
            adjusted_note_value = note_value + difference
        adjusted_note_value += get_plane_interval(plane_number)
        adjusted_note_value %= 16  # Ensure within 0-15
        last_note_value = adjusted_note_value
        return adjusted_note_value
    else:
        # Handle rests and hold over notes
        next_note_exists = any(plane1_notes[i] is not None for i in range(note_index + 1, last_active_note_index + 1))
        if next_note_exists and last_note_value is not None:
            return last_note_value
        else:
            last_note_value = None
            return None

def get_plane_interval(plane_number):
    if plane_number == 1:
        return 0  # Plane 1 is the base
    else:
        return plane_notes.get(plane_number, PLANE_INTERVALS.get(plane_number, 0))

def randomize_planes(set_display_time=True):
    global plane_notes, combo_press_display_time
    possible_intervals = [-7, -5, -3, 0, 3, 4, 5, 7, 9, 11]  # Possible scale degree intervals

    # Randomize plane intervals
    for plane_number in range(2, MAX_PLANES + 1):
        plane_notes[plane_number] = random.choice(possible_intervals)

    # Scramble the note sequence
    scramble_notes()

    # Generate new sequence steps
    generate_sequence_steps()

    if set_display_time:
        combo_press_display_time = time.ticks_ms()
    update_display()
    
def scramble_notes():
    global plane1_notes, reference_note1_value
    # Identify indices of active notes, excluding index 0
    active_indices = [i for i, note in enumerate(plane1_notes) if note is not None and i != 0]
    
    # Extract the note values at those indices
    active_notes = [plane1_notes[i] for i in active_indices]
    
    if not active_notes:
        return  # No active notes to scramble

    # Shuffle the active notes
    shuffle_list(active_notes)
    
    # Place the shuffled notes back into their original positions
    for idx, note in zip(active_indices, active_notes):
        plane1_notes[idx] = note
    
    # plane1_notes[0] remains unchanged
    # Update reference_note1_value since plane1_notes[0] remains the same
    reference_note1_value = plane1_notes[0] if plane1_notes[0] is not None else 0
    
    # Update last_active_note_index after scrambling notes
    update_last_active_note_index()
    
def shuffle_list(lst):
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)  # Get a random index from 0 to i
        lst[i], lst[j] = lst[j], lst[i]  # Swap elements

def init_patch():
    global planes, current_step_index, current_note_index, plane1_notes, plane_notes, last_note_value, reference_note1_value
    planes = 1
    current_step_index = -1
    current_note_index = 0
    last_note_value = None
    plane1_notes = [None] * MAX_NOTES
    plane1_notes[0] = 0
    reference_note1_value = plane1_notes[0]
    plane_notes = {}
    randomize_planes(set_display_time=False)

    update_last_active_note_index()

    update_display()

def initialize():
    global last_k1_value, last_k2_value, last_b1_state, last_b2_state, last_din_state
    last_k1_value = k1.read_position()
    last_k2_value = k2.read_position()
    last_b1_state = False
    last_b2_state = False
    last_din_state = din.value()
    init_patch()  # Call init_patch to initialize variables
    update_display()

def handle_screensaver(current_time):
    global screensaver_active, screensaver_last_update, screensaver_frame_index, last_activity_time
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

def handle_combo_press(current_time, b1_state, b2_state):
    global combo_press_time, last_activity_time
    if b1_state and b2_state:
        if combo_press_time == 0:
            combo_press_time = current_time
        elif time.ticks_diff(current_time, combo_press_time) > combo_press_threshold:
            randomize_planes()
            combo_press_time = 0
            last_activity_time = current_time
    else:
        combo_press_time = 0

def handle_b1_press(current_time, b1_state):
    global b1_press_time, b1_long_press_handled, last_activity_time, ain_mode, current_note_index, last_b1_state
    if b1_state and not last_b1_state:
        b1_press_time = current_time
        b1_long_press_handled = False
    elif b1_state:
        press_duration = time.ticks_diff(current_time, b1_press_time)
        if press_duration >= long_press_threshold and not b1_long_press_handled:
            ain_mode = 'DIATONIC' if ain_mode == 'ROOT' else 'ROOT'
            b1_long_press_handled = True
            update_display()
            last_activity_time = current_time
    elif not b1_state and last_b1_state:
        press_duration = time.ticks_diff(current_time, b1_press_time)
        if press_duration < long_press_threshold and not b1_long_press_handled:
            current_note_index = (current_note_index - 1) % MAX_NOTES
            update_display()
            last_activity_time = current_time
        b1_press_time = 0
        b1_long_press_handled = False
    last_b1_state = b1_state

def handle_b2_press(current_time, b2_state):
    global b2_press_time, b2_long_press_handled, last_activity_time, current_note_index, last_b2_state
    if b2_state and not last_b2_state:
        b2_press_time = current_time
        b2_long_press_handled = False
    elif b2_state:
        press_duration = time.ticks_diff(current_time, b2_press_time)
        if press_duration >= long_press_threshold and not b2_long_press_handled:
            init_patch()
            b2_long_press_handled = True
            last_activity_time = current_time
    elif not b2_state and last_b2_state:
        press_duration = time.ticks_diff(current_time, b2_press_time)
        if press_duration < long_press_threshold and not b2_long_press_handled:
            current_note_index = (current_note_index + 1) % MAX_NOTES
            update_display()
            last_activity_time = current_time
        b2_press_time = 0
        b2_long_press_handled = False
    last_b2_state = b2_state

def handle_k1_input(k1_value, current_time):
    global last_k1_value, plane1_notes, current_note_index, last_activity_time
    if abs(k1_value - last_k1_value) > 0.5:
        max_position = 16
        position = int((k1_value / 100) * (max_position + 1))
        position = min(position, max_position)  # Ensure position does not exceed max_position

        if current_note_index == 0:
            if ain_mode != 'DIATONIC':
                position = max(position, 1)  # Ensure position is at least 1
                plane1_notes[current_note_index] = position - 1
        else:
            plane1_notes[current_note_index] = None if position == 0 else position - 1

        # Update last_active_note_index after modifying plane1_notes
        update_last_active_note_index()

        last_k1_value = k1_value
        update_display()
        last_activity_time = current_time

def handle_k2_input(k2_value, current_time):
    global last_k2_value, planes, last_activity_time
    if abs(k2_value - last_k2_value) > 0.5:
        new_planes = int(round((k2_value / 99.0) * (MAX_PLANES - 1))) + 1
        if new_planes < 1:
            new_planes = 1
        elif new_planes > MAX_PLANES:
            new_planes = MAX_PLANES
        if new_planes != planes:
            planes = new_planes
            update_display()
            last_activity_time = current_time
            # Regenerate sequence steps
            generate_sequence_steps()
        last_k2_value = k2_value

def handle_din_input(din_state, current_time):
    global last_din_state, last_activity_time
    if din_state and not last_din_state:
        advance_sequence()
        last_activity_time = current_time
    last_din_state = din_state

def main():
    initialize()
    while True:
        current_time = time.ticks_ms()
        b1_state = b1.value()
        b2_state = b2.value()
        k1_value = k1.read_position()
        k2_value = k2.read_position()
        din_state = din.value()

        handle_screensaver(current_time)
        handle_combo_press(current_time, b1_state, b2_state)
        handle_b1_press(current_time, b1_state)
        handle_b2_press(current_time, b2_state)
        handle_k1_input(k1_value, current_time)
        handle_k2_input(k2_value, current_time)
        handle_din_input(din_state, current_time)

main()