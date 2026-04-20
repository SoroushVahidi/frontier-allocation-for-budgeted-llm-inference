# NeurIPS Artifact Audit (fixed-budget cross-controller frontier allocation)

## Scope

This audit identifies the most reliable existing repository outputs for a **text-only NeurIPS artifact layer** focused on:

- fixed-budget cross-controller frontier allocation,
- oracle frontier headroom,
- anti-collapse diversity diagnostics.

It explicitly avoids reframing the project into binary revise/defer routing.

## Canonical experimental outputs already present

Most reliable current machine-readable sources discovered in this repository:

1. `outputs/imported_methodology_frontier_eval/20260417T000000Z/`
   - `method_metrics.csv`
   - `oracle_gap_summary.csv`
   - `matched_comparison_summary.csv`
   - `budget_frontier_summary.csv`
   - `signal_slice_summary.csv`
   - `summary.json`

2. `outputs/full_method_comparison_bundle/20260419T214335Z/`
   - `manifest.json`
   - `per_seed_method_metrics.csv`
   - `per_method_metrics.csv`
   - `per_example_outcomes.csv`
   - `per_budget_ranking.csv`
   - `per_dataset_ranking.csv`

These two runs provide the best combined support for frontier tables, oracle-gap summaries, seed robustness, and anti-collapse diversity proxies.

## Available controller/reasoning families

From canonical CSVs and scripts, available families/methods include:

- Internal fixed-controller baselines:
  - `reasoning_greedy`
  - `self_consistency_3`
  - `reasoning_beam2`
  - `verifier_guided_search`
  - `program_of_thought`

- Adaptive/controller family variants:
  - `adaptive_min_expand_0`
  - `adaptive_min_expand_1`
  - `adaptive_min_expand_2`
  - `adaptive_budget_guarded` (present in imported frontier eval)

- Oracle frontier row:
  - `oracle_frontier_upper_bound`

- External adapter-mode baselines in full-method bundle:
  - `external_l1_exact`
  - `external_l1_max`
  - `external_s1_budget_forcing`
  - `external_tale_prompt_budgeting`

## Budget definitions already used

Observed budget grids in canonical outputs:

- Imported frontier eval run: budgets `8, 10`.
- Full method comparison bundle: budgets `4, 6, 8`.

Cost accounting is consistently action-based via:

- `actions_used` at per-example level,
- `avg_actions` in aggregated tables.

## Datasets already supported

Canonical multi-dataset bundle includes:

- `openai/gsm8k`
- `HuggingFaceH4/MATH-500`
- `HuggingFaceH4/aime_2024`

Imported methodology frontier run is single-dataset (`openai/gsm8k`) in the checked run.

## Main metrics already computed

Across canonical CSVs, available metrics include:

- `accuracy`
- `avg_actions`, `avg_expansions`, `avg_verifications`
- `budget_exhaustion_rate`, `underspend_rate`
- `oracle_accuracy`, `gap_to_oracle`
- matched `wins/losses/ties`, `net_win_rate`
- hard/easy slice metrics (`hard_accuracy`, `easy_accuracy`, etc.)

## Most reliable source-of-truth files for paper artifacts

For this manuscript direction, the most reliable source-of-truth files are:

- `outputs/imported_methodology_frontier_eval/20260417T000000Z/method_metrics.csv`
- `outputs/imported_methodology_frontier_eval/20260417T000000Z/oracle_gap_summary.csv`
- `outputs/imported_methodology_frontier_eval/20260417T000000Z/budget_frontier_summary.csv`
- `outputs/imported_methodology_frontier_eval/20260417T000000Z/signal_slice_summary.csv`
- `outputs/full_method_comparison_bundle/20260419T214335Z/per_seed_method_metrics.csv`
- `outputs/full_method_comparison_bundle/20260419T214335Z/per_example_outcomes.csv`
- `outputs/full_method_comparison_bundle/20260419T214335Z/manifest.json`

## Reliability notes and caveats

- A canonical explicit **uniform allocation baseline** was not found in the current canonical outputs.
- A canonical explicit **learned cross-controller policy** row (e.g., pairwise reliability policy) is not present in the selected canonical run bundles.
- Anti-collapse diversity metrics in this artifact layer are computed from **oracle winner-share composition over available families** in `per_example_outcomes.csv`; they are conservative proxies and not claimed as direct online policy entropy unless an explicit policy-trace artifact exists.
