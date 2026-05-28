# PAPER_CLAIMS_AND_EVIDENCE_MAP

> **Updated 2026-05-27:** The current canonical claim table is in Section 0 below. The original content (Section 1+) was written for the pre-FTA era (strict_f3 method) and is preserved for historical provenance. Do not use Section 1+ tables as current claim guidance.
>
> For the complete current safe/unsafe claim table, see also: `docs/CURRENT_CANONICAL_STATE_20260527.md` Section 6 and `outputs/repository_situation_and_scenario_ranking_20260527/run_20260527T010000Z/paper_claim_safety_table.csv`.

## 0. Current Claim Map (2026-05-27, FTA era)

| Claim | Status | Evidence | Caveat |
|---|---|---|---|
| FTA achieves 86.67% (260/300) Final-300 (Cohere × GSM8K, seed=71, budget=6) | **SAFE MAIN CLAIM** | `outputs/fta_independent_verification_20260527/` | Must state dataset=GSM8K only |
| FTA achieves 80.69% (581/720) Aggregate-720 (seeds 41+61+71) | **SAFE MAIN CLAIM** | `outputs/fta_independent_verification_20260527/` | Must disclose seed=61 failure-enriched |
| FTA CI vs L1/S1/TALE/best-external (Agg-720) all strictly positive | **SAFE MAIN CLAIM** | `outputs/fta_independent_verification_20260527/` | State source-stratified CI values |
| FTA gate features are gold-free at runtime (leakage audit PASS) | **SAFE MAIN CLAIM** | `fta_leakage_and_budget_audit.json` | Required disclosure |
| FTA adds 0 post-generation model calls | **SAFE MAIN CLAIM** | `fta_leakage_and_budget_audit.json` | Must also state full pool=24 calls |
| FIX-2=63, FIX-4=3, no-gate=234 (Final-300) | **SAFE MAIN CLAIM** | `fta_gate_action_audit.csv` | Independently reproduced |
| FIX-4 causes 0 regressions (3 wins, 0 losses) | **SAFE MAIN CLAIM** | `fta_gate_action_audit.csv` | Conservative gate |
| D9 CV 50.18%±2.52% vs frontier 34.36% (+15.82pp) on 550 multi-provider D6 pools | **SAFE SUPPORTING** | `job_d9_retrain_with_mistral_20260526/` | State CV not held-out; 3 providers |
| D9 gate: 0 false overrides at thresholds 0.3–0.8 | **SAFE SUPPORTING** | `d9_mistral_gate_threshold_sweep.csv` | Training data evaluation |
| Cloudrift rescue bucket: D6 55%, 0 regressions (40 MATH-500 cases) | **SAFE SUPPORTING** | `cloudrift_d6_bucket_metrics.csv` | Bucket-selected pilot; not random |
| Lenient extraction 98.8% coverage on Cloudrift/Qwen | **SAFE SUPPORTING** | `cloudrift_qwen_extraction_repair_summary.json` | 1 unrecoverable |
| FTA statistically superior to pooled ensemble | **UNSAFE — DO NOT CLAIM** | — | CI includes zero at n=300 and n=720 — MUST DISCLOSE |
| Full pool generation costs only B=6 calls | **UNSAFE — DO NOT CLAIM** | — | Costs 4×B=6=24; FTA post-generation adds 0 |
| FTA achieves 86.67% on MATH-500 or any other benchmark | **UNSAFE — DO NOT CLAIM** | — | GSM8K only; Cohere MATH-500 FTA=frontier=29% |
| D8.1 selector results are independent held-out accuracy | **UNSAFE — DO NOT CLAIM** | — | Test-split only; not independently validated |
| D6 standalone net gain is positive | **UNSAFE — DO NOT CLAIM** | — | Net=-38 across 550 pools; gate required |

---

## 1. Historical Claim Map (pre-FTA era — preserved for provenance)

Conservative map from claim type to evidence status.

## Legend

- **Safe**: defensible from current canonical docs/artifacts.
- **Supportive**: useful but not headline-safe without caveat.
- **Speculative / open**: not yet submission-safe.

## Claims map

