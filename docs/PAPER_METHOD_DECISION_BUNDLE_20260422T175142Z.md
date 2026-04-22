# Paper Method Decision Bundle (20260422T175142Z)

## Chosen decision surface
- Surface: `outputs/canonical_full_method_ranking_20260421T212948Z/`.
- Why: this is the cleanest single matched surface in-repo that includes the key in-house contenders and all fair near-direct external baselines under one budget/dataset/seed contract.

## Compared methods
- Requested in-house: strict_gate1_cap_k6, strict_gate1, strict_f2, strict_f3, strict_gate2
- Requested fair near-direct externals: external_s1_budget_forcing, external_tale_prompt_budgeting, external_l1_exact, external_l1_max
- Runnable on surface: strict_gate1_cap_k6, strict_f2, strict_f3, external_s1_budget_forcing, external_tale_prompt_budgeting, external_l1_exact, external_l1_max
- Blocked/caveated: strict_gate1, strict_gate2

## Aggregate results
- `strict_f3`: acc=0.6583333333333333, absent=0.2777777777777778, present_not_selected=0.06388888888888888
- `strict_gate1_cap_k6`: acc=0.6527777777777778, absent=0.2777777777777778, present_not_selected=0.06944444444444445
- `strict_f2`: acc=0.6222222222222222, absent=0.3, present_not_selected=0.07777777777777778
- `external_l1_max`: acc=0.49722222222222223, absent=0.5027777777777778, present_not_selected=0.0
- `external_tale_prompt_budgeting`: acc=0.4777777777777778, absent=0.5222222222222223, present_not_selected=0.0
- `external_s1_budget_forcing`: acc=0.43333333333333335, absent=0.5666666666666667, present_not_selected=0.0
- `external_l1_exact`: acc=0.425, absent=0.575, present_not_selected=0.0

## Mechanism diagnostics
- Budget-performance frontier: `budget_performance_frontier.csv`.
- Oracle-gap/regret: `oracle_gap_regret.csv`.
- Anti-collapse diagnostics: `collapse_diagnostics.csv` and `anti_collapse_plot_data.csv`.
- Failure decomposition: `failure_decomposition.csv` and `failure_decomposition_plot_data.csv`.

## Fairness caveats
- Near-direct externals are inference-only adapter comparisons under matched substrate conventions.
- Adjacent baselines are not merged into this decision surface.

## Final recommendation
- Recommendation: **paper should center strict_f3**
- Reason: strict_f3 remains stronger on the decision surface and is at least as strong as the top fair near-direct external comparator.

## Surface contract note

This bundle is manuscript-facing and does not redefine the broader operational default decision on the broader strict-phased surface.

- Manuscript-facing internal winner (this matched surface): `strict_f3`
- Broader operational default (different surface): `strict_gate1_cap_k6`
- Canonical cross-surface decision package: `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`

## Artifact paths
- `outputs/paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3/20260422T175142Z/`
- `docs/PAPER_METHOD_DECISION_BUNDLE_20260422T175142Z.md`
