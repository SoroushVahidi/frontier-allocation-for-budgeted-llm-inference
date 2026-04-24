# Anonymous Supplement Preparation (NeurIPS 2026)

This document describes how to build and audit an anonymous reviewer-facing supplement bundle.

## Included in the Anonymous Supplement

- Top-level reviewer docs generated at build time:
  - `README.md`
  - `REPRODUCIBILITY.md`
  - `CLAIM_BOUNDARIES.md`
  - `ANONYMITY.md`
  - `MANIFEST.md`
- Build/runtime files:
  - `pyproject.toml`
  - `requirements.txt`
  - `Makefile`
  - `QUICKSTART.md` (only if it passes anonymization filters)
- Reproducibility source trees:
  - `experiments/`
  - `configs/`
  - `tests/`
  - `scripts/paper/`
  - selected utility scripts needed for checks/artifact regeneration
- Paper-facing docs required for reproduction and claim boundaries:
  - `docs/NEURIPS_PAPER_ARTIFACTS.md`
  - `docs/PAPER_SOURCE_OF_TRUTH.md`
  - `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
  - `docs/PAPER_REPRODUCTION_CHECKLIST.md`
  - `docs/REPO_MAP.md`
  - `docs/CANONICAL_START_HERE.md`
  - `docs/CANONICAL_INSTALL_AND_DEV.md`
- Paper-facing outputs:
  - `outputs/paper_plot_data/`
  - `outputs/paper_tables/`
  - `outputs/paper_figures/`

## Excluded by Default

- VCS/automation metadata: `.git/`, `.github/`
- Operational/private trees: `archive/`, `logs/`, `jobs/`, `notebooks/`
- Env/cache metadata: `.env*`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`
- Notebook and transient artifacts: `*.ipynb`, `*.log`, `*.tmp`, `*.bak`
- Explicit private output:
  - `outputs/real_model_ours_vs_external_validation_20260424T_OPENAI_REAL_SMOKE/`
- Any file that matches identity/secret/local-path leakage patterns (author names, institution names, emails, private GitHub URLs, secret tokens, local absolute paths)

## Commands

```bash
make check
make anonymous-supplement
python scripts/audit_anonymous_supplement.py --path dist/neurips2026_anonymous_supplement
```

## Expected Build Outputs

- `dist/neurips2026_anonymous_supplement/`
- `dist/neurips2026_anonymous_supplement.zip`

## Ready-to-Upload Gate

The package is ready to upload when all are true:

1. `make check` passes.
2. `make anonymous-supplement` produces the staging directory and ZIP.
3. `python scripts/audit_anonymous_supplement.py --path dist/neurips2026_anonymous_supplement` reports **0 blocking findings**.
4. ZIP size is within the configured budget threshold.
