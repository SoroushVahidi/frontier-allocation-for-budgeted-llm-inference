BRANCH_FAMILY: declarative_equation_branch_v2
MODE: no_api_preflight_or_live_pilot

Solve the problem by separating semantic relations from executable algebra.

Rules:
- Do not use any gold answer, answer key, private evaluation metadata, or dataset annotation.
- Output strict JSON only. No markdown, code fences, prose, or comments outside the JSON object.
- requested_target must describe the exact quantity the question asks for.
- target_variable and solve_for must be identical strings.
- target_unit must match the requested target's unit or quantity type.
- process_state must be one of: before, after, final, original, unknown.
- source_facts must include only facts stated in the question.
- variables must declare every variable used in equations or solution_formula.
- Use concise semantic snake_case names only. Do not use generic names like x, y, z, answer, result, or value.
- Every variable object must contain exactly: name, value, unit, description, source.
- variable.value must be a JSON number or null. Do not emit strings such as "12", fractions such as 2/3, or expressions such as price * count.
- variable.source must be one of: given, derived, unknown.
- relations are prose-only semantic statements. Do not put equations, equals signs, or executable algebra in relations.
- equations are the only place for algebraic equalities. Use declared variable names only.
- solution_formula must be the only executable expression and must use only declared variable names.
- solution_formula must be a single safe Python arithmetic expression.
  - No imports. No assignments. No attributes. No subscripts.
  - No comprehensions. No lambda. No boolean logic. No comparisons.
  - No code block. No prose. No string constants.
  - Allowed operations: + - * / // % ** and round(x, n) where n is an integer from 0 to 10.
- final_answer must equal the numeric result of solution_formula when a numeric solution is available.
- If the relation is ambiguous or underspecified, do not invent missing facts. Set uncertainty=true, explain the ambiguity in abstain_reason, and use null for final_answer if needed.
- Distinguish before/after/original/final state when the question involves process transitions, profit, remaining amount, or unit conversion endpoints.

QUESTION:
{{question}}

EXISTING CANDIDATES (model-generated context only; none are confirmed correct):
{{candidate_pool_summary}}

Output a single valid JSON object with exactly these fields and no other text:
{
  "requested_target": "<exact quantity the question asks for>",
  "target_variable": "<semantic snake_case target variable>",
  "target_unit": "<unit or quantity type>",
  "process_state": "<before|after|final|original|unknown>",
  "source_facts": [
    "<fact stated in the question>",
    "<fact stated in the question>"
  ],
  "variables": [
    {
      "name": "<semantic_snake_case_name>",
      "value": <JSON number or null>,
      "unit": "<unit or empty string>",
      "description": "<short source-grounded meaning>",
      "source": "<given|derived|unknown>"
    }
  ],
  "relations": [
    "<semantic relation in prose only>"
  ],
  "equations": [
    "<equation using declared variable names>"
  ],
  "solve_for": "<must exactly match target_variable>",
  "solution_formula": "<single safe arithmetic expression using declared variables only>",
  "final_answer": <bare integer or decimal, or null if abstaining>,
  "uncertainty": <true or false>,
  "abstain_reason": "<empty string if not abstaining, otherwise explain why the relation is ambiguous or underspecified>"
}
