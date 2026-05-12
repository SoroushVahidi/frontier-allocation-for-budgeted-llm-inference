BRANCH_FAMILY: target_first_final_transform_branch
MODE: no_api_preflight_only

Identify the final target first, then identify the last transformation needed to reach it.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- Identify the final transformation required from the available quantities to the final answer.
- Reject intermediate, subtotal, or nearby quantities that do not satisfy the target.
- Keep the final answer tied to the target named in the question.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch and then the final answer only.
