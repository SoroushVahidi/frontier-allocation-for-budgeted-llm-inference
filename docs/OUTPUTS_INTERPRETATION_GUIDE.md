# Outputs interpretation guide

## Purpose

This note explains how to interpret the main output families without having to reverse-engineer them each time.

## Main output families

### 1. `outputs/current_full_method_comparison_bundle_20260420/`
Use this family when the question is about:
- current broad ranking,
- current competitive status,
- current full-method placement,
- current broad matched leader,
- and present paper-facing comparison claims.

This is the current broad comparison front door for the repository.

### 2. `outputs/twenty_exact_current_full_vs_best_fresh_20260420/`
Use this family when the question is about:
- the fresh exact 20-example current loss surface,
- absent-from-tree vs present-but-not-selected breakdown,
- repeated same-family expansion frequency,
- and exact current failure pattern analysis.

### 3. `outputs/current_failure_output_layer_repair_20260420/`
Use this family when the question is about:
- output-layer mismatch after correct internal reasoning was already present,
- deterministic output repair,
- and how much residual error was due to final surfaced-answer mismatch.

### 4. `outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/`
Use this family when the question is about:
- old-vs-current structural changes,
- whether the promoted tuned line materially changed tree shape,
- and targeted repair of older defeats.

### 5. `outputs/branch_label_bruteforce_learning/`
Use this family when the question is about:
- learned-controller results,
- near-tie / adjacent hard-slice metrics,
- fallback or deferral policy comparisons,
- specialist expert variants,
- bounded matched method comparisons.

### 6. `outputs/imported_methodology_frontier_eval/`
Use this family when the question is about:
- the older imported-methodology frontier surface,
- fixed vs adaptive vs oracle comparison on that bounded evaluation path,
- budget-frontier views for that older artifact family,
- and manuscript-style evaluation artifacts adapted from the old workflow.

Important:
- this family is still valid,
- but it is **not** the default current broad repository ranking surface anymore.

### 7. `outputs/paper_plot_data/`
Use this family only as:
- derived plot-input CSVs for the older bounded imported-methodology frontier surface.

Do **not** treat this folder as the current canonical ranking source.
Read `outputs/paper_plot_data/README.md` before using these files externally.

### 8. `outputs/external_baseline_completeness/` and `outputs/external_baseline_runnability/`
Use these when the question is about:
- what external baselines are runnable,
- what is only adjacent/import-validated,
- what is blocked,
- and what comparison claims are currently safe.

## Which outputs are most paper-facing right now

Most paper-facing output families currently are:
- `outputs/current_full_method_comparison_bundle_20260420/`
- `outputs/twenty_exact_current_full_vs_best_fresh_20260420/`
- `outputs/current_failure_output_layer_repair_20260420/`
- selected matched branch-learning comparison bundles under `outputs/branch_label_bruteforce_learning/`

## Which outputs are historical bounded paper-facing artifacts

Historical bounded paper-facing output families include:
- `outputs/imported_methodology_frontier_eval/20260417T000000Z/`
- derived CSVs in `outputs/paper_plot_data/`

These should be used only with explicit scope labeling.

## Which outputs are more diagnostic / research-internal

More diagnostic or method-development-oriented output families include:
- most target-regime and hard-region mining folders under `outputs/branch_label_bruteforce_targets/`,
- intermediate supervision-building folders,
- one-off bounded exploratory runs not promoted in the canonical docs.

## Practical rule

When presenting results externally:
- prefer outputs that already connect clearly to current canonical docs and current comparison notes,
- record the exact source bundle path,
- and avoid using a one-off diagnostic folder or historical bounded plot folder as if it were the current evidence source.

## Neighbor docs

- `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
- `docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md`
- `docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`
- `docs/imported_methodology_frontier_integration_report.md`
