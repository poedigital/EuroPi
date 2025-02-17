import sys
import json
import math
import time
from europi import oled, k1, k2, b1, b2, ain, cv1

###############################################################################
# CONFIG
###############################################################################
DEBUG_ENABLED = True      # Set to False to suppress debug prints.
KNOB_THRESHOLD = 0.1      # Minimum change in k1/k2 before debug prints.
AIN_THRESHOLD = 0.1       # Minimum change in AIN before debug prints.
SLEEP_INTERVAL = 0.1      # Main loop delay in seconds.

###############################################################################
# DEBUG PRINT HELPER
###############################################################################
def debug_print(*args, **kwargs):
    if DEBUG_ENABLED:
        print(*args, **kwargs)

###############################################################################
# LOADING THE DICTIONARY
###############################################################################
def load_saved_state(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (
            data.get("equation_dict", []),
            data.get("byte_array_dict", {}),
            data.get("operator_pool", {}),
            data.get("global_settings", {})
        )
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        sys.exit(1)

###############################################################################
# EQUATION ENGINE
###############################################################################
class EquationEngine:
    def __init__(self, operator_pool):
        self.context = {
            "t": 0.0  # Dynamic variable for time-based functions
        }
        # Load constants from operator_pool
        constants_dict = operator_pool.get("constants", {})
        for key, val in constants_dict.items():
            self.context[key] = val

        # Load operators from operator_pool
        self.operators = {}
        operators_list = operator_pool.get("operators", [])
        for op in operators_list:
            if op in ["+", "-", "*", "/"]:
                self.operators[op] = self.get_binary_operator(op)
            elif op in ["sin", "cos", "tan", "floor"]:
                self.operators[op] = getattr(math, op)
            else:
                debug_print(f"Unsupported operator: {op}")

    def get_binary_operator(self, op):
        """Return a lambda function for the given binary operator."""
        return {
            "+": lambda a, b: a + b,
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "/": lambda a, b: a / b if b != 0 else 0.0
        }.get(op, lambda a, b: 0.0)

    def evaluate_rpn(self, tokens):
        stack = []
        for token in tokens:
            if token in self.context:
                stack.append(self.context[token])
            elif token in self.operators:
                op = self.operators[token]
                if token in ["sin", "cos", "tan", "floor"]:
                    if not stack:
                        raise ValueError(f"Insufficient operands for unary operator '{token}'")
                    val = stack.pop()
                    stack.append(op(val))
                else:
                    if len(stack) < 2:
                        raise ValueError(f"Insufficient operands for binary operator '{token}'")
                    b = stack.pop()
                    a = stack.pop()
                    stack.append(op(a, b))
            else:
                try:
                    stack.append(float(token))
                except ValueError:
                    raise ValueError(f"Unknown token: {token}")
        return stack[0] if stack else 0.0

    def calculate_max(self, tokens, var_ranges):
        stack = []
        for token in tokens:
            if token in var_ranges:
                stack.append(var_ranges[token][1])  # Use max value
            elif token in self.operators:
                if token in ["sin", "cos", "tan", "floor"]:
                    if not stack:
                        stack.append(0.0)
                    else:
                        val = stack.pop()
                        stack.append(abs(self.operators[token](val)))
                else:
                    if len(stack) < 2:
                        stack.append(0.0)
                        continue
                    b = stack.pop()
                    a = stack.pop()
                    if token == '/':
                        # Prevent division by zero by using the minimum non-zero value
                        b_min = var_ranges.get("q", [0.1,1.0])[0]  # Assuming 'q' is the denominator
                        if b_min == 0.0:
                            max_val = 10.0  # Arbitrary cap to prevent infinity
                        else:
                            max_val = a / b_min
                    else:
                        max_val = self.operators[token](a, b)
                    stack.append(max_val)
            else:
                try:
                    stack.append(float(token))
                except ValueError:
                    stack.append(0.0)
        return stack[0] if stack else 0.0

###############################################################################
# CUSTOM GLYPH DRAWING (OPTIONAL)
###############################################################################
def draw_token(oled, token, x, y, byte_map):
    glyph_info = byte_map.get(token)
    if glyph_info:
        size = glyph_info["size"]
        rows = glyph_info["data"]
        for row_idx, row_bits in enumerate(rows[:size]):
            for col_idx in range(8):
                if (row_bits >> (7 - col_idx)) & 1:
                    oled.pixel(x + col_idx, y + row_idx, 1)
        return x + 8
    else:
        oled.text(token, x, y)
        return x + (6 * len(token))

def draw_rpn_line(oled, rpn_list, byte_map, start_x, start_y):
    x = start_x
    for token in rpn_list:
        x = draw_token(oled, token, x, start_y, byte_map)
        x += 3  # small gap

###############################################################################
# DISPLAY
###############################################################################
class TestDisplay:
    def __init__(self):
        self.k1_val = 0.0
        self.k2_val = 0.0
        self.ain_val = 0.0

    def set_values(self, k1v, k2v, ainv):
        self.k1_val = k1v
        self.k2_val = k2v
        self.ain_val = ainv

    def draw(self, eq_title, rpn_list, result, byte_map):
        oled.fill(0)
        oled.text(eq_title[:16], 0, 0)
        draw_rpn_line(oled, rpn_list, byte_map, 0, 12)
        oled.text(f"Res:{result:.2f}", 0, 24)
        oled.text(f"k1:{self.k1_val:.2f} k2:{self.k2_val:.2f}", 0, 34)
        oled.show()

###############################################################################
# BUTTON HELPERS
###############################################################################
def wait_for_button_release(button):
    while button.value() == 1:
        time.sleep(0.02)

###############################################################################
# RANGE SCALING
###############################################################################
def scale_to_range(raw, var_min, var_max, min_threshold=None):
    fraction = raw / 10.0
    scaled = var_min + fraction * (var_max - var_min)
    if min_threshold is not None:
        scaled = max(scaled, min_threshold)
    return scaled

###############################################################################
# FOLDING FUNCTION
###############################################################################
def fold_value(value, min_val=0.0, max_val=10.0):
    while value > max_val or value < min_val:
        if value > max_val:
            value = 2 * max_val - value
        elif value < min_val:
            value = 2 * min_val - value
    return value

###############################################################################
# MAIN
###############################################################################
def main():
    eq_list, byte_map, operator_pool, _ = load_saved_state("saved_state_Codex.txt")
    if not eq_list:
        print("No equations found in saved_state_Codex.txt!")
        return

    engine = EquationEngine(operator_pool)

    disp = TestDisplay()

    eq_index = 0
    prev_eq_index = -1
    prev_k1 = prev_k2 = prev_ain = -1.0

    # Precompute max results for scaling
    max_results = []
    for eq in eq_list:
        var_ranges = eq.get("settings", {}).get("ranges", {})
        max_val = engine.calculate_max(eq.get("rpn", []), var_ranges)
        max_results.append(max_val)

    while True:
        if b1.value() == 1:
            eq_index = (eq_index - 1) % len(eq_list)
            wait_for_button_release(b1)
        if b2.value() == 1:
            eq_index = (eq_index + 1) % len(eq_list)
            wait_for_button_release(b2)

        raw_k1 = k1.read_position(100) / 10.0  # 0.0..10.0 as float
        raw_k2 = k2.read_position(100) / 10.0  # 0.0..10.0 as float
        raw_ain = min(ain.read_voltage(0), 10.0)  # 0.0..10.0

        disp.set_values(raw_k1, raw_k2, raw_ain)

        eq = eq_list[eq_index]
        title = eq.get("title", "NoTitle")
        rpn = eq.get("rpn", [])
        vars_ = eq.get("vars", [])
        ranges = eq.get("settings", {}).get("ranges", {})

        engine.context["t"] = time.time()

        for i, var in enumerate(vars_):
            var_range = ranges.get(var, [0.0, 10.0])
            var_min, var_max = var_range[0], var_range[1]
            # Apply minimum threshold for 'q' to prevent division by zero
            if var == 'q':
                engine.context[var] = scale_to_range(raw_k1, var_min, var_max, min_threshold=0.1)
            else:
                engine.context[var] = scale_to_range(
                    raw_k1 if i == 0 else raw_k2 if i == 1 else raw_ain,
                    var_min,
                    var_max
                )

        try:
            result = engine.evaluate_rpn(rpn)
        except ValueError as e:
            debug_print("[ERROR]", e)
            oled.fill(0)
            oled.text("Error token:", 0, 0)
            oled.text(str(e)[:16], 0, 12)
            oled.show()
            time.sleep(2)
            continue

        # Scale result
        max_result = max_results[eq_index]
        if max_result != 0:
            scaled_result = (result / max_result) * 10.0
        else:
            scaled_result = 0.0
        folded_result = fold_value(scaled_result)
        cv_out = folded_result

        cv1.voltage(cv_out)

        disp.draw(title, rpn, folded_result, byte_map)

        # Debug if changed
        changed = (
            eq_index != prev_eq_index or
            abs(raw_k1 - prev_k1) > KNOB_THRESHOLD or
            abs(raw_k2 - prev_k2) > KNOB_THRESHOLD or
            abs(raw_ain - prev_ain) > AIN_THRESHOLD
        )

        if changed:
            debug_print(f"\n[DEBUG] eq_index={eq_index} => {title}")
            debug_print(f"   RPN: {rpn}")
            debug_print(f"   Vars: {vars_}")
            debug_print(f"   raw_k1={raw_k1:.2f}, raw_k2={raw_k2:.2f}, raw_ain={raw_ain:.2f}")
            for var in vars_:
                debug_print(f"   context[{var}] = {engine.context[var]:.3f}")
            debug_print(f"   => Raw result = {result:.3f}, Scaled => {scaled_result:.3f}, Folded => {folded_result:.3f}, CV out => {cv_out:.3f}")

        # Update previous states
        prev_eq_index = eq_index
        prev_k1 = raw_k1
        prev_k2 = raw_k2
        prev_ain = raw_ain

        time.sleep(SLEEP_INTERVAL)

###############################################################################
# ENTRY POINT
###############################################################################
if __name__ == "__main__":
    main()
