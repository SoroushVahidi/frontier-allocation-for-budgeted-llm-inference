BRANCH_FAMILY: ratio_base_branch
MODE: no_api_preflight_only

Identify the base quantity for any ratio, percentage, fraction, or proportion before arithmetic.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- State the ratio or percentage base explicitly before any computation.
- Keep the final answer tied to the target named in the question.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch and then the final answer only.
