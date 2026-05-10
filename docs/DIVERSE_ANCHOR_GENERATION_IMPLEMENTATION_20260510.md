# Diverse Anchor Generation Implementation (2026-05-10)

## Summary

This change adds the first **no-API scaffolding** for fixed-budget diverse prompt anchors. It does not claim a live accuracy gain and does not run any paid model calls. The implementation is intentionally minimal: it adds prompt-anchor definitions, fixed one-pass anchor execution hooks, candidate-pool metadata, support accounting, diversity/collapse metrics, and mocked tests so future live diagnostics can measure whether anchored generation improves gold-in-pool rate.

## Failure pattern targeted

The targeted pattern is the current gold-absent/candidate-generation bottleneck described in the handoff and failure-mining notes:

- many failures are not selection failures because the gold answer is absent from the candidate pool;
- fully tracked gold-absent cases commonly show frontier collapse or low answer diversity;
- collapse is especially visible in money/cost/revenue, multi-step arithmetic, and ratio/proportion/percentage cases.

The scaffolding therefore focuses on **early candidate-pool diversity**, not a new verifier or selector.

## Why Direct L1 Anchor alone is insufficient

The Direct L1 Anchor patch remains useful because it preserves a direct L1-style candidate in the selector pool and support counts. The effect audit showed it can increase diversity when available, but most gold-absent cases remain unresolved because the direct path is often also wrong. A single direct anchor is a floor, not a broad exploration strategy.

This implementation preserves the existing Direct L1 Anchor behavior while making it one member of a broader anchor family.

## Proposed diverse-anchor mechanism

When `enable_diverse_prompt_anchors=True`, the controller spends a fixed early budget across configured anchor IDs before allowing the remaining budget to flow into the frontier. The default scaffolded anchor IDs are:

1. `direct_l1_anchor`
2. `equation_first_anchor`
3. `unit_ledger_money_anchor`
4. `ratio_percentage_anchor`
5. `backward_check_anchor`

An optional `decomposition_anchor` is also defined for future inclusion.

Each anchor is a prompt style intended to induce a distinct reasoning family:

- direct L1/max-budget direct reasoning;
- equation-first setup;
- unit/entity ledger with money-specific wording;
- ratio/percentage base-denominator identification;
- backward/inverse check;
- decomposition into subgoals.

The initial runtime path is conservative:

- existing methods are unchanged unless the new flag is enabled;
- existing `direct_l1_anchor` support from `enable_direct_hybrid_seed` is reused rather than duplicated;
- each additional anchor consumes `diverse_prompt_anchor_budget_actions` actions, normally one mocked/model expansion;
- support counts are still grouped by normalized answer, so duplicate anchor answers increase support on one answer group rather than creating a new group.

## Exact files/functions changed

### `experiments/controllers.py`

Added:

- `DIVERSE_PROMPT_ANCHOR_SPECS`
- `DEFAULT_DIVERSE_PROMPT_ANCHOR_IDS`
- `compute_answer_group_entropy_from_counts`
- `DirectReserveFrontierGateController` constructor flags:
  - `enable_diverse_prompt_anchors`
  - `diverse_prompt_anchor_budget_actions`
  - `diverse_prompt_anchor_ids`
- `DirectReserveFrontierGateController._compose_diverse_prompt_anchor_question`
- `DirectReserveFrontierGateController._run_diverse_prompt_anchor_once`
- support-accounting integration for `diverse_anchor_records`
- selector-candidate metadata fields for anchor rows
- diversity/collapse metadata fields.

### `experiments/strategy_seeded_semantic_diversity_frontier_v1.py`

Added the method constant:

- `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor`

### `experiments/frontier_matrix_core.py`

Registered the no-API/runtime scaffold variant using the existing guarded K1/frontier4 frontier-tiebreak/direct-hybrid settings plus:

- `enable_diverse_prompt_anchors=True`
- `diverse_prompt_anchor_budget_actions=1`

### `tests/test_diverse_anchor_scaffolding_20260510.py`

Added mocked/no-API tests covering anchor metadata, answer-group diversity, duplicate-group support, collapse metadata, no API-key dependency, registry construction, and PAL conflict protection.

## Metadata added

Controller metadata now includes:

- `diverse_prompt_anchors_enabled`
- `diverse_prompt_anchor_ids_planned`
- `diverse_prompt_anchor_metadata`
- `per_anchor_support`
- `candidate_pool_answer_group_count`
- `answer_group_entropy`
- `frontier_collapse_detected`

Each selector-candidate row produced from an anchor includes:

- `anchor_id`
- `anchor_prompt_style`
- `source_family`
- `predicted_answer`
- `normalized_answer`
- `answer_group`
- `source_metadata`

Existing Direct L1 Anchor fields remain present:

- `direct_l1_anchor_present`
- `direct_l1_anchor_answer`
- `direct_l1_anchor_added_to_pool`
- `direct_l1_anchor_support_count`
- `direct_l1_anchor_selected`

## No-API tests added

The new tests use mocked/simulated generators only and do not require model API keys. They verify:

- diverse anchor IDs are present in `diverse_prompt_anchor_metadata` and candidate-pool rows;
- multiple anchors can create multiple answer groups;
- duplicate anchor answers increment support on an existing normalized answer group;
- `direct_l1_anchor` remains included and reuses existing direct-hybrid behavior;
- frontier-collapse metadata marks low-diversity candidate pools;
- registry construction works without API keys in simulated mode;
- strong PAL conflict protection still blocks a PAL takeover against an anchor/frontier-supported peer.

## Remaining risks

- These anchors are prompt scaffolds only; no live model accuracy claim is made.
- The budget split may reduce frontier expansion depth if too many anchors are enabled under a small total budget.
- Anchor prompts may be partly redundant on some problem types; future runs should stratify by problem type.
- `answer_group_entropy` is a simple support-count entropy metric, not a semantic diversity metric.
- No heavy PRM/process verifier is implemented; that remains a later extension.

## Later live/API diagnostic needed — do not run yet

A future approved live diagnostic should compare the existing direct-hybrid or production-equivalent line against the diverse-anchor variant on the same gold-absent/failure-focused slice.

Suggested budget estimate:

- 30 to 50 cases sampled from the latest gold-absent casebook;
- 5 anchored root calls per case at one action each;
- 150 to 250 additional model calls for anchor generation, plus existing controller calls for the matched baseline/variant;
- report only gold-in-pool rate, candidate answer-group count, answer-group entropy, collapse rate, and exact match under the existing selector/tiebreak contract.

No such live/API diagnostic was run in this change.
