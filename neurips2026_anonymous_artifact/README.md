# Anonymous NeurIPS 2026 Supplement Artifact

This package is an anonymous reviewer-facing artifact for NeurIPS 2026.

Canonical reproduction path (no external API keys required):

```bash
python scripts/check_repo_health.py
python -m pytest
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Canonical generated outputs appear in:
- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

Real-model/provider diagnostics are not part of the canonical reviewer reproduction path unless explicitly included and scoped in claim-boundary docs.
