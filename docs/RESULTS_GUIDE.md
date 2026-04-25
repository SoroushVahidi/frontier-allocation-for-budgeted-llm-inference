# RESULTS_GUIDE

## Canonical paper-facing results

Primary directories:
- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

Primary builder:
- `python scripts/paper/run_all_neurips_paper_artifacts.py`

## Appendix/supporting results

Examples:
- anti-collapse calibration sweeps
- matched-budget ToT-style adapter analyses
- external-validity expansions under explicit contracts
- fairness/contract checklists

These are supporting context and should not be used to overstate headline claims.

## Exploratory/provenance-only results

Explicitly exploratory/provenance-only unless promoted by the manuscript:
- Cohere real-model diagnostics and decision packages
- rich failure-trace packages and partial runs
- incomplete/negative real-model runs
- `strict_f3_case_split_direction_aware_v1` offline evaluation

For `strict_f3_case_split_direction_aware_v1` (offline):
- `strict_f3_case_split_direction_aware_v1`: **0.5952**
- `strict_f3`: **0.6085**

Interpretation: this exploratory case-split/direction-aware variant did not improve over `strict_f3`; keep as calibration-sensitive negative evidence.

## Reproduction checks (no external APIs)

```bash
python scripts/check_repo_health.py
python -m ruff check
python -m pytest
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Python-only checks for environments that cannot execute make

Use the commands above directly. `make check` may remain available for local users but is not required for anonymous review reproduction.
