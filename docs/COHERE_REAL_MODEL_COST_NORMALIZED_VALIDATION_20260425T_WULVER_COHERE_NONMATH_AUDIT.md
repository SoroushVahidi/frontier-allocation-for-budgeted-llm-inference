# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260425T_WULVER_COHERE_NONMATH_AUDIT`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260425T_WULVER_COHERE_NONMATH_AUDIT --resume --max-examples 200 --target-scored-per-slice 100`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['natural_plan', 'gpqa_diamond']`
- Budgets: `[4, 6, 8]`
- Seeds: `[11, 23]`
- Methods: `['strict_f3_anti_collapse_weak_v1', 'strict_f3', 'external_l1_max', 'tale', 's1']`
- Sample-size target per slice: `100` (max-examples cap `200`)

## Completion status
- Total expected slices: `60`
- Completed slices: `24`
- Incomplete slices: `36`
- Zero-record slices: `36`
- Per-provider completion counts:
  - cohere: 24/60
- Per-method completion counts:
  - external_l1_max: 6/12
  - s1: 6/12
  - strict_f3: 6/12
  - strict_f3_anti_collapse_weak_v1: 6/12
  - tale: 0/12
- Per-dataset completion counts:
  - gpqa_diamond: 24/30
  - natural_plan: 0/30

## Staged status
- Stage 1 (GSM8K): 0/0 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'summarize_only'}}

## Main accuracy table
- provider=cohere method=external_l1_max: mean_accuracy=0.0833, total_scored=600
- provider=cohere method=s1: mean_accuracy=0.0800, total_scored=600
- provider=cohere method=strict_f3: mean_accuracy=0.0617, total_scored=600
- provider=cohere method=strict_f3_anti_collapse_weak_v1: mean_accuracy=0.0683, total_scored=600
- provider=cohere method=tale: mean_accuracy=0.0000, total_scored=0

## Token/latency/cost table
- provider=cohere method=external_l1_max: total_tokens=684930, estimated_total_cost_usd=3.278658
- provider=cohere method=s1: total_tokens=1398070, estimated_total_cost_usd=6.218142
- provider=cohere method=strict_f3: total_tokens=1412374, estimated_total_cost_usd=6.485886
- provider=cohere method=strict_f3_anti_collapse_weak_v1: total_tokens=1399848, estimated_total_cost_usd=6.372120
- provider=cohere method=tale: total_tokens=0, estimated_total_cost_usd=0.000000

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=evaluable, delta=-0.021739130434782608, matched=598
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=not_evaluable_zero_matched_examples, delta=NA, matched=0
- provider=cohere best_frontier_vs_external_l1_max: status=evaluable, delta=-0.021739130434782608, matched=598

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **yes** (matched=598)
- If not, why not? **na_evaluable** (delta=-0.021739130434782608)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=36, mixed=True)
- Under provider=cohere, does strict_f3 beat external_l1_max? **no_or_mixed** (delta=-0.0217, matched=598)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260425T_WULVER_COHERE_NONMATH_AUDIT/`