| Claim | Status | Primary evidence | Notes |
|---|---|---|---|
| Repository identity is fixed-budget adaptive compute allocation with branch allocation + commit control + anti-collapse under budget. | Safe | `README.md`, `CANONICAL_START_HERE.md` | Keep explicit “not old binary revise-routing” statement. |
| Broader operational strict-phased default is `strict_gate1_cap_k6`. | Safe | `FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`, `CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md` | Broader strict-phased surface only. |
| Manuscript-facing matched-surface internal winner is `strict_f3`. | Safe | `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`, `MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`, `PAPER_METHOD_DECISION_BUNDLE_20260422T175142Z.md` | Matched-surface internal comparison only. |
| Diversity + answer-group aggregation + anti-collapse contributes to final behavior under budget. | Safe (mechanistic) | `CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`, component ablation reports | Use as mechanism statement, not universal guarantee. |
| Failure modes are concentrated in early tree coverage / branch-family control. | Safe (within audited surfaces) | `CURRENT_BOTTLENECKS.md`, strict-phased and failure-stat docs | State audited-surface scope. |
| External baselines are comprehensively closed for all paper tables. | Not safe | `EXTERNAL_BASELINE_PAPER_READINESS_DECISION_PACKAGE.md` | Only a subset is main-table ready. |
| Adjacent imported baselines dominate our method on canonical surface. | Not safe | N/A | No canonical evidence to assert this. |
| Real-model confirmation is broad and final across many independent settings. | Supportive only | `OPENAI_REAL_MODEL_MAIN_RUN_AUDIT_20260424T160513Z.md`, `COHERE_REAL_MODEL_MAIN_RUN_AUDIT_20260424T163700Z.md`, `CROSS_PROVIDER_REAL_MODEL_MAIN_RUN_AUDIT_20260424T163701Z.md` | Cross-provider evidence is informative but not dominance-safe; keep bounded/appendix wording. |
| Canonical paper-facing ours-vs-external real-model package is fully completed cross-provider. | Speculative / open | `REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION_20260424T002900Z.md` | Current item is dry-run/package scaffolding; cross-provider API-backed completion remains open. |
| OpenAI smoke ours-vs-external run establishes main-paper-safe direction. | Not safe | `REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION_20260424T_OPENAI_REAL_SMOKE.md` | OpenAI-only subset-5 smoke with nonzero rows; observed direction in this run does not favor ours (best-ours < best-external), so it is not headline-safe and motivates larger rerun. |
| Combined OpenAI+Cohere real-model main-run evidence establishes frontier-allocation dominance over `external_l1_max`. | Not safe | `CROSS_PROVIDER_REAL_MODEL_MAIN_RUN_AUDIT_20260424T163701Z.md`, `REAL_MODEL_DECISION_PACKAGE_20260425T025417Z.md` | Cross-provider audit is already non-dominant; the decision package further strengthens the guardrail via unfavorable Cohere Stage-1 results. Safe wording stays bounded/competitive and appendix-only for real-model evidence. |
| Cohere Stage-1 real-model diagnostic supports real-model dominance over `external_l1_max`. | Not safe | `REAL_MODEL_DECISION_PACKAGE_20260425T025417Z.md`, `outputs/real_model_decision_package_20260425T025417Z/` | Decision package marks this as `diagnostic_unfavorable_incomplete` and `not_safe`: matched=30, strict_f3=0.5333, external_l1_max=0.8000, delta=-0.2667 (95% CI [-0.4667, -0.0667]); cost-normalized diagnostics also favor `external_l1_max`. |
| Controller is operationally specified enough for scientific evaluation at implementation level. | Supportive (with caveat) | `OPERATIONAL_CONTROLLER_SPECIFICATION_FOR_MANUSCRIPT_20260424T164500Z.md`, `outputs/operational_controller_specification_20260424T164500Z/` | Code-to-symbol mapping and hyperparameter tables are explicit; still no single closed-form controller equation, so manuscript should present abstraction + appendix operational spec together. |
| Unified claim-safety statistical audit supports dominance/SOTA framing. | Not safe | `UNIFIED_CLAIM_SAFETY_STATISTICAL_AUDIT_20260424T200000Z.md`, `outputs/unified_claim_safety_statistical_audit_20260424T200000Z/` | Audit answer set marks dominance framing unsafe; recommended framing is formulation + diagnostic + bounded artifact. |
| Held-out surface generalization evidence currently upgrades the paper to dominance/SOTA framing. | Not safe | `HELD_OUT_SURFACE_GENERALIZATION_CLAIM_SAFETY_20260424T231500Z_DRY.md`, `outputs/held_out_surface_generalization_claim_safety_20260424T231500Z_DRY/`, `outputs/paper_tables/held_out_claim_safety_table.csv` | Dry-run and claim-safety structure are in place; safe interpretation remains mixed/competitive/non-dominant until broader held-out runs complete. |
| DR-v2 outcome-verifier rerank (`direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`) beats `external_l1_max` or is canonical headline evidence. | Not safe until closed | `docs/METHOD_EVIDENCE_AND_FAILURE_SUMMARY_20260429.md`, completed `outputs/cohere_real_model_cost_normalized_validation_*` + report | Implementation is live-runnable; **100-case Cohere-backed verifier evidence is pending** completion/interpretation. Mock-only timestamps are **not** Cohere verifier backend proof. |

## Rules before writing a claim

1. Choose surface: broader operational vs manuscript matched.
2. Confirm evidence family is canonical in `PAPER_SOURCE_OF_TRUTH.md`.
3. If evidence is supportive-only, mark claim as bounded / appendix.
4. If evidence missing, mark as open gap in `PAPER_OPEN_GAPS_AND_RISKS.md`.
