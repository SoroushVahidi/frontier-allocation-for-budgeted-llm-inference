# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260429T_CODEX_LOCAL_REAL`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260429T_CODEX_LOCAL_REAL --resume --max-examples 100 --target-scored-per-slice 100`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k', 'HuggingFaceH4/MATH-500']`
- Budgets: `[2, 4, 6, 8]`
- Seeds: `[11, 13, 17]`
- Methods: `['strict_f3', 'strict_gate1_cap_k6', 'strict_f2', 'direct_reserve_semantic_frontier_v2', 'direct_reserve_semantic_frontier_v2_selection_fix_v1', 'external_l1_max', 'tale', 's1', 'self_consistency_3']`
- Sample-size target per slice: `100` (max-examples cap `100`)

## Completion status
- Total expected slices: `216`
- Completed slices: `0`
- Incomplete slices: `216`
- Zero-record slices: `214`
- Per-provider completion counts:
  - cohere: 0/216
- Per-method completion counts:
  - direct_reserve_semantic_frontier_v2: 0/24
  - direct_reserve_semantic_frontier_v2_selection_fix_v1: 0/24
  - external_l1_max: 0/24
  - s1: 0/24
  - self_consistency_3: 0/24
  - strict_f2: 0/24
  - strict_f3: 0/24
  - strict_gate1_cap_k6: 0/24
  - tale: 0/24
- Per-dataset completion counts:
  - HuggingFaceH4/MATH-500: 0/108
  - openai/gsm8k: 0/108

## Staged status
- Stage 1 (GSM8K): 0/108 slices completed.
- Stage 2 (MATH-500): 0/108 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'summarize_only'}}

## Main accuracy table
- provider=cohere method=direct_reserve_semantic_frontier_v2: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=direct_reserve_semantic_frontier_v2_selection_fix_v1: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=external_l1_max: mean_accuracy=0.6705, total_scored=88
- provider=cohere method=s1: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=self_consistency_3: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=strict_f2: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=strict_f3: mean_accuracy=0.5373, total_scored=67
- provider=cohere method=strict_gate1_cap_k6: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=tale: mean_accuracy=0.0000, total_scored=0

## Token/latency/cost table
- provider=cohere method=direct_reserve_semantic_frontier_v2: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=direct_reserve_semantic_frontier_v2_selection_fix_v1: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=external_l1_max: total_tokens=44103, estimated_total_cost_usd=0.245601
- provider=cohere method=s1: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=self_consistency_3: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=strict_f2: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=strict_f3: total_tokens=31412, estimated_total_cost_usd=0.154152
- provider=cohere method=strict_gate1_cap_k6: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=tale: total_tokens=0, estimated_total_cost_usd=0.000000

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=evaluable, delta=-0.11940298507462686, matched=67
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=not_evaluable_zero_matched_examples, delta=NA, matched=0
- provider=cohere best_frontier_vs_external_l1_max: status=evaluable, delta=-0.11940298507462686, matched=67
- provider=cohere frontier_family_best_vs_self_consistency_3: status=not_evaluable_zero_matched_examples, delta=NA, matched=0

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **yes** (matched=67)
- If not, why not? **na_evaluable** (delta=-0.11940298507462686)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=216, mixed=True)
- Under provider=cohere, does strict_f3 beat external_l1_max? **no_or_mixed** (delta=-0.1194, matched=67)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260429T_CODEX_LOCAL_REAL/`
