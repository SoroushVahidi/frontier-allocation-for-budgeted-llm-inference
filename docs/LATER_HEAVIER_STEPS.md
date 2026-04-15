# Later heavier steps (canonical later phase)

## Entry condition

Proceed with heavier runs only after the lightweight target-design phase shows improved label quality, more stable controller behavior, or clearly stronger matched comparisons.

## Heavy-phase priorities

1. **Broader target coverage.**
   - Expand action-conditional labels to larger datasets, more budgets, and more frontier states.
   - Stress-test the same target design rather than inventing many unrelated variants at once.

2. **Broader robustness sweeps.**
   - Multi-seed, multi-budget, multi-dataset comparisons.
   - Explicit collapse / under-spend / calibration drift analyses.

3. **Real-model evidence expansion.**
   - Larger matched-budget real-model evaluations.
   - More complete frontier tables and reviewer-facing summaries.

4. **Selective oracle-label and distillation scaling.**
   - Expand oracle-label pilot generation where it clearly helps the supervision story.
   - Use selective distillation only if it improves controller quality under matched evaluation.

5. **Conditional model-capacity expansion.**
   - Try heavier models only after target quality improves enough to justify the cost.
   - Evaluate whether gains persist versus simpler controller baselines.

6. **Richer action-space exploration.**
   - Only after the binary stop-vs-act story becomes stable.
   - Use richer actions to extend the paper story, not to hide unresolved binary-control issues.

## Heavy-phase guardrail

Scale should follow target-quality improvements. It should not be the first remedy for proxy-label mismatch.

## Desired heavy-phase output

- stronger controller-level robustness evidence,
- broader real-model evidence,
- clearer frontier plots and budget summaries,
- a paper-ready comparison package that includes both direct and adjacent adaptive-allocation baselines.
