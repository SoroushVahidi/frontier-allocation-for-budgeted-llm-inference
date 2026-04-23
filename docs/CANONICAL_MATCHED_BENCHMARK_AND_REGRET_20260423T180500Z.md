# Canonical matched benchmark and regret bundle (20260423T180500Z)

## Purpose
Jointly close Experiment 1 (canonical matched benchmark) and Experiment 5 (oracle headroom/regret) on one exact matched surface.

## Benchmark contract
- Source rows: `outputs/matched_surface_multiseed_main_comparison_20260423T002000Z/raw_case_results.csv`.
- Datasets: ['HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024', 'openai/gsm8k']
- Budgets: [4, 6, 8] actions
- Seeds: [11, 23, 37, 41, 53, 67]
- Per-(dataset,seed) subset size: 20
- Strict matched dimensions: dataset × seed × budget × example_id with shared grading and accounting.

## Included methods and fairness rules
- Main table: methods marked `main_table_eligible=true` in `method_status_matrix.csv`.
- Appendix-only: external adjacent/control-space-mismatched methods or methods without sufficient fairness closure.
- Rule source: `docs/external_baseline_paper_readiness_decision_matrix.json` plus canonical matched-surface inclusion.

## Reference/oracle definition
- Name: `bounded_hindsight_upper_envelope_on_matched_surface`.
- Not a true oracle: uses hindsight max over observed main-table methods on each exact case.
- Regret definition: `regret = reference_case_value - method_case_value` with binary correctness values.
- This keeps reference construction inside one fairness-closed surface.

## Main results (safe claims)
- Top raw-score method: `strict_f3` (accuracy 0.6213).
- Lowest-regret method: `strict_f3` (average regret 0.3694).
- Headroom from top raw-score method to bounded reference: 0.3694.
- Claims are regime-qualified via `regime_breakdown.csv` (dataset × budget × method).

## Caveats
- The reference is bounded by methods currently available on this surface; it is not a guarantee of globally attainable performance.
- External comparators in appendix remain scientifically useful but are not mixed into main-table claims.

## Output bundle
- `outputs/canonical_matched_benchmark_and_regret_20260423T180500Z/`
- Contains machine-readable summaries, frontier/regret plot data, fairness status matrix, and manuscript-facing summary.
