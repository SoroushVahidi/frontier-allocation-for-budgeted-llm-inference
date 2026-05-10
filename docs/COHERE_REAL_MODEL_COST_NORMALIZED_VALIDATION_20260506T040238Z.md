# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260506T040238Z`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260506T040238Z --resume --max-examples 240 --target-scored-per-slice 240`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-a-03-2025', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k']`
- Budgets: `[6]`
- Seeds: `[20260501]`
- Methods: `['external_l1_max', 'direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal']`
- Sample-size target per slice: `240` (max-examples cap `240`)

## Completion status
- Total expected slices: `2`
- Completed slices: `1`
- Incomplete slices: `1`
- Zero-record slices: `0`
- Per-provider completion counts:
  - cohere: 1/2
- Per-method completion counts:
  - direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal: 0/1
  - external_l1_max: 1/1
- Per-dataset completion counts:
  - openai/gsm8k: 1/2

## Staged status
- Stage 1 (GSM8K): 1/2 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal: mean_accuracy=0.8571, total_scored=140
- provider=cohere method=external_l1_max: mean_accuracy=0.7917, total_scored=240

## Token/latency/cost table
- provider=cohere method=direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal: total_tokens=374577, estimated_total_cost_usd=1.550235
- provider=cohere method=external_l1_max: total_tokens=631902, estimated_total_cost_usd=2.476530

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
- `outputs/cohere_real_model_cost_normalized_validation_20260506T040238Z/`
