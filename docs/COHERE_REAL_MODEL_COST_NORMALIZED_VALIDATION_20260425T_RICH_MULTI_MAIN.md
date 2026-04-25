# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260425T_RICH_MULTI_MAIN`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260425T_RICH_MULTI_MAIN --resume --max-examples 90 --target-scored-per-slice 60`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k']`
- Budgets: `[4, 6, 8]`
- Seeds: `[11, 23]`
- Methods: `['strict_f3', 'strict_gate1_cap_k6', 'strict_f3_anti_collapse_weak_v1', 'external_l1_max']`
- Sample-size target per slice: `60` (max-examples cap `90`)

## Completion status
- Total expected slices: `24`
- Completed slices: `1`
- Incomplete slices: `23`
- Zero-record slices: `20`
- Per-provider completion counts:
  - cohere: 1/24
- Per-method completion counts:
  - external_l1_max: 0/6
  - strict_f3: 1/6
  - strict_f3_anti_collapse_weak_v1: 0/6
  - strict_gate1_cap_k6: 0/6
- Per-dataset completion counts:
  - openai/gsm8k: 1/24

## Staged status
- Stage 1 (GSM8K): 1/24 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'summarize_only'}}

## Main accuracy table
- provider=cohere method=external_l1_max: mean_accuracy=0.7143, total_scored=35
- provider=cohere method=strict_f3: mean_accuracy=0.6562, total_scored=64
- provider=cohere method=strict_f3_anti_collapse_weak_v1: mean_accuracy=0.5455, total_scored=11
- provider=cohere method=strict_gate1_cap_k6: mean_accuracy=0.5581, total_scored=43

## Token/latency/cost table
- provider=cohere method=external_l1_max: total_tokens=16439, estimated_total_cost_usd=0.090477
- provider=cohere method=strict_f3: total_tokens=57440, estimated_total_cost_usd=0.294576
- provider=cohere method=strict_f3_anti_collapse_weak_v1: total_tokens=9434, estimated_total_cost_usd=0.048090
- provider=cohere method=strict_gate1_cap_k6: total_tokens=38180, estimated_total_cost_usd=0.194976

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=evaluable, delta=-0.11428571428571428, matched=35
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=evaluable, delta=0.06976744186046512, matched=43
- provider=cohere best_frontier_vs_external_l1_max: status=evaluable, delta=-0.11428571428571428, matched=35

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **yes** (matched=35)
- If not, why not? **na_evaluable** (delta=-0.11428571428571428)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=23, mixed=True)
- Under provider=cohere, does strict_f3 beat external_l1_max? **no_or_mixed** (delta=-0.1143, matched=35)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260425T_RICH_MULTI_MAIN/`
