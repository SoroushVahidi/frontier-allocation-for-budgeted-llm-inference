# Oracle label improvement result note (new-paper, 2026-04-14)

This pass stays on the **new-paper track** and focuses on improving
**approximate bounded oracle-ish continuation labels** (not exact global oracle truth).

## Run
- Main output root: `outputs/new_paper/oracle_label_improvement/20260414T153945Z/`

## Diagnosis of prior underperformance
From the bounded baseline diagnostic pass:
- Very high near-tie decision rate (`0.9167`).
- Very small top-branch margin (`0.0175`).
- Low dynamic spread in continuation values (`0.0774`).
- Strong one-feature dominance tendency (`0.8333` with |corr| >= 0.9).
- Weak rerun stability signal (cross-run value correlation `0.3635`).

Interpretation:
- The old oracle-ish labels were too tie-heavy and weakly separated,
  with unstable continuation values and low effective pairwise signal density.

## Bounded improvements implemented
1. **Rollout-value aggregation robustness**
   - Added `value_aggregation` option in oracle-ish label generation:
     - `max` (baseline)
     - `robust_blend` (improved): blend of q75/mean/median with std penalty.
2. **Uncertainty-aware pair conversion**
   - Added uncertainty-aware tie/confidence handling in pair construction,
     with effective-margin filtering for weak comparisons.

## Comparison summary
- Label quality improved:
  - near-tie rate: `0.9167 -> 0.4583`
  - mean top margin: `0.0175 -> 0.1364`
  - mean value spread: `0.0774 -> 0.3179`
  - one-feature dominance: `0.8333 -> 0.7500`
- But end task performance did **not** improve in this bounded run:
  - oracle-ish supervised vs proxy supervised delta accuracy:
    - baseline: `-0.0625`
    - improved: `-0.0625`

## Decision
- The improved construction made the labels cleaner by several diagnostics,
  but did not yet close the downstream gap in this bounded ablation.
- Oracle-ish supervision remains promising, but should remain a top-priority
  **diagnosis + calibration** direction rather than a scale-up-training direction right now.
