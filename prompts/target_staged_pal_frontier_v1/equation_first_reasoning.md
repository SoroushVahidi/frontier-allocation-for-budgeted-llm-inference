BRANCH_FAMILY: equation_first_reasoning
MODE: no_api_preflight_only

Write equations first, then compute.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- Map quantities into equations before any numeric calculation.
- Keep unit consistency visible.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Write the equations, then a short explanation of how they produce the target variable.
