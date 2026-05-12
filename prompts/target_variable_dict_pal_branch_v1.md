BRANCH_FAMILY: target_variable_dict_pal_branch_v1
MODE: no_api_preflight_only

Solve the problem below using explicit semantic variable binding.

Rules:
- Do not use any hidden reference answer, answer-key information, label metadata, or gold answer.
- Assign a semantic name to every variable you compute (e.g. `total_cost`, `items_per_box`, `daily_profit`). Never use generic names such as `x`, `y`, `z`, `answer`, `result`, or `val`.
- Compute all intermediate variables that are relevant to reaching the final target, and include them in `variables`.
- Identify at least one tempting nearby value that is NOT the final answer and list it in `rejected_non_final_variables` with its name. For example: if the question asks for profit, reject total_revenue; if it asks for the remainder, reject total_used.
- `answer_variable_name` must exactly match `target_variable_name`.
- `final_answer` must be a bare integer or decimal number. No `$`, `%`, commas, or units. No string wrapping.

QUESTION:
{{question}}

Output a single valid JSON object with exactly these fields and no other text:
{
  "problem_summary": "<one sentence: what quantity is being computed and from what>",
  "target_question": "<the exact quantity the question asks for>",
  "target_variable_name": "<semantic name for the final answer, e.g. daily_profit>",
  "target_unit": "<unit or type of the answer, e.g. dollars, items, minutes, percent>",
  "variables": [
    {
      "name": "<semantic_variable_name>",
      "description": "<what this variable represents in the problem>",
      "unit": "<unit or type>",
      "expression": "<arithmetic expression or formula, e.g. total_revenue - total_cost>",
      "value": <numeric value, not a string>
    }
  ],
  "rejected_non_final_variables": [
    "<name_of_tempting_wrong_intermediate>"
  ],
  "answer_variable_name": "<must equal target_variable_name exactly>",
  "final_answer": <bare integer or decimal, not a string>
}
