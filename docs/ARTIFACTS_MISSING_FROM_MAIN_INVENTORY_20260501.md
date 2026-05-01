# Artifacts missing from `origin/main` (inventory)

- **Generated:** 2026-05-01T00:48:56Z (UTC)
- **Repo root:** `/mmfs1/home/sv96/adaptive-reasoning-budget-allocation`
- **`origin/main`:** `3ef20864b89dc0be5aa3a74394e708721330f070`
- **`HEAD`:** `0f5294931a8c19938618aa69092af4214b7c398d` (`chore/local-outputs-snapshot-20260501`)

## Scope

Local paths under `outputs/` whose path matches external-baseline loss / casebook / trace-complete external / Wulver loss / selector-on-gold-present / best-methods-on-external-losses keywords (heuristic list in generator).

## Summary

| Metric | Count |
|--------|------:|
| Relevant local files under `outputs/` | 894 |
| Of those, **not** in `origin/main` | 551 |
| … tracked on **`HEAD`** (branch-only vs `main`) | 486 |
| … **disk-only** (not in `HEAD`; typically `.gitignore`) | 65 |

## High-priority directories (not on `main`, by file count)

| `outputs/` subtree | Files not on `main` |
|---------------------|----------------------:|
| `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/` | 96 |
| `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/` | 48 |
| `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/` | 48 |
| `outputs/trace_complete_external_losses_smoke_20260430T204400Z/` | 31 |
| `outputs/trace_complete_external_losses_smoke_20260430T204800Z/` | 31 |
| `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/` | 27 |
| `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/` | 22 |
| `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/` | 15 |
| `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/` | 15 |
| `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/` | 15 |
| `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/` | 15 |
| `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/` | 15 |
| `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/` | 15 |
| `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/` | 15 |
| `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/` | 12 |
| `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/` | 12 |
| `outputs/cohere_trace_complete_loss_subset_20260427T180000Z/` | 11 |
| `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/` | 11 |
| `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/` | 10 |
| `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/` | 9 |
| `outputs/trace_complete_external_losses_debug_20260430T204300Z/` | 9 |
| `outputs/cohere_direct_reserve_validation_TEST_CDR_NOKEY/` | 5 |
| `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_DRY/` | 5 |
| `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_EXCL/` | 5 |
| `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T175000Z/` | 5 |
| `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T180000Z/` | 5 |
| `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T183000_DEBUG4/` | 5 |
| `outputs/cohere_trace_complete_loss_subset_20260427T175000Z/` | 5 |
| `outputs/cohere_trace_complete_loss_subset_DEBUG_SELECTION/` | 4 |
| `outputs/(root-level files)` | 3 |
| `outputs/cohere_trace_complete_loss_subset_20260427T183000Z/` | 3 |
| `outputs/direct_reserve_frontier_gate_trace_smoke_TEST_TRACE_SCHEMA_OFFLINE/` | 3 |
| `outputs/external_baseline_runnability/` | 3 |
| `outputs/large_selector_tournament_20260430T182316Z/` | 3 |
| `outputs/cohere_trace_complete_loss_subset_20260427T172834Z/` | 2 |
| `outputs/cohere_trace_complete_loss_subset_20260427T174225Z/` | 2 |
| `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG10/` | 2 |
| `outputs/selector_on_gold_present_losses_20260430T211700Z/` | 2 |
| `outputs/cohere_real_model_cost_normalized_validation_20260428T195414Z/` | 1 |
| `outputs/external_loss_casebook_20260430T184023Z/` | 1 |
| `outputs/external_loss_casebook_broad_20260430T185500Z/` | 1 |
| `outputs/large_selector_tournament_20260430T181201Z/` | 1 |
| `outputs/real_model_cost_validation_20260428T195414Z/` | 1 |
| `outputs/trace_complete_external_losses_20260430T194200Z/` | 1 |
| `outputs/trace_complete_external_losses_retry_20260430T204900Z_dryrun/` | 1 |

## `strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG`

