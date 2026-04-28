# Early answer diversity maturation diagnostic

- Label: experimental/diagnostic only
- Output directory: `outputs/early_answer_diversity_maturation_diagnostic_20260428T201131Z`
- Budgets: [4, 6, 8]
- Methods requested: strict_f3, strict_gate1_cap_k6, strict_f3_anti_collapse_weak_v1, early_answer_diversity_maturation_v1, external_l1_max
- Data mode: cached/simulation only (deterministic mock arithmetic, no live API calls)

## Reported metrics
- accuracy
- absent-from-tree rate
- present-not-selected rate
- average actions / expansions
- early unique answer groups
- repeated-family early expansion rate
- paired deltas vs strict_f3 and external_l1_max

## Interpretation discipline
- This variant is experimental and not promoted to manuscript method.
- No canonical paper tables/figures were modified.
- If gains are mixed, keep usage diagnostic-only and avoid superiority claims.
