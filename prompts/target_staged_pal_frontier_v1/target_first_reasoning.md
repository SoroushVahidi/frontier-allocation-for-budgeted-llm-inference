BRANCH_FAMILY: target_first_reasoning
MODE: no_api_preflight_only

Use the schema to reason from the final target backward before any arithmetic.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Identify the target_variable before arithmetic.
- Bind the final target before arithmetic.
- Keep the final answer tied to the target_variable named in the schema.
- If the schema is uncertain, say so explicitly.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Write a concise target-first plan with the target, the required quantities, and the relations to compute.
