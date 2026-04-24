# Imported methodology integration report (bounded pass)

## Scope and guardrails

This pass intentionally **does not** revert the project to binary "revise vs not revise" routing.
All imported ideas were adapted to the current fixed-budget **branch/frontier allocation** action space.

## Historical repository assets inspected and selectively adapted

Historical repository inspected: `https://github.com/<ANON_ORG>/<ANON_REPO>`.

Repository-grounded files used as templates for evaluation discipline and artifacts:

- `scripts/run_cross_regime_comparison.py`
  - Reused pattern: matched cross-method summary rows and regime-level aggregation.
- `scripts/run_oracle_strategy_eval.py`
  - Reused pattern: explicit oracle upper-bound evaluation row and gap accounting.
- `scripts/run_real_budget_sweep.py`
  - Reused pattern: budget-curve/frontier exports in machine-readable CSV+JSON.
- `scripts/run_signal_ablation_experiment.py`
  - Reused pattern: signal-slice summaries (hard/easy), plus per-policy accuracy gap reporting.
- `scripts/generate_final_manuscript_artifacts.py` and `scripts/generate_paper_tables.py`
  - Reused pattern: manuscript-facing compact artifact bundle, not just console logs.

## What was implemented in the current repository

New script:
- `scripts/run_imported_methodology_frontier_eval.py`

What this script adds for current branch-allocation setting:
1. **Matched comparison discipline** on a fixed eval split across all methods.
2. **Fixed vs adaptive vs oracle** evaluation table at each budget.
3. **Oracle headroom/gap-to-oracle** summary for each method.
4. **Budget-aware frontier export** across user-specified budgets.
5. **Signal-separation summary** (hard/easy slices) adapted to current data availability.
6. **Artifact bundle** under `outputs/imported_methodology_frontier_eval/<run_id>/`.

## Current-controller path coverage (bounded, no new method invention)

The integration layer evaluates existing controller families already available through
`experiments/frontier_matrix_core.py`:

- Fixed baselines: `reasoning_greedy`, `self_consistency_3`, `reasoning_beam2`, `verifier_guided_search`, `program_of_thought`.
- Adaptive/controller line (existing): priority pick among
  `adaptive_bt_pairwise_reliability` → `adaptive_bt_pairwise` → `adaptive_budget_guarded` → `adaptive_min_expand_1`.
- Oracle row: `oracle_frontier_upper_bound` over the same candidate method pool at the same budget.

In this run, pairwise model paths were not provided, so the selected adaptive method was
`adaptive_budget_guarded`.

## Produced artifacts (this run)

Run id: `20260417T000000Z`

- `outputs/imported_methodology_frontier_eval/20260417T000000Z/summary.json`
- `outputs/imported_methodology_frontier_eval/20260417T000000Z/method_metrics.csv`
- `outputs/imported_methodology_frontier_eval/20260417T000000Z/oracle_gap_summary.csv`
- `outputs/imported_methodology_frontier_eval/20260417T000000Z/matched_comparison_summary.csv`
- `outputs/imported_methodology_frontier_eval/20260417T000000Z/budget_frontier_summary.csv`
- `outputs/imported_methodology_frontier_eval/20260417T000000Z/signal_slice_summary.csv`

## What transferred well vs did not transfer

### Transferred well

- **Matched evaluation discipline**: clean paired win/loss/tie summaries per budget.
- **Oracle headroom analysis**: direct quantification of method-to-oracle gap.
- **Budget frontier export**: compact budget→accuracy/action/gap table.
- **Signal-slice reporting**: hard/easy split provides immediate failure localization.

### Did not transfer cleanly (and therefore was not forced)

- Binary revise-routing specific semantics (e.g., revise-helpful labels, false-positive revise counts)
  do not map one-to-one to multi-branch frontier actions.
- Strategy-specific revise gating thresholds from old v6/v7 policy files were not copied, because they
  encode a different action space and would create a misleading equivalence claim.

## Current results from imported layer (simulator run)

From `method_metrics.csv` and frontier exports:

- Budget 8: best non-oracle fixed method was `reasoning_beam2` (accuracy `0.7778`),
  while selected adaptive (`adaptive_budget_guarded`) was `0.0000`; oracle upper bound was `1.0000`.
- Budget 10: best non-oracle fixed method was `self_consistency_3` (accuracy `0.7778`),
  selected adaptive was `0.4444`; oracle upper bound remained `1.0000`.
- Gap-to-oracle remains substantial for non-oracle methods in both budgets.

## Required final analysis

### Which imported manuscript ideas were actually useful

Most useful in this repository right now:
1. Matched comparator reporting (prevents cherry-picking).
2. Oracle headroom summaries (makes residual opportunity explicit).
3. Budget-frontier views (shows tradeoff shape, not single-point claims).
4. Signal-slice breakdowns (shows where failures concentrate).

### Which weaknesses remain even after using them

- The layer improves **measurement clarity**, but does not itself improve controller quality.
- When pairwise model checkpoints are absent, adaptive evaluation falls back to weaker internal variants,
  which can underperform fixed baselines.
- Hard-slice definition is currently proxy-based and should be tied to stronger branch-state signals.

### New bottleneck after this pass

Primary bottleneck is now **controller signal quality/calibration under fixed budget**, not missing evaluation structure.
In short: evaluation is now clearer than the adaptive policy signal it is evaluating.

### Best next method step (bounded)

Next bounded step should be to plug the strongest already-trained pairwise/tie-aware scorer checkpoints
into this new evaluation layer (no new baseline campaign), then compare:
`adaptive_bt_pairwise` vs `adaptive_bt_pairwise_reliability` vs fixed baselines under the same matched/oracle framework.

That isolates whether the current gap is mostly due to evaluation blind spots (now reduced) or model-side signal limits.
