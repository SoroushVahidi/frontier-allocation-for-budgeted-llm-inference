# Canonical script start

This file is the shortest script-level entry point for the **current** project.

## What to run first

These are the main current-paper scripts.

### Frontier / controller path
- `run_cross_strategy_frontier_allocation.py` — main frontier-allocation scaffold.
- `run_multi_action_allocation_pass.sh` — multi-action run wrapper.
- `evaluate_branch_scorer_controller.py` — controller-level comparison for learned and heuristic policies.
- `evaluate_branch_scorer_robustness.py` — robustness sweeps across seeds, budgets, and initializations.
- `run_new_paper_frontier_matrix.py` — frontier-matrix and anti-collapse paper tables.
- `run_comparative_frontier_audit.py` — matched-budget comparative audit.

### Local stop-vs-act helper path
Use this only after the frontier/controller framing is already clear.

- `run_new_paper_stop_vs_act_controller.py`
- `run_new_paper_stop_vs_act_target_stabilization_pass.py`
- `run_new_paper_stop_vs_act_matched_comparator_pass.py`
- `run_new_paper_stop_vs_act_policy_coupled_stop_pass.py`

## What is canonical vs exploratory

### Canonical
- frontier/controller allocation scaffold,
- branch-priority / next-step allocation comparisons,
- matched controller audits,
- paper-facing frontier summaries.

### Exploratory
- reliability-aware BT variants,
- warm-start variants,
- tie-aware and ambiguity-aware experiments,
- method-specific diagnostics.

### Historical
- old binary revise-routing support scripts.

## Practical rule

If you are not sure where to start:
1. run the canonical frontier/controller path first,
2. use stop-vs-act scripts only as helper-path experiments,
3. use the full [`README.md`](README.md) only when you need the broader script inventory.
