# Direct Reserve v2 Thresholded+Ordered Local Validation (2026-04-28)

## Scope and constraints

This validation is local/offline only:

- No Cohere calls.
- No Slurm jobs.
- No long experiment runs.
- Canonical methods (`strict_f3`, `strict_f2`, `strict_gate1_cap_k6`, `external_l1_max`) were not modified.

## What was validated

1. **Method identity and scope**
   - Method name is exactly `direct_reserve_semantic_frontier_v2_thresholded_ordered`.
   - Method is registered in diagnostic strategy wiring and marked diagnostic-only metadata.

2. **Route structure**
   - Confirmed v2 route decisions include:
     - `stop_with_incumbent`
     - `one_more_direct_continuation`
     - `limited_frontier_challenge`

3. **Threshold wiring and behavior**
   - `commit_threshold` affects early-stop route.
   - `continuation_threshold` now affects challenger compute *before frontier expansion* (pre-frontier continuation gate).
   - `replacement_threshold` affects challenger replacement decision.

4. **Replacement and source metadata**
   - Verified cases where challenger is blocked from replacing incumbent.
   - Verified cases where parseable challenger replaces empty/unparseable incumbent.
   - Verified metadata fields include `route_decision`, `continuation_value`, `final_source`, `frontier_actions_used`, `direct_actions_used`.

## Lightweight checks executed

- `python -m compileall experiments scripts`
- `pytest -q tests/test_semantic_diversity_direct_reserve_v2_thresholded_ordered.py`
- `python scripts/check_thresholded_ordered_v2_behavior.py`

## Local behavior summary (script output)

Output artifacts:

- `outputs/local_thresholded_ordered_v2_behavior/behavior_summary.csv`
- `outputs/local_thresholded_ordered_v2_behavior/behavior_summary.md`

Compact local conclusions:

- v2 **does stop early** on strong incumbent cases.
- v2 **does open frontier** on weak/empty incumbent cases.
- v2 uses **fewer actions than v1** in easy direct-answer cases in this synthetic diagnostic.
- Weak challengers are prevented from replacing a stronger incumbent in the stress cases.
- Parseable challengers can replace empty incumbents when frontier opens.

## Routes observed locally

Observed in unit tests and script scenarios:

- `stop_with_incumbent`
- `one_more_direct_continuation`
- `limited_frontier_challenge`

## Early commit status

Early commit path is active via `commit_threshold` when incumbent confidence is high under low uncertainty.

## Continuation-threshold timing

Current v2 computes a pre-frontier continuation signal (`continuation_value_pre_frontier`) and can block frontier expansion when this value is below `continuation_threshold`.

Therefore continuation threshold is **not only post-hoc metadata** in current local validation.

## Replacement-threshold status

Replacement is not unconditional; v2 keeps incumbent unless challenger evidence clears replacement logic. Local tests confirm both keep and replace outcomes.

## Bugs found/fixed in this local pass

- Fixed: continuation threshold previously did not gate frontier expansion early enough for compute savings.
  - Added pre-frontier continuation scoring and threshold gate.
  - Added metadata `continuation_value_pre_frontier`.

## Is v2 ready for a small Wulver Cohere run?

**Tentative yes (small diagnostic run only).**

Rationale:

- Thresholds now affect behavior (not only logging) in local tests.
- Action reduction behavior is visible in compact synthetic cases.
- Route and source diagnostics are available for audit.

## Remaining risks

- Synthetic/offline scenarios can overestimate stability; real-provider disagreement patterns may differ.
- The continuation proxy is heuristic and may need re-calibration on real Cohere traces.
- Family maturation counts are still partly metadata-driven and should be rechecked with real semantic-family distributions.
