# Experiments

This directory contains experiment implementation code plus lightweight result notes. Large result trees belong under **`outputs/`** (gitignored).

## What is actually here (current state)

Core modules:

- `controllers.py`: controller policies (greedy, best-of-n, beam, adaptive variants).
- `branching.py`: branch generators (simulation + API-backed pathways).
- `scoring.py`: branch scoring utilities.
- `data.py`: pilot/example data utilities.
- `hf_datasets.py`: dataset sampling/adapter helpers.
- `branch_scorer_v3.py`: learned branch-scorer simulation/evaluation helpers.

Result/diagnostic notes:

- `branch_scorer_v3_result_note.md`
- `branch_scorer_v4_result_note.md`
- `adaptive_min_expand_note.md`
- `eptree_baseline_note.md`
- `pilot_*.md`

## How this maps to the two paper tracks

- Old manuscript track (binary revise-routing): mostly orchestrated from `scripts/` and manuscript docs.
- New track (cross-controller frontier allocation): uses these modules heavily via `scripts/run_cross_strategy_frontier_allocation.py` and learned-scorer scripts.

## Reproducibility notes

- Do not commit raw model outputs or large data files.
- Prefer running through scripts in `scripts/` and configs in `configs/`.
- Write run artifacts under **`outputs/`** only (legacy singular `output/` is deprecated and gitignored).
