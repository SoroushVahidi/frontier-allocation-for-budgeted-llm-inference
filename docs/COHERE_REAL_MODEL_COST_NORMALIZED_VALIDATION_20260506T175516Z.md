# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260506T175516Z`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260506T175516Z --resume --max-examples 11 --target-scored-per-slice 11`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-a-03-2025', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k']`
- Budgets: `[6]`
- Seeds: `[20260501]`
- Methods: `['direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal']`
- Sample-size target per slice: `11` (max-examples cap `11`)

## Completion status
- Total expected slices: `1`
- Completed slices: `1`
- Incomplete slices: `0`
- Zero-record slices: `0`
- Per-provider completion counts:
  - cohere: 1/1
- Per-method completion counts:
  - direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal: 1/1
- Per-dataset completion counts:
  - openai/gsm8k: 1/1

## Staged status
- Stage 1 (GSM8K): 1/1 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal: mean_accuracy=0.2727, total_scored=11

## Token/latency/cost table
- provider=cohere method=direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal: total_tokens=34604, estimated_total_cost_usd=0.147396

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
- `outputs/cohere_real_model_cost_normalized_validation_20260506T175516Z/`
