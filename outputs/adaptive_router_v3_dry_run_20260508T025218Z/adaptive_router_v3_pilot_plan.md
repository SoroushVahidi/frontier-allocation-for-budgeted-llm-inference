# Adaptive router v3 capped pilot plan

- Candidate set: cases routed to high-performing scaffolds only (`ratio_partition`, `state_composition`, `average_target_score`, `combinatorics_counting`).
- Exclude held-back percent-base cases for first pilot.
- Recommended call cap: 10-14 calls.
- Success criteria:
  - rescue both-wrong cases,
  - avoid worsening external_l1-only cases,
  - no gold leakage,
  - no over-triggering on easy/base-correct cases.
- If pilot is stable and positive, then consider re-enabling percent-base behind a strict flag after scaffold refinement.
