# Artifact status and plot policy (2026-04-20)

## Purpose

This note prevents a recurring repository problem:
older bounded plot/table bundles being read as if they were the current broad repository result surface.

The repository now contains multiple valid artifact families created for different phases of the project.
They should not be mixed without an explicit note about scope.

## Canonical current ranking surface

For the current repository state, the canonical broad comparison surface is:

- `docs/CURRENT_FULL_METHOD_COMPARISON_BUNDLE_STATUS_2026_04_20.md`
- `docs/CURRENT_RANKING_AND_COMPETITIVE_STATUS_2026_04_20.md`
- `outputs/current_full_method_comparison_bundle_20260420/`

Use this family when the question is:
- which method is best now,
- where the latest integrated full method ranks now,
- what the strongest direct adversary is now,
- and what the broad competitive bottleneck is now.

## Canonical current failure-analysis surface

For the current exact-failure and bottleneck picture, use:

- `docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md`
- `outputs/twenty_exact_current_full_vs_best_fresh_20260420/`
- `docs/CURRENT_FAILURE_OUTPUT_LAYER_REPAIR_STATUS_2026_04_20.md`
- `outputs/current_failure_output_layer_repair_20260420/`

Use this family when the question is:
- what still goes wrong now,
- absent-from-tree vs present-but-not-selected breakdown,
- repeated same-family expansion frequency,
- and whether output-layer mismatch is still dominant.

## Older bounded frontier plot surface

The following family is still valid, but only for its original bounded scope:

- `outputs/imported_methodology_frontier_eval/20260417T000000Z/`
- derived CSVs under `outputs/paper_plot_data/`
- `docs/NEURIPS_FIGURE_AND_TABLE_AUDIT.md`

Interpretation rule:
- this is an older paper-facing frontier bundle,
- built on a single-dataset GSM8K bounded surface,
- with budgets 8 and 10,
- and a different method pool than the current April 20 broad-comparison surface.

Therefore:
- these plots/tables are **historical bounded artifacts**,
- they may still be used when discussing that specific evaluation surface,
- but they must **not** be presented as the current whole-repository ranking picture.

## Plot and table safety classes

### Safe for current broad claims
- figures/tables derived directly from `outputs/current_full_method_comparison_bundle_20260420/`
- figures/tables derived directly from the fresh exact failure bundle and current output-layer repair bundle

### Safe with bounded-scope labeling
- figures/tables derived from `outputs/imported_methodology_frontier_eval/20260417T000000Z/`
- files currently stored under `outputs/paper_plot_data/`

Required label for bounded-scope use:
- state clearly that the artifact is from the older bounded imported-methodology frontier surface
- state dataset and budget scope explicitly

### Not safe for current headline claims
- any figure/table that mixes April 17 imported-methodology rows with April 19–20 current comparison rows without explicit normalization and documentation
- any figure/table that uses `outputs/paper_plot_data/` as if it were the current canonical broad ranking source
- any one-off exploratory run not referenced by current canonical docs

## Practical maintenance rule

When adding a new paper-facing figure or table:
1. record the exact source bundle path;
2. record whether it is current-canonical or bounded-historical;
3. store or link the machine-readable source beside the figure/table;
4. add/update a note in `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md` if the artifact becomes current-facing.

## Specific note on `program_of_thought`

If a plot built from `outputs/paper_plot_data/` shows `program_of_thought` at zero accuracy, that is not automatically a plotting bug.
It is consistent with the older imported-methodology frontier bundle.
But it is still only evidence about that bounded surface, not about every current repository comparison surface.

## Cross-links

- `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
- `docs/OUTPUTS_INTERPRETATION_GUIDE.md`
- `docs/CURRENT_FULL_METHOD_COMPARISON_BUNDLE_STATUS_2026_04_20.md`
- `docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md`
- `outputs/paper_plot_data/README.md`
