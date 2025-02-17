import sys
import os
import importlib.util
import time

# ---- Configuration ---- #
BASE_PATH = "/Users/pierre-philipmasse/Desktop/mod/europi/EuroPi/software/firmware"
MOCKS_PATH = os.path.join(BASE_PATH, "mocks")

# Ensure paths are available
sys.path.insert(0, MOCKS_PATH)  # Load mock modules first
sys.path.append(BASE_PATH)  # Load EuroPi firmware

# Load the mock machine module (ensures EuroPi works)
try:
    import machine
    print("[INFO] Using MOCK machine module")
except ImportError:
    print("[ERROR] Mock machine module not found!")
    sys.exit(1)

# Load EuroPi firmware
try:
    import europi
    print(f"[INFO] Loaded EuroPi from {europi.__file__}")
except ImportError as e:
    print(f"[ERROR] Could not load europi: {e}")
    sys.exit(1)

# ---- Virtual EuroPi Emulator ---- #
class VirtualEuroPi:
    """A wrapper to virtualize the EuroPi environment."""
    
    def __init__(self):
        self.k1, self.k2 = 0.5, 0.5  # Simulate knobs
        self.b1, self.b2 = False, False  # Simulate buttons
        self.din = [0] * 4  # Simulate 4 digital inputs
        self.ain = [0] * 4  # Simulate 4 analog inputs
        self.cv = [0] * 6  # Simulate 6 CV outputs

    def emulate_script(self, script):
        """Load and execute a EuroPi script inside the virtual environment."""
        print("[INFO] Running script in virtual EuroPi environment.")
        try:
            for _ in range(100):  # Simulate 100 iterations instead of infinite loop
                script(self)
                time.sleep(0.1)  # Simulate a small delay between loop iterations
        except KeyboardInterrupt:
            print("\n[INFO] Exiting Virtual EuroPi.")

# ---- Script Loader ---- #
def run_script(script_path):
    """Load and run a EuroPi script inside the virtual environment."""
    if not os.path.exists(script_path):
        print(f"[ERROR] Script not found: {script_path}")
        return

    virtual = VirtualEuroPi()
    module_name = os.path.splitext(os.path.basename(script_path))[0]

    try:
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        script_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = script_module
        spec.loader.exec_module(script_module)

        # Handle class-based scripts like Codex
        if hasattr(script_module, "Codex"):
            print("[INFO] Detected Codex class, initializing...")
            script_instance = script_module.Codex()
            script_instance.main()  # Run the main loop
        elif hasattr(script_module, "main"):
            print("[INFO] Running main() function...")
            script_module.main(virtual)
        else:
            print(f"[ERROR] Script '{script_path}' is missing a 'main()' function or Codex class.")
    except Exception as e:
        print(f"[ERROR] Failed to load script {script_path}: {e}")
# ---- Main Execution ---- #
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[USAGE] python europi_script_runner.py path/to/your_script.py")
        sys.exit(1)

    run_script(sys.argv[1])