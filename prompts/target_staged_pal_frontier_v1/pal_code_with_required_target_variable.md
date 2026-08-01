BRANCH_FAMILY: pal_code_with_required_target_variable
MODE: no_api_preflight_only

Write PAL code that assigns the final answer to the exact target_variable named in the schema.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- The code must print the final target_variable value.
- Do not introduce an extra final-answer variable that bypasses the target variable.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Return only the code block or plain code needed to compute the target variable.
