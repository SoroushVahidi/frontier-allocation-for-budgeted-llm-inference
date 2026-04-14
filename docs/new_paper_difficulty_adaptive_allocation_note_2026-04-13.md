# New-paper difficulty-adaptive allocation baseline (2026-04-13)

## What was added

A lightweight, auditable difficulty-aware allocation baseline for cross-controller frontier allocation:

- Script: `scripts/run_new_paper_difficulty_adaptive_allocation.py`
- Output root: `outputs/new_paper/difficulty_adaptive_allocation/<run_id>/`

The method keeps the same average budget by assigning half the eval queries to `B+1` and half to `B-1`.

- **Uniform baseline:** first half gets `B+1` (difficulty-agnostic)
- **Difficulty-adaptive baseline:** top predicted-hard half gets `B+1`

Controller at each budget level is selected from calibration performance (same existing frontier/controller stack).

## Difficulty proxies audited

Cheap proxies from current artifacts:

- Question-level text features: char/token length, digit count, operator count, simple multi-step cue.
- Calibration trace outcomes from primary method (`adaptive_min_expand_1`): correctness and `budget_exhausted`.

Difficulty label used for training:

- hard = primary incorrect OR primary budget exhausted (on calibration split).

Model:

- `TfidfVectorizer` + `LogisticRegression` (fallback constant model if labels collapse).

## Metrics emitted

`difficulty_method_metrics.csv` includes:

- accuracy
- realized cost
- oracle gap (to base-budget oracle frontier)
- under-spend / unused budget
- selected low/high controllers

Additional files:

- `difficulty_proxy_audit.csv`
- `allocation_decisions.csv`
- `selected_controller_frequencies.csv`
- `difficulty_interpretation.md`
- `run_manifest.json`

## Example run

```bash
python scripts/run_new_paper_difficulty_adaptive_allocation.py \
  --subset-size 18 \
  --budgets 4,6 \
  --adaptive-min-expand-grid 0,1,2
```

Outputs were written to:

- `outputs/new_paper/difficulty_adaptive_allocation/20260413T235228Z/`

## Notes

- This is intentionally lightweight and does not use RL or heavy redesign.
- Current pilot is small/simulated; use larger subsets and real API backend for stronger conclusions.
