# Repo status summary

**Checkpoint:** `outputs/repo_polish_checkpoint_20260508T232940Z/`  
**Generated (UTC):** 20260508T232940Z

## Git

| Field | Value |
|------|--------|
| Branch | `research-next-frontier-iteration-2` |
| HEAD | `5549682` |
| Latest commit | `5549682 Add gated live execution support for Stage-3 replay checkpoint` |
| Porcelain lines (approx) | 415 |
| Modified/tracked dirty entries | 19 |
| Untracked entries | 396 |

## Commands captured

### git status --short

```
M README.md
 M START_HERE_CURRENT.md
 M docs/CURRENT_ARTIFACTS_INDEX_20260507.md
 M docs/CURRENT_METHOD_STATUS_20260507.md
 M docs/CURRENT_RESEARCH_HANDOFF_20260507.md
 M docs/FAILED_DIRECTIONS_20260507.md
 M docs/NEW_CHAT_STARTER_PROMPT_20260507.md
 M experiments/adaptive_retry_router.py
 M experiments/controllers.py
 M experiments/data.py
 M experiments/final_target_verifier.py
 M experiments/frontier_matrix_core.py
 M experiments/output_layer_repair.py
 M experiments/strategy_seeded_semantic_diversity_frontier_v1.py
 M experiments/targeted_discovery_retry.py
 M scripts/replay_track_b_commitment_gate.py
 M scripts/run_cohere_real_model_cost_normalized_validation.py
 M tests/test_targeted_discovery_retry_v1.py
 M tests/test_track_b_overlay_commitment_gate.py
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260506T025806Z.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260506T040238Z.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260506T130225Z.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260506T151731Z.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260506T173309Z.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260506T175516Z.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260506T185133Z.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260506T194114Z.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260507T152735Z.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260507T161935Z.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_live_run_20260507T204409Z.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_main_table_baselines_live_sanity.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_production_equiv_v1_runtime_tiny_live_smoke_20260508T195428Z.md
?? docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_production_equiv_v1_runtime_tiny_live_smoke_debug.md
?? docs/GSM8K_PAL_STRUCTURAL_VALIDATOR_PLAN_20260507.md
?? docs/TARGET_STAGED_PAL_RETRY_EXPERIMENT_PLAN_20260507.md
?? docs/references/
?? experiments/call_accounting.py
?? experiments/gsm8k_structural_validate.py
?? experiments/schema_grounded_retry.py
?? experiments/target_staged_pal_pilot_dry_run.py
?? experiments/target_staged_pal_pilot_manifest.py
?? experiments/target_staged_pal_pilot_runner.py
?? experiments/target_staged_pal_prompt.py
?? local_patches/
?? manifests/
?? outputs/_tmp_atlas_test/
?? outputs/_tmp_method_validate/
?? outputs/adaptive_router_v3_cohere_pilot_20260508T025727Z/
?? outputs/adaptive_router_v3_dry_run_20260508T025218Z/
?? outputs/adaptive_router_v3_dry_run_20260508T025305Z/
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/call_plan.json
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/case_overlap_report.json
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/cohere_real_model_cost_normalized_validation_20260507T161935Z/
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/collection_state.json
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/counterfactual_policy_summary.csv
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/failure_case_matrix.md
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/failure_cluster_summary.csv
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/failure_collection_report.md
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/failure_collection_summary.json
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/failure_pattern_mining_report.md
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/manifest.json
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/pal_loss_external_win_cases.csv
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/pal_wrong_all_external_wrong_cases.csv
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/present_not_selected_replay_report.md
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/present_not_selected_replay_table.csv
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/selected_failure_cases.csv
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/top_manual_inspection_cases.md
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/track_b_gate_offline_replay_guardrails.csv
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/track_b_gate_offline_replay_report.md
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/track_b_gate_offline_replay_summary.json
?? outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/track_b_gate_offline_replay_targets.csv
?? outputs/cohere_paired_pal_retry_vs_external_l1_100case_20260506T185133Z/
?? outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/
?? outputs/cohere_paired_pal_retry_vs_external_l1_300case_BASELINE_REMAT_20260506/
?? outputs/cohere_paired_pal_retry_vs_external_l1_300case_poolfix_20260506/
?? outputs/cohere_paired_pal_vs_external_l1_100case_20260506T025806Z/
?? outputs/cohere_pal_empty_code_retry_followup_15case_20260506T175516Z/
?? outputs/cohere_pal_empty_code_retry_smoke_5case_20260506T173309Z/
?? outputs/cohere_pal_retry_vs_3_external_baselines_30case_20260507T152735Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T012723Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T012724Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T012727Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T015601Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T015602Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T015615Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T015616Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T020859Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T020900Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T020906Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T023256Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T023712Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T024115Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T024551Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T025806Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T035833Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T040238Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T040323Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T125113Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T130225Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T130231Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T151731Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T171720Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T171725Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T171740Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T171744Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T171822Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T171827Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T171833Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T173333Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T175533Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T183110Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T183124Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T183128Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T184242Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T184759Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T185216Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260506T194131Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T011331Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T011554Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T013619Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T020943Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T021054Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T021254Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T021300Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T021358Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T022926Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T023004Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T023047Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T023431Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T033938Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T033955Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T034436Z/
?? outputs/cohere_real_model_cost_normalized_validation_20260507T152800Z/
?? outputs/cohere_real_model_cost_normalized_validation_PAL_IMPL_AUDIT_VALIDATE/
?? outputs/cohere_real_model_cost_normalized_validation_PREFLIGHT_PAL_REGISTRY_CHECK/
?? outputs/cohere_real_model_cost_normalized_validation_faithful_external_baselines_validate/
?? outputs/cohere_real_model_cost_normalized_validation_faithful_external_baselines_validate_test/
?? outputs/cohere_real_model_cost_normalized_validation_main_table_baselines_live_sanity/
?? outputs/cohere_real_model_cost_normalized_validation_main_table_external_baselines_validate/
?? outputs/cohere_real_model_cost_normalized_validation_main_table_external_baselines_validate_test/
?? outputs/cohere_real_model_cost_normalized_validation_production_equiv_v1_runtime_tiny_live_smoke_20260508T195428Z/
?? outputs/cohere_real_model_cost_normalized_validation_production_equiv_v1_runtime_tiny_live_smoke_debug/
?? outputs/cohere_real_model_cost_normalized_validation_production_equiv_v1_runtime_wired_validate/
?? outputs/cohere_real_model_cost_normalized_validation_production_equiv_v1_validate/
?? outputs/cohere_track_b_ab_pilot_30case_20260507T204409Z/
?? outputs/core4_50case_parsing_rescore_audit_20260508T181119Z/
?? outputs/core4_baseline_5case_diagnosis_20260508T165835Z/
?? outputs/current_merged_research_status_20260505/
?? outputs/discovery3_candidate_diversity_selection_v1_design_20260508T190533Z/
?? outputs/discovery3_candidate_diversity_selection_v1_design_20260508T190601Z/
?? outputs/discovery3_candidate_diversity_selection_v1_dry_run_20260508T190533Z/
?? outputs/discovery3_candidate_diversity_selection_v1_dry_run_20260508T190601Z/
?? outputs/discovery3_candidate_diversity_selection_v1_live_pilot_20260508T191036Z/
?? outputs/discovery3_candidate_diversity_selection_v1_live_pilot_20260508T191122Z/
?? outputs/discovery3_candidate_diversity_selection_v1_parsefix_5case_live_20260508T193024Z/
?? outputs/discovery3_candidate_diversity_selection_v1_parsefix_dry_run_20260508T191659Z/
?? outputs/discovery3_parsefix_parser_fallback_audit_20260508T193503Z/
?? outputs/discovery3_v1_parse_failure_debug_20260508T191659Z/
?? outputs/expanded_failure_bank_collection_20260508T185435Z/
?? outputs/external_baseline_faithful_impl_plan_20260508T160533Z/
?? outputs/external_baseline_faithfulness_audit_20260508T160139Z/
?? outputs/external_full_suite_matched50_comparison_20260508T222631Z/
?? outputs/external_l1_advantage_analysis_20260508T030420Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T022701Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T023315Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T032242Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T032933Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T033026Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T140353Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T140722Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T141156Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T141203Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T141252Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T141324Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T142122Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T150140Z/
?? outputs/external_l1_capfail_test_integrated_checkpoint_dry_run_20260508T152401Z/
?? outputs/external_l1_checkpoint_readiness_20260508T021402Z/
?? outputs/external_l1_only_fix_cohere_pilot_20260508T031227Z/
?? outputs/external_l1_only_fix_dry_run_20260508T031022Z/
?? outputs/external_l1_only_fix_failure_patch_plan_20260508T031556Z/
?? outputs/external_l1_only_fix_micro_pilot_20260508T031744Z/
?? outputs/external_l1_only_routing_v2_failure_analysis_20260508T024806Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T022701Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T023315Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T032242Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T032933Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T033026Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T140353Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T140722Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T141156Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T141204Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T141252Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T141324Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T142122Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T150140Z/
?? outputs/external_l1_reusepath_test_integrated_checkpoint_dry_run_20260508T152401Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T022701Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T023315Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T032242Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T032933Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T033026Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T140353Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T140722Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T141156Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T141204Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T141252Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T141324Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T142122Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T150140Z/
?? outputs/external_l1_schema_test_integrated_checkpoint_dry_run_20260508T152401Z/
?? outputs/external_l1_stage1_integrated_checkpoint_20260508T021848Z/
?? outputs/external_l1_stage1_integrated_checkpoint_20260508T021923Z/
?? outputs/external_l1_stage2_checkpoint_readiness_20260508T022726Z/
?? outputs/external_l1_stage2_integrated_checkpoint_20260508T023303Z/
?? outputs/external_l1_stage2_integrated_checkpoint_dry_run_20260508T022730Z/
?? outputs/external_l1_stage2_integrated_validated_fixes_checkpoint_20260508T032208Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T022701Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T023315Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T032242Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T032933Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T033026Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T140352Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T140722Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T141156Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T141203Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T141252Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T141324Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T142122Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T150140Z/
?? outputs/external_l1_stage2_test_integrated_checkpoint_dry_run_20260508T152401Z/
?? outputs/external_only_loss_collection_completion_check_20260506/
?? outputs/external_only_loss_collection_pal_vs_l1_20260506T040238Z/
?? outputs/external_only_loss_collection_pal_vs_l1_completed_20260506T125123Z/
?? outputs/external_only_loss_collection_pal_vs_l1_round2_20260506T130225Z/
?? outputs/external_only_loss_collection_pal_vs_l1_round3_20260506T151731Z/
?? outputs/external_only_loss_pattern_audit_15_20260506/
?? outputs/external_only_loss_pattern_audit_20_20260506/
?? outputs/external_only_loss_pattern_audit_31_20260506/
?? outputs/external_pal_pot_fair_50case_live_20260508T222348Z/
?? outputs/external_sc6_fair_50case_live_20260508T221625Z/
?? outputs/failure_case_corpus_20260507/integrated_30case_4way_followup.md
?? outputs/failure_case_corpus_20260507/selected_discovery_hypothesis_checklist.md
?? outputs/failure_case_corpus_20260507/trce_offline_validation_ledger.csv
?? outputs/failure_case_corpus_20260507/trce_offline_validation_report.md
?? outputs/failure_case_corpus_external_losses_88case_mixed_legacy_20260507T041547Z/
?? outputs/failure_case_corpus_inputs_external_losses_88case_20260507T041700Z/
?? outputs/failure_case_corpus_inputs_k1_frontier_tiebreak_10case_20260507T040900Z/
?? outputs/failure_case_corpus_k1_frontier_tiebreak_10case_20260507T041532Z/
?? outputs/fair_core4_loss_micro_pilot_live_20260508T182630Z/
?? outputs/fair_core4_loss_micro_pilot_live_20260508T182731Z/
?? outputs/fair_core4_loss_micro_pilot_plan_20260508T182408Z/
?? outputs/fair_core4_loss_pattern_bank_20260508T182155Z/
?? outputs/fair_core4_paired_comparison_report_20260508T181853Z/
?? outputs/fair_core4_vs_our_method_alignment_plan_20260508T181550Z/
?? outputs/final_paired_pal_external_preflight_20260505/
?? outputs/gold_absent_discovery_diagnosis_20260508T005544Z/
?? outputs/gold_absent_external_success_schema_mining_20260507/
?? outputs/gsm8k_structural_validator_eval_20260507/
?? outputs/integrated_live_pilot_v1_20260508T020827Z/
?? outputs/integrated_live_pilot_v1_20260508T020844Z/
?? outputs/integrated_live_pilot_v1_20260508T020859Z/
?? outputs/integrated_structural_commit_targeted_retry_v1_replay_20260508T020150Z/
?? outputs/integrated_structural_commit_targeted_retry_v1_replay_20260508T020401Z/
?? outputs/latest_pal_external_loss_bank_20260508T004000Z/
?? outputs/main_table_baseline_call_accounting_calibration_20260508T164916Z/
?? outputs/main_table_baselines_live_sanity_local_cases_20260508T164033Z/
?? outputs/main_table_baselines_live_sanity_local_cases_test/
?? outputs/main_table_baselines_live_sanity_local_cases_zzzz_live/
?? o\n... (truncated)
```

