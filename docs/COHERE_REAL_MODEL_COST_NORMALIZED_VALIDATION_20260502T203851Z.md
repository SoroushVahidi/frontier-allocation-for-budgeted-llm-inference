# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260502T203851Z`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260502T203851Z --resume --max-examples 100 --target-scored-per-slice 100`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-a-03-2025', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k']`
- Budgets: `[6]`
- Seeds: `[20260501]`
- Methods: `['strict_f3', 'strict_gate1_cap_k6', 'strict_f2', 'external_l1_max', 'tale', 's1']`
- Sample-size target per slice: `100` (max-examples cap `100`)

## Completion status
- Total expected slices: `6`
- Completed slices: `6`
- Incomplete slices: `0`
- Zero-record slices: `0`
- Per-provider completion counts:
  - cohere: 6/6
- Per-method completion counts:
  - external_l1_max: 1/1
  - s1: 1/1
  - strict_f2: 1/1
  - strict_f3: 1/1
  - strict_gate1_cap_k6: 1/1
  - tale: 1/1
- Per-dataset completion counts:
  - openai/gsm8k: 6/6

## Staged status
- Stage 1 (GSM8K): 6/6 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=external_l1_max: mean_accuracy=0.9200, total_scored=100
- provider=cohere method=s1: mean_accuracy=0.9100, total_scored=100
- provider=cohere method=strict_f2: mean_accuracy=0.5600, total_scored=100
- provider=cohere method=strict_f3: mean_accuracy=0.2200, total_scored=100
- provider=cohere method=strict_gate1_cap_k6: mean_accuracy=0.5700, total_scored=100
- provider=cohere method=tale: mean_accuracy=0.9200, total_scored=100

## Token/latency/cost table
- provider=cohere method=external_l1_max: total_tokens=300795, estimated_total_cost_usd=1.213653
- provider=cohere method=s1: total_tokens=364235, estimated_total_cost_usd=1.439721
- provider=cohere method=strict_f2: total_tokens=415413, estimated_total_cost_usd=1.688727
- provider=cohere method=strict_f3: total_tokens=425128, estimated_total_cost_usd=1.726224
- provider=cohere method=strict_gate1_cap_k6: total_tokens=422175, estimated_total_cost_usd=1.719045
- provider=cohere method=tale: total_tokens=288494, estimated_total_cost_usd=1.157010

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=evaluable, delta=-0.7, matched=100
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=evaluable, delta=-0.35, matched=100
- provider=cohere best_frontier_vs_external_l1_max: status=evaluable, delta=-0.35, matched=100

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **yes** (matched=100)
- If not, why not? **na_evaluable** (delta=-0.7)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **no_appendix_only** (incomplete_slices=0, mixed=True)
- Under provider=cohere, does strict_f3 beat external_l1_max? **no_or_mixed** (delta=-0.7000, matched=100)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260502T203851Z/`
