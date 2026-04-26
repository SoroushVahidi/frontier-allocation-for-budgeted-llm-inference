# COHERE_NONMATH_EXTERNAL_VALIDITY_AUDIT

Timestamp: `20260425T_WULVER_COHERE_NONMATH_AUDIT`
Output package: `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/`

1. Did Cohere readiness pass inside the batch job?
- yes (if job reached this report-generation step and logged COHERE_READINESS_OK).
2. Which exact datasets were used?
- []
3. Which exact methods were successfully run?
- []
4. Which methods or datasets were unavailable, if any?
- methods_unsupported=[]
5. How many scored examples were collected per dataset/method/budget/seed?
- dataset=natural_plan method=strict_f3_anti_collapse_weak_v1 seed=11 budget=4 n_scored=None
- dataset=natural_plan method=strict_f3 seed=11 budget=4 n_scored=None
- dataset=natural_plan method=external_l1_max seed=11 budget=4 n_scored=None
- dataset=natural_plan method=tale seed=11 budget=4 n_scored=None
- dataset=natural_plan method=s1 seed=11 budget=4 n_scored=None
- dataset=natural_plan method=strict_f3_anti_collapse_weak_v1 seed=11 budget=6 n_scored=None
- dataset=natural_plan method=strict_f3 seed=11 budget=6 n_scored=None
- dataset=natural_plan method=external_l1_max seed=11 budget=6 n_scored=None
- dataset=natural_plan method=tale seed=11 budget=6 n_scored=None
- dataset=natural_plan method=s1 seed=11 budget=6 n_scored=None
- dataset=natural_plan method=strict_f3_anti_collapse_weak_v1 seed=11 budget=8 n_scored=None
- dataset=natural_plan method=strict_f3 seed=11 budget=8 n_scored=None
- dataset=natural_plan method=external_l1_max seed=11 budget=8 n_scored=None
- dataset=natural_plan method=tale seed=11 budget=8 n_scored=None
- dataset=natural_plan method=s1 seed=11 budget=8 n_scored=None
- dataset=natural_plan method=strict_f3_anti_collapse_weak_v1 seed=23 budget=4 n_scored=None
- dataset=natural_plan method=strict_f3 seed=23 budget=4 n_scored=None
- dataset=natural_plan method=external_l1_max seed=23 budget=4 n_scored=None
- dataset=natural_plan method=tale seed=23 budget=4 n_scored=None
- dataset=natural_plan method=s1 seed=23 budget=4 n_scored=None
- dataset=natural_plan method=strict_f3_anti_collapse_weak_v1 seed=23 budget=6 n_scored=None
- dataset=natural_plan method=strict_f3 seed=23 budget=6 n_scored=None
- dataset=natural_plan method=external_l1_max seed=23 budget=6 n_scored=None
- dataset=natural_plan method=tale seed=23 budget=6 n_scored=None
- dataset=natural_plan method=s1 seed=23 budget=6 n_scored=None
- dataset=natural_plan method=strict_f3_anti_collapse_weak_v1 seed=23 budget=8 n_scored=None
- dataset=natural_plan method=strict_f3 seed=23 budget=8 n_scored=None
- dataset=natural_plan method=external_l1_max seed=23 budget=8 n_scored=None
- dataset=natural_plan method=tale seed=23 budget=8 n_scored=None
- dataset=natural_plan method=s1 seed=23 budget=8 n_scored=None
- dataset=gpqa_diamond method=strict_f3_anti_collapse_weak_v1 seed=11 budget=4 n_scored=None
- dataset=gpqa_diamond method=strict_f3 seed=11 budget=4 n_scored=None
- dataset=gpqa_diamond method=external_l1_max seed=11 budget=4 n_scored=None
- dataset=gpqa_diamond method=tale seed=11 budget=4 n_scored=None
- dataset=gpqa_diamond method=s1 seed=11 budget=4 n_scored=None
- dataset=gpqa_diamond method=strict_f3_anti_collapse_weak_v1 seed=11 budget=6 n_scored=None
- dataset=gpqa_diamond method=strict_f3 seed=11 budget=6 n_scored=None
- dataset=gpqa_diamond method=external_l1_max seed=11 budget=6 n_scored=None
- dataset=gpqa_diamond method=tale seed=11 budget=6 n_scored=None
- dataset=gpqa_diamond method=s1 seed=11 budget=6 n_scored=None
- dataset=gpqa_diamond method=strict_f3_anti_collapse_weak_v1 seed=11 budget=8 n_scored=None
- dataset=gpqa_diamond method=strict_f3 seed=11 budget=8 n_scored=None
- dataset=gpqa_diamond method=external_l1_max seed=11 budget=8 n_scored=None
- dataset=gpqa_diamond method=tale seed=11 budget=8 n_scored=None
- dataset=gpqa_diamond method=s1 seed=11 budget=8 n_scored=None
- dataset=gpqa_diamond method=strict_f3_anti_collapse_weak_v1 seed=23 budget=4 n_scored=None
- dataset=gpqa_diamond method=strict_f3 seed=23 budget=4 n_scored=None
- dataset=gpqa_diamond method=external_l1_max seed=23 budget=4 n_scored=None
- dataset=gpqa_diamond method=tale seed=23 budget=4 n_scored=None
- dataset=gpqa_diamond method=s1 seed=23 budget=4 n_scored=None
- dataset=gpqa_diamond method=strict_f3_anti_collapse_weak_v1 seed=23 budget=6 n_scored=None
- dataset=gpqa_diamond method=strict_f3 seed=23 budget=6 n_scored=None
- dataset=gpqa_diamond method=external_l1_max seed=23 budget=6 n_scored=None
- dataset=gpqa_diamond method=tale seed=23 budget=6 n_scored=None
- dataset=gpqa_diamond method=s1 seed=23 budget=6 n_scored=None
- dataset=gpqa_diamond method=strict_f3_anti_collapse_weak_v1 seed=23 budget=8 n_scored=None
- dataset=gpqa_diamond method=strict_f3 seed=23 budget=8 n_scored=None
- dataset=gpqa_diamond method=external_l1_max seed=23 budget=8 n_scored=None
- dataset=gpqa_diamond method=tale seed=23 budget=8 n_scored=None
- dataset=gpqa_diamond method=s1 seed=23 budget=8 n_scored=None
6. Did strict_f3_anti_collapse_weak_v1 beat external_l1_max on Natural Plan?
- mean_accuracy_diff=NA
7. Did strict_f3_anti_collapse_weak_v1 beat external_l1_max on GPQA Diamond?
- mean_accuracy_diff=NA
8. Did strict_f3_anti_collapse_weak_v1 beat default strict_f3?
- natural_plan_diff=NA; gpqa_diamond_diff=NA
9. What are the token, latency, and estimated-cost differences?
- method=external_l1_max mean_tokens=None accuracy_per_1k_tokens=0.0001216669343339222 mean_estimated_cost_usd=None
- method=s1 mean_tokens=None accuracy_per_1k_tokens=5.722174140064518e-05 mean_estimated_cost_usd=None
- method=strict_f3 mean_tokens=None accuracy_per_1k_tokens=4.366171188839972e-05 mean_estimated_cost_usd=None
- method=strict_f3_anti_collapse_weak_v1 mean_tokens=None accuracy_per_1k_tokens=4.8814823704668896e-05 mean_estimated_cost_usd=None
- method=tale mean_tokens=None accuracy_per_1k_tokens=0.0 mean_estimated_cost_usd=None
10. Is this evidence favorable, mixed, or unfavorable for the broader-than-math claim?
- mixed_or_incomplete
11. Should the result be main-paper, appendix-only, or provenance-only?
- provenance_only
12. What incomplete slices remain?
- count=36 (see `incomplete_slices.csv` for details)

Claim discipline: supporting/diagnostic real-model evidence only; no universal-dominance claim.
