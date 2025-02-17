import json, math, time
from europi import oled, k1, k2, ain  # Ensure correct imports

CODEX_FILE = "/flash/codex.txt"

class Equation:
    def __init__(self, data):
        self.id = data["id"]
        self.title = data["title"]
        self.equation = data["equation"]
        self.vars = data["vars"]
        self.ranges = data["settings"]["ranges"]
        self.rpn = data["rpn"]

class OperatorPool:
    def __init__(self, data):
        self.operators = data.get("operators", [])
        self.functions = data.get("functions", [])
        self.constants = data.get("constants", {})

class EquationEngine:
    def __init__(self, equations, op_pool):
        self.equations = {eq.id: eq for eq in equations}
        self.ops = {op: self.get_op_func(op) for op in op_pool.operators}
        self.funcs = {f: getattr(math, f) for f in op_pool.functions if hasattr(math, f)}
        self.constants = op_pool.constants

    def get_op_func(self, op):
        return {
            "+": lambda a, b: a + b,
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "/": lambda a, b: a / b if b != 0 else float('inf'),
            "^": lambda a, b: math.pow(a, b)
        }.get(op, None)

    def evaluate(self, eq_id, vars_map):
        eq = self.equations.get(eq_id)
        if not eq:
            raise ValueError(f"Eq ID {eq_id} not found.")
        stack = []
        context = {**self.constants, **vars_map, **self.funcs}
        for token in eq.rpn:
            if token in context:
                val = context[token]
                if callable(val):
                    if not stack:
                        raise ValueError(f"Insufficient operands for '{token}'")
                    stack.append(val(stack.pop()))
                else:
                    stack.append(val)
            elif token in self.ops:
                if len(stack) < 2:
                    raise ValueError(f"Insufficient operands for '{token}'")
                b, a = stack.pop(), stack.pop()
                stack.append(self.ops[token](a, b))
            else:
                raise ValueError(f"Unknown token '{token}'")
        if len(stack) != 1:
            raise ValueError("RPN did not resolve to single result.")
        return stack[0]

class TestDisplay:
    def __init__(self):
        self.k1, self.k2, self.c = 0.0, 0.0, 0.0

    def update(self, eq, res):
        oled.fill(0)
        oled.text(f"EQ: {' '.join(eq)}", 0, 0)
        oled.text(f"Res: {res:.3f}", 0, 12)
        oled.text(f"k1: {self.k1:.2f} | k2: {self.k2:.2f}", 0, 24)
        oled.text(f"c: {self.c:.2f}", 0, 36)
        oled.show()

    def set_vals(self, k1, k2, c):
        self.k1, self.k2, self.c = k1, k2, c

def load_codex(file_path=CODEX_FILE):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        equations = [Equation(eq) for eq in data.get("equation_dict", [])]
        op_pool = OperatorPool(data.get("operator_pool", {}))
        return equations, op_pool
    except Exception as e:
        print(f"[ERROR] Load codex: {e}")
        return [], OperatorPool({})

def read_knob1():
    return 0.5  # Replace with actual hardware reading

def read_knob2():
    return 0.2  # Replace with actual hardware reading

def map_vars(eq, k1, k2, c):
    mapping = {}
    inputs = [k1, k2, c]
    for i, var in enumerate(eq.vars):
        vmin, vmax = eq.ranges.get(var, [0.0, 1.0])
        val = inputs[i] if i < len(inputs) else (vmin + vmax) / 2
        mapping[var] = vmin + (vmax - vmin) * val
    return mapping

def display_error(msg):
    oled.fill(0)
    oled.text("Error:", 0, 0)
    oled.text(msg[:21], 0, 12)
    oled.show()
    time.sleep(2)
    oled.fill(0)
    oled.show()

def main():
    equations, op_pool = load_codex()
    if not equations:
        display_error("No Equations Loaded")
        return
    engine = EquationEngine(equations, op_pool)
    selected_id = 1
    if selected_id not in engine.equations:
        display_error(f"Eq ID {selected_id} Not Found")
        return
    display = TestDisplay()
    while True:
        try:
            k1 = read_knob1()
            k2 = read_knob2()
            ain_voltage = ain.read_voltage(1)
            c = min(max(ain_voltage / 3.3, 0.0), 1.0)
            eq = engine.equations[selected_id]
            vars_map = map_vars(eq, k1, k2, c)
            res = engine.evaluate(selected_id, vars_map)
            display.set_vals(k1, k2, c)
            display.update(eq.rpn, res)
        except Exception as e:
            display_error(str(e))
        time.sleep(0.2)

if __name__ == "__main__":
    main()