# Later heavier steps (after HPC returns)

## Entry condition

Proceed with heavy runs only after lightweight target-design phase shows improved label quality and stable signal trends.

## Heavy-phase priorities

1. **Larger-scale label generation.**
   - Expand approximate marginal labels to larger datasets/slices.
   - Increase coverage of budgets and frontier states.

2. **Broader robustness sweeps.**
   - Multi-seed, multi-budget, multi-dataset comparisons.
   - Stress tests for collapse behavior and calibration drift.

3. **Real-model evidence expansion.**
   - Larger matched-budget real-model evaluations.
   - More comprehensive cross-controller frontier tables.

4. **Model-capacity expansion (conditional).**
   - Try heavier models only after target quality has improved.
   - Evaluate whether gains persist vs simpler stop-vs-act baselines.

5. **Advanced label construction (if still needed).**
   - Larger rollout-based label generation.
   - Oracle-assisted label construction for selected hard slices.

## Heavy-phase guardrail

Scale should follow target-quality improvements; it should not be the first remedy for proxy-label mismatch.
