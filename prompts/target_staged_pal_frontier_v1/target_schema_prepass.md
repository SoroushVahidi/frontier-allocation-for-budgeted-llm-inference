BRANCH_FAMILY: target_schema_prepass
MODE: no_api_preflight_only

Extract a deterministic target schema from the question below.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Do not solve the problem.
- Bind the final target before arithmetic by naming the final quantity only as a schema.
- Return JSON only.

Return exactly these keys:
target_variable, entity, unit, time_or_state, operation_goal, known_quantities, required_relations, uncertainty

QUESTION:
{{question}}