- **Path:** `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/`
- **Purpose:** Wulver bundle for cases where internal `strict_f3` is wrong and `external_l1_max` is correct (CSVs + jsonl + summary on disk).

| File | On `origin/main` | On `HEAD` | On disk | Ignore rule (if not in `HEAD`) |
|------|:-----------------:|:--------:|:-------:|--------------------------------|
| `README.md` | no | yes | yes | — |
| `loss_cases_for_manual_inspection.md` | no | yes | yes | — |
| `loss_cases_strict_f3_wrong_external_correct.csv` | no | yes | yes | — |
| `loss_cases_strict_f3_wrong_external_correct.jsonl` | no | no | yes | .gitignore:57:outputs/**/*.jsonl | outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/loss_cases_strict_f3_wrong_external_correct.jsonl |
| `matched_examples.csv` | no | yes | yes | — |
| `matched_examples.jsonl` | no | no | yes | .gitignore:57:outputs/**/*.jsonl | outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/matched_examples.jsonl |
| `rich_feature_table.csv` | no | yes | yes | — |
| `rich_feature_table.jsonl` | no | no | yes | .gitignore:57:outputs/**/*.jsonl | outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/rich_feature_table.jsonl |
| `summary.json` | no | yes | yes | — |

## Disk-only paths (not in `HEAD`)

These exist on MMFS but are excluded from the current branch index (see ignore rule).

- `outputs/best_methods_on_external_losses_20260430T195200Z_dry_run_plan.log`
  - *ignore:* `.gitignore:34:outputs/* | outputs/best_methods_on_external_losses_20260430T195200Z_dry_run_plan.log`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/loss_cases_absent_from_tree.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/loss_cases_absent_from_tree.jsonl`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/loss_cases_absent_from_tree.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/loss_cases_absent_from_tree.jsonl`
- `outputs/cohere_direct_reserve_validation_TEST_CDR_NOKEY/difference_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_direct_reserve_validation_TEST_CDR_NOKEY/difference_cases.jsonl`
- `outputs/cohere_direct_reserve_validation_TEST_CDR_NOKEY/loss_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_direct_reserve_validation_TEST_CDR_NOKEY/loss_cases.jsonl`
- `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_DRY/difference_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_DRY/difference_cases.jsonl`
- `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_DRY/loss_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_DRY/loss_cases.jsonl`
- `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_EXCL/difference_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_EXCL/difference_cases.jsonl`
- `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_EXCL/loss_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_EXCL/loss_cases.jsonl`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T175000Z/difference_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T175000Z/difference_cases.jsonl`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T175000Z/loss_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T175000Z/loss_cases.jsonl`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T180000Z/difference_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T180000Z/difference_cases.jsonl`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T180000Z/loss_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T180000Z/loss_cases.jsonl`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T183000_DEBUG4/difference_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T183000_DEBUG4/difference_cases.jsonl`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T183000_DEBUG4/loss_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T183000_DEBUG4/loss_cases.jsonl`
- `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/per_example_records.jsonl`
  - *ignore:* `.gitignore:62:outputs/**/per_example_records.jsonl | outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/per_example_records.jsonl`
