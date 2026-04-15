# Oracle-distilled stop-vs-act matched-control evaluation protocol (pre-pilot readiness)

## Status and scope

This note defines the **operational evaluation gate** for oracle-distilled stop-vs-act runs before real pilot labels are available at scale. It is a readiness protocol, not an oracle-results claim.

## 1) Why naive filtered-vs-unfiltered is insufficient

Naive filtered-vs-unfiltered comparisons are confounded by at least three effects:

1. **Coverage effect**: fewer rows can change variance and class balance independent of label quality.
2. **Rate/compute effect**: a student can look better or worse mainly because it acts less/more often.
3. **Slice concentration effect**: apparent gains can come from easy regions while warning regions (especially uncertainty/disagreement) degrade.

Therefore, naive filtered-vs-unfiltered should not be used as a decision rule for the oracle-distillation phase.

## 2) Mandatory matched-coverage random control

For each selective oracle-distilled run family (at minimum accepted-only and accepted+borderline), comparisons must include a **random-filter baseline at matched retained coverage**:

- Same upstream pool definition.
- Same train/eval split logic.
- Same model family and optimization settings.
- Retained coverage matched within configured tolerance.

Pass/fail condition:
- If matched-coverage random is missing, the comparison is incomplete.

## 3) Mandatory ACT-rate / compute-rate checks

Each run must report:

- Predicted ACT-rate on eval rows (required now).
- Observed avg-actions/compute-rate if available from coupled controller eval (optional now, required for final promotion).

Pairwise control requirement:
- For selective-vs-random matched pairs, include ACT-rate gap and, when available, avg-actions gap.
- If rate mismatch exceeds tolerance, treat any quality claim as provisional pending matched-rate follow-up.
- Prefer matched-threshold comparisons at a declared target ACT-rate, with explicit residual mismatch reporting.
- Prefer a small shared matched-rate frontier summary in addition to one-point matched-rate checks.

## 4) Required slice breakdowns

Every compared run must include at least the following slice summaries:

1. **Uncertainty bins** (e.g., borderline vs non-borderline).
2. **Oracle-margin bins** (low / mid / high |gap|).
3. **Disagreement bins** (low/mid/high agreement-rate proxy).
4. **Remaining-budget bins** (low/mid/high remaining budget).

Interpretation rule:
- A global average gain with deterioration in warning slices (uncertainty/disagreement) is not sufficient for promotion.

## 4b) Required controller-behavior metrics when primitive gaps exist

When per-state `oracle_action_gap` (or contract-equivalent ACT-vs-STOP utility gap) is present,
evaluation outputs must report controller-behavior metrics:

- BAR (beneficial ACT rate),
- HAR (harmful ACT rate),
- HPSR (harmful premature STOP rate),
- BSR (beneficial STOP rate),
- oracle-action regret.

If the gap primitive is missing, summaries must mark behavior metrics as unavailable with explicit reason
instead of silently defaulting to zero.

## 5) Safe vs unsafe claims before real pilot results

### Safe now (after pipeline upgrade)

- The evaluation scaffold now enforces required control slots and slice reporting fields.
- The repository is structurally ready to run matched-control oracle-distilled comparisons once real labels arrive.

### Unsafe now

- Any statement that oracle-distillation improves controller quality.
- Any statement that selective filtering beats random in the oracle phase.
- Any final model-selection claim.

## Required run roles for oracle-phase comparisons

The comparison gate expects these role-tagged runs:

- `anchor_default`
- `oracle_distilled_accepted_only`
- `oracle_distilled_accepted_plus_borderline`
- `random_matched_coverage_baseline`

If any role is missing, mark readiness as incomplete.

## Minimal acceptance checklist (readiness)

A comparison pack is ready only if:

1. All required run roles are present.
2. Required slice keys are present for every run.
3. Pairwise selective-vs-random matched-coverage checks are emitted.
4. ACT-rate gaps are emitted (and avg-actions gaps when available).
5. Non-claim warnings remain active for mock/non-oracle provenance.
