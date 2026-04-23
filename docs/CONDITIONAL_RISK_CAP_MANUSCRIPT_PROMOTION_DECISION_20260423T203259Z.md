# Conditional risk-cap manuscript promotion decision (2026-04-23)

## Decision question

Does `strict_f3_conditional_early_risk_cap_k2_v1` change the manuscript-facing matched-surface main-method story, or should it stay supportive-only?

## 1) Audit of what already existed

Inspected manuscript source-of-truth and canonical comparison docs/artifacts:
- `docs/PAPER_SOURCE_OF_TRUTH.md`
- `docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
- `docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`
- `docs/NEURIPS_PAPER_ARTIFACTS.md`
- canonical matched-surface bundle: `outputs/matched_surface_multiseed_main_comparison_20260423T235900Z/`

Findings:
- Canonical matched-surface comparison already contained `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`, and near-direct external baselines.
- It **did not include** `strict_f3_conditional_early_risk_cap_k2_v1`.

Therefore, the minimally required rerun was needed.

## 2) Minimal rerun performed (only what was missing)

Runner:
- `scripts/run_matched_surface_multiseed_main_comparison.py`

Contract used (kept canonical):
- datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- budgets: `4,6,8`
- seeds: `11,23,37,41,53,67` (canonical manuscript matched-surface discipline)
- methods:
  - internal: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`, `strict_f3_conditional_early_risk_cap_k2_v1`
  - near-direct externals: `l1_max`, `tale`, `s1`, `l1_exact`
  - retained existing lane in this bundle: `zhai_cpo_mode_a`

Output bundle:
- `outputs/matched_surface_multiseed_main_comparison_20260423T203259Z/`

## 3) Aggregate results relevant to promotion decision

From `per_method_summary.csv`:
- `strict_f3`: mean accuracy `0.6213`
- `strict_gate1_cap_k6`: `0.6167`
- `strict_f2`: `0.6111`
- `strict_f3_conditional_early_risk_cap_k2_v1`: `0.6000`
- strongest near-direct external (`l1_max`): `0.4843`

Head-to-head vs current manuscript method (`strict_f3`):
- mean accuracy gap (`conditional - strict_f3`): `-0.0213`
- paired permutation p-value: `0.3885`
- absent-from-tree rate: conditional `0.2981` vs strict_f3 `0.2972` (not better)
- present-not-selected rate: conditional `0.1009` vs strict_f3 `0.0815` (worse)

Winner under this canonical contract remains:
- **`strict_f3`**

## 4) Manuscript-impact interpretation

- The conditional-risk candidate showed supportive gains on targeted hard-slice diagnostics and seed-stability within that line.
- But on the manuscript-facing matched main comparison, it does **not** improve the main method story; it underperforms `strict_f3` on mean accuracy and does not improve the core failure decomposition profile.
- Given 9-page main-body constraints, promoting this variant into the main method would add complexity without improving the headline matched-surface result.

## 5) Final recommendation

**Keep current manuscript method unchanged (`strict_f3`).**

Promotion status for `strict_f3_conditional_early_risk_cap_k2_v1`:
- **appendix/supportive refinement only** (mechanism-level evidence),
- **not** manuscript-facing main-method replacement,
- **not** a main-table winner update.

No broad canonical doc rewrite is warranted from this decision alone.
