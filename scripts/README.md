# Scripts index

All scripts write run artifacts under `outputs/` unless overridden.

This file is the runnable-code front door for the repository.

## Read this first

- Current repository interpretation: [`../docs/CANONICAL_START_HERE.md`](../docs/CANONICAL_START_HERE.md)
- Current strict-phased status: [`../docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`](../docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md)
- Current experiment-family index: [`../docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`](../docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md)
- Current code entry path: [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- Current external-baseline strengthening order: [`../docs/CURRENT_BASELINE_NEXT_STEPS_2026_04_21.md`](../docs/CURRENT_BASELINE_NEXT_STEPS_2026_04_21.md)
- Paper-facing baseline guide: [`../docs/main_baselines.md`](../docs/main_baselines.md)
- Repository map: [`../docs/REPO_MAP.md`](../docs/REPO_MAP.md)
- Artifact-status policy: [`../docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md`](../docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md)
- Historical script entry points: [`HISTORICAL_INDEX.md`](HISTORICAL_INDEX.md)

## Interpretation labels

- **Canonical**: current strict-phased default-decision path for the NeurIPS-oriented project.
- **Exploratory**: active side branches and narrower diagnostics, not settled default winners.
- **Integration/prep**: dataset and baseline readiness tooling.
- **Historical**: older-track support scripts retained only for provenance.

## Most common workflows

### 1. Run the current strict-phased default-decision path
- `run_hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421.py`
- `run_hundred_three_gate_design_eval_strict_phased.py`
- `build_new_hundred_newest_vs_best_failure_statistics.py`
- `build_canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics.py`

### 2. Run current learned or capped alternatives
- `run_learned_f2_to_f3_gate_v1_eval.py`
- `run_hard_max_family_expansions_eval.py`

### 3. Run the current near-direct external baseline stack
- `run_s1_budget_forcing_baseline.py`
- `run_tale_baseline.py`
- `run_l1_baseline.py`

### 4. Run the current adjacent external baseline stack
- `run_best_route_adjacent_integration.py`
- `run_best_route_full_integration_attempt.py`
- `run_when_solve_when_verify_adjacent_integration.py`
- `run_rest_mcts_partial_runnable_integration.py`
- `verify_rest_mcts_import.py`

### 5. Check dataset and baseline readiness
- `verify_hf_dataset_access.py`
- `generate_dataset_integration_report.py`
- `generate_external_baseline_integration_report.py`
- `list_external_baselines.py`

## Canonical scripts (current project path)

| Script | Role |
|---|---|
| `run_hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421.py` | Strict forced F2 vs strict forced F3 comparison under phased law |
| `run_hundred_three_gate_design_eval_strict_phased.py` | Strict phased Gate 1 / Gate 2 / Gate 3 comparison |
| `build_new_hundred_newest_vs_best_failure_statistics.py` | Build the newest-vs-best exact-loss 100-case statistics surface |
| `build_canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics.py` | Build the finalized-default (`strict_gate1_cap_k6`) canonical exact-loss 100-case statistics bundle |
| `run_learned_f2_to_f3_gate_v1_eval.py` | Train and evaluate a learned strict post-F2 gate |
| `run_hard_max_family_expansions_eval.py` | Evaluate hard per-family expansion caps on the strict target |
| `run_full_method_comparison_bundle.py` | Current broad matched comparison / ranking bundle |
| `build_twenty_exact_current_full_vs_best_fresh.py` | Build the fresh exact current-full-vs-best loss surface |

## External baseline scripts worth knowing first

| Script | Role |
|---|---|
| `run_s1_budget_forcing_baseline.py` | MODE A matched-substrate s1 baseline |
| `run_tale_baseline.py` | MODE A matched-substrate TALE baseline |
| `run_l1_baseline.py` | MODE A matched-substrate L1 baseline |
| `run_best_route_adjacent_integration.py` | BEST-Route adjacent import-validated integration lane |
| `run_best_route_full_integration_attempt.py` | BEST-Route stronger execution attempt / stabilization lane |
| `verify_best_route_import.py` | Strict BEST-Route import validation |
| `run_when_solve_when_verify_adjacent_integration.py` | When-To-Solve/Verify adjacent integration lane |
| `verify_when_solve_when_verify_import.py` | Strict solve/verify import validation |
| `run_rest_mcts_partial_runnable_integration.py` | ReST-MCTS* official-code partial-runnable integration lane |
| `verify_rest_mcts_import.py` | ReST-MCTS import validation lane |
| `generate_external_baseline_integration_report.py` | Generate the current external baseline integration summary |
| `list_external_baselines.py` | Print external baseline registry |

## Exploratory or adjacent controlled workflows

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

- The current highest-leverage internal scripts are the strict-phased force/gate comparisons, newest-vs-best exact-loss statistics, learned post-F2 gate, and hard family-expansion-cap analysis.
- The current strongest paper-facing external stack is the MODE A `s1` / `TALE` / `L1` runners plus ReST-MCTS* as the strongest adjacent search baseline, with BEST-Route still needing stabilization.
- `run_cross_strategy_frontier_allocation.py` and related frontier scripts remain useful, but they are no longer the default first path for the current default-model question.
- Use the paired docs in `../docs/` when interpreting any narrower experimental line; many exploratory scripts are not intended to stand alone as headline results.
