# Oracle-distilled matched-rate frontier evaluation protocol (pre-HPC readiness)

## Status

This note defines an evaluation-readiness extension beyond single-point matched ACT-rate comparison.
It does not run heavy oracle-label generation and does not support oracle-phase performance claims.

## 1) Why one matched ACT-rate point is still insufficient

A single matched ACT-rate point can be unstable as a decision criterion:

- ranking can flip across nearby rates,
- one selected target may over/under-emphasize particular state regions,
- policy tradeoffs (BAR/HAR/HPSR/BSR/regret) can change non-uniformly with intervention rate.

Therefore one-point matching should remain, but not be the only comparison object.

## 2) Why a matched-rate frontier is a better object

A small shared frontier compares controllers over multiple comparable intervention budgets.
This reduces sensitivity to one operating point and better reflects policy robustness.

Operational interpretation:

- if a selective policy only wins at one narrow rate, evidence is weaker,
- if it wins across most shared rates (with acceptable mismatch), evidence is stronger.

## 3) Required frontier outputs

For each compared run family, report:

1. **Quality vs matched ACT-rate** (accuracy/AUC/Brier over shared grid).
2. **Behavior metrics vs matched ACT-rate** (BAR/HAR/HPSR/BSR/regret when available).
3. **Optional compute-rate frontier diagnostics** (availability and mismatch reporting when observed compute fields exist).
4. **Pairwise selective-vs-random deltas across frontier**.
5. **Compact summaries**:
   - mean delta across available frontier points,
   - win counts across frontier points,
   - optional AUC-style integral of deltas over the shared rate axis,
   - average residual mismatch.

## 4) Shared ACT-rate grid selection

Preferred order:

1. User-specified grid (explicit comma-separated ACT-rate targets).
2. Automatic anchor-derived grid from anchor threshold sweep.
3. Fallback to one-point target if anchor sweep unavailable.

Automatic grid rule:

- choose a small deterministic subset of anchor sweep ACT-rates (e.g., 5 points) spread across the range,
- use nearest threshold point per run at each target,
- record per-point residual mismatch.

## 5) Safe vs unsafe claims before real oracle outputs

### Safe

- The pipeline now supports one-point and frontier matched-rate diagnostics.
- Frontier deltas and compact summaries can be computed structurally.
- Residual mismatch and missingness are explicit.

### Unsafe

- Claiming oracle-distilled superiority from mock/proxy runs.
- Claiming causal policy improvement without validated pilot labels.
- Declaring final promotion from one-point or frontier metrics alone before real oracle-phase evidence.

## 6) Guardrails

- Preserve non-claim markers for mock/non-oracle provenance.
- Treat smoke tests as structural validation only.
- Require real oracle pilot outputs for substantive scientific claims.
