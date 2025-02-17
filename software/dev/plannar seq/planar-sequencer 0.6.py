from europi import *
import time
import random

# Define constants
MAX_PLANES = 8
MAX_NOTES = 8

# Define scales (intervals in semitones)
SCALES = {
    'major': [0, 2, 4, 5, 7, 9, 11],
    'minor': [0, 2, 3, 5, 7, 8, 10],
    'harmonic_major': [0, 2, 4, 5, 7, 8, 11],
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
}

# Assign scales to outputs
OUTPUT_SCALES = {
    cv1: 'major',
    cv2: 'minor',
    cv4: 'harmonic_major',
    cv5: 'harmonic_minor',
}

# Plane intervals (in scale degrees)
PLANE_INTERVALS = {
    2: 7,   # +1 octave (7 scale degrees in major scale)
    3: 4,   # + perfect 5th
    4: -3,  # - perfect 4th
    5: 0,   # Unison
    6: 3,   # + perfect 4th
    7: 7,   # +1 octave
    8: 4,   # + perfect 5th
}

# Initialize variables
planes = 1                      # Number of active planes
current_step_index = -1         # Index of the current step in the sequence
last_note_value = None          # Initialize last note value

# Initialize note data structures
plane1_notes = [None] * MAX_NOTES    # Notes in Plane 1
plane1_notes[0] = 0                  # First note is always on and set to scale degree 0

# Reference value for note 1
reference_note1_value = plane1_notes[0]

# Randomized plane data (planes 2 to 8)
plane_notes = {}    # Dictionary to hold intervals for planes 2 to 8

# For combo press detection
combo_press_time = 0
combo_press_threshold = 100        # Time in ms to detect combo press
combo_press_display_time = 0       # For displaying feedback
combo_press_feedback_duration = 1000  # Duration to display feedback in ms

# For b2 long press feedback
b2_long_press_display_time = 0    # For displaying 'x' when sequence is cleared

# Variables for note editing
current_note_index = 0             # Index of the current note being edited

# For button press times
long_press_threshold = 1000        # Time in ms to detect long press
b1_press_time = 0
b2_press_time = 0
b1_long_press_handled = False      # Flag to prevent multiple triggers
b2_long_press_handled = False      # Flag to prevent multiple triggers

# AIN mode
ain_mode = 'ROOT'  # Default to 'ROOT' mode

# Variables for sample and hold
last_ain_voltage = None
last_root_note = 36  # Default root note (C2)
voltage_threshold = 0.02  # Voltage change threshold for sample and hold

# --- Screensaver Variables ---
screensaver_active = False
screensaver_last_update = 0
screensaver_interval = 500  # Time in ms between screensaver frames
screensaver_timeout = 10000  # Time in ms of inactivity before screensaver activates (10 seconds)
last_activity_time = time.ticks_ms()
screensaver_frames = ['   ', '.  ', '.. ', '...']
screensaver_frame_index = 0
# ------------------------------

def read_root_note():
    global last_ain_voltage, last_root_note
    voltage = ain.read_voltage()
    if ain_mode == 'ROOT':
        # Implement sample and hold
        if last_ain_voltage is None or abs(voltage - last_ain_voltage) > voltage_threshold:
            last_ain_voltage = voltage
            midi_note = int((voltage / 5.0) * 60) + 36
            # Wrap midi_note to stay within 36 to 84 (C2 to C6)
            midi_note = ((midi_note - 36) % 48) + 36
            last_root_note = midi_note
        return last_root_note
    elif ain_mode == 'DIATONIC':
        # Use the last_root_note set in ROOT mode
        # Map AIN voltage to scale degrees
        max_position = 16
        position = int((voltage / 5.0) * max_position) % max_position
        plane1_notes[0] = position
        # Do not change reference_note1_value
        update_display()
        # Return the last root note set in ROOT mode
        return last_root_note
    else:
        # Default behavior
        midi_note = int((voltage / 5.0) * 60) + 36
        return midi_note

