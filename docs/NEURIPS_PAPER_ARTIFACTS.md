# NeurIPS Paper Artifacts Guide

## Purpose

This guide describes the text-only paper-artifact pipeline for the current manuscript direction:

**fixed-budget cross-controller frontier allocation for reasoning, with oracle frontier headroom and anti-collapse analysis**.

## Canonical input files

The pipeline reads only canonical repository outputs and fails loudly if they are missing.

### Imported frontier eval canonical run
- `outputs/imported_methodology_frontier_eval/<run_id>/summary.json`
- `outputs/imported_methodology_frontier_eval/<run_id>/method_metrics.csv`
- `outputs/imported_methodology_frontier_eval/<run_id>/oracle_gap_summary.csv`
- `outputs/imported_methodology_frontier_eval/<run_id>/matched_comparison_summary.csv`
- `outputs/imported_methodology_frontier_eval/<run_id>/budget_frontier_summary.csv`
- `outputs/imported_methodology_frontier_eval/<run_id>/signal_slice_summary.csv`

### Full method comparison canonical run
- `outputs/full_method_comparison_bundle/<run_id>/manifest.json`
- `outputs/full_method_comparison_bundle/<run_id>/per_seed_method_metrics.csv`
- `outputs/full_method_comparison_bundle/<run_id>/per_method_metrics.csv`
- `outputs/full_method_comparison_bundle/<run_id>/per_example_outcomes.csv`
- `outputs/full_method_comparison_bundle/<run_id>/per_budget_ranking.csv`
- `outputs/full_method_comparison_bundle/<run_id>/per_dataset_ranking.csv`

> Run selection rule: the latest directory under each canonical root that contains all required files.

## Generated outputs

### Tables (`outputs/paper_tables/`)
- `task_controller_summary.csv` (+ `.tex`)
- `main_frontier_comparison.csv` (+ `.tex`)
- `oracle_headroom_summary.csv`
- `anti_collapse_diagnostics.csv`
- `allocation_ablations.csv` (+ `.tex`)
- `robustness_sensitivity.csv`

### Plot data (`outputs/paper_plot_data/`)
- `figure1_support_metadata.csv`
- `main_frontier_curves.csv`
- `oracle_gap_curves.csv`
- `allocation_composition_by_budget.csv`
- `allocation_diversity_vs_budget.csv`
- `difficulty_slice_performance.csv`
- `appendix_per_dataset_frontier_curves.csv`

## Script entry points

Main runner:
- `scripts/paper/run_all_neurips_artifacts.py`

Table builder:
- `scripts/paper/build_neurips_tables.py`

Plot-data builders:
- `scripts/paper/build_frontier_plot_data.py`
- `scripts/paper/build_oracle_gap_plot_data.py`
- `scripts/paper/build_allocation_composition_plot_data.py`
- `scripts/paper/build_anti_collapse_plot_data.py`
- `scripts/paper/build_appendix_frontier_plot_data.py`

Shared utilities and validation:
- `scripts/paper/artifact_utils.py`

## How to rerun

From repository root:

```bash
python scripts/paper/run_all_neurips_artifacts.py
```

Optional check:

```bash
python -m py_compile scripts/paper/*.py
```

## Mapping to the NeurIPS paper story

- **Task/controller summary**: what datasets, method families, budgets, and metrics define the fixed-budget setup.
- **Main frontier comparison**: fixed-family vs heuristic adaptive vs oracle frontier at representative budgets.
- **Oracle headroom summary**: explicit remaining headroom from non-oracle methods to oracle.
- **Anti-collapse diagnostics**: diversity of family usage needed by oracle winner-share composition.
- **Ablations**: currently available anti-collapse-related variations (min-expand guards) plus explicit missing-ablation gaps.
- **Robustness/sensitivity**: seed-level and dataset-level sensitivity summaries for key methods.
- **Plot CSVs**: direct source data for main and appendix figures without generating binary images.

## Validation and reproducibility safeguards

- Required input files are validated; missing files raise hard errors.
- Latest valid run directories are selected by required-file completeness (prevents partial stale run selection).
- No binary artifacts are produced.
- Missing baselines/policies (uniform allocation, fully learned controller policy) are surfaced explicitly as missing instead of being fabricated.

## Scientific claims supported vs not supported

### Supported by current canonical outputs
- Fixed-budget cross-controller frontier comparisons.
- Oracle-gap/headroom accounting.
- Strongly conservative anti-collapse diversity proxies from per-example outcome composition.
- Seed/dataset sensitivity summaries for methods present in canonical bundle.

### Not currently supported as direct claims
- A canonical explicit uniform-allocation baseline curve/row.
- A canonical explicit learned cross-controller policy in the selected canonical bundle.
- Full feature-toggle ablations for family-aware/difficulty-aware/oracle-target supervision in paper-grade canonical outputs.

These missing components are reported as gaps in generated artifacts rather than inferred as available.
