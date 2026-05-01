# Stability note

- Contract: same manuscript-facing matched datasets and budget range as canonical matched-surface family (GSM8K, MATH-500, AIME-2024; budgets 4/6/8; subset size 20).
- Expanded seed set used: [11, 23, 37, 47, 59].
- Internal focus methods: strict_f3, strict_gate1_cap_k6, strict_f2.
- Fair near-direct external baselines included: external_s1_budget_forcing, external_tale_prompt_budgeting, external_l1_exact, external_l1_max.
- Aggregate strict_f3 accuracy: 0.622222.
- Aggregate strict_gate1_cap_k6 accuracy: 0.585556.
- Delta (strict_f3 - strict_gate1_cap_k6): 0.036667.
- Winner on this expanded-seed rerun: strict_f3.
- Evidence status relative to prior manuscript-facing winner: strengthens.