- `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/progress_heartbeat.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/progress_heartbeat.jsonl`
- `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/raw/failures.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/raw/failures.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T172834Z/selected_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T172834Z/selected_cases.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T174225Z/selected_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T174225Z/selected_cases.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T175000Z/branch_traces.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T175000Z/branch_traces.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T175000Z/per_example_trace_records.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T175000Z/per_example_trace_records.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T175000Z/selected_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T175000Z/selected_cases.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T175000Z/step_traces.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T175000Z/step_traces.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T180000Z/branch_traces.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T180000Z/branch_traces.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T180000Z/per_example_trace_records.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T180000Z/per_example_trace_records.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T180000Z/selected_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T180000Z/selected_cases.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T180000Z/step_traces.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T180000Z/step_traces.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000Z/selected_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T183000Z/selected_cases.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG10/selected_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG10/selected_cases.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/branch_traces.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/branch_traces.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/per_example_trace_records.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/per_example_trace_records.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/selected_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/selected_cases.jsonl`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/step_traces.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/step_traces.jsonl`
- `outputs/cohere_trace_complete_loss_subset_DEBUG_SELECTION/selected_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/cohere_trace_complete_loss_subset_DEBUG_SELECTION/selected_cases.jsonl`
- `outputs/external_loss_casebook_20260430T184023Z/cohere_annotation_cache.jsonl`
  - *ignore:* `.gitignore:230:outputs/external_loss_casebook_20260430T184023Z/cohere_annotation_cache.jsonl | outputs/external_loss_casebook_20260430T184023Z/cohere_annotation_cache.jsonl`
- `outputs/external_loss_casebook_broad_20260430T185500Z/cohere_annotation_cache.jsonl`
  - *ignore:* `.gitignore:229:outputs/external_loss_casebook_broad_20260430T185500Z/cohere_annotation_cache.jsonl | outputs/external_loss_casebook_broad_20260430T185500Z/cohere_annotation_cache.jsonl`
- `outputs/large_selector_tournament_20260430T181201Z/artifact_scan/reconstructed_artifacts/cohere_direct_reserve_failure_replay_seed_latest_per_example_records.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/large_selector_tournament_20260430T181201Z/artifact_scan/reconstructed_artifacts/cohere_direct_reserve_failure_replay_seed_latest_per_example_records.jsonl`
- `outputs/large_selector_tournament_20260430T182316Z/artifact_scan/reconstructed_artifacts/cohere_direct_reserve_failure_replay_seed_latest_per_example_records.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/large_selector_tournament_20260430T182316Z/artifact_scan/reconstructed_artifacts/cohere_direct_reserve_failure_replay_seed_latest_per_example_records.jsonl`
- `outputs/large_selector_tournament_20260430T182316Z/selector_tournament/override_casebook.csv`
  - *ignore:* `.gitignore:58:outputs/**/*casebook*.csv | outputs/large_selector_tournament_20260430T182316Z/selector_tournament/override_casebook.csv`
- `outputs/large_selector_tournament_20260430T182316Z/selector_tournament_cohere/override_casebook.csv`
  - *ignore:* `.gitignore:58:outputs/**/*casebook*.csv | outputs/large_selector_tournament_20260430T182316Z/selector_tournament_cohere/override_casebook.csv`
- `outputs/selector_on_gold_present_losses_20260430T211700Z/cohere_outcome_verifier_cache.jsonl`
  - *ignore:* `.gitignore:60:outputs/**/*cache*.jsonl | outputs/selector_on_gold_present_losses_20260430T211700Z/cohere_outcome_verifier_cache.jsonl`
- `outputs/selector_on_gold_present_losses_20260430T211700Z/cohere_pairwise_verifier_cache.jsonl`
  - *ignore:* `.gitignore:60:outputs/**/*cache*.jsonl | outputs/selector_on_gold_present_losses_20260430T211700Z/cohere_pairwise_verifier_cache.jsonl`
- `outputs/selector_on_gold_present_losses_20260430T211700Z_dry_run.log`
  - *ignore:* `.gitignore:34:outputs/* | outputs/selector_on_gold_present_losses_20260430T211700Z_dry_run.log`
- `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/loss_cases_strict_f3_wrong_external_correct.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/loss_cases_strict_f3_wrong_external_correct.jsonl`
- `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/matched_examples.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/matched_examples.jsonl`
- `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/rich_feature_table.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/rich_feature_table.jsonl`
- `outputs/trace_complete_external_losses_20260430T194200Z/trace_complete_loss_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/trace_complete_external_losses_20260430T194200Z/trace_complete_loss_cases.jsonl`
- `outputs/trace_complete_external_losses_debug_20260430T204300Z/trace_complete_loss_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/trace_complete_external_losses_debug_20260430T204300Z/trace_complete_loss_cases.jsonl`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_dryrun/trace_complete_loss_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/trace_complete_external_losses_retry_20260430T204900Z_dryrun/trace_complete_loss_cases.jsonl`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/per_example_records.jsonl`
  - *ignore:* `.gitignore:62:outputs/**/per_example_records.jsonl | outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/per_example_records.jsonl`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/progress_heartbeat.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/progress_heartbeat.jsonl`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/generation_runner_stderr.log`
  - *ignore:* `.gitignore:27:*.log | outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/generation_runner_stderr.log`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/generation_runner_stdout.log`
  - *ignore:* `.gitignore:27:*.log | outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/generation_runner_stdout.log`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/trace_complete_loss_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/trace_complete_loss_cases.jsonl`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/per_example_records.jsonl`
  - *ignore:* `.gitignore:62:outputs/**/per_example_records.jsonl | outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/per_example_records.jsonl`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/progress_heartbeat.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/progress_heartbeat.jsonl`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/generation_runner_stderr.log`
  - *ignore:* `.gitignore:27:*.log | outputs/trace_complete_external_losses_smoke_20260430T204400Z/generation_runner_stderr.log`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/generation_runner_stdout.log`
  - *ignore:* `.gitignore:27:*.log | outputs/trace_complete_external_losses_smoke_20260430T204400Z/generation_runner_stdout.log`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/trace_complete_loss_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/trace_complete_external_losses_smoke_20260430T204400Z/trace_complete_loss_cases.jsonl`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/per_example_records.jsonl`
  - *ignore:* `.gitignore:62:outputs/**/per_example_records.jsonl | outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/per_example_records.jsonl`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/progress_heartbeat.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/progress_heartbeat.jsonl`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/generation_runner_stderr.log`
  - *ignore:* `.gitignore:27:*.log | outputs/trace_complete_external_losses_smoke_20260430T204800Z/generation_runner_stderr.log`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/generation_runner_stdout.log`
  - *ignore:* `.gitignore:27:*.log | outputs/trace_complete_external_losses_smoke_20260430T204800Z/generation_runner_stdout.log`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/trace_complete_loss_cases.jsonl`
  - *ignore:* `.gitignore:57:outputs/**/*.jsonl | outputs/trace_complete_external_losses_smoke_20260430T204800Z/trace_complete_loss_cases.jsonl`

## Branch-only paths (in `HEAD`, not in `origin/main`)

Merge **`chore/local-outputs-snapshot-20260501` → `main`** (PR) to publish without regenerating artifacts.

<details>
<summary>Full list (486 paths)</summary>

- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/aggregate_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/anti_collapse_diagnostics.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/commands_assumptions_caveats.md`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/datasets_compared.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/failure_decomposition.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/manifest.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/methods_compared.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/per_budget_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/per_dataset_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/per_example_rows.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/providers_and_models.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/repair_impact_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/retry_error_log.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/seed_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_4_openai_gsm8k/summary.md`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/aggregate_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/anti_collapse_diagnostics.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/commands_assumptions_caveats.md`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/datasets_compared.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/failure_decomposition.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/manifest.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/methods_compared.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/per_budget_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/per_dataset_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/per_example_rows.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/providers_and_models.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/repair_impact_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/retry_error_log.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/seed_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_6_openai_gsm8k/summary.md`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/aggregate_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/anti_collapse_diagnostics.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/commands_assumptions_caveats.md`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/datasets_compared.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/failure_decomposition.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/manifest.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/methods_compared.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/per_budget_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/per_dataset_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/per_example_rows.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/providers_and_models.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/repair_impact_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/retry_error_log.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/seed_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_11_8_openai_gsm8k/summary.md`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/aggregate_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/anti_collapse_diagnostics.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/commands_assumptions_caveats.md`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/datasets_compared.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/failure_decomposition.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/manifest.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/methods_compared.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/per_budget_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/per_dataset_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/per_example_rows.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/providers_and_models.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/repair_impact_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/retry_error_log.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/seed_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_4_openai_gsm8k/summary.md`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/aggregate_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/anti_collapse_diagnostics.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/commands_assumptions_caveats.md`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/datasets_compared.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/failure_decomposition.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/manifest.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/methods_compared.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/per_budget_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/per_dataset_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/per_example_rows.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/providers_and_models.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/repair_impact_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/retry_error_log.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/seed_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_6_openai_gsm8k/summary.md`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/aggregate_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/anti_collapse_diagnostics.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/commands_assumptions_caveats.md`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/datasets_compared.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/failure_decomposition.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/manifest.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/methods_compared.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/per_budget_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/per_dataset_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/per_example_rows.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/providers_and_models.json`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/repair_impact_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/retry_error_log.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/seed_summary.csv`
- `outputs/canonical_real_model_validation_20260425T_WULVER_COHERE_LONG_cohere_23_8_openai_gsm8k/summary.md`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/by_budget_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/by_dataset_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/by_problem_type_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/by_seed_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/candidate_fix_recommendations.md`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/cost_latency_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/loss_cases_absent_from_tree.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/manifest.json`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/missing_data_request.md`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/path_proximity_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/trace_availability_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/by_budget_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/by_dataset_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/by_problem_type_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/by_seed_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/candidate_fix_recommendations.md`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/cost_latency_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/loss_cases_absent_from_tree.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/manifest.json`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/missing_data_request.md`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/path_proximity_summary.csv`
- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/trace_availability_summary.csv`
- `outputs/cohere_direct_reserve_validation_TEST_CDR_NOKEY/difference_cases_for_manual_inspection.md`
- `outputs/cohere_direct_reserve_validation_TEST_CDR_NOKEY/loss_cases.csv`
- `outputs/cohere_direct_reserve_validation_TEST_CDR_NOKEY/loss_cases_for_manual_inspection.md`
- `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_DRY/difference_cases_for_manual_inspection.md`
- `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_DRY/loss_cases.csv`
- `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_DRY/loss_cases_for_manual_inspection.md`
- `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_EXCL/difference_cases_for_manual_inspection.md`
- `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_EXCL/loss_cases.csv`
- `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_EXCL/loss_cases_for_manual_inspection.md`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T175000Z/difference_cases_for_manual_inspection.md`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T175000Z/loss_cases.csv`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T175000Z/loss_cases_for_manual_inspection.md`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T180000Z/difference_cases_for_manual_inspection.md`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T180000Z/loss_cases.csv`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T180000Z/loss_cases_for_manual_inspection.md`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T183000_DEBUG4/difference_cases_for_manual_inspection.md`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T183000_DEBUG4/loss_cases.csv`
- `outputs/cohere_direct_reserve_validation_TRACE_SUBSET_20260427T183000_DEBUG4/loss_cases_for_manual_inspection.md`
- `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/claim_safety_table.csv`
- `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/cost_normalized_summary.csv`
- `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/incomplete_slices.csv`
- `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/manifest.json`
- `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/method_summary.csv`
- `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/pairwise_comparisons.csv`
- `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/slice_summary.csv`
- `outputs/cohere_real_model_cost_normalized_validation_20260428T195414Z/paired_vs_external_l1_max.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T172834Z/selected_cases.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T174225Z/selected_cases.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T175000Z/selected_cases.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T180000Z/branch_abandonment_audit.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T180000Z/candidate_controller_fixes.md`
- `outputs/cohere_trace_complete_loss_subset_20260427T180000Z/commit_timing_audit.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T180000Z/manifest.json`
- `outputs/cohere_trace_complete_loss_subset_20260427T180000Z/path_proximity_metrics.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T180000Z/selected_cases.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T180000Z/token_cost_latency_summary.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000Z/cohere_api_key_issue.md`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000Z/selected_cases.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG10/selected_cases.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/branch_abandonment_audit.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/candidate_controller_fixes.md`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/commit_timing_audit.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/manifest.json`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/path_proximity_metrics.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/selected_cases.csv`
- `outputs/cohere_trace_complete_loss_subset_20260427T183000_DEBUG4/token_cost_latency_summary.csv`
- `outputs/cohere_trace_complete_loss_subset_DEBUG_SELECTION/candidate_controller_fixes.md`
- `outputs/cohere_trace_complete_loss_subset_DEBUG_SELECTION/manifest.json`
- `outputs/cohere_trace_complete_loss_subset_DEBUG_SELECTION/selected_cases.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/README.md`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/absent_from_tree_cases.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/absent_from_tree_problem_type_summary.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/all_paired_cases.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/answer_difference_summary.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/both_correct_cases.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/both_wrong_cases.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/casebook_for_manual_review.md`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/mapping_verification_summary.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/missing_fields_report.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/present_not_selected_cases.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/present_not_selected_problem_type_summary.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/problem_type_summary.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/strict_f3_correct_external_wrong.csv`
- `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/strict_f3_wrong_external_correct.csv`
- `outputs/direct_reserve_frontier_gate_trace_smoke_TEST_TRACE_SCHEMA_OFFLINE/traces/trace_smoke_1_external_l1_max.json`
- `outputs/direct_reserve_frontier_gate_trace_smoke_TEST_TRACE_SCHEMA_OFFLINE/traces/trace_smoke_2_external_l1_max.json`
- `outputs/direct_reserve_frontier_gate_trace_smoke_TEST_TRACE_SCHEMA_OFFLINE/traces/trace_smoke_3_external_l1_max.json`
- `outputs/external_baseline_integration_report.md`
- `outputs/external_baseline_runnability/20260421T190758Z/verification_note.md`
- `outputs/external_baseline_runnability/20260421T190758Z/verification_summary.csv`
- `outputs/external_baseline_runnability/20260421T190758Z/verification_summary.json`
- `outputs/real_model_cost_validation_20260428T195414Z/paired_vs_external_l1_max.csv`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_12_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_12_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_12_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_158_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_158_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_158_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_17_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_17_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_17_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_1_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_1_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_1_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_3_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_3_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_3_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_576_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_576_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_576_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_5_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_5_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_5_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_6_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_6_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_6_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_7_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_7_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/full_traces/openai_gsm8k_7_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_0_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_0_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_0_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_11_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_11_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_11_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_12_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_12_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_12_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_14_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_14_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_14_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_158_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_158_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_158_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_17_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_17_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_17_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_18_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_18_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_18_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_1_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_1_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_1_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_2_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_2_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_2_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_3_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_3_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_3_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_4_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_4_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_4_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_576_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_576_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_576_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_5_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_5_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_5_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_6_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_6_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_6_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_7_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_7_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_7_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_8_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_8_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/full_traces/openai_gsm8k_8_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_0_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_0_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_0_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_0_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_0_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_0_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_11_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_11_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_11_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_11_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_11_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_11_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_12_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_12_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_12_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_12_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_12_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_12_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_14_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_14_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_14_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_14_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_14_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_14_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_158_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_158_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_158_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_158_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_158_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_158_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_17_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_17_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_17_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_17_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_17_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_17_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_18_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_18_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_18_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_18_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_18_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_18_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_1_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_1_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_1_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_1_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_1_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_1_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_2_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_2_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_2_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_2_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_2_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_2_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_3_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_3_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_3_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_3_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_3_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_3_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_4_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_4_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_4_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_4_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_4_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_4_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_576_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_576_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_576_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_576_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_576_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_576_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_5_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_5_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_5_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_5_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_5_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_5_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_6_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_6_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_6_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_6_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_6_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_6_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_7_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_7_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_7_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_7_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_7_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_7_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_8_b4_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_8_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_8_b6_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_8_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_8_b8_external_l1_exact.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z/full_traces/openai_gsm8k_8_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_0_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_0_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_0_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_11_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_11_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_11_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_12_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_12_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_12_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_14_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_14_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_14_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_158_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_158_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_158_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_17_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_17_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_17_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_18_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_18_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_18_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_1_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_1_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_1_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_2_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_2_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_2_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_3_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_3_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_3_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_4_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_4_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_4_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_576_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_576_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_576_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_5_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_5_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_5_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_6_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_6_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_6_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_7_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_7_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_7_b8_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_8_b4_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_8_b6_external_l1_max.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/openai_gsm8k_8_b8_external_l1_max.json`
- `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/README.md`
- `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/loss_cases_for_manual_inspection.md`
- `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/loss_cases_strict_f3_wrong_external_correct.csv`
- `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/matched_examples.csv`
- `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/rich_feature_table.csv`
- `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/summary.json`
- `outputs/trace_complete_external_losses_debug_20260430T204300Z/artifact_scan.csv`
- `outputs/trace_complete_external_losses_debug_20260430T204300Z/artifact_scan_report.md`
- `outputs/trace_complete_external_losses_debug_20260430T204300Z/generation_plan.json`
- `outputs/trace_complete_external_losses_debug_20260430T204300Z/generation_plan.md`
- `outputs/trace_complete_external_losses_debug_20260430T204300Z/trace_collection_report.md`
- `outputs/trace_complete_external_losses_debug_20260430T204300Z/trace_complete_loss_cases.csv`
- `outputs/trace_complete_external_losses_debug_20260430T204300Z/trace_complete_loss_summary.json`
- `outputs/trace_complete_external_losses_debug_20260430T204300Z/trace_complete_loss_summary.md`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/answer_group_table.csv`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/candidate_branch_table.csv`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/claim_safety_table.csv`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/cost_normalized_summary.csv`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/incomplete_slices.csv`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/manifest.json`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/method_summary.csv`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/pairwise_comparisons.csv`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/per_case_trace_index.csv`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/slice_summary.csv`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/trace_audit_per_case.csv`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/traces/openai_gsm8k_0_direct_reserve_semantic_frontier_v2.json`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/traces/openai_gsm8k_0_external_l1_max.json`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/traces/openai_gsm8k_1_direct_reserve_semantic_frontier_v2.json`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/traces/openai_gsm8k_1_external_l1_max.json`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/traces/openai_gsm8k_2_direct_reserve_semantic_frontier_v2.json`
- `outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/cohere_real_model_cost_normalized_validation_smoke/traces/openai_gsm8k_2_external_l1_max.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/artifact_scan.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/artifact_scan_report.md`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/answer_group_table.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/candidate_branch_table.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/claim_safety_table.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/cost_normalized_summary.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/incomplete_slices.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/manifest.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/method_summary.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/pairwise_comparisons.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/per_case_trace_index.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/slice_summary.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/trace_audit_per_case.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/traces/openai_gsm8k_0_direct_reserve_semantic_frontier_v2.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/traces/openai_gsm8k_0_external_l1_max.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/traces/openai_gsm8k_1_direct_reserve_semantic_frontier_v2.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/traces/openai_gsm8k_1_external_l1_max.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/traces/openai_gsm8k_2_direct_reserve_semantic_frontier_v2.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/cohere_real_model_cost_normalized_validation_20260430T204400Z/traces/openai_gsm8k_2_external_l1_max.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/generation_plan.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/generation_plan.md`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/generation_runner_command.txt`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/trace_collection_report.md`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/trace_complete_loss_cases.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/trace_complete_loss_summary.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204400Z/trace_complete_loss_summary.md`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/artifact_scan.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/artifact_scan_report.md`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/answer_group_table.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/candidate_branch_table.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/claim_safety_table.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/cost_normalized_summary.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/incomplete_slices.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/manifest.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/method_summary.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/pairwise_comparisons.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/per_case_trace_index.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/slice_summary.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/trace_audit_per_case.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/traces/openai_gsm8k_0_direct_reserve_semantic_frontier_v2.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/traces/openai_gsm8k_0_external_l1_max.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/traces/openai_gsm8k_1_direct_reserve_semantic_frontier_v2.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/traces/openai_gsm8k_1_external_l1_max.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/traces/openai_gsm8k_2_direct_reserve_semantic_frontier_v2.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/cohere_real_model_cost_normalized_validation_20260430T204800Z/traces/openai_gsm8k_2_external_l1_max.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/generation_plan.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/generation_plan.md`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/generation_runner_command.txt`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/trace_collection_report.md`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/trace_complete_loss_cases.csv`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/trace_complete_loss_summary.json`
- `outputs/trace_complete_external_losses_smoke_20260430T204800Z/trace_complete_loss_summary.md`

</details>
