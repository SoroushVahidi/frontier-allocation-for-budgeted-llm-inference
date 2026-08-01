BRANCH_FAMILY: backward_from_target_check_executable_repair_v1
MODE: live_pilot

Solve this problem using backward reasoning combined with an executable arithmetic formula.

Step 1 — Identify the exact target quantity.
Step 2 — List the key numeric facts from the problem.
Step 3 — Work backward from the target to derive the needed operations and source facts.
Step 4 — Identify what relation or computation failed in prior attempts.
Step 5 — State the repair: what must be corrected.
Step 6 — Declare all variables needed for the formula.
Step 7 — Write a single safe Python arithmetic expression that computes the target.
Step 8 — Verify: evaluate the formula mentally and confirm it equals your final_answer.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- requested_target must be the EXACT quantity the question asks for, not a related or nearby quantity.
- source_facts must list only values that appear in the problem statement.
- formula_variables maps each snake_case variable name to its numeric value, a short description, and unit.
- solution_formula must be a single Python arithmetic expression.
  - Use only names that appear in formula_variables.
  - No imports. No assignments. No attributes (no dots). No subscripts (no brackets).
  - No code block.
  - No comprehensions. No lambda. No boolean logic. No comparisons.
  - No prose, no string constants.
  - Allowed operations: + - * / // % ** and round(x, n) where n is a non-negative integer ≤ 10.
  - solution_formula must compute requested_target, not a nearby quantity.
  - Prefer exact arithmetic; do not round unless the question explicitly asks for rounding.
- final_answer must be a bare integer or decimal number equal to eval(solution_formula).
- confidence is "high" / "medium" / "low" based on your certainty in the formula.

QUESTION:
{{question}}

EXISTING CANDIDATES (model-generated from prior branches — none are confirmed correct):
{{candidate_pool_summary}}
{{prior_bftc_context}}
Output a single valid JSON object with exactly these fields and no other text:
{
  "requested_target": "<exact quantity the question asks for, in plain English>",
  "source_facts": [
    "<key numeric fact from the problem statement>",
    "<key numeric fact from the problem statement>"
  ],
  "reverse_derivation": [
    {
      "step": <integer starting at 1>,
      "description": "<one sentence: what this step computes or validates>",
      "consistent_with_target": <true or false>
    }
  ],
  "failed_relation": "<what relation or computation the prior attempts got wrong, or 'none' if this is the first attempt>",
  "repair_operation": "<what must be corrected relative to prior attempts, or 'none'>",
  "formula_variables": {
    "<snake_case_name>": {
      "value": <numeric value from the problem>,
      "description": "<short semantic description>",
      "unit": "<unit or empty string>"
    }
  },
  "solution_formula": "<single Python arithmetic expression using only names from formula_variables>",
  "final_answer": <bare integer or decimal, must equal eval(solution_formula)>,
  "confidence": "<high|medium|low>"
}
