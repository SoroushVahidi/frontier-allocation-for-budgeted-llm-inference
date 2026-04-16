# Scripts index

All scripts write run artifacts under `outputs/` unless overridden.

## Interpretation labels

- **Canonical**: current frontier-allocation path for the NeurIPS-oriented project.
- **Exploratory**: useful active branches and diagnostics, not settled default winners.
- **Integration/prep**: dataset/baseline readiness tooling.
- **Historical**: older-track support scripts retained for provenance.

## Canonical scripts (current project path)

| Script | Role |
|---|---|
| `run_cross_strategy_frontier_allocation.py` | Main frontier-allocation scaffold (legacy filename) |
| `run_multi_action_allocation_pass.sh` | Multi-action allocation run wrapper |
| `evaluate_branch_scorer_controller.py` | Controller-level comparison for learned/heuristic policies |
| `evaluate_branch_scorer_robustness.py` | Multi-seed/budget/init robustness sweep |
| `run_new_paper_frontier_matrix.py` | Frontier matrix / anti-collapse summary tables |
| `run_comparative_frontier_audit.py` | Matched-budget comparative audit |
| `run_light_external_style_baseline_comparison.py` | Lightweight internal-vs-external-style local comparison |
| `run_light_anchor_vs_s1_comparison.py` | Lightweight matched anchor vs external s1 baseline adapter |
| `run_new_paper_stop_vs_act_controller.py` | Stop-vs-act lightweight pipeline (dataset + train/eval) |
| `run_new_paper_stop_vs_act_target_stabilization_pass.py` | Bounded default-target stabilization/variance-reduction comparison |
| `run_new_paper_stop_vs_act_matched_comparator_pass.py` | Bounded matched ACT-vs-STOP comparator pass |
| `run_new_paper_stop_vs_act_policy_coupled_stop_pass.py` | Bounded policy-coupled STOP-baseline pass |

## Exploratory branch-scorer workflows

| Script | Role |
|---|---|
| `run_new_paper_bt_pairwise_branch_scorer.py` | End-to-end pairwise BT pipeline |
| `run_new_paper_bt_reliability_weighted_branch_scorer.py` | Reliability-aware BT variants |
| `run_new_paper_external_warmstart_branch_scorer.py` | External warm-start variants |
| `run_new_paper_tie_aware_bt.py` | Tie-aware BT variant |
| `run_new_paper_tie_aware_bt_stability.py` | Tie-aware stability/calibration checks |
| `run_new_paper_tie_aware_hybrid_gating.py` | Hybrid gating variant |
| `run_new_paper_ambiguous_branch_dataset.py` | Ambiguous-pair dataset construction |
| `run_new_paper_ambiguous_pair_targeted_experiment.py` | Targeted ambiguous-pair experiment |
| `run_new_paper_pairwise_diagnostic_audit.py` | Pairwise confidence/label diagnostics |
| `run_new_paper_raokupper_resolution_audit.py` | Rao-Kupper contradiction-resolution audit |
| `run_new_paper_raokupper_confirmation.py` | Bounded independent confirmation for Rao-Kupper audit |

## Integration/preparation scripts

| Script | Role |
|---|---|
| `verify_hf_dataset_access.py` | Verify evaluation-dataset access (HF + git-clone-backed dataset keys) and summarize status |
| `dataset_smoke_sample.py` | Lightweight dataset smoke samples (HF datasets + local-clone datasets such as NaturalPlan) |
| `generate_dataset_integration_report.py` | Main evaluation-dataset integration report (includes MATH-500, AMO-Bench, and NaturalPlan clone-path status) |
| `verify_external_reasoning_datasets.py` | External supervision access/schema checks |
| `generate_external_reasoning_dataset_integration_report.py` | External supervision integration report |
| `prepare_external_reasoning_datasets.py` | Readiness ranking and normalized previews |
| `generate_external_baseline_integration_report.py` | External baseline integration report |
| `list_external_baselines.py` | Print external baseline registry |

