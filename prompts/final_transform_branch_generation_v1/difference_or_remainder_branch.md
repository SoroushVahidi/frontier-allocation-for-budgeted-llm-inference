BRANCH_FAMILY: difference_or_remainder_branch
MODE: no_api_preflight_only

Bind the difference, remainder, or how-many-more target before arithmetic.

Target-binding checklist:
1. What is the final target?
2. What unit/state/share/base does the final target require?
3. What intermediate quantities are tempting but not final?
4. What final transform maps intermediates to the target?

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Do not reproduce a salient intermediate, a prior candidate value, or another prominent number as the final answer unless the target-binding checklist independently confirms it is the requested quantity.
- Bind the final target before arithmetic.
- For "how many more/less," compute both compared quantities, then subtract.
- For "left/remaining/leftover," compute total available minus total used.
- If the problem involves folding, layering, or stacking (e.g., pages per sheet from folding), state the number of pages/units per layer explicitly and divide total by that multiplier.
- Keep the minuend, subtrahend, and remainder roles explicit.
- Warn against returning one side of the comparison or the total used.
- Keep the final answer tied to the requested difference or remainder.
- Final answer format: `FINAL_ANSWER: <number>`.
- Do not prefix the answer with `$`, `%`, or any unit — output a bare integer or decimal only.
- Do not output any other number after `FINAL_ANSWER`.
- Keep reasoning concise.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch, then `FINAL_ANSWER: <bare number>` only.
