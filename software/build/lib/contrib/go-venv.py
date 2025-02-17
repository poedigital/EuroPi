import sys
import os
import importlib
import types
import numpy as np
import pygame
import time

# set path to europi source files
EUROPI_PATH = "/Users/pierre-philipmasse/Desktop/mod/europi/EuroPi/software"  # update to your path
sys.path.append(EUROPI_PATH)

# attempt to import the real europi modules
try:
    import europi
except ImportError:
    print("[ERROR] Could not load real europi module. Ensure EUROPI_PATH is correct.")

# create virtual replacements for hardware interfaces
class VirtualEuroPi:
    """A wrapper to virtualize the EuroPi environment."""

    def __init__(self):
        pygame.init()
        self.width, self.height = 128, 64
        self.screen = pygame.display.set_mode((self.width * 4, self.height * 4))
        pygame.display.set_caption("Virtual EuroPi")
        
        # emulate knobs, buttons, cv, oled, etc.
        self.k1 = 0.5
        self.k2 = 0.5
        self.b1 = False
        self.b2 = False
        self.din = [0] * 4
        self.ain = [0] * 4
        self.cv = [0] * 6
        self.oled_buffer = np.zeros((128, 64), dtype=np.uint8)

    def update_oled(self):
        """Update the virtual OLED display."""
        self.screen.fill((0, 0, 0))
        for y in range(64):
            for x in range(128):
                if self.oled_buffer[x, y] == 1:
                    pygame.draw.rect(self.screen, (255, 255, 255), (x * 4, y * 4, 4, 4))
        pygame.display.flip()

    def handle_input(self):
        """Map keyboard keys to EuroPi controls."""
        keys = pygame.key.get_pressed()
        self.b1 = keys[pygame.K_q]
        self.b2 = keys[pygame.K_w]
        self.k1 += (keys[pygame.K_a] - keys[pygame.K_s]) * 0.1
        self.k2 += (keys[pygame.K_d] - keys[pygame.K_f]) * 0.1

    def emulate_script(self, script):
        """Load and execute a EuroPi script inside the virtual environment."""
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return

            self.handle_input()
            script(self)  # execute user script
            self.update_oled()
            time.sleep(0.1)

# replace hardware calls with virtual ones
def patch_europi():
    """Replace hardware functions in the original EuroPi module with virtual ones."""
    virtual = VirtualEuroPi()
    
    europi.k1 = virtual.k1
    europi.k2 = virtual.k2
    europi.b1 = virtual.b1
    europi.b2 = virtual.b2
    europi.din = virtual.din
    europi.ain = virtual.ain
    europi.cv1 = virtual.cv[0]
    europi.cv2 = virtual.cv[1]
    europi.cv3 = virtual.cv[2]
    europi.cv4 = virtual.cv[3]
    europi.cv5 = virtual.cv[4]
    europi.cv6 = virtual.cv[5]

    europi.OLED = virtual  # replace OLED with our pygame emulator
    europi.update_oled = virtual.update_oled

    return virtual

# load and run a europi script inside the virtual environment
def run_script(script_path):
    """Load a EuroPi script and execute it in the virtual environment."""
    if not os.path.exists(script_path):
        print(f"[ERROR] Script not found: {script_path}")
        return

    virtual = patch_europi()

    module_name = os.path.splitext(os.path.basename(script_path))[0]
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    script_module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = script_module
    spec.loader.exec_module(script_module)

    # start the emulator
    if hasattr(script_module, "main"):
        virtual.emulate_script(script_module.main)
    else:
        print("[ERROR] Script has no 'main' function.")

if __name__ == "__main__":
    script_path = sys.argv[1] if len(sys.argv) > 1 else None
    if script_path:
        run_script(script_path)
    else:
        print("[USAGE] python europi_virtual.py path/to/script.py")