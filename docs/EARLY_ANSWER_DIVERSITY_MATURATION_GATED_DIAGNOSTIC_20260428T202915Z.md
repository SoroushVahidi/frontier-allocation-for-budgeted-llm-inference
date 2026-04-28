# Early answer diversity maturation gated diagnostic

- Status: experimental / diagnostic only
- Why v1 was modified: unconditional early override was too disruptive and showed lower accuracy vs strict_f3 on prior simulation slice.
- Output directory: `outputs/early_answer_diversity_maturation_diagnostic_20260428T202915Z`
- Budgets: [4]
- Exact method list: strict_f3, early_answer_diversity_maturation_v1, early_answer_diversity_maturation_gated_v1, strict_f3_anti_collapse_weak_v1, strict_gate1_cap_k6, external_l1_max
- strict_gate1_cap_k6: included (n=6)
- Data mode: cached/simulation only (deterministic mock arithmetic, no live API calls)

## Key deltas (gated vs baselines)
- accuracy delta vs strict_f3: -0.3333
- absent-from-tree delta vs strict_f3: 0.0000
- accuracy delta vs external_l1_max: 0.0000
- override rate: 0.0000
- trigger distribution: {}

## Recommendation
- discard
- Keep v1 as provenance-only experimental method; do not promote either variant without consistent gains.
