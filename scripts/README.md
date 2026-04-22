# Scripts index

All scripts write run artifacts under `outputs/` unless overridden.

This file is the runnable-code front door for the repository.

## Read this first

- Current repository interpretation: [`../docs/CANONICAL_START_HERE.md`](../docs/CANONICAL_START_HERE.md)
- Canonical internal method decision package: [`../docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`](../docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md)
- One-minute disambiguation note: [`../docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`](../docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md)
- Current strict-phased status: [`../docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`](../docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md)
- Current experiment-family index: [`../docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`](../docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md)
- Current code entry path: [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- Setup and local checks: [`../docs/CANONICAL_INSTALL_AND_DEV.md`](../docs/CANONICAL_INSTALL_AND_DEV.md)
- Repository map: [`../docs/REPO_MAP.md`](../docs/REPO_MAP.md)
- Contributor placement and maintenance guide: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- Artifact-status policy: [`../docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md`](../docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md)
- Historical script entry points: [`HISTORICAL_INDEX.md`](HISTORICAL_INDEX.md)

## Interpretation labels

- **Canonical**: current strict-phased default-decision path for the NeurIPS-oriented project.
- **Exploratory**: active side branches and narrower diagnostics, not settled default winners.
- **Integration/prep**: dataset and baseline readiness tooling.
- **Historical**: older-track support scripts retained only for provenance.

## Most common workflows

### 0. Canonical first run (broad default decision)
- `run_broader_strict_phased_default_decision_eval.py`
- Read `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
- Inspect `outputs/final_strict_phased_default_decision_eval_20260421T042913Z/`

### 1. Run the current strict-phased default-decision path
- `run_hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421.py`
- `run_hundred_three_gate_design_eval_strict_phased.py`
- `build_new_hundred_newest_vs_best_failure_statistics.py`
- `build_canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics.py`

### 2. Run current learned or capped alternatives
- `run_learned_f2_to_f3_gate_v1_eval.py`
- `run_hard_max_family_expansions_eval.py`

### 3. Run broad comparison or baseline support
- `run_full_method_comparison_bundle.py`
- `build_twenty_exact_current_full_vs_best_fresh.py`
- `run_integrated_controller_component_ablation.py`
- `run_manuscript_surface_component_ablation.py`
- `package_strict_f3_component_ablation_paper_surface.py`
- `run_paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3.py`
- `run_s1_budget_forcing_baseline.py`
- `run_tale_baseline.py`
- `run_l1_baseline.py`

### 4. Check dataset and baseline readiness
- `verify_hf_dataset_access.py`
- `generate_dataset_integration_report.py`
- `generate_external_baseline_integration_report.py`
- `build_external_adjacent_baseline_bundle.py`
- `list_external_baselines.py`

### 5. Run maintenance checks
- `make smoke`
- `make health`
- `make lint`
- `make test`
- `make check`

## Canonical scripts (current project path)

| Script | Role |
|---|---|
| `run_hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421.py` | Strict forced F2 vs strict forced F3 comparison under phased law |
| `run_hundred_three_gate_design_eval_strict_phased.py` | Strict phased Gate 1 / Gate 2 / Gate 3 comparison |
| `build_new_hundred_newest_vs_best_failure_statistics.py` | Build the newest-vs-best exact-loss 100-case statistics surface |
| `build_canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics.py` | Build the finalized-default (`strict_gate1_cap_k6`) canonical exact-loss 100-case statistics bundle |
| `run_learned_f2_to_f3_gate_v1_eval.py` | Train and evaluate a learned strict post-F2 gate |
| `run_hard_max_family_expansions_eval.py` | Evaluate hard per-family expansion caps on the strict target |
| `run_full_method_comparison_bundle.py` | Current broad matched comparison and ranking bundle |
| `build_twenty_exact_current_full_vs_best_fresh.py` | Build the fresh exact current-full-vs-best loss surface |
| `run_integrated_controller_component_ablation.py` | Canonical integrated-controller component ablation on strict-phased surface |
| `run_manuscript_surface_component_ablation.py` | Manuscript-facing strict_f3 component ablation on canonical matched surface |
| `package_strict_f3_component_ablation_paper_surface.py` | Non-rerun paper-facing packaging for existing strict_f3 manuscript-surface ablation artifacts |
| `run_paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3.py` | Focused manuscript decision bundle comparing strict_gate1_cap_k6 vs strict_f3 with fair near-direct externals |

## Exploratory or adjacent controlled workflows

| Script | Role |
|---|---|
| `run_fresh_twenty_current_full_improvement_eval_20260420.py` | Evaluate bounded controller improvements on the fresh 20-case slice |
| `build_targeted_failure_bundle_from_fresh_loss_surface_20260420.py` | Derive a mechanism-homogeneous targeted bundle from the fresh loss surface |
| `run_near_miss_correction_bundle_eval_20260420.py` | Evaluate the near-miss correction-gate variant on targeted and broad surfaces |
| `run_cross_strategy_frontier_allocation.py` | Older or legacy frontier-allocation scaffold |
| `run_new_paper_frontier_matrix.py` | Frontier matrix and anti-collapse summary tables |
| `run_comparative_frontier_audit.py` | Matched-budget comparative audit |
| `run_imported_methodology_frontier_eval.py` | Older bounded evaluation layer for the current branch-allocation setting |
| `evaluate_branch_scorer_controller.py` | Controller-level comparison for learned and heuristic policies |
| `evaluate_branch_scorer_robustness.py` | Multi-seed, budget, and initialization robustness sweep |

## Integration and preparation scripts

| Script | Role |
|---|---|
| `verify_hf_dataset_access.py` | Verify evaluation-dataset access and summarize status |
| `dataset_smoke_sample.py` | Lightweight dataset smoke samples |
| `generate_dataset_integration_report.py` | Main evaluation-dataset integration report |
| `verify_external_reasoning_datasets.py` | External supervision access and schema checks |
| `generate_external_reasoning_dataset_integration_report.py` | External supervision integration report |
| `build_canonical_branch_learning_corpus.py` | Build canonical processed branch-learning corpora |
| `run_canonical_branch_learning_pass.py` | Run a matched canonical learning pass from canonical corpora |
| `run_protected_strata_holdout_expansion.py` | Bounded split-seed holdout expansion targeting sparse protected strata |
| `build_external_prm_mathshepherd_apps_corpus.py` | Build conservative canonical-aligned external rows |
| `prepare_external_reasoning_datasets.py` | Readiness ranking and normalized previews |
| `generate_external_baseline_integration_report.py` | External baseline integration report |
| `build_external_adjacent_baseline_bundle.py` | Aggregate manuscript-safe bundle for BEST-Route / when_solve_when_verify / ReST-MCTS* adjacent baseline status |
| `run_rest_mcts_adjacent_integration.py` | Canonical ReST-MCTS adjacent contract runner with standardized artifact family export |
| `run_lets_verify_step_by_step_adjacent_integration.py` | Canonical Let's Verify Step by Step adjacent contract runner with PRM800K public-asset checks and standardized artifacts |
| `verify_lets_verify_step_by_step_import.py` | Strict validator for Let's Verify Step by Step adjacent import contract packages |
| `run_tree_plv_adjacent_integration.py` | Canonical Tree-PLV adjacent contract runner with conservative paper↔repo checks and standardized artifacts |
| `verify_tree_plv_import.py` | Strict validator for Tree-PLV adjacent import contract packages |
| `generate_tree_plv_status_report.py` | Generate machine-readable Tree-PLV completeness status artifacts |
| `list_external_baselines.py` | Print external baseline registry |

## Historical and provenance scripts

Historical entry points are documented in:
- [`HISTORICAL_INDEX.md`](HISTORICAL_INDEX.md)
- `../archive/historical_scripts/`

## Paper-facing script note

There are two ablation surfaces on purpose:
- `run_integrated_controller_component_ablation.py`: broader strict-phased operational surface around the broader operational default line (`strict_gate1_cap_k6`).
- `run_manuscript_surface_component_ablation.py`: canonical manuscript-facing matched internal surface around the manuscript-facing internal winner (`strict_f3`).

Keep these surfaces separated in interpretation and manuscript claims.

## Notes

- The current highest-leverage scripts are the strict-phased force/gate comparisons, newest-vs-best exact-loss statistics, learned post-F2 gate, and hard family-expansion-cap analysis.
- `run_cross_strategy_frontier_allocation.py` and related frontier scripts remain useful, but they are no longer the default first path for the current default-model question.
- Use the paired docs in `../docs/` when interpreting any narrower experimental line; many exploratory scripts are not intended to stand alone as headline results.
