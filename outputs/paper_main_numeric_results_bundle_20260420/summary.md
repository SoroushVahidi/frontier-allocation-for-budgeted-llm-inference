# Paper main numeric results bundle

- created_utc: `2026-04-20T16:54:49.765614+00:00`
- output_dir: `outputs/paper_main_numeric_results_bundle_20260420`
- datasets: `openai/gsm8k, EleutherAI/hendrycks_math, HuggingFaceH4/MATH-500, Idavidrein/gpqa, Hothan/OlympiadBench, meituan-longcat/AMO-Bench`
- budgets: `6, 8, 10`
- seeds: `42, 43, 44`
- methods: `strict_coupled_tie_aware_promoted, adaptive_budget_guarded, reasoning_beam2, self_consistency_3, reasoning_greedy, verifier_guided_search`
- api_backend/model: `simulator` / `gpt-4.1-mini`

## Key outputs
- `outputs/paper_main_numeric_results_bundle_20260420/per_dataset_budget_method_metrics.csv`
- `outputs/paper_main_numeric_results_bundle_20260420/aggregate_method_summary.csv`
- `outputs/paper_main_numeric_results_bundle_20260420/aggregate_dataset_summary.csv`
- `outputs/paper_main_numeric_results_bundle_20260420/per_seed_method_metrics.csv`
- `outputs/paper_main_numeric_results_bundle_20260420/skipped_items.csv`

## Notes
- This bundle reports matched-budget numeric comparisons only (no figure generation).
- `strict_coupled_tie_aware_promoted` is currently bridged to an in-repo adaptive controller row when native strategy wiring is unavailable.
