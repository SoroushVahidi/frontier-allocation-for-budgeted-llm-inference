BRANCH_FAMILY: target_variable_dict_pal_branch_v1
MODE: no_api_preflight_only

Solve the problem below using explicit semantic variable binding.

Rules:
- Do not use any hidden reference answer, answer-key information, label metadata, or gold answer.
- Assign a semantic name to every variable you compute (e.g. `total_cost`, `items_per_box`, `daily_profit`). Never use generic names such as `x`, `y`, `z`, `answer`, `result`, or `val`.
- All variable names must be concise snake_case: lowercase letters and underscores only. No spaces, no camelCase, no long phrases.
- Compute all intermediate variables that are relevant to reaching the final target, and include them in `variables`.
- The final target variable (the answer to the question) must be the **last** item in `variables[]`.
- `answer_variable_name` must exactly equal the `name` field of the last entry in `variables[]`. Not a synonym, not an alias, not an alternate spelling — the identical string.
- `target_variable_name` must exactly equal `answer_variable_name`. Both fields must contain the same string.
- Do not give the final target variable more than one name. Use exactly one consistent name for it throughout the entire JSON.
- Identify at least one tempting nearby value that is NOT the final answer and list it in `rejected_non_final_variables` with its name. For example: if the question asks for profit, reject total_revenue; if it asks for the remainder, reject total_used.
- `final_answer` must be a bare integer or decimal number. No `$`, `%`, commas, or units. No string wrapping.

QUESTION:
{{question}}

Output a single valid JSON object with exactly these fields and no other text:
{
  "problem_summary": "<one sentence: what quantity is being computed and from what>",
  "target_question": "<the exact quantity the question asks for>",
  "target_variable_name": "<semantic snake_case name for the final answer, e.g. daily_profit>",
  "target_unit": "<unit or type of the answer, e.g. dollars, items, minutes, percent>",
  "variables": [
    {
      "name": "<semantic_snake_case_name>",
      "description": "<what this variable represents in the problem>",
      "unit": "<unit or type>",
      "expression": "<arithmetic expression or formula, e.g. total_revenue - total_cost>",
      "value": <numeric value, not a string>
    }
  ],
  "rejected_non_final_variables": [
    "<name_of_tempting_wrong_intermediate>"
  ],
  "answer_variable_name": "<identical to target_variable_name and to the name field of the last entry in variables[]>",
  "final_answer": <bare integer or decimal, not a string>
}
