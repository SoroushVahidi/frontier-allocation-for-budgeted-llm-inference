BRANCH_FAMILY: difference_or_remainder_branch
MODE: no_api_preflight_only

Bind the difference, remainder, or how-many-more target before arithmetic.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- Keep the minuend, subtrahend, and remainder roles explicit.
- Keep the final answer tied to the requested difference or remainder.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch and then the final answer only.
