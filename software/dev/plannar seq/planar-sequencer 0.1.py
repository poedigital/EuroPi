# EuroPi Sequencer with Diatonic Note Adjustment and Chromatic Root Shift
# Author: [Your Name]
# Date: [Date]

from europi import *
import time

# Define constants
MAX_PLANES = 8  # Maximum number of planes
MAX_NOTES = 8   # Maximum number of notes per plane

# Define scales (intervals in semitones)
SCALES = {
    'major': [0, 2, 4, 5, 7, 9, 11],  # Ionian mode
    'minor': [0, 2, 3, 5, 7, 8, 10],  # Aeolian mode
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

# Adjusted plane intervals to stay within 2 octaves
PLANE_INTERVALS = {
    2: 12,  # +1 octave
    3: 7,   # + perfect 5th
    4: -5,  # - perfect 4th
    5: 0,   # Unison (same as Plane 1)
    6: 5,   # + perfect 4th
    7: 12,  # +1 octave
    8: 7,   # + perfect 5th
}

# Initialize variables
planes = 1  # Number of active planes
current_step_index = -1  # Index of the current step in the sequence

# Initialize note data structures
plane1_notes = [None] * MAX_NOTES  # Notes in Plane 1
plane1_notes[0] = 0  # First note is always on and set to scale degree 0

shift_mode = False  # Shift modifier flag

# Function to read the root note from AIN
def read_root_note():
    # Read voltage from AIN and map it to a MIDI note number (e.g., 36 to 96)
    voltage = ain.read_voltage()
    # Map 0V to 5V to MIDI notes 36 (C2) to 96 (C7)
    midi_note = int((voltage / 5.0) * 60) + 36
    return midi_note

# Function to get the interval in semitones for a scale degree
def get_scale_interval(scale_degree, scale_name='major'):
    scale_intervals = SCALES[scale_name]
    # Wrap the scale degree within the scale length
    index = scale_degree % len(scale_intervals)
    # Calculate how many octaves up or down we need to go
    octave_shift = (scale_degree // len(scale_intervals)) * 12
    interval = scale_intervals[index] + octave_shift
    return interval

# Function to update the OLED display
def update_display():
    oled.fill(0)  # Clear the display

    # Display Shift Mode Status
    shift_text = "SHIFT" if shift_mode else ""
    oled.text(shift_text, 0, 0)

    # Display Number of Planes
    planes_text = "Planes: {}".format(planes)
    oled.text(planes_text, 0, 0)

    # Display Number of Active Notes
    active_notes = len([note for note in plane1_notes if note is not None])
    notes_text = "Notes: {}".format(active_notes)
    oled.text(notes_text, 0, 10)

    # Display Current Note Value
    active_notes_indices = [i for i, note in enumerate(plane1_notes) if note is not None]
    if active_notes_indices:
        current_note_pos = (current_step_index // planes) % len(active_notes_indices)
        note_index = active_notes_indices[current_note_pos]
        note_value = plane1_notes[note_index]
        degree = note_value % len(SCALES['major']) + 1  # Scale degree (1-based)
        oled.text("Degree: {}".format(degree), 0, 20)
    else:
        oled.text("No Active Notes", 0, 20)

    oled.show()  # Refresh the display

# Function to handle sequencing (advance to the next step)
def advance_sequence():
    global current_step_index
    # Get the number of active notes
    active_notes_indices = [i for i, note in enumerate(plane1_notes) if note is not None]
    number_of_active_notes = len(active_notes_indices)
    if number_of_active_notes == 0:
        number_of_active_notes = 1  # Prevent division by zero
    # Compute total sequence length
    sequence_length = number_of_active_notes * planes
    # Advance to the next step
    current_step_index = (current_step_index + 1) % sequence_length
    # Update the display to reflect the new step
    update_display()
    # Output the notes for the new step
    output_notes()

# Function to output the notes for the current step
def output_notes():
    # Read the root note
    root_note = read_root_note()
    # Get the number of active notes
    active_notes_indices = [i for i, note in enumerate(plane1_notes) if note is not None]
    number_of_active_notes = len(active_notes_indices)
    if number_of_active_notes == 0:
        return  # No active notes to play
    # Compute the current note index and plane number
    note_index_in_plane1 = (current_step_index // planes) % number_of_active_notes
    plane_number = (current_step_index % planes) + 1

    # Get the note value from Plane 1
    note_index = active_notes_indices[note_index_in_plane1]
    note_value = plane1_notes[note_index]
    if note_value is None:
        return  # No note to play

    # Output to each CV output with its own scale
    for output, scale_name in OUTPUT_SCALES.items():
        # Get the interval for the note
        interval = get_scale_interval(note_value, scale_name)
        # Apply plane interval
        if plane_number > 1:
            interval += PLANE_INTERVALS.get(plane_number, 0)
        # Ensure interval stays within 2 octaves
        interval = interval % 24  # 24 semitones = 2 octaves
        # Calculate the MIDI note
        note_midi = root_note + interval
        # Calculate the voltage for the note (1V per octave)
        voltage = (note_midi - 36) / 12.0  # Assuming C2 (MIDI 36) is 0V
        # Output the voltage
        output.voltage(voltage)

# Main loop
def main():
    global planes, shift_mode, current_step_index

    last_k1_value = k1.read_position()
    last_k2_value = k2.read_position()
    last_b1_state = False
    last_b2_state = False

    # For timing the DIN clock input
    last_din_state = din.value()

    # Update the display initially
    update_display()

    while True:
        # Read buttons and knobs
        b1_state = b1.value()
        b2_state = b2.value()
        k1_value = k1.read_position()
        k2_value = k2.read_position()

        # Handle shift modifier (b1 long press)
        if b1_state and not last_b1_state:
            # Button pressed
            press_time = time.ticks_ms()
        elif not b1_state and last_b1_state:
            # Button released
            release_time = time.ticks_ms()
            if time.ticks_diff(release_time, press_time) > 500:
                # Long press detected
                shift_mode = not shift_mode
                update_display()
            else:
                # Short press detected
                if shift_mode:
                    # Handle shift + b1 functionality (if any)
                    pass
                else:
                    # Move to previous note for editing
                    active_notes_indices = [i for i, note in enumerate(plane1_notes) if note is not None]
                    if active_notes_indices:
                        current_note_pos = (current_step_index // planes) % len(active_notes_indices)
                        current_note_pos = (current_note_pos - 1) % len(active_notes_indices)
                        current_step_index = current_note_pos * planes - 1  # Set to previous note
                    else:
                        current_step_index = -1
                    update_display()
        last_b1_state = b1_state

        # Handle b2
        if b2_state and not last_b2_state:
            # Button pressed
            press_time = time.ticks_ms()
        elif not b2_state and last_b2_state:
            # Button released
            release_time = time.ticks_ms()
            if time.ticks_diff(release_time, press_time) > 500:
                # Long press detected
                # Regenerate additional planes
                regenerate_planes()
                update_display()
            else:
                # Short press detected
                if shift_mode:
                    # Handle shift + b2 functionality (if any)
                    pass
                else:
                    # Move to next note for editing
                    active_notes_indices = [i for i, note in enumerate(plane1_notes) if note is not None]
                    if active_notes_indices:
                        current_note_pos = (current_step_index // planes) % len(active_notes_indices)
                        current_note_pos = (current_note_pos + 1) % len(active_notes_indices)
                        current_step_index = current_note_pos * planes - 1  # Set to next note
                    else:
                        current_step_index = -1
                    update_display()
        last_b2_state = b2_state

        # Read k1 to adjust note values diatonically
        if k1_value != last_k1_value:
            # Adjust the note at the current index
            active_notes_indices = [i for i, note in enumerate(plane1_notes) if note is not None]
            if active_notes_indices:
                current_note_pos = (current_step_index // planes) % len(active_notes_indices)
                note_index = active_notes_indices[current_note_pos]
            else:
                note_index = 0  # Default to first note
            # Map k1 to scale degrees diatonically
            scale_length = len(SCALES['major'])
            position = int((k1_value / 100) * (scale_length * 2))  # Covering 2 octaves
            plane1_notes[note_index] = position
            last_k1_value = k1_value
            update_display()

        # Read k2 to adjust number of planes
        if k2_value != last_k2_value:
            planes = int((k2_value / 100) * MAX_PLANES)
            if planes < 1:
                planes = 1
            last_k2_value = k2_value
            update_display()

        # Handle DIN clock input for sequencing
        din_state = din.value()
        if din_state and not last_din_state:
            # Rising edge detected on DIN input (external clock pulse)
            advance_sequence()
        last_din_state = din_state

        # Small delay to prevent CPU overload
        time.sleep(0.001)

def regenerate_planes():
    # Function to regenerate additional planes (introduce randomness)
    import random
    for plane_number in range(2, planes + 1):
        # Randomize the interval within an octave range (-12 to +12 semitones)
        PLANE_INTERVALS[plane_number] = random.randint(-12, 12)

# Run the main loop
main()

