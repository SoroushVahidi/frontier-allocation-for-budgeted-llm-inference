# Output Directory Index — 2026-05-28

Index of important output directories as of the 2026-05-28 project pause.
All paths are relative to the repository root.
**Do not commit these directories** — they are large artifacts tracked locally only.

For the full output list see `git status --short | grep "^?? outputs/"`.

---

## Tier 1 — Canonical Evidence (Do Not Delete)

| Directory | Role | Size note |
|---|---|---|
| `outputs/final_fix24_all_external_validation_20260519_20260520T000902Z/` | **FTA Final-300 canonical validation** — all-baseline seed=71 run | Large |
| `outputs/final_fix24_all_external_postrun_20260520_20260520T025349Z/` | FTA Final-300 post-run metrics and CI | Medium |
| `outputs/fta_independent_verification_20260527/run_20260527T003000Z/` | **FTA independent re-verification** — Final-300 and Agg-720 reproduced from raw records | Medium |
| `outputs/canonical_final300_cohere_contract_matched_live_20260523T181948Z/` | Final-300 Cohere contract-matched run | Large |
| `outputs/canonical_final300_cohere_contract_matched_validation_prep_20260523/` | Validation prep for final-300 | Small |

---

## Tier 2 — Supporting Multi-Provider Evidence (Keep)

| Directory | Role | Notes |
|---|---|---|
| `outputs/job_d9_retrain_with_mistral_20260526/run_20260526T234411Z/` | **D9 gated selector with Mistral** — CV=50.18%±2.52%, 550 pools, 0 false overrides | Key D9 artifact |
| `outputs/job_d9_retrain_with_cohere_math500_expansion_20260526/run_20260526T144632Z/` | D9 retrain with Cohere MATH-500 expansion | Supporting |
| `outputs/job_d9_expanded_pool_selector_after_d6_20260526/` | D9 pilot after initial D6 expansion | Supporting |
| `outputs/job_d9_validation_leakage_cv_audit_20260526/` | D9 leakage and CV audit | Audit record |
| `outputs/job_d6_cohere_math500_expansion_20260526/run_20260526T141221Z/` | D6 Cohere MATH-500 expansion — NEGATIVE (net=−30) | Keep for context |
| `outputs/job_d6_full_one_variant_generation_20260526/` | D6 full one-variant — 160/160 | D6 evidence |
| `outputs/job_d6_mistral_eval_20260526/run_20260526T232755Z/` | D6 Mistral evaluation | Mistral evidence |
| `outputs/job_d6_mistral_pilot_20260526/` | D6 Mistral pilot | Pilot |

---

## Tier 3 — Cloudrift/Qwen Work (Keep)

| Directory | Role | Notes |
|---|---|---|
| `outputs/job_cloudrift_qwen_extraction_repair_20260526/run_20260527T002012Z/` | **Cloudrift/Qwen extraction repair** — 98.8% lenient extraction, D6=55%, 0 regressions | Prompt fix needed before new generation |
| `outputs/cloudrift_gsm8k_final300_20260528_140037/` | Cloudrift GSM8K Final-300 run | Recent |
| `outputs/cloudrift_gsm8k_final300_20260528_135956/` | Cloudrift GSM8K Final-300 (aborted earlier attempt) | Diagnostic |

---

## Tier 4 — MATH-500 Evidence (Keep)

| Directory | Role | Notes |
|---|---|---|
| `outputs/math500_cohere_failure_pool_audit_20260528/` | **Cohere MATH-500 failure pool audit** — 498 unique examples, 135 selector-fixable | Committed `5b780df8` |
| `outputs/cohere_math500_official_scenario4_20260524/cohere_math500_full_20260524T144902Z/` | **Official Cohere MATH-500 Scenario 4** — 300 examples seed=71 budget=6, canonical | Primary MATH-500 artifact |
| `outputs/local_failure_workbench_20260525/generalization_replay_20260524T220438/` | **4-scenario official replay** — 1200 rows, all FTA metadata | Key analysis artifact |
| `outputs/cohere_math500_official_scenario4_processing_20260524/` | Scenario 4 processing — selector replay, failure taxonomy | Derived analysis |
| `outputs/cohere_math500_failure_learning_20260525/` | Cohere MATH-500 failure learning — 300 cases, feature table, selector comparisons | Analysis |
| `outputs/cohere_math500_agreement_only_analysis_20260524/` | Agreement-only analysis — 20 recovery, 9 regression cases | Analysis |
| `outputs/cohere_math500_auxiliary_mlj_reprocess_20260524/` | Seed=11 auxiliary, 488 examples — diagnostic_only | Diagnostic |
| `outputs/scenarios_5_6_math500_full_tracking_20260524/` | Mistral MATH-500 Scenario 5 — 300 examples | Cross-provider |

---

## Tier 5 — Diagnostic Artifacts (Keep, Lower Priority)

| Directory | Role | Notes |
|---|---|---|
| `outputs/fta_cg_transfer_failure_analysis_20260528/` | **FTA-CG overfit diagnosis** — OVERFIT_RULE, do not implement | Committed `727e5c97` |
| `outputs/repository_situation_and_scenario_ranking_20260527/run_20260527T010000Z/` | Scenario ranking report — FTA rank #1 in Cohere×GSM8K | Audit |
| `outputs/current_research_evidence_summary_20260527/run_20260527T003000Z/` | Evidence summary | Audit |
| `outputs/project_state_and_branch_audit_20260525/` | Earlier state audit | Superseded by this pass |
| `outputs/xgb53_router_v2_tmux_validation_20260524/` | XGB53 router V2 validation | Supporting |
| `outputs/router_v2_improvement_campaign_20260524/` | Router V2 improvement — 22→53 features, 84.15% CV | Historical D9 predecessor |
| `outputs/applied_intelligence_*_20260527/` (many dirs) | Manuscript support data collection | Manuscript pipeline |
| `outputs/all_external_baseline_policy_eval_20260519_*` | All-external baseline eval | Baseline audit |
| `outputs/math500_fta_transfer_diagnostic_20260523/` | MATH-500 FTA transfer diagnostic | Early diagnostic |

---

## Tier 6 — Test / Integration / Dry-Run Outputs (Low Priority)

Directories with `TEST_` in name (e.g., `outputs/cohere_direct_reserve_validation_TEST_CDR_NOKEY/`) are integration test outputs. Safe to leave; not needed for research claims.

---

## Tier 7 — Historical / Superseded (Archive-safe)

| Directory | Notes |
|---|---|
| `outputs/anti_collapse_calibration_sweep_20260424TTESTACALZ/` | April 2026 calibration sweep; superseded |
| `outputs/broad_diversity_aggregation_cohere_gemini_confirmation_20260418/` | April 2026 aggregation pilot |
| `outputs/canonical_real_model_validation_20260424T_*/` (12 Cohere MATH-500 dirs) | 20-example pilot runs; all have zero-byte per_example_rows.csv — no usable data |
| `outputs/anonymization_audit*/` | Pre-submission audit; historical |
| `outputs/neurips*/` | NeurIPS 2026 artifact outputs; historical |

---

## Storage Summary (approximate)

| Category | Approx size | Count dirs |
|---|---|---|
| Total outputs/ | ~51 GB | ~1330 |
| Tier 1 canonical evidence | ~5–8 GB | ~5 |
| Tier 2 D9/D6 multi-provider | ~10 GB | ~15 |
| Tier 3–4 MATH-500 + Cloudrift | ~5 GB | ~20 |
| Tier 5–7 diagnostic + historical | ~28 GB | ~1290 |

None of these are committed to git. All are local-only.
