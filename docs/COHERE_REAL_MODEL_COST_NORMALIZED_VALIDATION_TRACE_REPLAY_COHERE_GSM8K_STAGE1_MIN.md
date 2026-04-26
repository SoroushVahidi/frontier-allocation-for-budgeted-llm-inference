# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN --resume --max-examples 5 --target-scored-per-slice 5`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k']`
- Budgets: `[4, 6, 8]`
- Seeds: `[11, 23]`
- Methods: `['strict_f3', 'external_l1_max', 'direct_reserve_frontier_gate_v1']`
- Sample-size target per slice: `5` (max-examples cap `5`)

## Completion status
- Total expected slices: `18`
- Completed slices: `18`
- Incomplete slices: `0`
- Zero-record slices: `0`
- Per-provider completion counts:
  - cohere: 18/18
- Per-method completion counts:
  - direct_reserve_frontier_gate_v1: 6/6
  - external_l1_max: 6/6
  - strict_f3: 6/6
- Per-dataset completion counts:
  - openai/gsm8k: 18/18

## Staged status
- Stage 1 (GSM8K): 18/18 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=direct_reserve_frontier_gate_v1: mean_accuracy=0.6667, total_scored=30
- provider=cohere method=external_l1_max: mean_accuracy=0.7000, total_scored=30
- provider=cohere method=strict_f3: mean_accuracy=0.5667, total_scored=30

## Token/latency/cost table
- provider=cohere method=direct_reserve_frontier_gate_v1: total_tokens=32798, estimated_total_cost_usd=0.168822
- provider=cohere method=external_l1_max: total_tokens=15872, estimated_total_cost_usd=0.083136
- provider=cohere method=strict_f3: total_tokens=31153, estimated_total_cost_usd=0.157815

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=evaluable, delta=-0.13333333333333333, matched=30
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=not_evaluable_zero_matched_examples, delta=NA, matched=0
- provider=cohere best_frontier_vs_external_l1_max: status=evaluable, delta=-0.13333333333333333, matched=30

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **yes** (matched=30)
- If not, why not? **na_evaluable** (delta=-0.13333333333333333)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=0, mixed=True)
- Under provider=cohere, does strict_f3 beat external_l1_max? **no_or_mixed** (delta=-0.1333, matched=30)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN/`
