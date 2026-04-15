# Oracle-distilled matched-ACT-rate / matched-compute-rate evaluation protocol (pre-HPC readiness)

## Status

This protocol is an evaluation-readiness upgrade. It adds matched-rate comparison mechanics without running heavy oracle-label generation.

## 1) Why native-threshold comparisons are insufficient

Comparing controllers only at each run's native threshold is confounded by intervention intensity:

- one model may appear better primarily because it ACTs less,
- another may appear better primarily because it ACTs more.

Therefore native-threshold quality metrics are diagnostic, but not sufficient for controller promotion decisions.

## 2) Why matched-rate views are necessary

The stop-vs-act model is a budgeted policy. Comparisons should hold spend approximately constant:

- **matched predicted ACT-rate** (required),
- **matched observed avg-actions / compute-rate** (when available).

This turns comparisons into "quality at comparable intervention budget" rather than "quality at arbitrary thresholds".

## 3) What must be matched

For a valid matched-rate comparison:

1. Same evaluation pool.
2. Comparable retained-coverage controls already required by protocol.
3. Threshold-calibrated ACT-rate matching against a declared target ACT-rate.
4. If observed avg-actions exist, report compute-rate mismatch and pass/fail tolerance.

Target ACT-rate selection policy:

- use user-specified target if provided,
- otherwise use anchor-default native predicted ACT-rate,
- fallback to mean native ACT-rate only if anchor is absent.

## 4) Required outputs

Outputs must include:

1. **Matched ACT-rate point per run** (selected threshold, achieved ACT-rate, residual mismatch).
2. **Quality at matched ACT-rate** (accuracy/AUC/Brier).
3. **Behavior metrics at matched ACT-rate** (BAR/HAR/HPSR/BSR/regret when primitive available).
4. **Selective-vs-random deltas at matched ACT-rate**.
5. **Matched compute-rate report** when observed avg-actions are present.

Approximate match rule:

- choose deterministic nearest-threshold point from each run's threshold sweep,
- report absolute residual and tolerance pass/fail.

## 5) Safe vs unsafe claims (before real pilot results)

### Safe

- The pipeline can now emit native-threshold and matched-rate views.
- Residual mismatch and availability are explicitly reported.
- Matched-rate selective-vs-random deltas can be computed structurally.

### Unsafe

- Claiming oracle-distilled superiority from mock/proxy runs.
- Claiming causal benefit without real validated oracle pilot labels.
- Promoting a controller solely from native-threshold metrics when matched-rate views disagree.

## 6) Guardrails

- Keep non-claim markers active for mock/non-oracle provenance.
- Treat smoke tests as structural plumbing checks only.
- Defer substantive conclusions to real oracle-phase runs.
