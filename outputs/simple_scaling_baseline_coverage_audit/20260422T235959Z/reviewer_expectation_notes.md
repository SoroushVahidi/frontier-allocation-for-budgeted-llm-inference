# Reviewer expectation notes: simple scaling axis

- Reviewer expectation: include at least one direct, simple inference-time scaling comparator in the near-direct layer.
- Current package already includes `external_s1_budget_forcing` as a matched-substrate inference-time budget-forcing baseline.
- `self_consistency_3` is also present in canonical ranking artifacts as internal context for Best-of-N/self-consistency behavior.
- Therefore this pass keeps baseline scope minimal and avoids adding a redundant new direct baseline.

Claim boundary:
- Do not describe this as a full official s1 post-training reproduction; this is an inference-only adapter lane.