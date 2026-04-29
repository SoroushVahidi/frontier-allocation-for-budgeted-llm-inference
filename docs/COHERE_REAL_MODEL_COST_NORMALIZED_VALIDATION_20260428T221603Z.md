# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260428T221603Z`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260428T221603Z --resume --max-examples 2 --target-scored-per-slice 2`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k', 'HuggingFaceH4/MATH-500']`
- Budgets: `[4]`
- Seeds: `[11]`
- Methods: `['direct_reserve_semantic_frontier_v2', 'external_l1_max', 'strict_f3', 'strict_gate1_cap_k6', 'strict_f3_anti_collapse_weak_v1', 'tale', 's1']`
- Sample-size target per slice: `2` (max-examples cap `2`)

## Completion status
- Total expected slices: `14`
- Completed slices: `12`
- Incomplete slices: `2`
- Zero-record slices: `2`
- Per-provider completion counts:
  - cohere: 12/14
- Per-method completion counts:
  - direct_reserve_semantic_frontier_v2: 0/2
  - external_l1_max: 2/2
  - s1: 2/2
  - strict_f3: 2/2
  - strict_f3_anti_collapse_weak_v1: 2/2
  - strict_gate1_cap_k6: 2/2
  - tale: 2/2
- Per-dataset completion counts:
  - HuggingFaceH4/MATH-500: 6/7
  - openai/gsm8k: 6/7

## Staged status
- Stage 1 (GSM8K): 6/7 slices completed.
- Stage 2 (MATH-500): 6/7 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=direct_reserve_semantic_frontier_v2: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=external_l1_max: mean_accuracy=0.7500, total_scored=4
- provider=cohere method=s1: mean_accuracy=0.2500, total_scored=4
- provider=cohere method=strict_f3: mean_accuracy=0.7500, total_scored=4
- provider=cohere method=strict_f3_anti_collapse_weak_v1: mean_accuracy=0.2500, total_scored=4
- provider=cohere method=strict_gate1_cap_k6: mean_accuracy=0.5000, total_scored=4
- provider=cohere method=tale: mean_accuracy=0.7500, total_scored=4

## Token/latency/cost table
- provider=cohere method=direct_reserve_semantic_frontier_v2: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=external_l1_max: total_tokens=2350, estimated_total_cost_usd=0.012294
- provider=cohere method=s1: total_tokens=4431, estimated_total_cost_usd=0.020421
- provider=cohere method=strict_f3: total_tokens=4313, estimated_total_cost_usd=0.020859
- provider=cohere method=strict_f3_anti_collapse_weak_v1: total_tokens=3804, estimated_total_cost_usd=0.018888
- provider=cohere method=strict_gate1_cap_k6: total_tokens=4332, estimated_total_cost_usd=0.023148
- provider=cohere method=tale: total_tokens=2355, estimated_total_cost_usd=0.012885

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=evaluable, delta=0.0, matched=4
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=evaluable, delta=0.25, matched=4
- provider=cohere best_frontier_vs_external_l1_max: status=evaluable, delta=0.0, matched=4

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **yes** (matched=4)
- If not, why not? **na_evaluable** (delta=0.0)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=2, mixed=True)
- Under provider=cohere, does strict_f3 beat external_l1_max? **no_or_mixed** (delta=+0.0000, matched=4)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260428T221603Z/`
