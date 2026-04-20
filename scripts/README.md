# Scripts index

All scripts write run artifacts under `outputs/` unless overridden.

This file is the runnable-code front door for the repository.

## Read this first

- Current repository interpretation: [`../docs/CANONICAL_START_HERE.md`](../docs/CANONICAL_START_HERE.md)
- Current code entry path: [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- Repository map: [`../docs/REPO_MAP.md`](../docs/REPO_MAP.md)
- Repo audit/cleanup rationale: [`../docs/REPOSITORY_AUDIT_AND_CLEANUP_2026_04_20.md`](../docs/REPOSITORY_AUDIT_AND_CLEANUP_2026_04_20.md)
- Historical script entry points: [`HISTORICAL_INDEX.md`](HISTORICAL_INDEX.md)

## Interpretation labels

- **Canonical**: current frontier-allocation path for the NeurIPS-oriented project.
- **Exploratory**: active side branches and narrower diagnostics, not settled default winners.
- **Integration/prep**: dataset and baseline readiness tooling.
- **Historical**: older-track support scripts retained only for provenance.

## Most common workflows

### 1. Run the current paper/controller path
- `run_cross_strategy_frontier_allocation.py`
- `run_multi_action_allocation_pass.sh`
- `evaluate_branch_scorer_controller.py`
- `evaluate_branch_scorer_robustness.py`
- `run_new_paper_frontier_matrix.py`
- `run_comparative_frontier_audit.py`
- `run_imported_methodology_frontier_eval.py`

### 2. Run current diagnosis/failure analysis
- `run_worst_real_failure_casebook_with_reasoning.py`
- `build_twenty_defeat_casebook_20260419.py`
- `build_twenty_defeat_case_trees_20260419.py`
- `run_branch_observability_smoke.py`
- `run_oracle_mismatch_study.py`

### 3. Check dataset and baseline readiness
- `verify_hf_dataset_access.py`
- `generate_dataset_integration_report.py`
- `generate_external_baseline_integration_report.py`
- `list_external_baselines.py`

## Canonical scripts (current project path)

| Script | Role |
|---|---|
| `run_cross_strategy_frontier_allocation.py` | Main frontier-allocation scaffold (legacy filename) |
| `run_multi_action_allocation_pass.sh` | Multi-action allocation run wrapper |
| `evaluate_branch_scorer_controller.py` | Controller-level comparison for learned/heuristic policies |
| `evaluate_branch_scorer_robustness.py` | Multi-seed/budget/init robustness sweep |
| `run_new_paper_frontier_matrix.py` | Frontier matrix / anti-collapse summary tables |
| `run_comparative_frontier_audit.py` | Matched-budget comparative audit |
| `run_imported_methodology_frontier_eval.py` | Bounded old-manuscript-style evaluation layer for the current branch-allocation setting |
| `run_light_external_style_baseline_comparison.py` | Lightweight internal-vs-external-style local comparison |
| `run_light_anchor_vs_s1_comparison.py` | Lightweight matched anchor vs external s1 baseline adapter |
| `run_new_paper_stop_vs_act_controller.py` | Stop-vs-act lightweight pipeline |
| `run_new_paper_stop_vs_act_target_stabilization_pass.py` | Bounded default-target stabilization pass |
| `run_new_paper_stop_vs_act_matched_comparator_pass.py` | Bounded ACT-vs-STOP comparator pass |
| `run_new_paper_stop_vs_act_policy_coupled_stop_pass.py` | Bounded policy-coupled STOP-baseline pass |

## Exploratory hard-case and branch-learning workflows

| Script | Role |
|---|---|
| `build_bruteforce_target_regimes.py` | Build target regimes for branch-allocation supervision |
| `train_bruteforce_branch_allocator.py` | Main unified learner training entrypoint from brute-force supervision |
| `evaluate_bruteforce_branch_allocator.py` | Evaluate trained allocators with hard-slice diagnostics |
| `run_target_fidelity_regime_experiment.py` | Matched learner comparisons across supervision regimes |
| `run_hard_case_feature_representation_experiment.py` | Fixed-supervision old-vs-richer feature-set experiment |
| `run_ambiguity_calibration_and_fallback_experiment.py` | Ambiguity-handling experiments with calibration/fallback control |
| `run_near_tie_policy_experiment.py` | Dedicated near-tie routing experiments |
| `run_near_tie_pointwise_expert_experiment.py` | Near-tie pointwise-expert experiments |
| `run_pairwise_svm_margin_experiment.py` | Matched logistic-vs-SVM margin comparisons |
| `run_structured_ambiguity_experiment.py` | Representation/defer-target/oracle-proxy ambiguity experiments |
| `run_defer_fallback_experiment.py` | Defer-only vs defer-plus-fallback comparisons |
| `run_branch_value_uncertainty_derived_defer_experiment.py` | Value-target + uncertainty-head derived-defer pass |
| `run_branch_value_uncertainty_strict_validation_pass.py` | Strict validation harness for the value+uncertainty method |
| `run_cohere_rerank_branch_allocation_experiment.py` | Bounded Cohere Rerank branch-scoring comparison |

## Integration/preparation scripts

| Script | Role |
|---|---|
| `verify_hf_dataset_access.py` | Verify evaluation-dataset access and summarize status |
| `dataset_smoke_sample.py` | Lightweight dataset smoke samples |
| `generate_dataset_integration_report.py` | Main evaluation-dataset integration report |
| `verify_external_reasoning_datasets.py` | External supervision access/schema checks |
| `generate_external_reasoning_dataset_integration_report.py` | External supervision integration report |
| `build_canonical_branch_learning_corpus.py` | Build canonical processed branch-learning corpora |
| `run_canonical_branch_learning_pass.py` | Run a matched canonical learning pass from canonical corpora |
| `run_protected_strata_holdout_expansion.py` | Bounded split-seed holdout expansion targeting sparse protected strata |
| `build_external_prm_mathshepherd_apps_corpus.py` | Build conservative canonical-aligned external rows |
| `prepare_external_reasoning_datasets.py` | Readiness ranking and normalized previews |
| `generate_external_baseline_integration_report.py` | External baseline integration report |
| `list_external_baselines.py` | Print external baseline registry |

## Historical/provenance scripts

Historical entry points are documented in:
- [`HISTORICAL_INDEX.md`](HISTORICAL_INDEX.md)
- `../archive/historical_scripts/`

## Notes

- `run_cross_strategy_frontier_allocation.py` keeps a legacy filename for compatibility; docs refer to the current framing as cross-controller frontier allocation.
- Stop-vs-act is a bounded helper formulation inside the current project, not the whole project identity.
- Use the paired docs in `../docs/` when interpreting any narrower experimental line; many exploratory scripts are not intended to stand alone as headline results.
