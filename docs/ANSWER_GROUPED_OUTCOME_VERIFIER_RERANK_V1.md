# Answer-Grouped Outcome-Verifier Rerank v1

Implemented `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1` building blocks in `experiments/answer_grouped_outcome_verifier.py`:
- candidate/verifier/group/decision dataclasses;
- candidate scoring with probability clipping, logit transform, major-error and inconsistency caps;
- answer grouping with per-source cap and support bonus;
- tie-break policy and representative-candidate selection;
- verifier protocol and deterministic mock verifier;
- strict prompt builder (no gold-answer exposure).

Paper-inspired direction:
- Cobbe-style outcome-verifier reranking signal;
- answer-group aggregation and self-consistency-like support bonus.

Not yet done in this change:
- no live Cohere outcome-verifier API backend;
- no 100-case Cohere validation run in this task.

Next real validation command (method-registration dependent):
`python scripts/run_cohere_real_model_cost_normalized_validation.py --providers cohere --datasets openai/gsm8k --budgets 4 --seeds 11 --methods direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1,external_l1_max --target-scored-per-slice 100 --timestamp <TS>`
