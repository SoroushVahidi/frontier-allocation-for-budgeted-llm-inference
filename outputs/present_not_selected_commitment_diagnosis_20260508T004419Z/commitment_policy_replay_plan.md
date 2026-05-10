# Commitment policy offline replay plan (next implementation step)

## Positive targets (PNS / commitment failures)
- **Full PNS replay inventory (23):** listed in `present_not_selected_replay_report.md` §A.
- **Track B proved fixes:** `openai_gsm8k_1087`, `openai_gsm8k_1279`, `openai_gsm8k_1290` (see `track_b_gate_offline_replay_targets.csv`).
- **Still-wrong / abstained under offline gate (20 rows):** all `outcome_tag=unchanged_still_wrong` in `track_b_gate_offline_replay_targets.csv`.
- **Extra union case without replay row:** `openai_gsm8k_851` (needs trace export).

## Regression guardrails (already-correct cohorts)
- **Both PAL and best-external correct:** 183 rows on band 1072–1318 (`present_not_selected_replay_report.md` §E).
- **PAL-only wins:** 5 rows — high priority no-regress.
- Reuse counters in `counterfactual_policy_summary.csv`; `prefer_strong_pal_executable` showed lowest both-correct regressions (1) in §E table.

## Implementation files / scripts to inspect
- **`experiments/output_layer_repair.py`** — `decide_track_b_overlay_commitment_gate`.
- **`experiments/controllers.py`** — integration around line ~8236 (`enable_track_b_overlay_commitment_gate`).
- **`scripts/replay_track_b_commitment_gate.py`** — offline replay harness.
- **`tests/test_track_b_overlay_commitment_gate.py`**.
- Offline audits: `scripts/track_a_discovery_diagnostics.py`, `scripts/pal_code_static_audit.py`.
- Validation runner: `scripts/run_cohere_real_model_cost_normalized_validation.py`.

## Suggested method id
- `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1`

## Estimated impact (offline; not executed here)
| Rule | PNS rows likely touched | Cannot fix alone (from §D2 report) | Track B overlap | Regression note |
|------|-------------------------|-------------------------------------|-----------------|-----------------|
| B overlay/surface | 16 (`primary_commitment_mechanism` count) | Histogram-only losses (e.g. 1083, 1085) | 3 proved fixes | Medium — mirror §E regressions for max-support style |
| C tie-break peer | 3 | Ambiguous multi-peer ties | partial | Medium |
| D normalize/abstain | 2 + ambiguous rows | Requires schema fix | abstain-safe | Low |
| E histogram repair | 2 | Needs dedup policy | none | High — duplicate inflation |

## Next step
1. Implement Rule A+B behind feature flag on method id above. 2. Replay 23 PNS + 183 guardrail IDs offline. 3. Expand to union case 851 with exported replay row.
