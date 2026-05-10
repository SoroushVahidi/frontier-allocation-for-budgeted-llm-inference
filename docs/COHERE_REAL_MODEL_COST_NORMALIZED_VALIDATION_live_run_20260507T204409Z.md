# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `live_run_20260507T204409Z`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp live_run_20260507T204409Z --resume --max-examples 40 --target-scored-per-slice 30`
- Providers: `['cohere']`
- Provider models: `{'cohere': 'command-r-plus-08-2024', 'openai': 'gpt-4o-mini'}`
- Datasets: `['openai/gsm8k']`
- Budgets: `[6]`
- Seeds: `[20260501]`
- Methods: `['direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal', 'direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_track_b_commitment_v1']`
- Sample-size target per slice: `30` (max-examples cap `40`)

## Completion status
- Total expected slices: `2`
- Completed slices: `2`
- Incomplete slices: `0`
- Zero-record slices: `0`
- Per-provider completion counts:
  - cohere: 2/2
- Per-method completion counts:
  - direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal: 1/1
  - direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_track_b_commitment_v1: 1/1
- Per-dataset completion counts:
  - openai/gsm8k: 2/2

## Staged status
- Stage 1 (GSM8K): 2/2 slices completed.
- Stage 2 (MATH-500): 0/0 slices completed.
- Stage 3 (AIME 2024): 0/0 slices completed.
- Provider status: {'cohere': {'ready': '1', 'reason': 'ok'}}

## Main accuracy table
- provider=cohere method=direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal: mean_accuracy=0.6667, total_scored=30
- provider=cohere method=direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_track_b_commitment_v1: mean_accuracy=0.7333, total_scored=30

## Token/latency/cost table
- provider=cohere method=direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal: total_tokens=36760, estimated_total_cost_usd=0.159036
- provider=cohere method=direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_track_b_commitment_v1: total_tokens=34270, estimated_total_cost_usd=0.146754

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- provider=cohere strict_f3_vs_external_l1_max: status=not_evaluable_zero_matched_examples, delta=NA, matched=0
- provider=cohere strict_f3_vs_strict_gate1_cap_k6: status=not_evaluable_zero_matched_examples, delta=NA, matched=0

## Clear answers
- Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison? **no** (matched=0)
- If not, why not? **not_evaluable_zero_matched_examples** (delta=NA)
- Was OpenAI fallback used? **no** (not_requested)
- Is the evidence still appendix-only, or strong enough for main-paper use? **yes** (incomplete_slices=0, mixed=False)
- Under provider=cohere, does strict_f3 beat external_l1_max? **not_evaluable_zero_matched_examples** (matched=0)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_live_run_20260507T204409Z/`
