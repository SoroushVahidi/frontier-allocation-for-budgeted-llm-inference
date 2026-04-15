# Current bottlenecks (canonical)

## Primary bottleneck

The primary bottleneck is **supervision target quality** and **proxy-label mismatch** for allocation decisions.

## Explicit non-bottlenecks (for current phase)

The primary bottleneck is **not**:
- infrastructure completeness,
- absence of heavier models,
- inability to run broader sweeps.

## Why this bottleneck dominates now

Current learned branch/controller scoring depends heavily on approximate proxy labels. Those proxies are useful, but they do not directly encode whether the next compute action is worth the budget in the present state.

This mismatch weakens:
- controller-level robustness,
- transfer across datasets/seeds/budgets,
- calibration of stop/act behavior.

## Practical consequence

The next efficient progress comes from improving action-conditional targets, not from immediate scale-up.

## Canonical near-term response

1. Build cheap approximate marginal labels (stop-vs-one-more-action, short-horizon delta utility, +1 or small-k rollout comparisons).
2. Mark uncertainty/ambiguity explicitly.
3. Train/evaluate a budget-conditioned stop-vs-act controller with uncertainty-aware training.
4. Re-run matched bounded comparisons against strong heuristics and pairwise BT baseline.
