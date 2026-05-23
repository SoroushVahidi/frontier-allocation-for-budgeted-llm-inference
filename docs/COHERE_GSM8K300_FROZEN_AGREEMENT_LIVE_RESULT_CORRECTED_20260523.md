Cohere GSM8K-300 — Corrected Frozen Agreement Live Result (2026-05-23)

Output root:
- Original run: outputs/live_validation_hardening_frozen_agreement_policy_20260523/cohere_real_model_cost_normalized_validation_20260523T131849Z
- Corrected summaries: outputs/cohere_gsm8k300_frozen_agreement_live_result_corrected_20260523

Integrity: all checks passed; 300 unique examples; per-method scored=300; no duplicates or failed rows.

Full-coverage accuracies (N=300):
- Agreement-only (agreement_only_2of3_against_frontier): 229/300 = 0.7633333333333333
- Pooled-4 with fallback: 230/300 = 0.7666666666666667
- Frontier (direct_reserve_semantic_frontier_v2): 223/300 = 0.7433333333333333
- L1 (external_l1_max): 216/300 = 0.72
- S1 (external_s1_budget_forcing): 220/300 = 0.7333333333333333
- TALE (external_tale_prompt_budgeting): 205/300 = 0.6833333333333333

Recoveries/regressions:
- agreement_only_2of3 vs frontier: recoveries=22, regressions=16, net +6
- pooled-4 vs frontier: recoveries=11, regressions=4, net +7

Paired bootstrap CIs (policy minus comparator):
- agreement_only_2of3 vs frontier: agreement_only_2of3_against_frontier_vs_frontier,300,0.020000000000000018,-0.020000000000000018,0.06000000000000005
- agreement_only_2of3 vs L1: agreement_only_2of3_against_frontier_vs_L1,300,0.043333333333333335,0.0033333333333332993,0.08666666666666667
- pooled-4 vs frontier: pooled_4_with_fallback_vs_frontier,300,0.023333333333333428,0.0,0.04999999999999993

Explanation of previous coverage-limited metrics:
- The earlier 216/261 and 222/262 numbers represented accuracy computed only on examples where an external (2-of-3 or pooled-4) majority existed. They are conditional metrics, not full-system metrics with fallback behaviors.

Verdict:
- Integrity: successful (complete, no failures).
- Agreement-only improves point accuracy vs frontier (229 vs 223), but CI vs frontier includes zero => not statistically significant at 95%.
- Agreement-only beats L1 significantly (CI excludes zero).
- Pooled-4 slightly outperforms agreement-only by 1 example; pooled-4 shows borderline significant improvement vs frontier.

Files produced:
- outputs/cohere_gsm8k300_frozen_agreement_live_result_corrected_20260523
- outputs/cohere_gsm8k300_live_contract_audit_20260523

