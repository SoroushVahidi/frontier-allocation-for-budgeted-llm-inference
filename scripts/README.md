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
| `run_new_paper_stop_vs_act_controller.py` | Stop-vs-act lightweight pipeline (dataset + train/eval) |

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
| `verify_hf_dataset_access.py` | Verify HF access and summarize status |
| `dataset_smoke_sample.py` | Lightweight dataset smoke samples |
| `generate_dataset_integration_report.py` | Main evaluation-dataset integration report |
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
