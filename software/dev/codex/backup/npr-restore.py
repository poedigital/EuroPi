
def reverse_expansion(tokens, expansion_map):
    """Restores original tokens from expanded form based on the expansion map."""
    reversed_tokens = []
    expanded_to_original = {tuple(v): k for k, v in expansion_map.items()}  # reverse map

    i = 0
    while i < len(tokens):
        match_found = False
        for exp_seq, original_token in expanded_to_original.items():
            if tokens[i:i + len(exp_seq)] == list(exp_seq):
                reversed_tokens.append(original_token)
                i += len(exp_seq)  # skip over expanded sequence
                match_found = True
                break

        if not match_found:
            reversed_tokens.append(tokens[i])
            i += 1

    return reversed_tokens


"""
Interpreter Decryption Plan
Yes, you can use reverse_expansion() in your interpreter code as the first step in decrypting the expanded tokens back into their original variables. Below, I'll provide:

Comprehensive context on how the "encryption" (expansion) works
Reverse-engineering protocol for the interpreter
Additional code needed for smooth decryption
A structured outline and a reverse-engineering prompt for future reference
1. Comprehensive Context on "Encryption" (Expansion)
When an equation is tokenized, we apply expansion rules based on the operator_pool["variables"] dictionary.
This means that during tokenization:

A variable like y(n+1) may be expanded into:

css
Copy
Edit
['A', '⋅', 'sgn', '(', 'sin', '(', '2πfn', '+', 'φ', ')', ')']
y(n+1) was replaced with a predefined sequence of tokens.
This is stored in operator_pool["variables"]["y(n+1)"]["expansion"].
The resulting Reverse Polish Notation (RPN) stores only the expanded version, removing the original token.

Before sending to the RP2040 interpreter, we must reverse this expansion (decrypt) back to y(n+1).

2. Reverse-Engineering Protocol for Interpreter
In the interpreter stage, we follow this decryption sequence:

Identify possible expansions in operator_pool["variables"]

Check which variables are marked "expandable": True
Extract their "expansion" sequences.
Scan the tokenized equation (RPN or Infix)

Compare sequences of tokens to known expansions.
If an exact sequence match is found, replace it with the original variable name.
Store and maintain the restored structure

This restored form will be used in the interpreter for evaluation.
3. Additional Code for Decryption (Interpreter Side)
Step 1: Reverse Expansion Before Processing
python
Copy
Edit
def reverse_expansion(tokens):
    """Replaces expanded token sequences with their original variable names."""
    reverse_map = {
        tuple(v["expansion"]): k
        for k, v in operator_pool["variables"].items()
        if v.get("expandable")
    }

    restored_tokens = []
    i = 0
    while i < len(tokens):
        match_found = False
        for expansion, original in reverse_map.items():
            exp_len = len(expansion)
            if tokens[i:i+exp_len] == list(expansion):
                restored_tokens.append(original)  # Replace with original variable
                i += exp_len
                match_found = True
                break
        if not match_found:
            restored_tokens.append(tokens[i])
            i += 1

    return restored_tokens
Step 2: Apply Before Interpreter Processing
python
Copy
Edit
def process_equation_for_interpreter(rpn_tokens):
    """Decrypts RPN tokens and prepares them for evaluation."""
    decrypted_tokens = reverse_expansion(rpn_tokens)
    print(f"[DEBUG] Decrypted Tokens: {decrypted_tokens}")

    # Now send decrypted_tokens for evaluation on RP2040
    send_to_interpreter(decrypted_tokens)
Step 3: Interpreter Reads Decrypted Tokens
python
Copy
Edit
def send_to_interpreter(tokens):
    """Simulates sending tokens to the RP2040 interpreter."""
    equation_string = " ".join(tokens)
    print(f"[INTERPRETER INPUT] {equation_string}")
    # Here, the RP2040 would parse this and compute the result
4. Outline of Expansion & Decryption Process
Phase 1: Expansion (Encryption) During Tokenization
User defines y(n+1) as expandable

Expansion stored in operator_pool["variables"]["y(n+1)"] = {'expandable': True, 'expansion': ['A', '⋅', 'sgn', '(', 'sin', '(', '2πfn', '+', 'φ', ')', ')']}
Equation tokenized:

scss
Copy
Edit
y(n+1) = A ⋅ sgn ( sin ( 2πfn + φ ) )
y(n+1) is replaced by its expansion sequence.
Final stored tokenized equation (RPN)

css
Copy
Edit
['A', '2πfn', 'φ', '+', 'sin', 'sgn', '⋅']
The original variable y(n+1) is removed and replaced.
Phase 2: Decryption in the Interpreter
Reverse map is built:

python
Copy
Edit
reverse_map = { ('A', '⋅', 'sgn', '(', 'sin', '(', '2πfn', '+', 'φ', ')', ')'): 'y(n+1)' }
Interpreter scans the token sequence.

If it finds a sequence match, it replaces it with the original variable.
Final restored tokens before execution:

css
Copy
Edit
['y(n+1)']
This is what the interpreter executes.
5. Reverse-Engineering Prompt for Future Debugging
Context:
The tokenized equation stored in JSON is expanded, meaning certain variables (e.g., y(n+1)) are split into multiple tokens. Before evaluation on the RP2040, these must be collapsed back into their original form.

Reverse-Engineering Prompt
sql
Copy
Edit
The equation processing system expands variables into multi-token sequences.
To restore them before execution, we must identify patterns in the stored tokens.
Each expandable variable is stored in operator_pool["variables"], marked with:
    - "expandable": True
    - "expansion": [list of tokens replacing it]

Restoration process:
1. Extract all expandable variables and their expansions.
2. Compare tokenized equations with stored expansions.
3. Replace expanded sequences with their original variable names.

Example:
Stored expanded tokens:
    ['A', '⋅', 'sgn', '(', 'sin', '(', '2πfn', '+', 'φ', ')', ')']

Must be converted back to:
    ['y(n+1)']

Use `reverse_expansion()` to achieve this.
Check the operator pool for `expandable=True` entries.
Summary
✅ Expansion during tokenization replaces variables with their token sequences.
✅ Interpreter must decrypt these sequences before execution.
✅ reverse_expansion() restores original variable names.
✅ The outlined process ensures that equations remain structured and reversible.
"""