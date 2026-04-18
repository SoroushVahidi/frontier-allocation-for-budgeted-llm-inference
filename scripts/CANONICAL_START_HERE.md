# Canonical scripts start here

This is the fastest script-level entry point for the current project.

## Smallest runnable paths

### If you want one script that best reflects the paper direction
Start with:
- `run_cross_strategy_frontier_allocation.py`

### If you want one script for the current leading target-fidelity direction
Start with:
- `run_multistep_branch_utility_target_experiment.py`

### If you want one script for the current hard-case bottleneck
Start with:
- `run_structured_ambiguity_experiment.py`

### If you want one script for the earlier value-supervision line
Start with:
- `run_branch_value_uncertainty_strict_validation_pass.py`

## Before you run scripts

For the shortest current repository-facing orientation, read:
- `../docs/CURRENT_LEADING_DIRECTION_2026_04_17.md`
- `../docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`
- `../docs/MAIN_BOTTLENECK_FOCUS_2026_04_18.md`
- `../docs/DAILY_OPERATOR_PATH_2026_04_18.md`
- `../docs/REPOSITORY_POLISH_PASS_2026_04_17.md`

## If you want the current paper path

Start with these scripts:
- `run_cross_strategy_frontier_allocation.py`
- `evaluate_branch_scorer_controller.py`
- `evaluate_branch_scorer_robustness.py`
- `run_new_paper_frontier_matrix.py`
- `run_comparative_frontier_audit.py`
- `run_imported_methodology_frontier_eval.py`

## If you want the current leading multistep line

Start with these scripts:
- `run_multistep_branch_utility_target_experiment.py`
- `build_bruteforce_target_regimes.py`
- `run_canonical_branch_learning_pass.py`
- `train_bruteforce_branch_allocator.py`

## If you want the current hard-case / near-tie method line

Start with these scripts:
- `run_near_tie_policy_experiment.py`
- `run_near_tie_pointwise_expert_experiment.py`
- `run_ambiguity_calibration_and_fallback_experiment.py`
- `train_bruteforce_branch_allocator.py`
- `run_target_fidelity_regime_experiment.py`
- `run_structured_ambiguity_experiment.py`
- `run_defer_fallback_experiment.py`

## If you want the earlier target-design / value-supervision line

Start with these scripts:
- `run_branch_value_uncertainty_derived_defer_experiment.py`
- `run_branch_value_uncertainty_strict_validation_pass.py`
- `build_bruteforce_target_regimes.py`
- `train_bruteforce_branch_allocator.py`

## If you want dataset / supervision preparation

Start with these scripts:
- `build_canonical_branch_learning_corpus.py`
- `run_canonical_branch_learning_pass.py`
- `build_bruteforce_target_regimes.py`
- `run_bruteforce_branch_label_generator.py`

## If you want external baseline work

Start with these scripts:
- `run_s1_budget_forcing_baseline.py`
- `run_tale_baseline.py`
- `run_l1_baseline.py`
- external baseline validation/generation scripts described in [`README.md`](README.md)

## Rule of thumb

- Use this page first.
- Use [`README.md`](README.md) for the full script index.
- Use `run_imported_methodology_frontier_eval.py` when you need cleaner manuscript-style fixed/adaptive/oracle summaries.
- Treat historical script paths as provenance support, not the default path.
- The current highest-leverage code path is the one that most directly tests target fidelity on hard close-branch cases rather than broad controller proliferation.
