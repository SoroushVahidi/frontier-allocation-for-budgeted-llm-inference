# Scripts index

All scripts write run artifacts under `outputs/` unless overridden.

## Quick interpretation labels

- **Canonical (old manuscript)**: supports binary revise-routing manuscript line.
- **Canonical (new paper)**: supports cross-controller frontier allocation line.
- **Exploratory**: useful experiments/diagnostics, not default method.
- **Integration/prep**: dataset/baseline readiness tooling.
- **Utility**: smoke tests and helpers.

## Canonical: old manuscript track

| Script | Role |
|---|---|
| `run_heavy_real_routing_eval.sh` | Main heavy evaluation entry for binary revise-routing track |

## Canonical: new-paper track

| Script | Role |
|---|---|
| `run_cross_strategy_frontier_allocation.py` | Frontier-allocation scaffold (legacy filename) |
| `run_multi_action_allocation_pass.sh` | Multi-action allocation run wrapper |
| `evaluate_branch_scorer_controller.py` | Controller-level comparison for branch scorers |
| `evaluate_branch_scorer_robustness.py` | Multi-seed/budget/init robustness sweep |
| `run_new_paper_frontier_matrix.py` | Multi-dataset frontier matrix / anti-collapse tables |
| `run_comparative_frontier_audit.py` | Matched-budget audit versus baselines |

## Branch-scorer workflows (new-paper)

| Script | Status | Role |
|---|---|---|
| `build_v3_ranking_dataset.py` | exploratory/historical context | Build scalar ranking dataset |
| `train_branch_scorer_v3.py` | exploratory/historical context | Train scalar scorer |
| `build_bt_pairwise_branch_dataset.py` | canonical (current branch-scorer data path) | Build pairwise branch-comparison dataset |
| `train_bt_pairwise_branch_scorer.py` | canonical (current branch-scorer train path) | Train pairwise BT scorer |
| `run_new_paper_bt_pairwise_branch_scorer.py` | canonical (current branch-scorer default) | End-to-end BT pairwise run |
| `run_new_paper_bt_reliability_weighted_branch_scorer.py` | exploratory | Reliability-aware BT variants |
| `run_new_paper_external_warmstart_branch_scorer.py` | exploratory | External warm-start comparison |
| `run_new_paper_pairwise_diagnostic_audit.py` | exploratory diagnostic | Pairwise label/confidence diagnostics |
| `run_new_paper_prm_branch_scoring.py` | exploratory | PRM-style branch scoring audit |

## Dataset and baseline integration/preparation

| Script | Role |
|---|---|
| `verify_hf_dataset_access.py` | Verify HF dataset access and write status summary |
| `dataset_smoke_sample.py` | Lightweight per-dataset smoke samples |
| `generate_dataset_integration_report.py` | Main evaluation-dataset integration report |
| `verify_external_reasoning_datasets.py` | Access/schema checks for external supervision datasets |
| `generate_external_reasoning_dataset_integration_report.py` | Run-scoped external supervision integration report |
| `prepare_external_reasoning_datasets.py` | Readiness ranking and normalized previews |
| `generate_external_baseline_integration_report.py` | External baseline-code integration report |
| `list_external_baselines.py` | Print external baseline registry |

## Utility and pilot helpers

| Script | Role |
|---|---|
| `run_real_model_fixed_budget_pilot.py` | Small real-model fixed-budget pilot |
| `run_pilot_gsm8k.py` | Pilot run from `configs/pilot_gsm8k.yaml` |
| `evaluate_pilot_gsm8k.py` | Summarize pilot run directory |
| `smoke_frontier_methods.py` | Simulator-only smoke for frontier methods |
| `smoke_test.py` | Minimal repository smoke test |
| `run_branch_scorer_ml_sweep.sh` | Shell sweep helper |

## Notes

- `run_cross_strategy_frontier_allocation.py` keeps its legacy filename for compatibility; docs refer to this as cross-controller frontier allocation.
- Exploratory scripts are important for learning, but should not be described as final-method evidence without robustness support.