### git diff --stat

```
README.md                                          |   2 +-
 START_HERE_CURRENT.md                              |  15 +-
 docs/CURRENT_ARTIFACTS_INDEX_20260507.md           |  32 ++
 docs/CURRENT_METHOD_STATUS_20260507.md             |  13 +-
 docs/CURRENT_RESEARCH_HANDOFF_20260507.md          | 201 +++++-------
 docs/FAILED_DIRECTIONS_20260507.md                 |   9 +
 docs/NEW_CHAT_STARTER_PROMPT_20260507.md           |  15 +-
 experiments/adaptive_retry_router.py               |  35 +++
 experiments/controllers.py                         | 341 ++++++++++++++++++++-
 experiments/data.py                                | 138 +++++++++
 experiments/final_target_verifier.py               |  64 ++++
 experiments/frontier_matrix_core.py                | 132 ++++++++
 experiments/output_layer_repair.py                 | 150 +++++++++
 ...rategy_seeded_semantic_diversity_frontier_v1.py |  12 +
 experiments/targeted_discovery_retry.py            | 314 +++++++++++++++++++
 scripts/replay_track_b_commitment_gate.py          |  37 ++-
 ...cohere_real_model_cost_normalized_validation.py |  28 ++
 tests/test_targeted_discovery_retry_v1.py          |  58 ++++
 tests/test_track_b_overlay_commitment_gate.py      |   1 +
 19 files changed, 1456 insertions(+), 141 deletions(-)
```