## Historical/provenance scripts

| Script | Role |
|---|---|
| `run_heavy_real_routing_eval.sh` | Older binary revise-routing track support |
| `run_final_manuscript_eval.sh` | Older manuscript evaluation wrapper |

## Notes

- `run_cross_strategy_frontier_allocation.py` keeps a legacy filename for compatibility; docs refer to this as cross-controller frontier allocation.
- Current canonical method direction is documented in `docs/STOP_VS_ACT_DIRECTION.md` (stop-vs-act), but implementation scripts are still evolving.

## Oracle-label pilot execution

| Script | Role |
|---|---|
| `run_oracle_label_pilot_hpc.sh` | HPC-oriented wrapper: preflight, optional manifest build, generator hook, validator gate, run summary |
| `run_oracle_label_generator_interface_stub.py` | Interface-stabilization stub CLI for heavy generator contract; supports testing-only `--mock-mode` outputs |
| `run_oracle_label_generator_prototype.py` | First real paired-rollout oracle-label prototype generator (limited subset, CPU-oriented) |
| `run_oracle_label_generator_heavy.py` | Production-leaning heavy-path generator with resume/progress/state-error handling for shard-scale runs |
| `oracle_label_pilot_sharding.py` | Deterministic shard split/merge utility for pilot-state manifests and per-shard oracle-label outputs |
| `build_stop_vs_act_oracle_distillation_dataset.py` | Selective-distillation preprocessing: bucket oracle rows into accepted/borderline/rejected, apply manifest-aware mock checks, and emit weighted distillation-ready JSONL |
| `build_random_matched_coverage_oracle_distillation_dataset.py` | Build deterministic random matched-coverage distillation baselines per regime (accepted-only or accepted+borderline), including repeated-draw mode and overlap summaries |
| `train_oracle_distilled_stop_vs_act_student.py` | Oracle-distilled student train/eval path with retained-coverage accounting, ACT-rate reporting, and required slice summaries (uncertainty/margin/disagreement/budget) |
| `compare_oracle_distilled_stop_vs_act_runs.py` | Matched-control comparison scaffold with required roles (anchor, accepted-only, accepted+borderline, matched random), repeated-random variance summaries, and readiness gates |
| `run_oracle_distilled_regime_bundle.py` | Regime-level orchestration runner that bundles repeated random draws, selective/anchor/random student runs, and one comparison-ready package |

## s1 baseline integration scripts (fair split)

| Script | Role |
|---|---|
| `run_s1_budget_forcing_baseline.py` | Canonical s1 fair-baseline runner with MODE A (inference-only) and MODE B (strict official/full import + verification). MODE B emits `official_mode_import.csv`, `official_mode_import_report.md`, `fairness_report.md`, and `manifest.json` under `outputs/s1_baseline/<run_id>/`. |
| `run_s1_baseline_comparison_bundle.py` | Merge one or more s1 run directories into manuscript-ready aggregate comparison artifacts. |
| `verify_s1_mode_b_import.py` | Strict validator for s1 MODE B official/full import packages (required files, metadata schema, fairness checks, and table-readiness checks). |
| `generate_s1_mode_b_import_report.py` | Generates reviewer-facing markdown report from MODE B verification JSON. |

## TALE baseline integration scripts (fair split)

| Script | Role |
|---|---|
| `run_tale_baseline.py` | Canonical TALE fair-baseline runner with MODE A (prompt budgeting inference-only) and MODE B (strict official/full import + verification with TALE-vs-TALE-PT variant separation). MODE B emits `official_mode_import.csv`, `official_mode_import_report.md`, `fairness_report.md`, and `manifest.json` under `outputs/tale_baseline/<run_id>/`. |
| `run_tale_comparison_bundle.py` | Merge one or more TALE run directories into manuscript-ready aggregate comparison artifacts. |
| `verify_tale_mode_b_import.py` | Strict validator for TALE MODE B official/full import packages (schema, provenance, fairness checks, and TALE-vs-TALE-PT variant separation checks). |
| `generate_tale_mode_b_import_report.py` | Generates reviewer-facing markdown report from TALE MODE B verification JSON. |

