# External-L1-only routing-v2 failure analysis

## Why v2 helped both-wrong but not external-l1-only
- Most external_l1-only cases remain hard because failures are concentrated in base/no-retry carryover and percent-base semantics where v2 is still weak.
- Both-wrong rescues came from scaffolds that impose strong algebraic/state structure (ratio_partition, state_composition, average_target_score, combinatorics_counting).

## Shared external_l1-only pattern
- High concentration in known loss-bank discovery-style cases with ambiguous target/base mapping and under-triggered adaptive routing.

## Adaptive-feature-router relevance
- target quantity cues: needed to avoid intermediate-value outputs.
- number-role coverage: needed to map percent/base/subtotal roles robustly.
- unified error score: useful to decide when to escalate from base to specialized scaffold.
- possible intermediate stop: could suppress low-confidence outputs before final answer commit.

## Decision
- A) refine percent_base_denominator: yes (priority).
- B) implement adaptive feature router: yes (next major step).
- C) integrate only high-performing scaffolds: yes (ratio/state/average/combinatorics).
- D) run Stage 3 TALE/S1 exploratory: optional in parallel, not substitute for fixes.
- E) rerun Stage 2: after selective integration + percent-base refinement.

## Optional Cursor implementation query (do not execute now)
- "Implement adaptive routing feature scorer (target-cue + number-role coverage + confidence gate) and wire it only for targeted-retry trigger decisions under a strict allowlist."