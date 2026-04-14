# New-paper anti-collapse audit note (2026-04-13)

## Goal

Strengthen anti-collapse behavior in adaptive frontier controllers while staying lightweight and auditable.

Compared methods:

- `adaptive_min_expand_0`
- `adaptive_min_expand_1`
- `adaptive_min_expand_2`
- `adaptive_budget_guarded` (new)

## Audit of current anti-collapse behavior

The existing anti-collapse knob (`min_expansions_before_prune`) already exposes a clear mechanism tradeoff:

- Higher fixed `k` lowers prune share and increases forced expansion share.
- Higher fixed `k` generally raises realized action usage.
- Accuracy impact is dataset/budget dependent and is not monotone in all runs.

## New lightweight anti-collapse variant

Implemented in `AdaptiveController` as a single mechanism bundle:

1. **Adaptive min-expand:** effective minimum expansions increases by +1 while at least 50% budget remains.
2. **Verification exploration floor:** verification blocked until branch has at least one expansion.
3. **Budget-aware prune guard:** when enough budget remains, near-threshold low-progress branches are forced to expand rather than pruned.

This variant is exposed as `adaptive_budget_guarded` in frontier strategy construction.

## Run configuration

```bash
python scripts/run_new_paper_anti_collapse_audit.py \
  --subset-size 18 \
  --budgets 4,6 \
  --adaptive-min-expand-grid 0,1,2
```

Output directory:

- `outputs/new_paper/anti_collapse_audit/20260413T235830Z/`

## What was measured

- prune share
- forced expand share
- realized action usage (`avg_actions`)
- accuracy
- oracle gap

Files:

- `anti_collapse_method_metrics.csv`
- `anti_collapse_behavior.csv`
- `anti_collapse_interpretation.md`

## Result summary (honest read)

On this small simulated run:

- `adaptive_budget_guarded` reduced collapse-like behavior versus low-`k` settings (lower prune share than `k=0`, higher action usage).
- It **did not beat** `adaptive_min_expand_2` on accuracy or oracle gap at either tested budget.
- Net outcome is **mixed / not a clear material improvement** over the strongest fixed-`k` baseline in this pilot.

This should be treated as a mechanism-level diagnostic improvement, not a headline performance win.
