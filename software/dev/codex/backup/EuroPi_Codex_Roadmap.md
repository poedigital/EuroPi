
# EuroPi Codex: Development Roadmap

## Overview
The EuroPi Codex project aims to create a modular, interactive platform for experimenting with mathematical equations in the Eurorack format. The goal is to produce equational voltage outputs and rhythmic gates with intuitive controls and visualization, making chaos musical and controlled.

---

## **Roadmap Segments**

### 1. **User Interface (UI)**
- **Features**:
  - Display the equation dead center on the OLED.
  - Highlight currently selected parameter with a square around it.
  - Indicate K1, K2, and AIN assignments below the equation.
  - Visualize the equation's output as a steady waveform occupying 2/3 of the OLED.
  - Display voltage reading and contextual indicators (e.g., 2/5) as needed.
- **Interaction**:
  - B1/B2 long presses for parameter assignment.
  - B1/B2 short presses for cycling through parameters.
  - Combo short press for threshold adjustment menu.

---

### 2. **Computational Engine**
- **Responsibilities**:
  - Evaluate equations dynamically using inputs (K1, K2, AIN).
  - Ensure variable consistency when switching equations.
  - Support for real-time CV generation and gate logic.
- **Outputs**:
  - CV1-CV3: Continuous voltage outputs.
  - Gate4-Gate6: Threshold-based rhythmic gates.
  - Compound output (e.g., sum, logic) for CV3/Gate6.

---

### 3. **Parameter Assignment**
- **Functionality**:
  - Map K1, K2, and AIN to equation parameters.
  - Provide clear OLED feedback during assignment.
- **Control Scheme**:
  - Long press B1/B2 for parameter assignment menu.
  - Highlight selected parameter on OLED during assignment.

---

### 4. **Threshold Processing**
- **Purpose**:
  - Act as a sensitivity filter for gate generation.
  - Adjust gate occurrence frequency by modifying threshold.
- **Interaction**:
  - Access threshold settings via combo short press (B1+B2).
  - Display contextual menu for adjustments.

---

### 5. **Outputs**
- **Roles**:
  - CV1/Gate4: Base output with threshold gate.
  - CV2/Gate5: Inverted CV with inverted gate.
  - CV3/Gate6: Compound output (sum, logic) with threshold gate.
- **Quantization**:
  - No internal quantization for note values.
  - Focus on generating equational CV for external processing.

---

### 6. **Builder Mode (Future Phase)**
- **Purpose**:
  - Enable creation and testing of equations in a standalone script.
  - Allow for algorithm export/import using a shared file.
- **Features**:
  - Use AIN for parameter selection in builder mode.
  - Save and load equations to/from a common file.

---

## **Development Steps**

1. **Establish Computational Engine**
   - Define how equations are stored, evaluated, and managed.
   - Implement parameter mapping for K1, K2, and AIN.

2. **Build UI Framework**
   - Design OLED layout:
     - Central equation display.
     - Parameter indicators and assignments.
     - Waveform visualization.
   - Implement menus for parameter focus and threshold adjustment.

3. **Integrate Outputs**
   - Assign CV1-CV3 and Gate4-Gate6 roles.
   - Develop compound output (sum, logic, or other).

4. **Implement Threshold Processing**
   - Finalize sensitivity-based thresholding.
   - Test rhythmic gate generation.

5. **Builder Mode and Expansions**
   - Develop standalone script for creating and testing equations.
   - Explore binary-to-audio encoding for equation transfer.

---

## **Questions for Refinement**
1. Should we maintain compound outputs as sums, or explore logic-based relationships?
2. Is the current threshold menu design sufficient, or do we need per-gate adjustments?
3. Would prioritizing waveform clarity over equation visibility enhance usability?
4. Is builder mode necessary in phase 1, or can it be deferred?

---

## **Next Steps**
- Refine the computational engine for equation handling.
- Draft OLED layout with parameter highlighting and waveform display.
- Begin threshold implementation with contextual menu support.
- Test and define compound output roles.

---

### **References**
- Mutable Instruments (Binary-to-Audio Encoding)
- MicroPython Documentation
- SSD1306 OLED Driver Documentation

---
