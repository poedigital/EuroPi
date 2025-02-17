import json

# mock data structures
operator_pool = {
    "operators": {"+": 1, "-": 1, "*": 2, "⋅": 2, "/": 2, "^": 3},
    "functions": {"sin": 4, "cos": 4, "sgn": 4},
    "constants": {"π": 3.14159, "φ": 1.618033988749895},
    "groupings": {"(", ")"},
    "variables": {
        "y(n+1)": {"expandable": True, "expansion": ["n", "1", "+"]},
        "A": {"expandable": False},
        "2πfn": {"expandable": False}
    }
}

equation_dict = [
    {
        "id": 1,
        "title": "test_eq",
        "equation": "y(n+1) = A ⋅ sgn ( sin ( 2πfn + φ ) )",
        "tokens": [],
        "rpn": [],
        "vars": []
    }
]

def tokenize_equation(eq_idx=0):
    """Tokenizes the equation, applies expansion, and updates the dictionary."""
    eq_data = equation_dict[eq_idx]
    equation_text = eq_data.get("equation", "").strip()
    
    if not equation_text:
        return []

    print("\n[DEBUG] Tokenizing Equation:", equation_text)

    raw_tokens = equation_text.split()
    tokens = []
    variables = []

    for token in raw_tokens:
        category = (
            "function" if token in operator_pool["functions"] else
            "operator" if token in operator_pool["operators"] else
            "constant" if token in operator_pool["constants"] else
            "grouping" if token in operator_pool["groupings"] else
            "variable" if token in operator_pool["variables"] else
            "unknown"
        )

        if category == "variable":
            variables.append(token)
            var_info = operator_pool["variables"].get(token, {})
            if var_info.get("expandable"):
                expansion = var_info.get("expansion", [])
                if not expansion:
                    print(f"[ERROR] Expansion for '{token}' is marked expandable but is empty!")
                else:
                    print(f"[DEBUG] Expanding '{token}' → {expansion}")
                    tokens.extend(expansion)
                    continue  # Skip inserting the original token

        tokens.append(token)

    equation_dict[eq_idx]["tokens"] = tokens
    equation_dict[eq_idx]["vars"] = list(set(variables))

    print("[DEBUG] Final Tokenized Output:", tokens)
    return tokens

def infix_to_rpn(tokens):
    """Converts an infix tokenized equation into Reverse Polish Notation (RPN)."""
    precedence = {
        "+": 1, "-": 1,
        "⋅": 2, "*": 2, "/": 2,
        "^": 3
    }

    output = []
    operator_stack = []
    function_stack = []  # stores function calls for correct precedence

    print("\n[DEBUG] Starting infix_to_rpn")
    print(f"[DEBUG] Tokens received: {tokens}")

    for token in tokens:
        if token == "=":  
            print(f"[DEBUG] Skipping '=' (assignment operator, not needed in RPN)")
            continue

        if token in operator_pool["constants"] or token in operator_pool["variables"]:
            output.append(token)
            print(f"[DEBUG] Variable/Constant '{token}' added to RPN output")

        elif token in operator_pool["functions"]:
            function_stack.append(token)
            operator_stack.append(token)  # functions go onto operator stack
            print(f"[DEBUG] Function '{token}' pushed to function_stack and operator_stack")

        elif token in operator_pool["operators"]:
            print(f"[DEBUG] Operator '{token}' encountered")
            while (operator_stack and operator_stack[-1] != '(' and
                   precedence.get(operator_stack[-1], 0) >= precedence[token]):
                popped = operator_stack.pop()
                output.append(popped)
                print(f"  → [POP] '{popped}', added to RPN output")
            operator_stack.append(token)
            print(f"  → [PUSH] '{token}' (operator stack now: {operator_stack})")

        elif token == '(':
            operator_stack.append(token)
            print("[DEBUG] '(' pushed to stack")

        elif token == ')':
            print("[DEBUG] ')' encountered, processing enclosed group")
            while operator_stack and operator_stack[-1] != '(':
                popped = operator_stack.pop()
                output.append(popped)
                print(f"  → [POP] '{popped}', added to RPN output")
            operator_stack.pop()  # Remove '('
            print("  → '(' discarded")

            # Apply function if it was before '('
            if function_stack:
                func = function_stack.pop()
                output.append(func)
                print(f"  → [FUNC APPLY] '{func}', added to RPN output")

    while operator_stack:
        popped = operator_stack.pop()
        output.append(popped)
        print(f"[DEBUG] Final Stack Pop: '{popped}', added to RPN output")

    print(f"[DEBUG] Final RPN Output: {output}")
    return output

# run tokenizer
tokenized_output = tokenize_equation()
rpn_output = infix_to_rpn(tokenized_output)

# update equation dictionary
equation_dict[0]["rpn"] = rpn_output

# save debug output
with open("tokenized_output.json", "w", encoding="utf-8") as f:
    json.dump(equation_dict, f, indent=4)

print("\n[INFO] Tokenization and RPN conversion test completed. Check tokenized_output.json for results.")
