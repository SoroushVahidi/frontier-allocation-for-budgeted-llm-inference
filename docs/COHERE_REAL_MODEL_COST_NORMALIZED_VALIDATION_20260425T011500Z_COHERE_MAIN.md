# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION

- Timestamp: `20260425T011500Z_COHERE_MAIN`
- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260425T011500Z_COHERE_MAIN --resume --max-examples 100 --target-scored-per-slice 100`
- Cohere model: `command-r-plus-08-2024`
- Datasets: `['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']`
- Budgets: `[4, 6, 8]`
- Seeds: `[11, 23]`
- Methods: `['strict_f3', 'strict_gate1_cap_k6', 'strict_f2', 'external_l1_max', 'self_consistency_3']`
- Sample-size target per slice: `100` (max-examples cap `100`)

## Completion status
- Incomplete slices: `1`

## Main accuracy table
- strict_f3: mean_accuracy=0.6000, total_scored=100
- strict_gate1_cap_k6: mean_accuracy=0.5556, total_scored=9

## Token/latency/cost table
- strict_f3: total_tokens=92277, estimated_total_cost_usd=0.472827
- strict_gate1_cap_k6: total_tokens=8144, estimated_total_cost_usd=0.041964

## Cost-normalized performance table
- See `cost_normalized_summary.csv` in artifact directory.

## Paired comparison table
- strict_f3_vs_external_l1_max: delta=+0.0000, 95%CI=[+0.0000,+0.0000], matched=0
- strict_f3_vs_strict_gate1_cap_k6: delta=-0.1111, 95%CI=[-0.3333,+0.0000], matched=9
- best_frontier_vs_external_l1_max: delta=+0.0000, 95%CI=[+0.0000,+0.0000], matched=0

## Clear answers
- Does strict_f3 beat external_l1_max under Cohere cost-normalized evaluation? **no_or_mixed** (delta=+0.0000)
- Does best frontier-allocation method beat external_l1_max? **no_or_mixed** (best_method=strict_f3, delta=+0.0000)
- Are frontier-allocation methods merely competitive but not dominant? **yes** (mixed/near-tie outcomes across paired comparisons)
- Is Cohere evidence strong enough to move from appendix-only to main-paper evidence? **no_appendix_only** (incomplete_slices=1, mixed=True)

## Manuscript-safe wording
- Treat Cohere evidence as bounded external-validity evidence under this matched setup.
- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.

## Forbidden overclaim wording
- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.

## Artifact directory
- `outputs/cohere_real_model_cost_normalized_validation_20260425T011500Z_COHERE_MAIN/`
