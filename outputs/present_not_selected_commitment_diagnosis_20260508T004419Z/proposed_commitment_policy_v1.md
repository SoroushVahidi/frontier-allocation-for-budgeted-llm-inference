# Proposed commitment policy v1 (offline; gold used only in eval)

## Preconditions
- All signals below are **gold-free at runtime** except offline scoring.
- Apply only when PAL executed (`pal_exec_ok`) and parsed stdout exists.

## Rule A — Executable consistency flag
- Compute `executable_consistent` when normalized `pal_json_answer` matches normalized executable `stdout` (or single print output).
- If the committed/surfaced PAL answer disagrees with `stdout`, mark **surface_exec_mismatch**.

## Rule B — Overlay vs surface repair (Track B provenance)
- If `pal_overlay_previous_answer` is defined and differs from `pal_surfaced_normalized`, and overlay value appears as a peer in answer-group / branch metadata, prefer **re-surfacing overlay** when tie-break fired or when **surface_exec_mismatch** (see `override_overlay_prior_matches_tiebreak_conflicts_with_pal_stdout`).
- **Guards:** require histogram peer support ≥1 OR prior tie-break; abstain if ambiguous multi-peer tie (`gate_abstain_reason` patterns in `track_b_gate_offline_replay_targets.csv`).

## Rule C — Frontier tie-break peer vs pool gold
- When `frontier_tiebreak_triggered` and selected peer ≠ DR final leaf but an alternate leaf matches DR / pool, re-check branch scores; prefer peer aligned with executable DR if scores within epsilon.

## Rule D — Selector normalization / abstain
- When gold is flagged in tree but **not** in normalized selector pool (`gold_in_tree_but_not_in_selector_pool_normalized`), **abstain override** unless pool normalizer fixes bucket; do not promote PAL stdout blindly.

## Rule E — Histogram collapse guard
- When support histogram omits a pool candidate (`gold_in_pool_but_missing_from_answer_group_histogram`) or duplicate inflates a wrong group (`histogram_skew_duplicate_paths_favor_wrong_answer`), require **pool→histogram promotion pass** or cap duplicate branch weights before max-support commit.

## Rule F — Global abstain
- If executable consistency fails, parse ambiguity, or uniform multi-group tie with stdout off-manifold, abstain (mirror Track B abstain buckets).
