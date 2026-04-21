# Budget-aware family cap evaluation (20260421T162842Z)

## Scope
Evaluate whether strict_gate1 same-family hard cap should remain fixed at K=6 or switch to budget-aware K(b) formulas, while preserving strict-phased law and controller logic.

## Candidate formulas
- `fixed_k6`: `K(b)=6`
- `min6_half`: `K(b)=min(6,floor(b/2))`
- `min6_third`: `K(b)=min(6,floor(b/3))`
- `min6_quarter`: `K(b)=min(6,floor(b/4))`
- `half`: `K(b)=max(1,floor(b/2))`
- `third`: `K(b)=max(1,floor(b/3))`
- `quarter`: `K(b)=max(1,floor(b/4))`

## Evaluation surface
- datasets: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'olympiadbench']
- subset size per dataset/seed: 8
- seeds: [13, 37, 101]
- budgets: [4, 6, 8, 10, 12, 14, 16]
- total evaluated rows: 504

## Overall comparison
| formula | accuracy | absent_from_tree | present_not_selected | repeated_same_family_present | avg_longest_same_family_run | avg_max_family_share | avg_actions | avg_expansions | avg_verifications | improved_vs_fixed_k6 | worsened_vs_fixed_k6 | unchanged_vs_fixed_k6 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed_k6 | 0.6944 | 104 | 50 | 402 | 3.617 | 0.630 | 7.845 | 6.948 | 0.897 | 0 | 0 | 504 |
| half | 0.6448 | 117 | 62 | 376 | 3.472 | 0.565 | 7.665 | 7.335 | 0.329 | 107 | 132 | 265 |
| min6_half | 0.6270 | 117 | 71 | 387 | 3.272 | 0.544 | 8.202 | 7.327 | 0.875 | 95 | 129 | 280 |
| min6_third | 0.5734 | 165 | 50 | 287 | 2.183 | 0.513 | 8.518 | 5.254 | 3.264 | 86 | 147 | 271 |
| third | 0.5675 | 169 | 49 | 285 | 2.161 | 0.520 | 8.101 | 5.067 | 3.034 | 76 | 140 | 288 |
| quarter | 0.4881 | 217 | 41 | 213 | 1.639 | 0.507 | 8.343 | 4.010 | 4.333 | 75 | 179 | 250 |
| min6_quarter | 0.4861 | 221 | 38 | 234 | 1.677 | 0.511 | 8.335 | 4.058 | 4.278 | 83 | 188 | 233 |

## Best formula by budget
| budget | best_formula | formula_expr |
|---:|---|---|
| 4 | fixed_k6 | K(b)=6 |
| 6 | half | K(b)=max(1,floor(b/2)) |
| 8 | fixed_k6 | K(b)=6 |
| 10 | fixed_k6 | K(b)=6 |
| 12 | fixed_k6 | K(b)=6 |
| 14 | min6_third | K(b)=min(6,floor(b/3)) |
| 16 | fixed_k6 | K(b)=6 |

## Budget dependence assessment
- low-budget winners (<=6): ['fixed_k6', 'half']
- high-budget winners (>=12): ['fixed_k6', 'min6_third', 'fixed_k6']
- fixed_k6 winner-count across budgets: 5 / 7
- formulas winning at least half the budgets: ['fixed_k6']

## Recommended formula by budget regime
- low budgets [4, 6]: `fixed_k6` (K(b)=6), accuracy=0.6042
- medium budgets [8, 10]: `fixed_k6` (K(b)=6), accuracy=0.7569
- high budgets [12, 14, 16]: `fixed_k6` (K(b)=6), accuracy=0.7130

## Final decision
- Overall winner on this evaluated surface: **fixed_k6** (`K(b)=6`).
- Fixed K=6 should be retained only if it remains competitive across most budgets; otherwise replace with a budget-aware rule or piecewise regime policy.
- Conclusion is scoped to this evaluated simulator surface and current strict-phased repository phase, not universal optimality.

## Artifacts
- output directory: `outputs/budget_aware_family_cap_eval_20260421T162842Z`
- machine-readable aggregate summary: `aggregate_summary.json`
- per-budget summary: `per_budget_summary.json` and `per_budget_summary_table.csv`
- per-dataset summary: `per_dataset_summary.json`
- head-to-head summaries: `head_to_head_vs_fixed_k6.json`
- recommended formula by budget regime: `recommended_formula_by_budget_regime.json`