BRANCH_FAMILY: profit_revenue_cost_branch
MODE: no_api_preflight_only

Bind the profit, revenue, cost, or price target before arithmetic.

Target-binding checklist:
1. What is the final target?
2. What unit/state/share/base does the final target require?
3. What intermediate quantities are tempting but not final?
4. What final transform maps intermediates to the target?

Rules:
- Do not use any hidden reference answer, answer-key information, or label metadata.
- Do not reproduce a salient intermediate, a prior candidate value, or another prominent number as the final answer unless the target-binding checklist independently confirms it is the requested quantity.
- Bind the final target before arithmetic.
- Distinguish profit, revenue, cost, sale price, purchase price, spent, earned, made, and loss quantities explicitly.
- Write the formula explicitly: `profit = revenue - total_cost` or `profit = sale_price - purchase_price - extra_costs`.
- Enumerate all cost and additive components before the final subtraction.
- Do not return sale price, revenue, increase, or total cost when profit is asked.
- Keep the final answer tied to the requested financial target.
- Final answer format: `FINAL_ANSWER: <number>`.
- Do not output any other number after `FINAL_ANSWER`.
- Keep reasoning concise.

QUESTION:
{{question}}

TARGET_SCHEMA_JSON:
{{target_schema_json}}

Respond with a concise target-binding sketch, then `FINAL_ANSWER: <number>` only.
