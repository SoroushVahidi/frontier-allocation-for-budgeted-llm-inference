# Adaptive Reasoning Budget Allocation (Anonymous NeurIPS 2026 Repository)

This repository studies **frontier allocation for budgeted LLM inference** under explicit action-budget contracts.

## Main reproducible claims (paper-facing)

- The paper uses a **matched action-budget surface** and **matched-budget adapter baselines**.
- Canonical tables/figures are regenerated from committed scripts and artifacts without external LLM APIs.
- Real-model provider runs are retained as **supporting/diagnostic real-model audits** (not evidence of universal dominance).

## Canonical reproduction path (no API keys required)

```bash
python scripts/check_repo_health.py
python -m ruff check
python -m pytest
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Canonical outputs:
- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

## Reviewer navigation

- `docs/REVIEWER_QUICKSTART.md`
- `docs/PAPER_SOURCE_OF_TRUTH.md`
- `docs/RESULTS_GUIDE.md`
- `docs/CLAIM_BOUNDARIES.md`
- `docs/ARTIFACT_MANIFEST.md`

## Scope separation

- **Paper-facing canonical evidence:** matched-surface manuscript artifacts used by paper tables/figures.
- **Appendix/supporting evidence:** robustness, ablations, and contract/fairness checks.
- **Exploratory/provenance-only evidence:** negative/partial runs and exploratory algorithm attempts.
- **Non-review/private/local-only:** machine-local traces, task metadata, and private execution leftovers (flagged in manifests; not used for claims).

## External API note

Paper artifact regeneration does **not** require OpenAI/Cohere keys. Optional real-model scripts that require provider keys are explicitly labeled and are not required for reviewer reproduction.
