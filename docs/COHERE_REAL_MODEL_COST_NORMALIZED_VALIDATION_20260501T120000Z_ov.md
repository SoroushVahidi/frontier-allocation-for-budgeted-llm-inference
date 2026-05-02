# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260501T120000Z_ov`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260501T120000Z_ov --resume --max-examples 0 --target-scored-per-slice 4`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-a-03-2025', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k']`
- Budgets: `[4]`
- Seeds: `[20260501]`
- Methods: `['external_l1_max', 'direct_reserve_semantic_frontier_v2', 'direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1']`
- Sample-size target per slice: `4` (max-examples cap `0`)

## Completion status
- Total expected slices: `3`
- Completed slices: `3`
- Incomplete slices: `0`
- Zero-record slices: `0`
- Per-provider completion counts:
  - cohere: 3/3
- Per-method completion counts:
  - direct_reserve_semantic_frontier_v2: 1/1
  - direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1: 1/1
  - external_l1_max: 1/1
- Per-dataset completion counts:
  - openai/gsm8k: 3/3

## Staged status
- Stage 1 (GSM8K): 3/3 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=direct_reserve_semantic_frontier_v2: mean_accuracy=1.0000, total_scored=4
- provider=cohere method=direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1: mean_accuracy=1.0000, total_scored=4
- provider=cohere method=external_l1_max: mean_accuracy=1.0000, total_scored=4

## Token/latency/cost table
- provider=cohere method=direct_reserve_semantic_frontier_v2: total_tokens=13511, estimated_total_cost_usd=0.053757
- provider=cohere method=direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1: total_tokens=13546, estimated_total_cost_usd=0.054258
- provider=cohere method=external_l1_max: total_tokens=8361, estimated_total_cost_usd=0.033675

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=not_evaluable_zero_matched_examples, delta=NA, matched=0
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=not_evaluable_zero_matched_examples, delta=NA, matched=0

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **no** (matched=0)
- If not, why not? **not_evaluable_zero_matched_examples** (delta=NA)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **yes** (incomplete_slices=0, mixed=False)
- Under provider=cohere, does strict_f3 beat external_l1_max? **not_evaluable_zero_matched_examples** (matched=0)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260501T120000Z_ov/`
