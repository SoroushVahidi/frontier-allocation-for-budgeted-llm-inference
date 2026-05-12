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
- Bind the final target before arithmetic.
- Explicitly bind the before-state and after-state.
- Work backward from the final state using inverse operations.
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
