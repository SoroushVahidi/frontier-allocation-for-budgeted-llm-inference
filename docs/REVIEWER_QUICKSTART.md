# Reviewer Quickstart (Anonymous)

## 1) Reproduce paper-facing artifacts

```bash
python scripts/check_repo_health.py
python -m ruff check
python -m pytest
python scripts/paper/run_all_neurips_paper_artifacts.py
```

If full `pytest` is slow, run targeted tests (documented in `docs/RESULTS_GUIDE.md`) plus artifact regeneration.

## 2) Find canonical outputs

- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

## 3) Understand evidence boundaries

- Canonical claims: `docs/PAPER_SOURCE_OF_TRUTH.md`
- Claim wording limits: `docs/CLAIM_BOUNDARIES.md`
- Full artifact classification: `docs/ARTIFACT_MANIFEST.md`

## 4) Optional (not required for review)

Provider API-based runs (OpenAI/Cohere) are optional diagnostics only and not needed to regenerate paper-facing evidence.
