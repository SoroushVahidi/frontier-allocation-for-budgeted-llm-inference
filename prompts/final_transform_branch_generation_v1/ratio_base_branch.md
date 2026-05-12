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
- Bind the final target before arithmetic.
- Identify the numerator and denominator/base before computing.
- If the question asks for a percent, fraction, or probability, write `target = numerator / base` or `target_percent = 100 * numerator / base`.
- Warn against using the wrong base or total.
- For weighted points, identify the count first, then the score or points.
- Keep the final answer tied to the target named in the question.
- Final answer format: `FINAL_ANSWER: <number>`.
- Do not output any other number after `FINAL_ANSWER`.
- Keep reasoning concise.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch, then `FINAL_ANSWER: <number>` only.
