# Probabilistic branch-value allocation status (2026-04-17)

## Objective

Bounded go/no-go experiment: test whether probabilistic value-based branch choice improves hard close-branch behavior enough to justify continuing, without unacceptable damage to accepted accuracy.

## Pre-implementation insertion-point summary

Cleanest insertion points found before coding:

1. **Existing branch-value targets and predicted branch values**
   - `scripts/run_branch_value_uncertainty_strict_validation_pass.py` already fits branch-level value (`estimated_value_if_allocate_next`) and a residual-risk head from candidate tables.
   - It populates per-pair `pred_value_i/pred_value_j` via candidate lookup with no target-schema changes required.

2. **Current compare/defer conversion logic**
   - `_apply_variant(..., variant="full_method")` in `scripts/run_branch_value_uncertainty_strict_validation_pass.py` is the canonical value+uncertainty defer conversion path.
   - This is the minimal place to preserve baseline behavior and add alternate commit policies around it.

3. **Minimal-disruption place to add probabilistic policy**
   - New bounded runner added at `scripts/run_probabilistic_branch_value_allocation_experiment.py`.
   - It reuses the same candidate/pair tables and value/risk training path, then swaps only the pair decision policy.

4. **Existing strict validation / matched evaluation harnesses**
   - Reused canonical regime roots and matched seeds from strict validation conventions.
   - Reused validation-threshold tuning for baseline canonical mode, then evaluated all modes on matched test rows.

## Modes tested

1. `baseline_canonical`
   - Unchanged canonical value + uncertainty defer behavior with tuned `(gap_threshold, z_threshold)`.

2. `deterministic_value_top1`
   - Forced top-1 by predicted value sign (`pred_value_i - pred_value_j`), no defer.

3. `probabilistic_value_choice`
   - Forced stochastic branch choice, no defer.

4. `probabilistic_value_choice_temperature_sweep`
   - Tiny bounded grid: `T in {0.50, 0.75, 1.00}`.

## Probability rule and stability

For branch values `v_i, v_j`:

- `p(i | v_i, v_j, T) = clip( exp(v_i / T) / (exp(v_i / T) + exp(v_j / T)), eps, 1-eps )`
- with `T > 0` temperature, `eps = 1e-6`.

Why this rule:

- Safer than direct `A/(A+B)` on raw values that can be negative or poorly scaled.
- Stable softmax implementation (`subtract max-logit`) avoids overflow.
- Clipping prevents exact `0/1` probabilities and keeps entropy finite.

## Commands run

See machine note:
- `outputs/branch_label_bruteforce_learning/probabilistic_branch_value_allocation_20260417/probabilistic_branch_allocation_commands_and_caveats.md`

## Main metrics (aggregate over matched regimes × seeds)

### Core mode summary

- **baseline_canonical**
  - accepted accuracy: **0.9333**
  - coverage: **0.2698**
  - defer rate: **0.7302**
  - near-tie accepted accuracy: **0.0000**
  - adjacent-rank accepted accuracy: **0.8889**

- **deterministic_value_top1**
  - accepted accuracy: **0.5952**
  - coverage: **1.0000**
  - defer rate: **0.0000**
  - near-tie accepted accuracy: **0.2000**
  - adjacent-rank accepted accuracy: **0.4794**

- **probabilistic_value_choice (T=0.75)**
  - accepted accuracy: **0.4563**
  - coverage: **1.0000**
  - defer rate: **0.0000**
  - near-tie accepted accuracy: **0.2556**
  - adjacent-rank accepted accuracy: **0.4317**
  - mean selection entropy: **0.6917 nats**

### Delta summaries

- **probabilistic vs baseline canonical**
  - Δ accepted accuracy: **-0.4770**
  - Δ coverage: **+0.7302**
  - Δ defer rate: **-0.7302**
  - Δ near-tie accepted accuracy: **+0.2556**
  - Δ adjacent-rank accepted accuracy: **-0.4571**

- **probabilistic vs deterministic top-1**
  - Δ accepted accuracy: **-0.1389**
  - Δ near-tie accepted accuracy: **+0.0556**
  - Δ adjacent-rank accepted accuracy: **-0.0476**

### Temperature sweep (bounded)

Across `T=0.50, 0.75, 1.00`:
- accepted accuracy remained **0.4563** in this bounded run,
- near-tie accepted accuracy remained **0.2556**,
- entropy changed only slightly (**0.6899 -> 0.6923 nats**).

## Required evaluation questions

A. **Close-branch/near-tie behavior:** improved versus deterministic top-1 and baseline accepted slice (near-tie +0.0556 vs top-1, +0.2556 vs baseline), but baseline has low near-tie accepted coverage due to deferral.

B. **Over-deferral / brittle forced choices:** probabilistic mode removes defer by construction (coverage 1.0), but this comes with large quality loss.

C. **Preserve accepted accuracy:** **No**. Accepted accuracy drops sharply relative to baseline canonical (0.4563 vs 0.9333).

D. **Justify continuation:** **No** for this variant. Gains in near-tie slice are not credible enough given severe core accepted-accuracy damage.

## Hard conclusion

**Drop this direction in its current forced stochastic form.**

This bounded test mostly adds randomness and recovers coverage by removing defer, but causes unacceptable deterioration in core accepted accuracy and adjacent-rank quality. The result is mixed at best on hard slices and clearly negative on overall accepted quality, so it does not clear the repository’s continue bar.

## Artifacts

- Run directory:
  - `outputs/branch_label_bruteforce_learning/probabilistic_branch_value_allocation_20260417/`
- Machine-readable outputs:
  - config/manifest,
  - per-seed summary,
  - matched summary by mode,
  - aggregate comparison,
  - bounded temperature sweep summary,
  - commands/assumptions/caveats note.
