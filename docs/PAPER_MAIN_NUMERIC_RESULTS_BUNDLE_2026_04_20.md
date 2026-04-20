# Paper Main Numeric Results Bundle (2026-04-20)

## Purpose

This bundle is the paper-critical matched-budget numeric evaluation pass for manuscript tables in
**"Adaptive Frontier Allocation for Budgeted LLM Inference"**.

It is designed to run on Wulver via `sbatch`, write machine-readable CSV/JSON artifacts under `outputs/`,
and provide a deterministic, resumable experiment path.

## Canonical execution command

The Wulver job launches this exact script command pattern:

`python scripts/run_paper_main_numeric_results_bundle.py --output-dir outputs/paper_main_numeric_results_bundle_<YYYYMMDD> --datasets "openai/gsm8k,EleutherAI/hendrycks_math,HuggingFaceH4/MATH-500,Idavidrein/gpqa,Hothan/OlympiadBench,meituan-longcat/AMO-Bench" --budgets "6,8,10" --seeds "42,43,44" --subset-size 24 --api-backend simulator --model gpt-4.1-mini --resume`

Sbatch launcher:

`sbatch jobs/paper_main_numeric_results_bundle_wulver.sbatch`

## Datasets

Default required paper-facing surface in this bundle:

- `openai/gsm8k`
- `EleutherAI/hendrycks_math` (MATH)
- `HuggingFaceH4/MATH-500`
- `Idavidrein/gpqa` (GPQA Diamond config)
- `Hothan/OlympiadBench`
- `meituan-longcat/AMO-Bench`

Natural Plan policy:

- `google-deepmind/natural-plan` is **optional**.
- It is only included when `--include-natural-plan` is set (or `PAPER_MAIN_NUMERIC_INCLUDE_NATURAL_PLAN=1`)
  and local clone requirements are satisfied.
- If clone requirements are missing, it is skipped with explicit reporting in `skipped_items.csv`.

## Budgets

- Default budgets: `6,8,10`
- Rationale: reuse canonical new-paper matched-budget conventions already used by existing comparative scripts.

## Methods

Focused paper-facing comparison set:

- `strict_coupled_tie_aware_promoted` (integrated promoted line, currently bridged alias when needed)
- `adaptive_budget_guarded` (strong internal broad-family comparator)
- `reasoning_beam2`
- `self_consistency_3`
- `reasoning_greedy`
- `verifier_guided_search` (included because stable runnable implementation exists)

## Seeds

- Default seeds: `42,43,44`
- Bundle exports both per-seed rows and aggregated uncertainty summaries.

## Output directory and files

Default output root:

- `outputs/paper_main_numeric_results_bundle_<YYYYMMDD>/`

Core outputs:

- `per_seed_method_metrics.csv` (dataset x seed x budget x method)
- `per_dataset_budget_method_metrics.csv` (mean/std/stderr over seeds)
- `aggregate_method_summary.csv` (aggregate method-level summary with uncertainty)
- `aggregate_dataset_summary.csv` (dataset-level aggregate summaries)
- `manifest.json`
- `config.json`
- `resume_state.json`
- `skipped_items.csv`
- `summary.md`

## Skips and failure handling

- Missing/unsupported methods for a block are logged to `skipped_items.csv` and do not crash the full run.
- Optional Natural Plan inclusion is skipped with explicit reason if local clone files are missing.
- API backend key absence fails fast for non-simulator backends (clear message) rather than silently falling back.
- `--resume` allows continuing partially completed runs via `resume_state.json`.

## Paper support scope

This bundle supports numeric manuscript tables that require:

- matched-budget method comparison across the benchmark surface,
- per-dataset and aggregate reporting,
- mean + uncertainty over multiple seeds.

This bundle does **not** claim:

- figure production,
- full external-baseline reproduction parity,
- or non-matched / non-budget-controlled comparisons.
