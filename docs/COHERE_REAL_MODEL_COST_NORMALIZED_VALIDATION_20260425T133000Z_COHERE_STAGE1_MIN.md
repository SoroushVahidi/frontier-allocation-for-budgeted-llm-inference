# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260425T133000Z_COHERE_STAGE1_MIN`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260425T133000Z_COHERE_STAGE1_MIN --resume --max-examples 0 --target-scored-per-slice 100`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']`
- Budgets: `[4, 6, 8]`
- Seeds: `[11, 23]`
- Methods: `['strict_f3', 'strict_gate1_cap_k6', 'strict_f2', 'external_l1_max', 'self_consistency_3']`
- Sample-size target per slice: `100` (max-examples cap `0`)

## Completion status
- Total expected slices: `90`
- Completed slices: `0`
- Incomplete slices: `90`
- Zero-record slices: `72`
- Per-provider completion counts:
  - cohere: 0/90
- Per-method completion counts:
  - external_l1_max: 0/18
  - self_consistency_3: 0/18
  - strict_f2: 0/18
  - strict_f3: 0/18
  - strict_gate1_cap_k6: 0/18
- Per-dataset completion counts:
  - HuggingFaceH4/MATH-500: 0/30
  - HuggingFaceH4/aime_2024: 0/30
  - openai/gsm8k: 0/30

## Staged status
- Stage 1 (GSM8K): 0/30 slices completed.
- Stage 2 (MATH-500): 0/30 slices completed.
- Stage 3 (AIME 2024): 0/30 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'summarize_only'}}

## Main accuracy table
- provider=cohere method=external_l1_max: mean_accuracy=0.7833, total_scored=45
- provider=cohere method=self_consistency_3: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=strict_f2: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=strict_f3: mean_accuracy=0.5167, total_scored=45
- provider=cohere method=strict_gate1_cap_k6: mean_accuracy=0.5000, total_scored=30

## Token/latency/cost table
- provider=cohere method=external_l1_max: total_tokens=21917, estimated_total_cost_usd=0.121107
- provider=cohere method=self_consistency_3: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=strict_f2: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=strict_f3: total_tokens=43003, estimated_total_cost_usd=0.218733
- provider=cohere method=strict_gate1_cap_k6: total_tokens=29295, estimated_total_cost_usd=0.153273

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=evaluable, delta=-0.26666666666666666, matched=30
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=evaluable, delta=0.03333333333333333, matched=30
- provider=cohere best_frontier_vs_external_l1_max: status=evaluable, delta=-0.26666666666666666, matched=30
- provider=cohere frontier_family_best_vs_self_consistency_3: status=not_evaluable_zero_matched_examples, delta=NA, matched=0

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **yes** (matched=30)
- If not, why not? **na_evaluable** (delta=-0.26666666666666666)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=90, mixed=True)
- Under provider=cohere, does strict_f3 beat external_l1_max? **no_or_mixed** (delta=-0.2667, matched=30)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN/`
