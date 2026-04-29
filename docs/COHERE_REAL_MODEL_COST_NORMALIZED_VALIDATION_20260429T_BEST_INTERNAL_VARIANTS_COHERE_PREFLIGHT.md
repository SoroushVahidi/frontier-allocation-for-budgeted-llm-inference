# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260429T_BEST_INTERNAL_VARIANTS_COHERE_PREFLIGHT`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260429T_BEST_INTERNAL_VARIANTS_COHERE_PREFLIGHT --resume --max-examples 10 --target-scored-per-slice 10`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k']`
- Budgets: `[4]`
- Seeds: `[11]`
- Methods: `['strict_f3', 'strict_gate1_cap_k6', 'strict_f2', 'direct_reserve_semantic_frontier_v2', 'direct_reserve_semantic_frontier_v2_selection_fix_v1', 'direct_reserve_semantic_frontier_v2_thresholded_ordered', 'external_l1_max', 'tale', 's1', 'self_consistency_3']`
- Sample-size target per slice: `10` (max-examples cap `10`)

## Completion status
- Total expected slices: `10`
- Completed slices: `9`
- Incomplete slices: `1`
- Zero-record slices: `1`
- Per-provider completion counts:
  - cohere: 9/10
- Per-method completion counts:
  - direct_reserve_semantic_frontier_v2: 1/1
  - direct_reserve_semantic_frontier_v2_selection_fix_v1: 1/1
  - direct_reserve_semantic_frontier_v2_thresholded_ordered: 0/1
  - external_l1_max: 1/1
  - s1: 1/1
  - self_consistency_3: 1/1
  - strict_f2: 1/1
  - strict_f3: 1/1
  - strict_gate1_cap_k6: 1/1
  - tale: 1/1
- Per-dataset completion counts:
  - openai/gsm8k: 9/10

## Staged status
- Stage 1 (GSM8K): 9/10 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=direct_reserve_semantic_frontier_v2: mean_accuracy=0.7000, total_scored=10
- provider=cohere method=direct_reserve_semantic_frontier_v2_selection_fix_v1: mean_accuracy=0.6000, total_scored=10
- provider=cohere method=direct_reserve_semantic_frontier_v2_thresholded_ordered: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=external_l1_max: mean_accuracy=0.6000, total_scored=10
- provider=cohere method=s1: mean_accuracy=0.7000, total_scored=10
- provider=cohere method=self_consistency_3: mean_accuracy=0.4000, total_scored=10
- provider=cohere method=strict_f2: mean_accuracy=0.4000, total_scored=10
- provider=cohere method=strict_f3: mean_accuracy=0.5000, total_scored=10
- provider=cohere method=strict_gate1_cap_k6: mean_accuracy=0.5000, total_scored=10
- provider=cohere method=tale: mean_accuracy=0.5000, total_scored=10

## Token/latency/cost table
- provider=cohere method=direct_reserve_semantic_frontier_v2: total_tokens=11367, estimated_total_cost_usd=0.060969
- provider=cohere method=direct_reserve_semantic_frontier_v2_selection_fix_v1: total_tokens=11088, estimated_total_cost_usd=0.056844
- provider=cohere method=direct_reserve_semantic_frontier_v2_thresholded_ordered: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=external_l1_max: total_tokens=5210, estimated_total_cost_usd=0.028422
- provider=cohere method=s1: total_tokens=9875, estimated_total_cost_usd=0.045165
- provider=cohere method=self_consistency_3: total_tokens=17734, estimated_total_cost_usd=0.086682
- provider=cohere method=strict_f2: total_tokens=9260, estimated_total_cost_usd=0.045432
- provider=cohere method=strict_f3: total_tokens=8338, estimated_total_cost_usd=0.040638
- provider=cohere method=strict_gate1_cap_k6: total_tokens=8400, estimated_total_cost_usd=0.041568
- provider=cohere method=tale: total_tokens=5026, estimated_total_cost_usd=0.026838

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=evaluable, delta=-0.1, matched=10
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=evaluable, delta=0.0, matched=10
- provider=cohere best_frontier_vs_external_l1_max: status=evaluable, delta=-0.1, matched=10
- provider=cohere frontier_family_best_vs_self_consistency_3: status=evaluable, delta=0.1, matched=10

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **yes** (matched=10)
- If not, why not? **na_evaluable** (delta=-0.1)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=1, mixed=True)
- Under provider=cohere, does strict_f3 beat external_l1_max? **no_or_mixed** (delta=-0.1000, matched=10)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260429T_BEST_INTERNAL_VARIANTS_COHERE_PREFLIGHT/`
