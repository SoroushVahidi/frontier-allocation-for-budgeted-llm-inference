# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260428T195414Z`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260428T195414Z --resume --max-examples 30 --target-scored-per-slice 30`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k', 'HuggingFaceH4/MATH-500']`
- Budgets: `[4, 6, 8]`
- Seeds: `[11, 23]`
- Methods: `['strict_f3', 'strict_gate1_cap_k6', 'strict_f3_anti_collapse_weak_v1', 'external_l1_max', 'tale', 's1']`
- Sample-size target per slice: `30` (max-examples cap `30`)

## Completion status
- Total expected slices: `72`
- Completed slices: `68`
- Incomplete slices: `4`
- Zero-record slices: `0`
- Per-provider completion counts:
  - cohere: 68/72
- Per-method completion counts:
  - external_l1_max: 8/12
  - s1: 12/12
  - strict_f3: 12/12
  - strict_f3_anti_collapse_weak_v1: 12/12
  - strict_gate1_cap_k6: 12/12
  - tale: 12/12
- Per-dataset completion counts:
  - HuggingFaceH4/MATH-500: 32/36
  - openai/gsm8k: 36/36

## Staged status
- Stage 1 (GSM8K): 36/36 slices completed.
- Stage 2 (MATH-500): 32/36 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=external_l1_max: mean_accuracy=0.5367, total_scored=356
- provider=cohere method=s1: mean_accuracy=0.5111, total_scored=360
- provider=cohere method=strict_f3: mean_accuracy=0.4500, total_scored=360
- provider=cohere method=strict_f3_anti_collapse_weak_v1: mean_accuracy=0.4194, total_scored=360
- provider=cohere method=strict_gate1_cap_k6: mean_accuracy=0.4056, total_scored=360
- provider=cohere method=tale: mean_accuracy=0.4944, total_scored=360

## Token/latency/cost table
- provider=cohere method=external_l1_max: total_tokens=224381, estimated_total_cost_usd=1.217235
- provider=cohere method=s1: total_tokens=429612, estimated_total_cost_usd=1.955760
- provider=cohere method=strict_f3: total_tokens=441838, estimated_total_cost_usd=2.158386
- provider=cohere method=strict_f3_anti_collapse_weak_v1: total_tokens=436219, estimated_total_cost_usd=2.137233
- provider=cohere method=strict_gate1_cap_k6: total_tokens=434439, estimated_total_cost_usd=2.141721
- provider=cohere method=tale: total_tokens=229677, estimated_total_cost_usd=1.158531

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=evaluable, delta=-0.0898876404494382, matched=356
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=evaluable, delta=0.044444444444444446, matched=360
- provider=cohere best_frontier_vs_external_l1_max: status=evaluable, delta=-0.0898876404494382, matched=356

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **yes** (matched=356)
- If not, why not? **na_evaluable** (delta=-0.0898876404494382)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=4, mixed=True)
- Under provider=cohere, does strict_f3 beat external_l1_max? **no_or_mixed** (delta=-0.0899, matched=356)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260428T195414Z/`
