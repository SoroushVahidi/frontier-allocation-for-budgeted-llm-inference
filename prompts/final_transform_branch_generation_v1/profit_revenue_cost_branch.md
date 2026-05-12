BRANCH_FAMILY: profit_revenue_cost_branch
MODE: no_api_preflight_only

Bind the profit, revenue, cost, or price target before arithmetic.

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Bind the final target before arithmetic.
- Distinguish profit, revenue, cost, price, and spent quantities explicitly.
- Keep the final answer tied to the requested financial target.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch and then the final answer only.
