# EuroPi Hardware Scripting Index

This index is a comprehensive guide for scripting on the EuroPi platform, covering its hardware, libraries, and programming considerations. It serves as a reference for interacting with knobs, buttons, CV inputs/outputs, the OLED display, RTC, and more.

---

## **1. Core Components Overview**

### **Knobs**

- **Identifiers**: `k1`, `k2`
    
- **Resolution**: 12-bit (4096 steps)
    
- **Usage**:
    
    ```
    knob_value = k1.percent()  # Read as a percentage (0.0 to 1.0)
    knob_position = k2.read_position()  # Read the current position
    ```
    
- **Advanced Features**:
    
    - `KnobBank` allows locking/unlocking knobs for grouped functionality.
        
    
    ```
    from experimental.knobs import KnobBank
    knob_bank = KnobBank.builder(k1)
        .with_locked_knob("param1", initial_percentage_value=0.5)
        .build()
    ```
    

### **Buttons**

- **Identifiers**: `b1`, `b2`
    
- **Debounce**: Fast double presses may not be detected.
    
- **Usage**:
    
    ```
    @b1.handler
    def on_press():
        print("Button 1 pressed")
    ```
    

### **Analog Input (AIN)**

- **Identifier**: `ain`
    
- **Voltage Range**: 0-10V
    
- **Usage**:
    
    ```
    voltage = ain.read_voltage()  # Returns voltage as a float
    ```
    

### **Digital Input (DIN)**

- **Identifier**: `din`
    
- **Voltage Detection**: Triggers above 0.7V.
    
- **Usage**:
    
    ```
    @din.handler
    def on_rise():
        print("DIN triggered")
    ```
    

### **CV Outputs**

- **Identifiers**: `cv1` to `cv6`
    
- **Voltage Range**: 0-10V
    
- **Usage**:
    
    ```
    cv1.voltage(5.0)  # Set CV output to 5V
    cv2.off()  # Turn off CV output
    ```
    

### **OLED Display**

- **Specifications**:
    
    - 128x32px resolution
        
    - SSD1306 driver
        
- **Key Methods**:
    
    |Method|Parameters|Description|
    |---|---|---|
    |`text`|`string, x, y, color`|Writes text at `(x, y)`|
    |`fill`|`color`|Fills screen with color (0 or 1)|
    |`line`|`x1, y1, x2, y2, color`|Draws a line|
    |`rect`|`x, y, width, height, color`|Draws rectangle|
    |`fill_rect`|`x, y, width, height, color`|Draws filled rectangle|
    |`show`|None|Updates the display|
    
    ```
    from europi import *
    oled.fill(0)  # Clear screen
    oled.text("Hello", 0, 0, 1)  # Write text
    oled.show()  # Refresh display
    ```
    

---

## **2. Programming Considerations**

### **Hardware Limitations**

- **Knobs, Buttons, and CV Outputs**:
    
    - Resolution: 12-bit (4096 steps).
        
    - Analog and knob reads cause slight script delays.
        
- **Clock Pulses**:
    
    - Pulses shorter than 10ms may not be detected.
        
- **Digital Input**:
    
    - Prone to false triggers from noisy signals.
        

### **OLED Tips**

- Perform all buffer operations before calling `oled.show()` to reduce CPU usage.
    
- Avoid burn-in by using screensavers or clearing the display during inactivity.
    

### **Overclocking**

- Safely overclock the Raspberry Pi Pico to 250MHz for faster analog reads:
    
    ```
    import machine
    machine.freq(250_000_000)
    ```
    

---

## **3. Advanced Features**

### **I2C Connectivity**

- **External Devices**:
    
    - Connect devices to the dedicated I2C header.
        
    - Configure in `EuroPiConfig.json`:
        
        ```
        {
            "EXTERNAL_I2C_FREQUENCY": 400000,
            "EXTERNAL_I2C_TIMEOUT": 100000
        }
        ```
        
    - Usage:
        
        ```
        from europi import external_i2c
        external_i2c.writeto(0x3c, b'\x00\xaf')
        ```
        

### **Multi-Threading**

- Utilize both cores of the Pico for separate tasks.
    
- **Example**:
    
    ```
    import _thread
    
    def thread1():
        while True:
            cv1.voltage(5)
            time.sleep(0.5)
    
    def thread2():
        while True:
            oled.fill(0)
            oled.text("Thread 2", 0, 0, 1)
            oled.show()
            time.sleep(1)
    
    _thread.start_new_thread(thread1, ())
    thread2()
    ```
    

### **Custom Images on OLED**

- Convert an image to a byte array using img2bytearray:
    
    ```
    from europi import *
    img = b'\x00\x01\x02...'  # Byte array
    imgFB = FrameBuffer(bytearray(img), 128, 32, MONO_HLSB)
    oled.blit(imgFB, 0, 0)
    oled.show()
    ```
    

---

## **4. Best Practices**

- **Optimize Display Updates**: Minimize `oled.show()` calls to reduce latency.
    
- **Use Screensavers**: Clear the screen after periods of inactivity to avoid burn-in.
    
- **Avoid Double Button Presses**: Account for debounce limitations.
    
- **Thread Safety**: Use locks when accessing shared data between threads.
    

---

## **5. Example Scripts**

### **Basic Script with Knobs and OLED**

```
from europi import *

def main():
    while True:
        oled.fill(0)
        oled.text(f"Knob1: {k1.percent():.2f}", 0, 0, 1)
        oled.text(f"Knob2: {k2.percent():.2f}", 0, 10, 1)
        oled.show()

main()
```

### **Bezier Curve Voltage Generator**

```
from europi import *
from experimental.knobs import KnobBank
import random

class Bezier:
    def __init__(self):
        self.kb = KnobBank.builder(k1).with_locked_knob("curve", initial_percentage_value=0.5).build()

    def main(self):
        while True:
            voltage = random.random() * self.kb.curve.percent() * 10
            cv1.voltage(voltage)

Bezier().main()
```

### **Multi-Threaded Waveform Visualizer**

```
from europi import *
import math
import _thread

class Visualizer:
    def __init__(self):
        self.heights = []
        self.lock = _thread.allocate_lock()

    def cv_thread(self):
        while True:
            for i in range(128):
                height = int(math.sin(i / 20) * 16 + 16)
                with self.lock:
                    self.heights.append(height)
                    if len(self.heights) > 128:
                        self.heights.pop(0)
                cv1.voltage(height / 32 * 10)

    def oled_thread(self):
        while True:
            oled.fill(0)
            with self.lock:
                for x, y in enumerate(self.heights):
                    oled.pixel(x, y, 1)
            oled.show()

    def run(self):
        _thread.start_new_thread(self.cv_thread, ())
        self.oled_thread()

Visualizer().run()
```

---

## **6. References**

- EuroPi GitHub Repository
    
- MicroPython Documentation
    
- SSD1306 OLED Driver Documentation
    

---

this index will evolve as more features and scripts are added to the europi platform.