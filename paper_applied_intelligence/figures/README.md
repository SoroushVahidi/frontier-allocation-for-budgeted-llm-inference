# Figure Assets

This directory contains placeholder LaTeX figure wrappers and data-source notes.

Expected plotting inputs (from result package):
- `outputs/machine_learning_journal_result_package_20260520_20260520T035127Z/figure_data_accuracy_vs_baseline.csv`
- `outputs/machine_learning_journal_result_package_20260520_20260520T035127Z/figure_data_delta_ci.csv`
- `outputs/machine_learning_journal_result_package_20260520_20260520T035127Z/figure_data_failure_breakdown.csv`

Suggested workflow:
1. Generate publication figures in Python/R from CSVs.
2. Export to PDF (`fig1.pdf`, `fig2.pdf`, `fig3.pdf`) in this directory.
3. Replace placeholders with `\includegraphics`.
