BRANCH_FAMILY: original_before_process_branch
MODE: no_api_preflight_only

Recover the original quantity before the process, change, or update is applied.

Target-binding checklist:
1. What is the final target?
2. What unit/state/share/base does the final target require?
3. What intermediate quantities are tempting but not final?
4. What final transform maps intermediates to the target?

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Do not reproduce a salient intermediate, a prior candidate value, or another prominent number as the final answer unless the target-binding checklist independently confirms it is the requested quantity.
- Bind the final target before arithmetic.
- Write a before/after state table: label the before-state variable B, each operation applied, and the resulting after-state value.
- Apply inverse operations in exact reverse order of the described process.
- Verify: forward-simulate from your answer; the result must match the stated after-state.
- Warn against returning an after-process amount.
- Separate population, count, money, payroll, and time totals from the requested original value.
- Keep the final answer tied to the original quantity requested.
- Final answer format: `FINAL_ANSWER: <number>`.
- Do not output any other number after `FINAL_ANSWER`.
- Keep reasoning concise.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch, then `FINAL_ANSWER: <number>` only.
