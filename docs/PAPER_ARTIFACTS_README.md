# PAPER_ARTIFACTS_README

This document defines the paper-facing artifact path, and separates canonical outputs from diagnostics.

## Canonical regeneration command

Run the canonical paper artifact pipeline:

```bash
python scripts/check_repo_health.py
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Canonical output directories

- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

These are the primary sources for manuscript-facing claims.

## Paper-facing vs diagnostic outputs

- **Paper-facing**: artifacts produced by `scripts/paper/run_all_neurips_paper_artifacts.py` into the three directories above.
- **Diagnostic only**: Cohere real-model and trace-focused audits such as:
  - `outputs/real_model_ours_vs_external_validation_*/`
  - `outputs/cohere_absent_from_tree_loss_diagnostics_*/`
  - `outputs/cohere_trace_complete_loss_subset_*/`
  - `outputs/cohere_direct_reserve_validation_*/`

Diagnostic outputs are useful for failure analysis and roadmap decisions, but are not automatically claim-bearing for the paper.

## Reviewer inspection priority

Reviewers should inspect, in order:

1. `docs/PAPER_SOURCE_OF_TRUTH.md`
2. `docs/CLAIM_BOUNDARIES_CURRENT.md`
3. `docs/SAFE_CLAIMS_FOR_NEURIPS_2026.md`
4. `outputs/paper_tables/`
5. `outputs/paper_plot_data/`
6. `outputs/paper_figures/`

## Anonymous artifact omission policy

Intentionally omitted from anonymous claim-bearing scope:

- local runtime traces and temporary debug logs,
- provider-key readiness failure notes tied to local environment,
- large exploratory outputs not required for canonical paper claims.

This omission policy does not delete diagnostics; it keeps claim boundaries explicit.
