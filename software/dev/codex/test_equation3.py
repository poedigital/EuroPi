import sys
import json
import math
import time
from europi import oled, k1, k2, b1, b2, ain, cv1

"""
todo and where we stand...

so, we were able to get pretty far with the calculatio engine.
right now we will need to parse everything in order to make sure
that we are aligned with the maths. i am trying real quick with o1
to merge the waveform with the eq engine... lets cross fingers.


todo is

check every single def one by one and make sure we have
1. no hard coded stuff
2. no errors.
3. test more equations
4. computational overhead tests


"""


DEBUG_ENABLED = True
KNOB_THRESHOLD = 0.1
AIN_THRESHOLD = 0.1
SLEEP_INTERVAL = 0.1

def debug_print(*args, **kwargs):
    if DEBUG_ENABLED:
        print(*args, **kwargs)

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
        print("Error loading:", e)
        sys.exit(1)

class EquationEngine:
    def __init__(self, operator_pool):
        self.context = {"t": 0.0}
        constants = operator_pool.get("constants", {})
        for k, v in constants.items():
            self.context[k] = v

        self.operators = {}
        # Binary operators
        ops_list = operator_pool.get("operators", [])
        for op in ops_list:
            if op in ["+", "-", "*", "/"]:
                self.operators[op] = self.get_binary_operator(op)
            else:
                debug_print("Unsupported operator:", op)

        # Unary functions
        funcs_list = operator_pool.get("functions", [])
        for func in funcs_list:
            if func in ["sin", "cos", "tan", "floor"]:
                self.operators[func] = getattr(math, func)
            else:
                debug_print("Unsupported function:", func)

    def get_binary_operator(self, op):
        if op == "+":
            return lambda a, b: a + b
        if op == "-":
            return lambda a, b: a - b
        if op == "*":
            return lambda a, b: a * b
        if op == "/":
            return lambda a, b: a / b if b != 0 else 0.0
        return lambda a, b: 0.0

    def evaluate_rpn(self, tokens):
        stack = []
        for token in tokens:
            if token in self.context:
                stack.append(self.context[token])
            elif token in self.operators:
                op = self.operators[token]
                if token in ["sin", "cos", "tan", "floor"]:
                    if not stack:
                        raise ValueError("Insufficient operands for unary op")
                    val = stack.pop()
                    stack.append(op(val))
                else:
                    if len(stack) < 2:
                        raise ValueError("Insufficient operands for binary op")
                    b = stack.pop()
                    a = stack.pop()
                    stack.append(op(a, b))
            else:
                try:
                    stack.append(float(token))
                except ValueError:
                    raise ValueError("Unknown token: " + token)
        return stack[0] if stack else 0.0

    def calculate_max(self, tokens, var_ranges):
        stack = []
        for token in tokens:
            if token in var_ranges:
                stack.append(var_ranges[token][1])
            elif token in self.operators:
                op = self.operators[token]
                if token in ["sin", "cos", "tan", "floor"]:
                    if not stack:
                        stack.append(0.0)
                    else:
                        val = stack.pop()
                        stack.append(abs(op(val)))
                else:
                    if len(stack) < 2:
                        stack.append(0.0)
                        continue
                    b = stack.pop()
                    a = stack.pop()
                    if token == "/" and b == 0.0:
                        b = 0.1
                    stack.append(op(a, b))
            else:
                try:
                    stack.append(float(token))
                except ValueError:
                    stack.append(0.0)
        return stack[0] if stack else 0.0

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

def draw_rpn_line(oled, rpn_list, byte_map, sx, sy):
    x = sx
    for t in rpn_list:
        x = draw_token(oled, t, x, sy, byte_map)
        x += 3

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
        oled.text("Res:{:.2f}".format(result), 0, 24)
        oled.text("k1:{:.2f} k2:{:.2f}".format(self.k1_val, self.k2_val), 0, 34)
        oled.show()

def wait_for_button_release(button):
    while button.value() == 1:
        time.sleep(0.02)

def scale_to_range(raw, mn, mx, min_thresh=None):
    frac = raw / 10.0
    val = mn + frac * (mx - mn)
    if min_thresh is not None:
        val = max(val, min_thresh)
    return val

def fold_value(value, mn=0.0, mx=10.0):
    while value > mx or value < mn:
        if value > mx:
            value = 2*mx - value
        elif value < mn:
            value = 2*mn - value
    return value

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

    max_results = []
    for eqd in eq_list:
        vrng = eqd.get("settings", {}).get("ranges", {})
        rpn = eqd.get("rpn", [])
        mv = engine.calculate_max(rpn, vrng)
        max_results.append(mv)

    while True:
        if b1.value() == 1:
            eq_index = (eq_index - 1) % len(eq_list)
            wait_for_button_release(b1)
        if b2.value() == 1:
            eq_index = (eq_index + 1) % len(eq_list)
            wait_for_button_release(b2)

        rk1 = k1.read_position(100) / 10.0
        rk2 = k2.read_position(100) / 10.0
        rain = min(ain.read_voltage(0), 10.0)

        disp.set_values(rk1, rk2, rain)

        eq = eq_list[eq_index]
        title = eq.get("title", "NoTitle")
        rpn = eq.get("rpn", [])
        varz = eq.get("vars", [])
        vrng = eq.get("settings", {}).get("ranges", {})

        engine.context["t"] = time.time()

        for i, vname in enumerate(varz):
            rng = vrng.get(vname, [0.0, 10.0])
            vmin, vmax = rng[0], rng[1]
            if vname == 'q':
                engine.context[vname] = scale_to_range(rk1, vmin, vmax, min_thresh=0.1)
            else:
                if i == 0:
                    val = scale_to_range(rk1, vmin, vmax)
                elif i == 1:
                    val = scale_to_range(rk2, vmin, vmax)
                else:
                    val = scale_to_range(rain, vmin, vmax)
                engine.context[vname] = val

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

        eq_max = max_results[eq_index]
        scaled_result = (result / eq_max)*10.0 if eq_max else 0.0
        folded = fold_value(scaled_result)
        cv1.voltage(folded)

        disp.draw(title, rpn, folded, byte_map)

        changed = (
            eq_index != prev_eq_index or
            abs(rk1 - prev_k1) > KNOB_THRESHOLD or
            abs(rk2 - prev_k2) > KNOB_THRESHOLD or
            abs(rain - prev_ain) > AIN_THRESHOLD
        )

        if changed:
            debug_print("\n[DEBUG] eq_index={} => {}".format(eq_index, title))
            debug_print("   RPN:", rpn)
            debug_print("   Vars:", varz)
            debug_print("   raw_k1={:.2f}, raw_k2={:.2f}, raw_ain={:.2f}".format(rk1, rk2, rain))
            for vn in varz:
                debug_print("   context[{}] = {:.3f}".format(vn, engine.context[vn]))
            debug_print("   => Raw result = {:.3f}, Scaled => {:.3f}, Folded => {:.3f}".format(result, scaled_result, folded))

        prev_eq_index = eq_index
        prev_k1 = rk1
        prev_k2 = rk2
        prev_ain = rain

        time.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    main()
