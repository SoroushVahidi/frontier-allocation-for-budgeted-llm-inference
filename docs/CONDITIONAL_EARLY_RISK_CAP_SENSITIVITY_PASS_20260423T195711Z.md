# Conditional early risk-cap tiny sensitivity pass (2026-04-23)

## Purpose

This is the immediate next minimal follow-up after the prior targeted success of:
- `strict_f3_conditional_early_risk_cap_k2_v1`

Question:
> Is that positive point locally stable under tiny nearby threshold changes, or fragile to one exact setting?

This pass intentionally stays narrow:
- same manuscript-relevant replay surface,
- same targeted hard-slice definition,
- no new controller family,
- no broad sweep,
- no rival-maturation branch.

## Surface and slice contract

- Surface source: `outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv`
- Replay scope: datasets `{openai/gsm8k, HuggingFaceH4/MATH-500, HuggingFaceH4/aime_2024}`, budgets `{4,6,8}`, seeds `{11,23}`, total 360 strict_f3 rows.
- Anchor: `strict_f3` runtime (`...hard_early_root_depth3_coverage_forced_v1`)
- Best conditional reference: `strict_f3_conditional_early_risk_cap_k2_v1`
- Targeted slice (same as prior run):
  - anchor failure
  - absent-from-tree
  - repeated-same-family present

## Tiny local neighborhood tested

Baseline successful template:
- early cap `K=2`
- early window `6`
- risk share trigger `0.60`
- risk run trigger `3`

Nearby variants (5):
1. `strict_f3_conditional_early_risk_cap_k2_window5_v1` (window 5)
2. `strict_f3_conditional_early_risk_cap_k2_window7_v1` (window 7)
3. `strict_f3_conditional_early_risk_cap_k2_share55_v1` (share 0.55)
4. `strict_f3_conditional_early_risk_cap_k2_share65_v1` (share 0.65)
5. `strict_f3_conditional_early_risk_cap_k3_v1` (cap 3)

## Output bundle

- `outputs/manuscript_slice_conditional_early_risk_cap_sensitivity_eval_20260423T195711Z/eval_manifest.json`
- `outputs/manuscript_slice_conditional_early_risk_cap_sensitivity_eval_20260423T195711Z/per_case_results.csv`
- `outputs/manuscript_slice_conditional_early_risk_cap_sensitivity_eval_20260423T195711Z/method_summary.csv`
- `outputs/manuscript_slice_conditional_early_risk_cap_sensitivity_eval_20260423T195711Z/target_slice_method_summary.csv`
- `outputs/manuscript_slice_conditional_early_risk_cap_sensitivity_eval_20260423T195711Z/aggregate_summary.json`

## Aggregate matched-surface results (key rows)

Best prior conditional baseline (`k2`, window 6, share 0.60):
- accuracy: **0.6389**
- absent-from-tree: **99**
- repeated-same-family: **314**
- gold-in-tree: **261**

Nearby variants:
- `share55`: accuracy **0.6417** (slightly higher), but absent **101** and repeated **316** (both worse than baseline conditional).
- `share65`: accuracy **0.6306**, absent **103** (worse), repeated **303** (better), gold-in-tree **257** (worse).
- `window7`: accuracy **0.6278**, absent **103** (worse), repeated **314** (same), gold-in-tree **257** (worse).
- `window5`: accuracy **0.5972**, absent **115** (worse), repeated **304** (better), gold-in-tree **245** (worse).
- `k3`: accuracy **0.5778**, absent **116** (worse), repeated **315** (worse), gold-in-tree **244** (worse).

## Targeted-slice summary (91 cases)

Baseline conditional remains strongest overall on the intended hard slice mix:
- baseline conditional: accuracy **0.7143**, absent **20**, repeated **77**, gold-in-tree **71**.

Notable neighbors:
- `share65` ties slice accuracy (**0.7143**) but still has worse absent (**21**) and repeated (**80**) than baseline conditional.
- others either reduce accuracy or worsen upstream entry metrics.

## Robustness judgment

Using the explicit promotion gate:
- maintain/improve accuracy,
- no material absent-from-tree worsening,
- no material repeated-same-family worsening,
- preserve upstream interpretation (gold-in-tree not worse),

**Result: `fragile_positive`.**

No nearby variant simultaneously satisfied the gate relative to the successful baseline conditional setting.

## Interpretation

- The original positive point (`strict_f3_conditional_early_risk_cap_k2_v1`) still looks real versus anchor strict_f3.
- But the tiny local neighborhood does **not** show multiple nearby settings with the same full profile.
- Current evidence supports keeping this mechanism as promising-but-sensitive exploratory evidence, not yet robust enough for stronger manuscript-facing promotion.

## Recommendation (next)

1. Keep the current successful baseline conditional setting frozen as the best known point.
2. If continuing, run one additional *very small* confirmatory rerun focused only on seed stability for this exact setting (not a wider parameter search).
3. Only consider stronger promotion if that rerun preserves both accuracy and upstream absent-from-tree behavior.

