# Next lightweight steps (before HPC returns)

## Objective

Improve supervision target design and controller signal quality with bounded, low-cost experiments.

## Priority sequence

1. **Binary stop-vs-act label design (budget-conditioned).**
   - Construct labels around “stop vs one-more-action” at decision states.
   - Condition labels/features on remaining budget and frontier context.

2. **Uncertainty-aware training setup.**
   - Add uncertainty indicators as model inputs.
   - Use uncertainty for filtering/reweighting ambiguous examples.

3. **Cheap approximate marginal-label experiments.**
   - +1 action delta labels.
   - short-horizon (small-k) rollout delta utility labels.
   - bounded rollout comparison labels for stop-vs-act.

4. **Bounded label audits.**
   - Audit disagreement rates, near-threshold instability, and calibration slices.
   - Mark uncertain/ambiguous examples explicitly.

5. **Matched comparisons (small scale).**
   - Compare stop-vs-act controller vs:
     - strong heuristic baseline(s),
     - plain pairwise BT branch scorer controller.
   - Keep budgets, seeds, and slices matched and auditable.

## Deliverables for this phase

- Label schema + audit summary.
- First stop-vs-act baseline results (small but matched).
- Updated safe-claim wording based on bounded evidence.

## Explicit non-goals (pre-HPC)

- No large benchmark expansion.
- No heavy model scaling before target quality improves.
- No overclaiming from exploratory wins.
