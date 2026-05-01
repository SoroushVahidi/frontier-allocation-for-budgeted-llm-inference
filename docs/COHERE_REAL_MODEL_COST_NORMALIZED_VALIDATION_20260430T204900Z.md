# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260430T204900Z`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260430T204900Z --resume --max-examples 0 --target-scored-per-slice 40`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k']`
- Budgets: `[4, 6, 8]`
- Seeds: `[11, 23, 37, 41, 53, 67]`
- Methods: `['direct_reserve_semantic_frontier_v2', 'external_l1_max']`
- Sample-size target per slice: `40` (max-examples cap `0`)

## Completion status
- Total expected slices: `36`
- Completed slices: `35`
- Incomplete slices: `1`
- Zero-record slices: `0`
- Per-provider completion counts:
  - cohere: 35/36
- Per-method completion counts:
  - direct_reserve_semantic_frontier_v2: 17/18
  - external_l1_max: 18/18
- Per-dataset completion counts:
  - openai/gsm8k: 35/36

## Staged status
- Stage 1 (GSM8K): 35/36 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=direct_reserve_semantic_frontier_v2: mean_accuracy=0.5994, total_scored=719
- provider=cohere method=external_l1_max: mean_accuracy=0.7222, total_scored=720

## Token/latency/cost table
- provider=cohere method=direct_reserve_semantic_frontier_v2: total_tokens=795483, estimated_total_cost_usd=4.159737
- provider=cohere method=external_l1_max: total_tokens=367144, estimated_total_cost_usd=2.011164

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=not_evaluable_zero_matched_examples, delta=NA, matched=0
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=not_evaluable_zero_matched_examples, delta=NA, matched=0

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **no** (matched=0)
- If not, why not? **not_evaluable_zero_matched_examples** (delta=NA)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=1, mixed=False)
- Under provider=cohere, does strict_f3 beat external_l1_max? **not_evaluable_zero_matched_examples** (matched=0)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260430T204900Z/`
