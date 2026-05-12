BRANCH_FAMILY: unit_conversion_branch
MODE: no_api_preflight_only

Convert the quantity into the requested unit before arithmetic.

Target-binding checklist:
1. What is the final target?
2. What unit/state/share/base does the final target require?
3. What intermediate quantities are tempting but not final?
4. What final transform maps intermediates to the target?

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Do not reproduce a salient intermediate, a prior candidate value, or another prominent number as the final answer unless the target-binding checklist independently confirms it is the requested quantity.
- Bind the final target before arithmetic.
- State both the source unit and the target unit explicitly.
- Write the conversion factor before computing.
- Warn against returning an unconverted quantity.
- Keep the final answer tied to the converted quantity requested.
- Final answer format: `FINAL_ANSWER: <number>`.
- Do not prefix the answer with `$`, `%`, or any unit — output a bare integer or decimal only.
- Do not output any other number after `FINAL_ANSWER`.
- Keep reasoning concise.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch, then `FINAL_ANSWER: <bare number>` only.
