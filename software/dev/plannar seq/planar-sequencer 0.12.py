from europi import *
import time
import random

MAX_PLANES = 8
MAX_NOTES = 8

SCALES = {
    'major': [0, 2, 4, 5, 7, 9, 11],
    'minor': [0, 2, 3, 5, 7, 8, 10],
    'harmonic_major': [0, 2, 4, 5, 7, 8, 11],
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
    'custom': [0, 2, 4, 5, 7, 8, 10],
}

# Removed cv3 from OUTPUT_SCALES
OUTPUT_SCALES = {
    cv1: 'major',
    cv2: 'minor',
    cv4: 'custom',
    cv5: 'harmonic_minor',
}

PLANE_INTERVALS = {
    2: 7,   # +1 octave (7 scale degrees in major scale)
    3: 4,   # + perfect 5th
    4: 3,  # - perfect 4th
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
last_ain_voltage = None  # Initialize last AIN voltage

screensaver_active = False
screensaver_last_update = 0
screensaver_interval = 500
screensaver_timeout = 10000  # Time in ms of inactivity before screensaver activates (10 seconds)
last_activity_time = time.ticks_ms()
screensaver_frames = ['   ', '.  ', '.. ', '...']
screensaver_frame_index = 0

def read_root_note():
    global last_ain_voltage, last_root_note
    voltage = ain.read_voltage()

    if ain_mode == 'ROOT':
        if last_ain_voltage is None or abs(voltage - last_ain_voltage) > voltage_threshold:
            last_ain_voltage = voltage
            midi_note = int(voltage * 12) + 36  # Map voltage to MIDI note (0V = MIDI 36)
            last_root_note = midi_note
        return last_root_note

    elif ain_mode == 'DIATONIC':
        if last_root_note is None:
            last_root_note = 60

        if last_ain_voltage is None or abs(voltage - last_ain_voltage) > voltage_threshold:
            last_ain_voltage = voltage

            midi_note = int(voltage * 12) + 36

            scale_name = OUTPUT_SCALES[cv1]
            scale_intervals = SCALES[scale_name]
            scale_length = len(scale_intervals)

            semitone_distance = midi_note - last_root_note

            max_scale_degrees = 32
            scale_semitones = []
            for degree in range(max_scale_degrees):
                octave = degree // scale_length
                index = degree % scale_length
                semitone = octave * 12 + scale_intervals[index]
                scale_semitones.append(semitone)

            closest_degree = min(range(len(scale_semitones)), key=lambda x: abs(scale_semitones[x] - semitone_distance))

            plane1_notes[0] = closest_degree

            update_last_active_note_index()
            update_display()
        return last_root_note

    else:
        midi_note = int(voltage * 12) + 36  # Map voltage to MIDI note
        return midi_note

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

    generate_sequence_steps()
    
def generate_sequence_steps(shuffle=False):
    global sequence_steps, planes, last_active_note_index
    sequence_steps = []

    for note_index in range(last_active_note_index + 1):
        note_value = plane1_notes[note_index]
        if note_value is not None:
            for plane_number in range(1, planes + 1):
                sequence_steps.append((note_index, plane_number))
        else:
            # Handle gaps differently when planes > 1
            # For example, add only one rest step regardless of the number of planes
            sequence_steps.append((note_index, 1))  # Only one rest step
            # Alternatively, skip adding rest steps entirely
            # pass

    if shuffle:
        if sequence_steps:
            first_step = sequence_steps[0]  # Save the first step
            steps_to_shuffle = sequence_steps[1:]  # Steps to be shuffled

            shuffle_list(steps_to_shuffle)

            # Reconstruct the sequence_steps list
            sequence_steps = [first_step] + steps_to_shuffle

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
        cv3.voltage(0)  # Ensure cv3 outputs 0V during rests
        return

    # **Handle cv3 separately to output the root note (plane 1, note 1)**
    root_note_value = plane1_notes[0]
    if root_note_value is not None:
        # Calculate the adjusted note value for plane1 note1
        adjusted_root_note_value = calculate_adjusted_note_value(0, root_note_value, 1)
        # Choose a scale for cv3 if desired, or use 'major' as default
        cv3_scale_name = 'major'  # You can change this to any scale
        interval_cv3 = get_scale_interval(adjusted_root_note_value, scale_name=cv3_scale_name)
        note_midi_cv3 = root_note + interval_cv3
        # Ensure note_midi_cv3 is within the desired range
        if note_midi_cv3 < 36:
            note_midi_cv3 += 12  # Shift up an octave if too low
        elif note_midi_cv3 > 84:
            note_midi_cv3 -= 12  # Shift down an octave if too high
        voltage_cv3 = (note_midi_cv3 - 36) / 12.0
        cv3.voltage(voltage_cv3)
    else:
        cv3.voltage(0)  # Output 0V if root note is not set

    # **Handle other CV outputs as before**
    for output, scale_name in OUTPUT_SCALES.items():
        interval = get_scale_interval(adjusted_note_value, scale_name)
        note_midi = root_note + interval
        # Ensure note_midi is within the desired range
        if note_midi < 36:
            note_midi += 12  # Shift up an octave if too low
        elif note_midi > 84:
            note_midi -= 12  # Shift down an octave if too high
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
        # Handle rests and hold-over notes
        next_note_exists = any(
            plane1_notes[i] is not None for i in range(note_index + 1, last_active_note_index + 1)
        )
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

    scramble_notes()

    generate_sequence_steps(shuffle=True)

    if set_display_time:
        combo_press_display_time = time.ticks_ms()
    update_display()
    
def scramble_notes():
    global plane1_notes, reference_note1_value
    # Identify indices of active notes, excluding index 0
    active_indices = [i for i, note in enumerate(plane1_notes) if note is not None and i != 0]
    
    active_notes = [plane1_notes[i] for i in active_indices]
    
    if not active_notes:
        return  # No active notes to scramble

    shuffle_list(active_notes)
    
    for idx, note in zip(active_indices, active_notes):
        plane1_notes[idx] = note
    
    reference_note1_value = plane1_notes[0] if plane1_notes[0] is not None else 0
    
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
    plane_notes = PLANE_INTERVALS.copy() 

    update_last_active_note_index()
    generate_sequence_steps()
    update_display()

def initialize():
    global last_k1_value, last_k2_value, last_b1_state, last_b2_state, last_din_state
    last_k1_value = k1.read_position()
    last_k2_value = k2.read_position()
    last_b1_state = False
    last_b2_state = False
    last_din_state = din.value()
    init_patch()
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
            # Regenerate sequence steps without shuffling
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
