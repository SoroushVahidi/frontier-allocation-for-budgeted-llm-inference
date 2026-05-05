# UNIT-TRACK Status (2026-05-05)

## Method ID
`direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_unit_track`

## Status
Optional diagnostic variant (not default).

## Motivation
Targeted to A7 unit/entity interpretation issues from the `l1_loss_subtype_branch_quality_audit_29_20260505T142227Z` run.

## Implementation summary (gold-free runtime)
- Unit/entity ledger branch that runs a `unit_track_seed` stage and produces:
  - unit/entity tracking metadata (`unit_consistency_status`, `unit_consistency_notes`, `unit_tracked_answer`, etc.)
  - a conservative unit overlay decision based on runtime ledger completeness + numeric parseability.
- Conservative overlay promotes the unit-track candidate only under strict, auditable non-gold conditions.
- Gate metadata is recorded in `unit_track_overlay`:
  - `unit_track_gate_enabled`, `unit_track_gate_triggered`, `unit_track_gate_reason`
  - `unit_track_gate_previous_answer`, `unit_track_gate_selected_answer`
  - `unit_track_gate_blocked_reason`, `unit_track_gate_candidate_strength`
  - `unit_track_gate_frontier_conflict`

## Tests passed
- `tests/test_unit_track_variant.py`
- `tests/test_api_branch_generator_json_parsing.py`
- `tests/test_output_layer_frontier_surfacing.py`
- `tests/test_guarded_k1_frontier4_method.py`

## Empirical evidence (A7 only; no external claims)
- `outputs/cohere_unit_track_live_smoke_A7_5case_20260505T150059Z/`
  - net vs prior k1/tiebreak: `+1/0`
- `outputs/cohere_unit_track_A7_13case_20260505T151052Z/`
  - exact: `1/13`
  - net vs prior k1/tiebreak: `+1/0`
  - deterministic gate replay (offline): `outputs/offline_unit_track_gate_replay_A7_13case_20260505T151052Z/`
    - baseline exact `1/13`, gated exact `1/13` (net `0/0`)

## Interpretation
UNIT-TRACK is safe but empirically weak on this slice:
- It is conservative and auditable, and we see small positive lift on A7 in the completed runs.
- The main bottleneck remains candidate generation / branch quality (not the final selection gate).

## Next recommendation
Park UNIT-TRACK for now and focus on stronger branch templates / candidate generation improvements (e.g., equation-first or decomposition-first candidate families).

## Claim boundary
Do not claim broad accuracy improvement or closure of the `external_l1_max` gap. UNIT-TRACK here is preserved for diagnostics/tooling rather than as a guaranteed improvement lever.

