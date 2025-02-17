from europi import cv1, cv2, ain, oled
from time import sleep
from europi_script import EuroPiScript
import machine  # Needed for machine.reset()

class Voltage(EuroPiScript):
    def __init__(self):
        super().__init__()

    def main(self):
        while True:
            # Read voltage from AIN
            voltage = ain.read_voltage()

            # Quantize the voltage to the nearest integer for CV2
            quantized_voltage = int(voltage + 0.5)  # Rounds the voltage to the nearest integer

            # Set CV1 to the exact voltage
            cv1.voltage(voltage)

            # Set CV2 to the quantized integer voltage
            cv2.voltage(quantized_voltage)

            # Display the voltages on the OLED
            oled.fill(0)  # Clear the display

            # Display AIN Voltage
            oled.text("AIN Voltage:", 0, 0)
            oled.text(f"{voltage:.3f} V", 0, 12)

            # Display CV2 Voltage
            oled.text(f"{quantized_voltage} V", 0, 24)

            oled.show()

            # Optional: Exit condition
            # Press both Button 1 and Button 2 simultaneously to exit and reset
            # Modify as needed based on your hardware setup
            # if b1.value() == 1 and b2.value() == 1:
            #     oled.fill(0)
            #     oled.text("Exiting...", 0, 0)
            #     oled.show()
            #     sleep(1)
            #     machine.reset()

            sleep(0.1)  # Adjust the delay as needed

if __name__ == "__main__":
    Voltage().main()


