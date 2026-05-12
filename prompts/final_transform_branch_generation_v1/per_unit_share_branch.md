BRANCH_FAMILY: per_unit_share_branch
MODE: no_api_preflight_only

Recover the per-unit, per-person, or shared quantity before arithmetic.

Target-binding checklist:
1. What is the final target?
2. What unit/state/share/base does the final target require?
3. What intermediate quantities are tempting but not final?
4. What final transform maps intermediates to the target?

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- Identify whether the target is per item, per pair, per person, per child, average per, or share.
- Convert units before division if needed.
- For pairs, convert single items to pairs before cost or share calculations.
- For leftovers, compute the leftover first, then divide by recipients.
- Keep the final answer tied to the requested per-unit or shared quantity.
- Final answer format: `FINAL_ANSWER: <number>`.
- Do not output any other number after `FINAL_ANSWER`.
- Keep reasoning concise.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch, then `FINAL_ANSWER: <number>` only.