### git diff --name-only

```
README.md
START_HERE_CURRENT.md
docs/CURRENT_ARTIFACTS_INDEX_20260507.md
docs/CURRENT_METHOD_STATUS_20260507.md
docs/CURRENT_RESEARCH_HANDOFF_20260507.md
docs/FAILED_DIRECTIONS_20260507.md
docs/NEW_CHAT_STARTER_PROMPT_20260507.md
experiments/adaptive_retry_router.py
experiments/controllers.py
experiments/data.py
experiments/final_target_verifier.py
experiments/frontier_matrix_core.py
experiments/output_layer_repair.py
experiments/strategy_seeded_semantic_diversity_frontier_v1.py
experiments/targeted_discovery_retry.py
scripts/replay_track_b_commitment_gate.py
scripts/run_cohere_real_model_cost_normalized_validation.py
tests/test_targeted_discovery_retry_v1.py
tests/test_track_b_overlay_commitment_gate.py
```

## outputs/ (newest first, maxdepth 1, sample)

- `outputs/repo_polish_checkpoint_20260508T232940Z/`
- `outputs/production_equiv_v1_runtime_wired_stage3_50_dry_run_test/`
- `outputs/pal_vs_production_equiv_casebook_live_20260508T223635Z/`
- `outputs/pal_vs_production_equiv_casebook_plan_20260508T223632Z/`
- `outputs/pal_pot_advantage_loss_pattern_audit_20260508T223121Z/`
- `outputs/pal_pot_advantage_loss_pattern_audit_20260508T223101Z/`
- `outputs/pal_pot_advantage_loss_pattern_audit_20260508T223046Z/`
- `outputs/main_table_baselines_live_sanity_local_cases_test/`
- `outputs/external_full_suite_matched50_comparison_20260508T222631Z/`
- `outputs/external_pal_pot_fair_50case_live_20260508T222348Z/`
- `outputs/external_sc6_fair_50case_live_20260508T221625Z/`
- `outputs/sc6_pal_external_baselines_10case_calibration_20260508T220734Z/`
- `outputs/sc6_pal_external_baselines_10case_calibration_20260508T220037Z/`
- `outputs/sc6_pal_external_baseline_call_plan_20260508T220034Z/`
- `outputs/method_maturity_stop_improvement_audit_20260508T212754Z/`
- `outputs/schema_grounded_retry_v1_parsefix_5case_live_20260508T210832Z/`
- `outputs/schema_grounded_retry_v1_parsefix_dry_run_20260508T210541Z/`
- `outputs/schema_grounded_retry_v1_format_failure_audit_20260508T210541Z/`
- `outputs/schema_grounded_retry_v1_5case_format_sanity_live_20260508T210210Z/`
- `outputs/schema_grounded_retry_v1_failure_family_bank_20260508T210018Z/`
- `outputs/schema_grounded_retry_v1_dry_run_20260508T205718Z/`
- `outputs/schema_grounded_retry_v1_design_20260508T205718Z/`
- `outputs/production_equiv_v1_retry_prompt_parsefix_5case_live_20260508T205314Z/`
- `outputs/production_equiv_v1_retry_prompt_parsefix_dry_run_20260508T205050Z/`
- `outputs/production_equiv_v1_retry_prompt_parse_audit_20260508T205050Z/`
- `outputs/production_equiv_v1_retry_policy_micro_pilot_live_20260508T204653Z/`
- `outputs/production_equiv_v1_retry_policy_micro_pilot_plan_20260508T204614Z/`
- `outputs/production_equiv_v1_retry_commit_loss_audit_20260508T204005Z/`
- `outputs/production_equiv_v1_stage3_50_live_checkpoint_rerun_20260508T203036Z/`
- `outputs/production_equiv_v1_10case_live_calibration_20260508T202627Z/`
- `outputs/production_equiv_v1_call_accounting_patch_20260508T202616Z/`
- `outputs/production_equiv_v1_50_live_failure_diagnosis_20260508T202315Z/`
- `outputs/production_equiv_v1_stage3_50_live_checkpoint_20260508T200357Z/`
- `outputs/production_equiv_v1_stage3_50_live_checkpoint_20260508T200214Z/`
- `outputs/production_equiv_v1_runtime_tiny_live_smoke_20260508T195621Z/`

## Pytest (requested subset)

See validation block in session log: `tests/test_main_table_external_baselines.py`, `tests/test_faithful_external_baselines.py`, `tests/test_production_equivalence_stage3.py`, `tests/test_schema_grounded_retry_v1.py`.

**Result at checkpoint time:** 25 passed (recorded in writer run).

## Policies

- No staging/commit performed.
- No API calls as part of this checkpoint.
- No deletions of timestamped outputs.
