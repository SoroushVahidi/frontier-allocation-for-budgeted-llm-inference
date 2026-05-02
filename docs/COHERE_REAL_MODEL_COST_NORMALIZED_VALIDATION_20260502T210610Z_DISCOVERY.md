# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260502T210610Z_DISCOVERY`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260502T210610Z_DISCOVERY --resume --max-examples 88 --target-scored-per-slice 88`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-a-03-2025', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k']`
- Budgets: `[4, 6, 8]`
- Seeds: `[11, 23, 37, 41, 53, 67]`
- Methods: `['direct_reserve_semantic_frontier_v2']`
- Sample-size target per slice: `88` (max-examples cap `88`)

## Completion status
- Total expected slices: `18`
- Completed slices: `0`
- Incomplete slices: `18`
- Zero-record slices: `2`
- Per-provider completion counts:
  - cohere: 0/18
- Per-method completion counts:
  - direct_reserve_semantic_frontier_v2: 0/18
- Per-dataset completion counts:
  - openai/gsm8k: 0/18

## Staged status
- Stage 1 (GSM8K): 0/18 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=direct_reserve_semantic_frontier_v2: mean_accuracy=0.8461, total_scored=88

## Token/latency/cost table
- provider=cohere method=direct_reserve_semantic_frontier_v2: total_tokens=406594, estimated_total_cost_usd=1.629234

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=not_evaluable_zero_matched_examples, delta=NA, matched=0
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=not_evaluable_zero_matched_examples, delta=NA, matched=0

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **no** (matched=0)
- If not, why not? **not_evaluable_zero_matched_examples** (delta=NA)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=18, mixed=False)
- Under provider=cohere, does strict_f3 beat external_l1_max? **not_evaluable_zero_matched_examples** (matched=0)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260502T210610Z_DISCOVERY/`