## L1 baseline integration scripts (fair split)

| Script | Role |
|---|---|
| `run_l1_baseline.py` | Canonical L1 fair-baseline runner with MODE A (inference-only L1-style Exact/Max length control adapter) and MODE B (official/full adapter reporting). Writes manifest, summary CSV, per-example JSONL, fairness report, and comparison tables under `outputs/l1_baseline/`. |
| `run_l1_comparison_bundle.py` | Merge one or more L1 run directories into manuscript-ready aggregate comparison artifacts. |


## External baseline completeness / runnability scripts

| Script | Role |
|---|---|
| `verify_external_baseline_runnability.py` | Smoke-verifies that s1/TALE/L1 MODE A runners execute and that MODE B adapters correctly report blocked/import status boundaries, and runs BEST-Route / when_solve_when_verify / cascade_routing / MoB / ReST-MCTS / OpenR adjacent import fixture checks. Writes artifacts under `outputs/external_baseline_runnability/<run_id>/`. |
| `generate_external_baseline_completeness_report.py` | Generates repository-facing external-baseline completeness report and machine-readable summary artifacts (`docs/external_baseline_completeness_report.md`, `outputs/external_baseline_completeness_summary.{json,csv}`). |
| `verify_best_route_import.py` | Strict validator for BEST-Route adjacent import packages (`metadata.json` + `results.csv`) with workflow-stage, bo-arm schema, and adjacent-only comparability checks. |
| `generate_best_route_status_report.py` | Generates conservative BEST-Route status artifacts under `outputs/external_baseline_completeness/` and documents safe vs unsafe claims. |
| `verify_when_solve_when_verify_import.py` | Strict validator for When-To-Solve-When-To-Verify adjacent import packages (SC-vs-GenRM strategy coverage, fixed-budget fields, and adjacent-only comparability checks). |
| `generate_when_solve_when_verify_status_report.py` | Generates conservative when_solve_when_verify status artifacts under `outputs/external_baseline_completeness/`. |
| `verify_cascade_routing_import.py` | Strict validator for Cascade Routing adjacent import packages (upstream workflow-stage declarations, routing/cascading/cascade-routing strategy coverage, and adjacent-only comparability checks). |
| `generate_cascade_routing_status_report.py` | Generates conservative cascade_routing status artifacts under `outputs/external_baseline_completeness/`. |
| `verify_mob_import.py` | Strict validator for MoB adjacent import packages (workflow-stage declarations, benchmark/model/num-samples identity checks, BoN+MoB algorithm coverage, and adjacent-only comparability checks). |
| `generate_mob_status_report.py` | Generates conservative mob_majority_of_bests status artifacts under `outputs/external_baseline_completeness/`. |
| `verify_rest_mcts_import.py` | Strict validator for ReST-MCTS adjacent import packages (workflow-stage declarations, dataset/model/search-setting checks, MCTS-search coverage, and adjacent-only comparability checks). |
| `generate_rest_mcts_status_report.py` | Generates conservative rest_mcts status artifacts under `outputs/external_baseline_completeness/`. |
| `verify_openr_import.py` | Strict validator for OpenR adjacent import packages (workflow-stage declarations, method-coverage checks, metric sanity checks, and adjacent-only comparability checks). |
| `generate_openr_status_report.py` | Generates conservative openr status artifacts under `outputs/external_baseline_completeness/`. |
| `verify_compute_optimal_tts_provenance.py` | Audits paper↔repo provenance signals for compute_optimal_tts (target OpenReview paper vs linked repo identity) and emits machine-readable provenance checks. |
| `generate_compute_optimal_tts_blocker_report.py` | Generates conservative blocker/status artifacts for compute_optimal_tts under `outputs/external_baseline_completeness/`. |
