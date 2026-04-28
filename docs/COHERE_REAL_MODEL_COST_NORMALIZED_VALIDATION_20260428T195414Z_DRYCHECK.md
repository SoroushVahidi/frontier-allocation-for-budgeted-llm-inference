# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260428T195414Z_DRYCHECK`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260428T195414Z_DRYCHECK --resume --max-examples 30 --target-scored-per-slice 30`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k', 'HuggingFaceH4/MATH-500']`
- Budgets: `[4, 6, 8]`
- Seeds: `[11, 23]`
- Methods: `['strict_f3', 'strict_gate1_cap_k6', 'strict_f3_anti_collapse_weak_v1', 'external_l1_max', 'tale', 's1']`
- Sample-size target per slice: `30` (max-examples cap `30`)

## Completion status
- Total expected slices: `72`
- Completed slices: `0`
- Incomplete slices: `72`
- Zero-record slices: `72`
- Per-provider completion counts:
  - cohere: 0/72
- Per-method completion counts:
  - external_l1_max: 0/12
  - s1: 0/12
  - strict_f3: 0/12
  - strict_f3_anti_collapse_weak_v1: 0/12
  - strict_gate1_cap_k6: 0/12
  - tale: 0/12
- Per-dataset completion counts:
  - HuggingFaceH4/MATH-500: 0/36
  - openai/gsm8k: 0/36

## Staged status
- Stage 1 (GSM8K): 0/36 slices completed.
- Stage 2 (MATH-500): 0/36 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'summarize_only'}}

## Main accuracy table
- provider=cohere method=external_l1_max: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=s1: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=strict_f3: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=strict_f3_anti_collapse_weak_v1: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=strict_gate1_cap_k6: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=tale: mean_accuracy=0.0000, total_scored=0

## Token/latency/cost table
- provider=cohere method=external_l1_max: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=s1: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=strict_f3: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=strict_f3_anti_collapse_weak_v1: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=strict_gate1_cap_k6: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=tale: total_tokens=0, estimated_total_cost_usd=0.000000

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=not_evaluable_zero_matched_examples, delta=NA, matched=0
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=not_evaluable_zero_matched_examples, delta=NA, matched=0
- provider=cohere best_frontier_vs_external_l1_max: status=not_evaluable_zero_matched_examples, delta=NA, matched=0

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **no** (matched=0)
- If not, why not? **not_evaluable_zero_matched_examples** (delta=NA)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=72, mixed=False)
- Under provider=cohere, does strict_f3 beat external_l1_max? **not_evaluable_zero_matched_examples** (matched=0)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260428T195414Z_DRYCHECK/`
