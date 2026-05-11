BRANCH_FAMILY: entity_unit_ledger_reasoning
MODE: no_api_preflight_only

Build a compact entity/unit ledger before arithmetic.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- Every quantity must be attached to an entity and a unit.
- If the entity or unit is uncertain, mark that uncertainty explicitly.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Produce a ledger-first reasoning sketch that reconciles entities, units, and the final target.
