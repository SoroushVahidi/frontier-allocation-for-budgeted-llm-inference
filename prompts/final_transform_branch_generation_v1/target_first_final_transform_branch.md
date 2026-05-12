BRANCH_FAMILY: target_first_final_transform_branch
MODE: no_api_preflight_only

Identify the final target first, then identify the last transformation needed to reach it.

Target-binding checklist:
1. What is the final target?
2. What unit/state/share/base does the final target require?
3. What intermediate quantities are tempting but not final?
4. What final transform maps intermediates to the target?

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- Classify the final transform as one of: `difference`, `remainder`, `profit`, `per_unit_share`, `ratio_probability`, `unit_conversion`, `original_before_process`, `additive_total`, or `other`.
- Write the formula for that transform before arithmetic.
- List all quantities used and all quantities deliberately rejected as non-final.
- Reject intermediate, subtotal, or nearby quantities that do not satisfy the target.
- Keep the final answer tied to the target named in the question.
- Final answer format: `FINAL_ANSWER: <number>`.
- Do not output any other number after `FINAL_ANSWER`.
- Keep reasoning concise.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch, then `FINAL_ANSWER: <number>` only.
