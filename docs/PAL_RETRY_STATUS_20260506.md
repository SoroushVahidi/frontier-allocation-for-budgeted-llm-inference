# PAL Retry-on-Empty-Code Status (2026-05-06)

## Motivation

The cumulative external-only loss audit isolated a dominant actionable failure mode where PAL emits no usable executable code payload. The retry-on-empty-code patch targets this specific gap by allowing one guarded regeneration attempt only when the first PAL attempt is empty or non-executable.

## External-Only Evidence (31 Cases)

- `L1_P1_code_absent`: 14
- `L1_P9_external_trace_advantage_unknown`: 10
- `L1_P5_correct_candidate_not_selected`: 4
- `L1_P2_unsafe_code`: 1
- `L1_P3_exec_failed`: 1
- `L1_P4_exec_succeeded_wrong`: 1

Code-absence (`L1_P1`) is the largest actionable bucket.

## Targeted Retry Evidence

- Retry-eligible from 31-case audit: 16/31
- Retry-eligible among `L1_P1`: 14/14

Live targeted retry reevaluation:

- Smoke (5 cases): retry ran 4/5, fixes 3, breaks 0
- Follow-up (11 cases): retry ran 4/11, fixes 3, breaks 0
- Aggregate (16 evaluated): fixes 6, breaks 0, net +6
- Aggregate retry exec-OK rate: 0.375

## Budget Semantics

- Retry is only considered for PAL-enabled method variants.
- Retry runs only when the first PAL attempt has empty or non-executable code.
- Retry consumes one frontier slot.
- Total budget remains fixed; no budget expansion is introduced.

## Runtime Safety Boundaries

- Retry execution reuses existing PAL sandbox and overlay logic.
- Runtime policy keeps disallowed operations blocked (including imports/files/network/eval/exec/open per PAL safety constraints).
- Gold/evaluation fields are for offline analysis only and are not used in runtime decision logic.

## Claim Boundaries

- This is targeted evidence on retry-eligible external-only losses, not an unbiased global estimate.
- No claim is made that PAL+retry globally beats `external_l1_max` yet.
- The fresh 100-case paired PAL vs external result is promising (+5 pp) but statistically non-decisive.

## Next Step After Merge

Run a fresh paired PAL+retry vs `external_l1_max` validation to measure net impact in an unbiased paired setting.
