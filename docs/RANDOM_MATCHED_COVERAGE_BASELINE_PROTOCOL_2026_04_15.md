# Random matched-coverage baseline protocol for oracle-distilled stop-vs-act (pre-HPC readiness)

## Purpose

This protocol defines how to generate random matched-coverage baselines for selective oracle distillation so that future comparisons can satisfy mandatory control gates.

## 1) Why random matched-coverage is necessary

Selective retention can change outcomes for reasons unrelated to supervision quality (coverage reduction, class mix shifts, easy-region concentration). A random baseline with the same retained coverage is required to isolate whether selective policies add value beyond simply keeping fewer rows.

## 2) What must be matched

For each selective regime, baseline generation must match:

1. **Retained coverage on the train pool** (`retained_rows / train_pool_rows`).
2. **Regime target**:
   - `accepted_only`
   - `accepted_plus_borderline`
3. **Source pool identity**: random baseline must be sampled from the exact same source distillation-ready train pool.
4. **Optional stratification dimensions** (when requested): bucket and/or budget.

## 3) Sampling rule (operational)

Given source train pool `P` and target regime retained count `K`:

1. Compute `K` from the selective regime on the same pool.
2. Sample `K` rows uniformly at random from `P` using deterministic seed.
3. If stratification is enabled, allocate per-stratum quotas from selective counts, sample within each stratum, and deterministically correct any remainder.
4. Mark selected train rows via `selected_for_training=1`; all other train rows get `0`.

## 4) What must remain identical between selective and random baselines

- Same distillation-ready source rows.
- Same split definitions (`train`/`test`).
- Same student model family, optimizer settings, thresholding, and evaluation pipeline.
- Same role/reporting expectations in comparison outputs (coverage, ACT/compute-rate, required slices).

Only the training-row selection rule should differ.

## 5) Safe vs unsafe claims after implementing this path (before real pilot labels)

### Safe

- The repository can now generate regime-specific random matched-coverage baselines (including accepted-only).
- Structural readiness can be tested end-to-end for coverage-matching controls.

### Unsafe

- Any claim that oracle-distilled selective policies outperform random baselines.
- Any claim about final oracle-phase model superiority.
- Any causal conclusion from mock/non-oracle smoke outputs.

## Required artifact metadata

Each generated random baseline must emit summary metadata with:

- `target_regime`
- `train_pool_rows`
- `regime_selected_rows`
- `retained_rows`
- `retained_coverage`
- `random_seed`
- stratification settings/quotas when used
- non-claim warning
