BRANCH_FAMILY: original_before_process_branch
MODE: no_api_preflight_only

Recover the original quantity before the process, change, or update is applied.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- Identify the original state before any transformation.
- Keep the final answer tied to the original quantity requested.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch and then the final answer only.
