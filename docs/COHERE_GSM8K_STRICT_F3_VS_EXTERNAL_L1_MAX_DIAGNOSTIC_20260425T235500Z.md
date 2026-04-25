# COHERE_GSM8K_STRICT_F3_VS_EXTERNAL_L1_MAX_DIAGNOSTIC_20260425T235500Z

- Source run directory: `outputs/cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN/`
- Diagnostic directory: `outputs/cohere_gsm8k_strict_f3_vs_external_l1_max_diagnostic_20260425T235500Z/`

## Required answers
1. Does strict_f3 beat external_l1_max under Cohere? **No or mixed**.
2. Is prior negative delta stable vs small-sample noise? Observed delta=-0.26666666666666666 with 95% CI [-0.4666666666666667, -0.06666666666666667], matched=30.
3. Budgets driving result: b4 delta=-0.3, b6 delta=-0.3, b8 delta=-0.2.
4. Seeds driving result: s11 delta=-0.2, s23 delta=-0.3333333333333333.
5. Cost/latency/token factors: see `cost_normalized_pairwise.csv`.
6. Runner mismatch evidence: see `runner_correctness_audit.csv`.
7. Evidence tier: **diagnostic_only_incomplete**; next recommended action: **improve_the_algorithm_or_runner**.

## Claim discipline
- If strict_f3 loses or remains mixed, this does not support a main-paper dominance claim.
- Safe framing remains appendix-only or diagnostic.
- Manuscript should not claim real-model superiority over external_l1_max from this slice.
