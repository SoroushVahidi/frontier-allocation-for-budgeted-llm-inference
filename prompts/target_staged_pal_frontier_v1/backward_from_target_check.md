BRANCH_FAMILY: backward_from_target_check
MODE: no_api_preflight_only

Start from the target and check the reasoning path in reverse.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- Verify each intermediate relation from the target back to the source facts.
- If uncertainty remains, mark it explicitly.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Write a backward-check plan that validates entity, unit, and state consistency before arithmetic.
