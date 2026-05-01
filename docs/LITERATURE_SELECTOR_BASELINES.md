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
