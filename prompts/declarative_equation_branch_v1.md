BRANCH_FAMILY: declarative_equation_branch_v1
MODE: no_api_preflight_or_live_pilot

Solve the problem by constructing the target relation before doing arithmetic.

Rules:
- Do not use any hidden reference answer, answer-key information, label metadata, or gold answer.
- requested_target must describe the exact quantity the question asks for.
- target_variable and solve_for must be identical strings.
- process_state must be one of: before, after, final, original, unknown.
- source_facts must include only facts stated in the question.
- variables must declare every variable used in equations or solution_formula.
- Use concise semantic snake_case names only. Do not use generic names like x, y, z, answer, result, or value.
- relations must describe how quantities compose before arithmetic. Use concise declarative relation statements, not prose paragraphs.
- equations must be declarative relations such as `total_cost = unit_price * item_count`. Do not write prose in equations.
- equation_rationale should briefly explain why the declared equations identify the requested target.
- solution_formula must solve for target_variable and use only variable names declared in variables.
- solution_formula must be a single safe Python arithmetic expression.
  - No imports. No assignments. No attributes. No subscripts.
  - No comprehensions. No lambda. No boolean logic. No comparisons.
  - No code block. No prose. No string constants.
  - Allowed operations: + - * / // % ** and round(x, n) where n is an integer from 0 to 10.
 - final_answer must equal the numeric result of solution_formula when a numeric solution is available.
 - If the relation is ambiguous or underspecified, do not invent missing facts. Set uncertainty=true, give an abstain_reason, and use null for final_answer if needed.
 - Distinguish before/after/original/final state when the question involves process transitions such as profit, remaining amount, pre/post change, or unit conversion endpoints.
- No gold answers, answer keys, or hidden labels may appear anywhere in the output.

QUESTION:
{{question}}

EXISTING CANDIDATES (model-generated context only; none are confirmed correct):
{{candidate_pool_summary}}
{{prior_context}}
Output a single valid JSON object with exactly these fields and no other text:
{
  "requested_target": "<exact quantity the question asks for>",
  "target_variable": "<semantic snake_case name for the requested target>",
  "target_unit": "<unit or type of the requested target>",
  "process_state": "<before|after|final|original|unknown>",
  "source_facts": [
    "<fact stated in the question>",
    "<fact stated in the question>"
  ],
  "variables": [
    {
      "name": "<semantic_snake_case_name>",
      "description": "<what this variable represents>",
      "unit": "<unit or empty string>",
      "value": <numeric value or null>
    }
  ],
  "relations": [
    "<declarative relation showing how named quantities compose>"
  ],
  "equations": [
    "<declarative relation using declared variable names>"
  ],
  "equation_rationale": "<brief explanation of why these equations solve the requested target>",
  "solve_for": "<must exactly match target_variable>",
  "solution_formula": "<single safe Python arithmetic expression that solves for target_variable>",
  "final_answer": <bare integer or decimal, or null if abstaining>,
  "uncertainty": <true or false>,
  "abstain_reason": "<empty string if not abstaining, otherwise explain why the relation is ambiguous or underspecified>"
}
