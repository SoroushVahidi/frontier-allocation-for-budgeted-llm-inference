# Literature Selector Baselines

## Self-consistency majority vote

- **Source:** Wang et al., *Self-Consistency Improves Chain of Thought Reasoning in Language Models* (ICLR 2023).
- **Implementation in this repo:**
  - existing candidate pool only (no new sampling)
  - GSM8K numeric normalization
  - unweighted majority vote on normalized final numeric answer
  - first-occurrence tie-break in candidate order
  - no verifier/search/gold/evaluation-only features at decision time
- **Caveats:**
  - original method samples multiple paths; this selector-only baseline reuses existing tree candidates
  - invalid/tie handling is deterministic implementation detail
  - this is a literature baseline, not a new selector contribution

## Same-pilot comparison: self-consistency vs Cohere outcome-verifier

- Attempted apples-to-apples comparison on the pilot slice (`max_examples=50`) with shared paired records.
- On this branch snapshot, full Cohere merged score cache for that exact slice is not fully available in committed artifacts, so strict full-coverage validation is blocked.
- Recommendation on this evidence: retain self-consistency as a literature baseline; keep Cohere as current selected selector until a full-coverage same-pilot rerun is available.
- Caveat: bounded pilot evidence and cache availability constraints.
