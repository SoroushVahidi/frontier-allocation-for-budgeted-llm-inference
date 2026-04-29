# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260428T222720Z`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260428T222720Z --resume --max-examples 2 --target-scored-per-slice 2`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k']`
- Budgets: `[4]`
- Seeds: `[11]`
- Methods: `['direct_reserve_semantic_frontier_v2', 'external_l1_max', 'strict_f3', 'strict_gate1_cap_k6', 'strict_f3_anti_collapse_weak_v1', 'tale', 's1']`
- Sample-size target per slice: `2` (max-examples cap `2`)

## Completion status
- Total expected slices: `7`
- Completed slices: `7`
- Incomplete slices: `0`
- Zero-record slices: `0`
- Per-provider completion counts:
  - cohere: 7/7
- Per-method completion counts:
  - direct_reserve_semantic_frontier_v2: 1/1
  - external_l1_max: 1/1
  - s1: 1/1
  - strict_f3: 1/1
  - strict_f3_anti_collapse_weak_v1: 1/1
  - strict_gate1_cap_k6: 1/1
  - tale: 1/1
- Per-dataset completion counts:
  - openai/gsm8k: 7/7

## Staged status
- Stage 1 (GSM8K): 7/7 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=direct_reserve_semantic_frontier_v2: mean_accuracy=0.5000, total_scored=2
- provider=cohere method=external_l1_max: mean_accuracy=1.0000, total_scored=2
- provider=cohere method=s1: mean_accuracy=0.5000, total_scored=2
- provider=cohere method=strict_f3: mean_accuracy=0.5000, total_scored=2
- provider=cohere method=strict_f3_anti_collapse_weak_v1: mean_accuracy=1.0000, total_scored=2
- provider=cohere method=strict_gate1_cap_k6: mean_accuracy=0.5000, total_scored=2
- provider=cohere method=tale: mean_accuracy=1.0000, total_scored=2

## Token/latency/cost table
- provider=cohere method=direct_reserve_semantic_frontier_v2: total_tokens=1836, estimated_total_cost_usd=0.009468
- provider=cohere method=external_l1_max: total_tokens=884, estimated_total_cost_usd=0.004644
- provider=cohere method=s1: total_tokens=1670, estimated_total_cost_usd=0.007902
- provider=cohere method=strict_f3: total_tokens=1639, estimated_total_cost_usd=0.008649
- provider=cohere method=strict_f3_anti_collapse_weak_v1: total_tokens=1626, estimated_total_cost_usd=0.008454
- provider=cohere method=strict_gate1_cap_k6: total_tokens=1637, estimated_total_cost_usd=0.008619
- provider=cohere method=tale: total_tokens=868, estimated_total_cost_usd=0.004644

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=evaluable, delta=-0.5, matched=2
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=evaluable, delta=0.0, matched=2
- provider=cohere best_frontier_vs_external_l1_max: status=evaluable, delta=-0.5, matched=2

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **yes** (matched=2)
- If not, why not? **na_evaluable** (delta=-0.5)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=0, mixed=True)
- Under provider=cohere, does strict_f3 beat external_l1_max? **no_or_mixed** (delta=-0.5000, matched=2)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260428T222720Z/`
