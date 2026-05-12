BRANCH_FAMILY: per_unit_share_branch
MODE: no_api_preflight_only

Recover the per-unit, per-person, or shared quantity before arithmetic.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- State the per-unit or per-share base explicitly.
- Keep the final answer tied to the requested per-unit or shared quantity.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch and then the final answer only.
