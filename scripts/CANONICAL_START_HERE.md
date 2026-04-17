# Canonical scripts start here

This is the fastest script-level entry point for the current project.

## If you want the current paper path

Start with these scripts:
- `run_cross_strategy_frontier_allocation.py`
- `evaluate_branch_scorer_controller.py`
- `evaluate_branch_scorer_robustness.py`
- `run_new_paper_frontier_matrix.py`
- `run_comparative_frontier_audit.py`
- `run_imported_methodology_frontier_eval.py`

## If you want the current hard-case / near-tie method line

Start with these scripts:
- `run_near_tie_policy_experiment.py`
- `run_near_tie_pointwise_expert_experiment.py`
- `run_ambiguity_calibration_and_fallback_experiment.py`
- `train_bruteforce_branch_allocator.py`
- `run_target_fidelity_regime_experiment.py`

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
