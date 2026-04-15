# Next lightweight steps (canonical near-term)

## Objective

Improve supervision target design and controller signal quality with bounded, low-cost experiments that strengthen the paper story without requiring large-scale runs.

## Near-term priority sequence

1. **Strengthen stop-vs-act target design.**
   - Construct cleaner ACT-vs-STOP comparisons.
   - Make STOP semantics more opportunity-cost-aware.
   - Keep the decision explicitly budget-conditioned.

2. **Improve uncertainty-aware training policy.**
   - Use uncertainty indicators as model inputs.
   - Use uncertainty for filtering / reweighting ambiguous examples.
   - Track ambiguous slices explicitly in reports.

3. **Run matched bounded controller comparisons.**
   - Compare stop-vs-act against strong heuristics.
   - Compare stop-vs-act against pairwise BT controller baseline.
   - Keep seeds, budgets, and slices matched and auditable.

4. **Integrate the most important external paper baselines fairly.**
   - Prioritize baselines that are closest to budget control and test-time allocation.
   - Separate faithful inference-only adapters from full external-method reproductions when needed.
   - Document fairness caveats explicitly.

5. **Sharpen manuscript-safe exports.**
   - Update safe claims after each bounded pass.
   - Keep note/report artifacts easy to cite later.
   - Convert exploratory results into reviewer-facing summaries only when the evidence is stable enough.

## Deliverables for this phase

- clearer ACT-vs-STOP target notes and audit outputs,
- matched small-scale controller comparisons,
- at least one important external baseline integration plan or implementation,
- updated safe-claim wording,
- cleaner paper-positioning materials.

## Explicit non-goals (near-term)

- No broad heavy scaling before target quality improves.
- No overclaiming from isolated wins.
- No diffusion back into the old binary revise-routing manuscript story.
