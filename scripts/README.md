# Scripts index

All scripts write run artifacts under `outputs/` unless overridden.

This file is the runnable-code front door for the repository.

## Read this first

- Current repository interpretation: [`../docs/CANONICAL_START_HERE.md`](../docs/CANONICAL_START_HERE.md)
- Current our-method status: [`../docs/CURRENT_OUR_METHOD_STATUS_20260422T001521Z.md`](../docs/CURRENT_OUR_METHOD_STATUS_20260422T001521Z.md)
- Current in-house winner decision: [`../docs/FINAL_INHOUSE_METHOD_DECISION_20260422T001521Z.md`](../docs/FINAL_INHOUSE_METHOD_DECISION_20260422T001521Z.md)
- Current paper-facing comparison package: [`../docs/PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md`](../docs/PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md)
- Current fairness / claim-boundary guide: [`../docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`](../docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md)
- Current simple-scaling coverage decision: [`../docs/SIMPLE_SCALING_BASELINE_COVERAGE_DECISION_20260422T235959Z.md`](../docs/SIMPLE_SCALING_BASELINE_COVERAGE_DECISION_20260422T235959Z.md)
- Current code entry path: [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- Repository map: [`../docs/REPO_MAP.md`](../docs/REPO_MAP.md)
- Artifact-status policy: [`../docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md`](../docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md)
- Historical script entry points: [`HISTORICAL_INDEX.md`](HISTORICAL_INDEX.md)

## Interpretation labels

- **Canonical**: current in-house decision and paper-facing comparison path for the NeurIPS-oriented project.
- **Exploratory**: active side branches and narrower diagnostics, not settled default winners.
- **Integration/prep**: dataset and baseline readiness tooling.
- **Historical**: older-track support scripts retained only for provenance.

## Most common workflows

### 1. Understand or rebuild the current in-house and external comparison layer
- `run_full_our_method_vs_external_baselines_comparison.py`
- `build_paper_facing_baseline_tables.py`
- `build_fairness_audit_for_direct_baselines.py`
- `build_simple_scaling_baseline_coverage_audit.py`

### 2. Run the current direct external baseline adapters
- `run_s1_budget_forcing_baseline.py`
- `run_tale_baseline.py`
- `run_l1_baseline.py`

### 3. Run current adjacent external baseline support paths
- `run_rest_mcts_adjacent_integration.py`
- `run_lets_verify_step_by_step_adjacent_integration.py`
- `run_tree_plv_adjacent_integration.py`
- `build_external_adjacent_baseline_bundle.py`

### 4. Run the current strict-phased internal method diagnostics
- `run_hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421.py`
- `run_hundred_three_gate_design_eval_strict_phased.py`
- `build_new_hundred_newest_vs_best_failure_statistics.py`
- `build_canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics.py`
- `run_hard_max_family_expansions_eval.py`

## Canonical scripts (current project path)

| Script | Role |
|---|---|
| `run_full_our_method_vs_external_baselines_comparison.py` | Canonical our-method vs external-baselines comparison bundle anchored on `strict_f3` |
| `build_paper_facing_baseline_tables.py` | Build the reviewer-facing split package: near-direct, adjacent, and discussion-only tables |
| `build_fairness_audit_for_direct_baselines.py` | Build the direct-baseline fairness audit, claim-safety matrix, and main-vs-appendix recommendation |
| `build_simple_scaling_baseline_coverage_audit.py` | Build the explicit audit that the direct package already covers the simple scaling axis |
| `run_broader_strict_phased_default_decision_eval.py` | Broader strict-phased promoted-default evaluation path |
| `build_new_hundred_newest_vs_best_failure_statistics.py` | Build the newest-vs-best exact-loss 100-case statistics surface |
| `run_hard_max_family_expansions_eval.py` | Evaluate hard per-family expansion caps on the strict target |

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
| `build_external_adjacent_baseline_bundle.py` | Aggregate manuscript-safe bundle for official adjacent baseline status |
| `run_rest_mcts_adjacent_integration.py` | Canonical ReST-MCTS adjacent contract runner with standardized artifact family export |
| `verify_rest_mcts_import.py` | Strict validator for ReST-MCTS adjacent import contract packages |
| `run_lets_verify_step_by_step_adjacent_integration.py` | Canonical Let's Verify Step by Step adjacent contract runner with PRM800K public-asset checks and standardized artifacts |
| `verify_lets_verify_step_by_step_import.py` | Strict validator for Let's Verify Step by Step adjacent import contract packages |
| `run_tree_plv_adjacent_integration.py` | Canonical Tree-PLV adjacent contract runner with conservative paper↔repo checks and standardized artifacts |
| `verify_tree_plv_import.py` | Strict validator for Tree-PLV adjacent import contract packages |
| `generate_tree_plv_status_report.py` | Generate machine-readable Tree-PLV completeness status artifacts |
| `list_external_baselines.py` | Print external baseline registry |

## Exploratory / adjacent controlled experiment workflows

| Script | Role |
|---|---|
| `run_fresh_twenty_current_full_improvement_eval_20260420.py` | Evaluate bounded controller improvements on the fresh 20-case slice |
| `build_targeted_failure_bundle_from_fresh_loss_surface_20260420.py` | Derive a mechanism-homogeneous targeted bundle from the fresh loss surface |
| `run_near_miss_correction_bundle_eval_20260420.py` | Evaluate the near-miss correction-gate variant on targeted and broad surfaces |
| `run_cross_strategy_frontier_allocation.py` | Older/legacy frontier-allocation scaffold |
| `run_new_paper_frontier_matrix.py` | Frontier matrix / anti-collapse summary tables |
| `run_comparative_frontier_audit.py` | Matched-budget comparative audit |
| `run_imported_methodology_frontier_eval.py` | Older bounded evaluation layer for the current branch-allocation setting |
| `evaluate_branch_scorer_controller.py` | Controller-level comparison for learned/heuristic policies |
| `evaluate_branch_scorer_robustness.py` | Multi-seed/budget/init robustness sweep |

## Historical/provenance scripts

Historical entry points are documented in:
- [`HISTORICAL_INDEX.md`](HISTORICAL_INDEX.md)
- `../archive/historical_scripts/`

## Notes

- The current highest-leverage scripts are the comparison/fairness/audit builders that define the paper-facing evaluation layer.
- The broader strict-phased and anti-collapse diagnostics remain important, but they are no longer the only front-door path because the repo now has an explicit our-method decision and comparison package.
- Use the paired docs in `../docs/` when interpreting any narrower experimental line; many exploratory scripts are not intended to stand alone as headline results.
