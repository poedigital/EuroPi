from europi import *
import math
import time

# Calibration Constants
A4_HZ = 440  # Standard tuning
C2_HZ = 65.41  # Lowest C in the typical synth range
REF_HZ = 55  # Reference frequency for calculation (A1)
HZ_OFFSET = 0.25  # Shift for placing C at 0V

# Smoothing Factor
ALPHA = 0.1  # Low-pass filter factor for smoothing ADC readings

# State variables
prev_adc = 0
smoothed_adc = 0

def hz_to_volts(hz):
    """Converts frequency in Hz to 1V/Oct CV"""
    if hz <= 0:
        return 0
    return math.log((hz / REF_HZ) / 2**HZ_OFFSET) / math.log(2)

def read_frequency():
    """Reads AIN and estimates the input frequency"""
    global smoothed_adc, prev_adc

    adc_value = ain.read_voltage()  # Read input voltage
    smoothed_adc = (ALPHA * adc_value) + ((1 - ALPHA) * smoothed_adc)  # Smooth readings

    # Approximate frequency by scaling ADC value
    hz_estimate = smoothed_adc * A4_HZ  # Scaled approximation

    return hz_estimate

def main_loop():
    """Main loop for Hz to 1V/Oct conversion"""
    while True:
        hz = read_frequency()
        volts = hz_to_volts(hz)

        # Output estimated 1V/Oct CV
        cv1.voltage(volts)

        # Print debug info
        print(f"Hz: {hz:.2f}, CV: {volts:.2f}V")

        time.sleep(0.05)  # Limit update rate

# Initialize and start
main_loop()
