BRANCH_FAMILY: ratio_base_branch
MODE: no_api_preflight_only

Identify the base quantity for any ratio, percentage, fraction, or proportion before arithmetic.

Target-binding checklist:
1. What is the final target?
2. What unit/state/share/base does the final target require?
3. What intermediate quantities are tempting but not final?
4. What final transform maps intermediates to the target?

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Do not reproduce a salient intermediate, a prior candidate value, or another prominent number as the final answer unless the target-binding checklist independently confirms it is the requested quantity.
- Bind the final target before arithmetic.
- Identify the numerator and denominator/base before computing.
- If the question asks for a percent, fraction, or probability, write `target = numerator / base` or `target_percent = 100 * numerator / base`.
- If a part of the total is given as a percentage of that same total (e.g., "item X is 60% of the total bill"), solve for the total first: `total = known_non_ratio_part / (1 - ratio)`.
- For weighted scores, compute each category's earned points independently (count × points × fraction_correct), then sum all categories.
- Warn against using the wrong base or total.
- Keep the final answer tied to the target named in the question.
- Final answer format: `FINAL_ANSWER: <number>`.
- Do not output any other number after `FINAL_ANSWER`.
- Keep reasoning concise.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch, then `FINAL_ANSWER: <number>` only.
