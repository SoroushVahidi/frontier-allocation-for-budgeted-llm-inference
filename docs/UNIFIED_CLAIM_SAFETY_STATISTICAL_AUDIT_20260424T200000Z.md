# UNIFIED_CLAIM_SAFETY_STATISTICAL_AUDIT_20260424T200000Z

Artifacts analyzed offline from `/workspace/adaptive-reasoning-budget-allocation/outputs/unified_claim_safety_statistical_audit_20260424T200000Z` inputs and repository docs.

## Reviewer-facing conclusions
A. Is strict_f3 statistically stronger than strict_gate1_cap_k6? supportive: Strict-F3 appears competitive with Strict-Gate1-Cap-K6, but the gap is fragile and surface-dependent.
B. Is strict_f3 robustly better than external_l1_max? not_safe: Frontier-allocation advantage versus external_l1_max is mixed and should be presented as non-dominant.
C. Do frontier-allocation methods dominate external_l1_max? not_safe: Frontier-allocation advantage versus external_l1_max is mixed and should be presented as non-dominant.
D. Are OpenAI and Cohere real-model results consistent with simulation? mixed; see real_model_vs_simulation_consistency.csv.
E. Is the paper safe as a dominance/SOTA paper? not_safe.
F. Is the paper safer as a formulation + diagnostic + bounded artifact paper? safe.
G. What exact claims should be used in the abstract, introduction, results, and limitations? See manuscript_recommended_wording.json and claim_safety_table.csv.
H. Which claims must not be made? See forbidden_overclaim column in claim_safety_table.csv.

## Pairwise statistics overview
- pairwise rows: 117
- artifact limitations: 6
