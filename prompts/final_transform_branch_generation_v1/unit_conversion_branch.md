BRANCH_FAMILY: unit_conversion_branch
MODE: no_api_preflight_only

Convert the quantity into the requested unit before arithmetic.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- State both the source unit and the target unit explicitly.
- Keep the final answer tied to the converted quantity requested.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch and then the final answer only.
