# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `main_table_baselines_live_sanity`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp main_table_baselines_live_sanity --resume --max-examples 0 --target-scored-per-slice 2`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k']`
- Budgets: `[4]`
- Seeds: `[11]`
- Methods: `['external_l1_max_fair_v1', 'external_self_consistency_4_fair_v1', 'external_self_consistency_6_fair_v1', 'external_pal_pot_fair_v1', 'external_s1_budget_forcing_faithful_v1', 'external_tale_ep_prompt_budgeting_faithful_v1']`
- Sample-size target per slice: `2` (max-examples cap `0`)

## Completion status
- Total expected slices: `6`
- Completed slices: `0`
- Incomplete slices: `6`
- Zero-record slices: `6`
- Per-provider completion counts:
  - cohere: 0/6
- Per-method completion counts:
  - external_l1_max_fair_v1: 0/1
  - external_pal_pot_fair_v1: 0/1
  - external_s1_budget_forcing_faithful_v1: 0/1
  - external_self_consistency_4_fair_v1: 0/1
  - external_self_consistency_6_fair_v1: 0/1
  - external_tale_ep_prompt_budgeting_faithful_v1: 0/1
- Per-dataset completion counts:
  - openai/gsm8k: 0/6

## Staged status
- Stage 1 (GSM8K): 0/6 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=external_l1_max_fair_v1: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=external_pal_pot_fair_v1: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=external_s1_budget_forcing_faithful_v1: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=external_self_consistency_4_fair_v1: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=external_self_consistency_6_fair_v1: mean_accuracy=0.0000, total_scored=0
- provider=cohere method=external_tale_ep_prompt_budgeting_faithful_v1: mean_accuracy=0.0000, total_scored=0

## Token/latency/cost table
- provider=cohere method=external_l1_max_fair_v1: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=external_pal_pot_fair_v1: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=external_s1_budget_forcing_faithful_v1: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=external_self_consistency_4_fair_v1: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=external_self_consistency_6_fair_v1: total_tokens=0, estimated_total_cost_usd=0.000000
- provider=cohere method=external_tale_ep_prompt_budgeting_faithful_v1: total_tokens=0, estimated_total_cost_usd=0.000000

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=not_evaluable_zero_matched_examples, delta=NA, matched=0
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=not_evaluable_zero_matched_examples, delta=NA, matched=0

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **no** (matched=0)
- If not, why not? **not_evaluable_zero_matched_examples** (delta=NA)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=6, mixed=False)
- Under provider=cohere, does strict_f3 beat external_l1_max? **not_evaluable_zero_matched_examples** (matched=0)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_main_table_baselines_live_sanity/`
