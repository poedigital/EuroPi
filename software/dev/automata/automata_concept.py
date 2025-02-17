"""
i’ll draft a test script for the europi that captures the core principles of our cybernetic automaton concept. the focus will be on:
	•	charge accumulation & decay (influenced by din and ain)
	•	nonlinear discharge curves (adjusted by k1)
	•	threshold-based event triggering (set by k2)
	•	subtle markov-based behavior shifts (influencing decay & charge thresholds over time)

i’ll also make sure the script follows the project structure in your europi files, so it integrates smoothly.

key test features
	•	din acts as a gate-controlled charge enabler
	•	ain influences charge accumulation speed
	•	k1 adjusts discharge curve steepness
	•	k2 sets charge threshold sensitivity
	•	b1 manually boosts charge slightly
	•	b2 temporarily slows down discharge
	•	cv1–cv3 output charge-influenced control signals
	•	gate1–gate3 trigger based on threshold conditions

let me draft the script now.

summary of this test script
	1.	charge accumulation & decay
	•	din (gate) controls whether charge accumulates
	•	ain (cv) modulates the speed of charge buildup
	•	k1 controls how fast charge decays (exponential scaling)
	•	k2 sets charge threshold for triggering events
	2.	markov-influenced decisions
	•	slight probability (markov_bias) biases how charge decays
	•	gate2 fires occasionally when charge crosses threshold + bias
	3.	cv & gate outputs
	•	cv1 = raw charge level (0–5V)
	•	cv2 = logarithmic charge curve (0–5V)
	•	cv3 = exponential charge mapping (0–5V)
	•	gate1 = fires when charge crosses threshold
	•	gate2 = probability-driven gate
	•	gate3 = fires on full discharge
	4.	button interaction
	•	b1 tap = small manual charge boost
	•	b2 tap = temporarily slow down discharge
	•	b1 hold = reset charge
	•	b2 hold = reset decay speed

next steps
	•	test this implementation to see how the charge system behaves
	•	tweak the markov bias influence if needed
	•	refine cv/gate mappings based on modular feedback

"""
from europi import *
import math
import time

# Initial charge value
charge = 0.0

# User-adjustable parameters
charge_threshold = 0.5  # k2: Sensitivity of charge affecting outputs
release_factor = 0.01  # k1: Speed of charge decay

# Markov probabilities (simple implementation)
markov_bias = 0.2  # Slight influence on charge decay rate

# Last gate state for DIN (to detect rising edges)
last_din_state = 0

# Function to update charge level
def update_charge():
    global charge
    
    # Read input values
    ain_value = ain.read_voltage() / 10  # Normalize 0–10V to 0–1
    din_state = din[0].value()
    
    # Check if DIN is high to allow charge accumulation
    if din_state:
        charge += ain_value * 0.05  # Accumulate charge based on AIN input
        charge = min(charge, 1.0)  # Cap at max level
    else:
        charge -= release_factor * (math.exp(-charge * 5) + markov_bias)
        charge = max(charge, 0.0)  # Prevent negative charge
    
    # Check if charge crosses threshold
    if charge > charge_threshold:
        gate1.on()
    else:
        gate1.off()
    
    # Probability-driven trigger event (Markov-influenced decision)
    if charge > charge_threshold * 1.2 and random.uniform(0, 1) < markov_bias:
        gate2.on()
        time.sleep(0.01)
        gate2.off()
    
    # Discharge threshold event
    if charge < 0.1:
        gate3.on()
        time.sleep(0.01)
        gate3.off()
    
    # CV Outputs
    cv1.voltage(charge * 5)  # Output charge level as CV
    cv2.voltage(math.log1p(charge) * 5)  # Logarithmic charge curve
    cv3.voltage((charge ** 2) * 5)  # Exponential mapping

# Adjust parameters via knobs
def adjust_params():
    global charge_threshold, release_factor
    
    charge_threshold = k2.read_position()  # Adjust charge threshold
    release_factor = k1.read_position() * 0.05  # Adjust release curve speed

# Button controls
def button_events():
    global charge
    
    if b1.fell:
        charge += 0.1  # Small manual charge boost
        charge = min(charge, 1.0)
    
    if b2.fell:
        release_factor *= 0.5  # Temporarily slow discharge
    
    if b1.held:
        charge = 0  # Long press b1 clears charge
    
    if b2.held:
        release_factor = 0.01  # Reset discharge rate

# Main loop
while True:
    adjust_params()
    button_events()
    update_charge()
    time.sleep(0.01)

##############################################################################
# concept 2
##############################################################################

from europi import *
import math
import time
import random

# Initial charge value
charge = 0.0

# User-adjustable parameters
charge_threshold = 0.5  # k2: Sensitivity of charge affecting outputs
release_factor = 0.01  # k1: Speed of charge decay

# Markov probabilities (adaptive learning bias)
markov_bias = 0.2  # Slight influence on charge decay rate
markov_memory = []  # Store past charge levels for adaptive bias

# Last gate state for DIN (to detect rising edges)
last_din_state = 0

# Function to update charge level
def update_charge():
    global charge, markov_memory, markov_bias
    
    # Read input values
    ain_value = ain.read_voltage() / 10  # Normalize 0–10V to 0–1
    din_state = din[0].value()
    
    # Adaptive markov bias: Adjust bias based on recent charge levels
    if len(markov_memory) > 10:
        avg_past_charge = sum(markov_memory) / len(markov_memory)
        markov_bias = avg_past_charge * 0.3  # Adjust bias dynamically
        markov_memory.pop(0)
    
    # Check if DIN is high to allow charge accumulation
    if din_state:
        charge += ain_value * 0.05  # Accumulate charge based on AIN input
        charge = min(charge, 1.0)  # Cap at max level
        markov_memory.append(charge)
    else:
        charge -= release_factor * (math.exp(-charge * 5) + markov_bias)
        charge = max(charge, 0.0)  # Prevent negative charge
    
    # Check if charge crosses threshold
    if charge > charge_threshold:
        gate1.on()
    else:
        gate1.off()
    
    # Probability-driven trigger event (Markov-influenced decision)
    if charge > charge_threshold * 1.2 and random.uniform(0, 1) < markov_bias:
        gate2.on()
        time.sleep(0.01)
        gate2.off()
    
    # Discharge threshold event
    if charge < 0.1:
        gate3.on()
        time.sleep(0.01)
        gate3.off()
    
    # CV Outputs
    cv1.voltage(charge * 5)  # Output charge level as CV
    cv2.voltage(math.log1p(charge) * 5)  # Logarithmic charge curve
    cv3.voltage((charge ** 2) * 5)  # Exponential mapping

# Adjust parameters via knobs
def adjust_params():
    global charge_threshold, release_factor
    
    charge_threshold = k2.read_position()  # Adjust charge threshold
    release_factor = k1.read_position() * 0.05  # Adjust release curve speed

# Button controls
def button_events():
    global charge, markov_bias
    
    if b1.fell:
        charge += 0.1  # Small manual charge boost
        charge = min(charge, 1.0)
    
    if b2.fell:
        release_factor *= 0.5  # Temporarily slow discharge
    
    if b1.held:
        charge = 0  # Long press b1 clears charge
    
    if b2.held:
        release_factor = 0.01  # Reset discharge rate
    
    if b1.held and b2.held:
        markov_memory.clear()  # Reset markov memory on combo press
        markov_bias = 0.2  # Reset adaptive bias

# Main loop
while True:
    adjust_params()
    button_events()
    update_charge()
    time.sleep(0.01)