def get_scale_interval(scale_degree, scale_name='major'):
    scale_intervals = SCALES[scale_name]
    scale_length = len(scale_intervals)
    index = scale_degree % scale_length
    octave_shift = (scale_degree // scale_length) * 12
    interval = scale_intervals[index] + octave_shift
    return interval

def update_display():
    global combo_press_display_time, b2_long_press_display_time
    oled.fill(0)  # Clear the display

    # --- Screensaver Activation Check ---
    current_time = time.ticks_ms()
    if screensaver_active:
        # Display screensaver
        frame = screensaver_frames[screensaver_frame_index]
        text_width = len(frame) * 6  # Approximate character width
        x_position = (128 - text_width) // 2
        oled.text(frame, x_position, 24)  # Vertically centered
        oled.show()
        return
    # ------------------------------------

    # Display AIN Mode Indicator
    # Draw a square at (0, 0) with size 11x11
    oled.rect(0, 0, 11, 11, 1)  # x, y, width, height, color

    # Display 'R' or 'D' inside the square
    if ain_mode == 'ROOT':
        oled.text('R', 2, 2)
    else:
        oled.text('D', 2, 2)

    # Display Combo Press Feedback (if within feedback duration)
    if combo_press_display_time != 0 and time.ticks_diff(current_time, combo_press_display_time) < combo_press_feedback_duration:
        # Display '*' at top right corner
        oled.text("*", 120, 0)
    elif b2_long_press_display_time != 0 and time.ticks_diff(current_time, b2_long_press_display_time) < combo_press_feedback_duration:
        # Display 'x' at top right corner
        oled.text("x", 120, 0)
    else:
        combo_press_display_time = 0  # Reset display time
        b2_long_press_display_time = 0

    # Display Plane Indicators
    planes_y_position = 0  # Adjusted height position for plane indicators
    planes_step_width = 7  # Width per plane indicator
    planes_total_width = planes_step_width * MAX_PLANES
    planes_margin = (128 - planes_total_width) // 2

    for i in range(MAX_PLANES):
        x_position = planes_margin + i * planes_step_width
        # Center the square within the plane step width
        square_size = 6
        square_x = x_position + (planes_step_width - square_size) // 2
        if i < planes:
            # Active plane - draw filled square
            oled.fill_rect(square_x, planes_y_position + 2, square_size, square_size, 1)
        else:
            # Inactive plane - draw empty square
            oled.rect(square_x, planes_y_position + 2, square_size, square_size, 1)

    # Display Note Values
    y_position = planes_y_position + 17  # Adjusted height position for the note values
    x_positions = []  # To store x positions of each note for caret positioning

    step_width = 14  # Adjusted width per step
    total_steps_width = step_width * MAX_NOTES  # Should be 112 pixels
    margin = (128 - total_steps_width) // 2  # Center the steps on the screen

    for i in range(MAX_NOTES):
        x_position = margin + i * step_width
        x_positions.append(x_position)
        # Get the note value
        note = plane1_notes[i]
        if note is not None:
            degree = (note % 16) + 1  # Scale degrees 1 to 16
            degree_str = str(degree)
            degree_len = len(degree_str)
            char_width = 6 * degree_len  # Approximate total width of the text
            # Center the text within the step_width
            text_x = x_position + (step_width - char_width) // 2
            oled.text(degree_str, text_x, y_position)
        else:
            # Center the '-' within the step_width
            text_x = x_position + (step_width - 6) // 2
            oled.text("-", text_x, y_position)
    # Display caret under current_note_index
    # Adjust caret position to be centered under the number
    caret_x = x_positions[current_note_index] + (step_width - 6) // 2
    caret_y = y_position + 10  # Position of the caret under the numbers
    oled.text("^", caret_x, caret_y)

    oled.show()  # Refresh the display

def advance_sequence():
    global current_step_index, sequence_length, last_active_note_index
    global last_activity_time  # Track activity for screensaver
    # Determine the last active note index
    last_active_note_index = 0
    for i in range(MAX_NOTES - 1, -1, -1):
        if plane1_notes[i] is not None:
            last_active_note_index = i
            break
    else:
        # If no active notes, do nothing
        return

    # Compute total sequence length
    sequence_length = (last_active_note_index + 1) * planes

    # Advance to the next step
    current_step_index = (current_step_index + 1) % sequence_length

    # Output the notes for the new step
    output_notes()

    # Update the display to highlight the current step
    update_display()

    # Reset screensaver timer
    last_activity_time = time.ticks_ms()
    screensaver_active = False  # Deactivate screensaver if it was active

def output_notes():
    global last_note_value
    # Read the root note
    root_note = read_root_note()
    # Compute the current note index and plane number
    note_index = (current_step_index // planes) % (last_active_note_index + 1)
    plane_number = (current_step_index % planes) + 1

    # Get the note value from Plane 1
    note_value = plane1_notes[note_index]

    if note_value is not None:
        # Adjust note_value for notes 2-8
        if note_index == 0:
            adjusted_note_value = plane1_notes[0]
        else:
            # Compute the difference
            difference = plane1_notes[0] - reference_note1_value
            adjusted_note_value = note_value + difference

        # Apply plane interval in scale degrees
        plane_interval = get_plane_interval(plane_number)
        adjusted_note_value += plane_interval

        # Ensure adjusted_note_value is within valid range
        max_position = 16  # Degrees 0 to 15
        adjusted_note_value = adjusted_note_value % max_position

        # Update last_note_value
        last_note_value = adjusted_note_value
    else:
        # Check if there is a next note in the sequence within the looped range
        next_note_exists = False
        for i in range(note_index + 1, last_active_note_index + 1):
            if plane1_notes[i] is not None:
                next_note_exists = True
                break
        if next_note_exists and last_note_value is not None:
            # Hold the last note over off steps
            adjusted_note_value = last_note_value
        else:
            # No next note, output silence
            adjusted_note_value = None
            last_note_value = None

    if adjusted_note_value is None:
        # Output zero voltage (silence)
        for output in OUTPUT_SCALES:
            output.voltage(0)
        return

    # Output to each CV output with its own scale
    for output, scale_name in OUTPUT_SCALES.items():
        # Get the interval for the note
        interval = get_scale_interval(adjusted_note_value, scale_name)
        # Calculate the MIDI note
        note_midi = root_note + interval
        # Adjust note_midi to prevent wrapping down too early
        if note_midi < 36:
            note_midi += 12  # Shift up an octave if too low
        elif note_midi > 84:
            note_midi -= 12  # Shift down an octave if too high
        # Calculate the voltage for the note (1V per octave)
        voltage = (note_midi - 36) / 12.0  # Assuming C2 (MIDI 36) is 0V
        # Output the voltage
        output.voltage(voltage)

def get_plane_interval(plane_number):
    if plane_number == 1:
        return 0  # Plane 1 is the base
    else:
        # Return the plane interval in scale degrees
        return plane_notes.get(plane_number, PLANE_INTERVALS.get(plane_number, 0))

def randomize_planes(set_display_time=True):
    global plane_notes, combo_press_display_time
    possible_intervals = [-7, -5, -3, 0, 3, 4, 5, 7, 9, 12]  # Possible scale degree intervals
    for plane_number in range(2, MAX_PLANES + 1):
        # Randomize the interval from predefined intervals
        plane_notes[plane_number] = random.choice(possible_intervals)
    if set_display_time:
        # Set the combo press display time to current time
        combo_press_display_time = time.ticks_ms()
    update_display()

def handle_combo_press():
    # Reroll planes 2 to 8
    randomize_planes()

def init_patch():
    global planes, current_step_index, current_note_index, plane1_notes, plane_notes, last_note_value, reference_note1_value, b2_long_press_display_time
    planes = 1
    current_step_index = -1
    current_note_index = 0
    last_note_value = None
    plane1_notes = [None] * MAX_NOTES
    plane1_notes[0] = 0  # Reset first note
    reference_note1_value = plane1_notes[0]
    plane_notes = {}
    randomize_planes()  # Initialize plane intervals
    # Set b2 long press display time
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

    # For timing the DIN clock input
    last_din_state = din.value()
    current_step_index = -1  # Initialize sequence index

    # Initialize plane intervals
    randomize_planes(set_display_time=False)

    # Update the display initially
    update_display()

    while True:
        # Read buttons and knobs
        b1_state = b1.value()
        b2_state = b2.value()
        k1_value = k1.read_position()
        k2_value = k2.read_position()

        current_time = time.ticks_ms()

        # --- Screensaver Activation ---
        # Check for inactivity
        if time.ticks_diff(current_time, last_activity_time) > screensaver_timeout:
            if not screensaver_active:
                screensaver_active = True
                screensaver_frame_index = 0
                update_display()
            else:
                # Update screensaver animation
                if time.ticks_diff(current_time, screensaver_last_update) > screensaver_interval:
                    screensaver_frame_index = (screensaver_frame_index + 1) % len(screensaver_frames)
                    screensaver_last_update = current_time
                    update_display()
        else:
            screensaver_active = False
        # -------------------------------

        # Handle combo press of b1 + b2
        if b1_state and b2_state:
            if combo_press_time == 0:
                combo_press_time = current_time
            elif time.ticks_diff(current_time, combo_press_time) > combo_press_threshold:
                # Combo press detected
                handle_combo_press()
                combo_press_time = 0  # Reset combo press time
                last_activity_time = current_time  # Update activity time
        else:
            combo_press_time = 0  # Reset if buttons are not both pressed

        # Handle b1 press/release
        if b1_state and not last_b1_state:
            # Button b1 pressed
            b1_press_time = current_time
            b1_long_press_handled = False
        elif b1_state:
            # Button b1 is being held down
            press_duration = time.ticks_diff(current_time, b1_press_time)
            if press_duration >= long_press_threshold and not b1_long_press_handled:
                # Long press - Toggle AIN mode
                ain_mode = 'DIATONIC' if ain_mode == 'ROOT' else 'ROOT'
                b1_long_press_handled = True
                update_display()
                last_activity_time = current_time  # Update activity time
        elif not b1_state and last_b1_state:
            # Button b1 released
            press_duration = time.ticks_diff(current_time, b1_press_time)
            if press_duration < long_press_threshold and not b1_long_press_handled:
                # Short press
                current_note_index = (current_note_index - 1) % MAX_NOTES
                update_display()
                last_activity_time = current_time  # Update activity time
            b1_press_time = 0  # Reset press time
            b1_long_press_handled = False
        last_b1_state = b1_state

        # Handle b2 press
        if b2_state and not last_b2_state:
            # Button b2 pressed
            b2_press_time = current_time
            b2_long_press_handled = False
        elif b2_state:
            # Button b2 is being held down
            press_duration = time.ticks_diff(current_time, b2_press_time)
            if press_duration >= long_press_threshold and not b2_long_press_handled:
                # Long press - INIT the patch
                init_patch()
                b2_long_press_handled = True
                last_activity_time = current_time  # Update activity time
        elif not b2_state and last_b2_state:
            # Button b2 released
            press_duration = time.ticks_diff(current_time, b2_press_time)
            if press_duration < long_press_threshold and not b2_long_press_handled:
                # Short press
                current_note_index = (current_note_index + 1) % MAX_NOTES
                update_display()
                last_activity_time = current_time  # Update activity time
            b2_press_time = 0  # Reset press time
            b2_long_press_handled = False
        last_b2_state = b2_state

        # Read k1 to adjust note values diatonically
        if abs(k1_value - last_k1_value) > 0.5:
            # Map k1 to scale degrees diatonically
            max_position = 16  # Degrees 0 to 15 (16 degrees)
            position = int((k1_value / 100) * max_position)
            position = position % max_position  # Wrap around at 16
            if current_note_index == 0:
                if ain_mode == 'DIATONIC':
                    # In DIATONIC mode, do not adjust plane1_notes[0] with k1
                    pass  # Do nothing, k1 does not affect plane1_notes[0]
                else:
                    # For main sequence note 1, "off" is not allowed
                    plane1_notes[current_note_index] = position
                    # Do not change reference_note1_value
            else:
                if position == 0:
                    # Turn the note off
                    plane1_notes[current_note_index] = None
                else:
                    plane1_notes[current_note_index] = position
            last_k1_value = k1_value
            update_display()
            last_activity_time = current_time  # Update activity time

        # Read k2 to adjust number of planes (up to 8)
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

        # Handle DIN clock input for sequencing
        din_state = din.value()
        if din_state and not last_din_state:
            # Rising edge detected on DIN input (external clock pulse)
            advance_sequence()
            last_activity_time = current_time  # Update activity time
        last_din_state = din_state

# Run the main loop
main()