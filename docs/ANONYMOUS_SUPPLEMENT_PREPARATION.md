# Anonymous Supplement Preparation (NeurIPS 2026)

This document defines the conservative process used to build an anonymized supplementary submission package for double-blind review.

## Included in the Anonymous Supplement

- Reviewer-facing top-level docs: `README.md`, `REPRODUCIBILITY.md`, `CLAIM_BOUNDARIES.md`, `ANONYMITY.md`, `MANIFEST.md`.
- Reproduction essentials: `pyproject.toml`, `requirements.txt`, `Makefile`, `QUICKSTART.md`, `LICENSE`.
- Runtime/config/test code paths required for manuscript artifact checks and regeneration:
  - `experiments/`
  - `scripts/`
  - `configs/`
  - `tests/`
  - `references/` (as-is, subject to anonymization audit)
- Canonical paper-facing docs:
  - `docs/CANONICAL_START_HERE.md`
  - `docs/CANONICAL_INSTALL_AND_DEV.md`
  - `docs/PAPER_SOURCE_OF_TRUTH.md`
  - `docs/NEURIPS_PAPER_ARTIFACTS.md`
  - `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
  - `docs/PAPER_REPRODUCTION_CHECKLIST.md`
  - `docs/REPO_MAP.md`
  - `scripts/CANONICAL_START_HERE.md`
- Paper-facing outputs:
  - `outputs/paper_plot_data/`
  - `outputs/paper_tables/`
  - `outputs/paper_figures/`

## Excluded by Default

- Repository metadata and automation internals: `.git/`, `.github/`.
- Historical/archive/provenance clutter and caches: `archive/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`.
- Environment and log artifacts: `.env*`, `*.log`, `*.tmp`, `*.bak`.
- Notebook files with execution metadata: `*.ipynb`.
- OpenAI real-model smoke output package path:
  - `outputs/real_model_ours_vs_external_validation_20260424T_OPENAI_REAL_SMOKE/`

## Rebuild Commands

```bash
make check
python scripts/audit_anonymous_supplement.py
python scripts/build_anonymous_neurips_supplement.py
python scripts/audit_anonymous_supplement.py --path dist/neurips2026_anonymous_supplement
python - <<'PY'
from pathlib import Path
z = Path("dist/neurips2026_anonymous_supplement.zip")
print(z.exists(), z.stat().st_size)
PY
```

## Latest Build Snapshot

- ZIP path: `dist/neurips2026_anonymous_supplement.zip`
- ZIP size: 2.25 MB (2,358,951 bytes)
- Audit output root: `outputs/anonymization_audit/`
- Remaining warnings: 3 warnings in staged supplement audit (absolute-path token references in script text)
- Blocking findings: 0

## Notes

- The anonymous supplement is built for reviewer reproducibility and claim-boundary clarity.
- The OpenAI-only real-model smoke run remains development/provenance-only and is not promoted as manuscript-facing headline evidence.
