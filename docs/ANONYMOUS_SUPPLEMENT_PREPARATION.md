# Anonymous Supplement Preparation (NeurIPS 2026)

This document defines the conservative process used to build an anonymized supplementary submission package for double-blind review.

## Included in the Anonymous Supplement

- Reviewer-facing top-level docs: `README.md`, `REPRODUCIBILITY.md`, `CLAIM_BOUNDARIES.md`, `ANONYMITY.md`, `MANIFEST.md`.
- Reproduction essentials: `pyproject.toml`, `requirements.txt`, `Makefile`, `QUICKSTART.md`.
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

## Final Readiness Audit (2026-04-24 UTC)

- Exact commands run:
  - `make check`
  - `make anonymous-supplement`
  - `python scripts/audit_anonymous_supplement.py --path dist/neurips2026_anonymous_supplement`
  - ZIP inspection (file count/size) via inline Python (`zipfile`)
  - Direct staged-token scan over `dist/neurips2026_anonymous_supplement/` (case-insensitive) with redacted snippets
- ZIP path: `dist/neurips2026_anonymous_supplement.zip`
- ZIP size: 2.249132 MB (2,358,386 bytes)
- Audit output directory: `outputs/anonymization_audit/20260424T012634Z`
- Blocking findings: 0
- Warning findings: 3
- Remaining warning explanation:
  - `scripts/audit_anonymous_supplement.py:52` uses absolute-path tokens as a regex detection pattern (`/home/`, `/Users/`, etc.); this is scanner logic, not leaked local provenance.
  - `scripts/verify_compute_optimal_tts_provenance.py:63` and `:149` contain the phrase `OpenReview/project/repo` in explanatory text; the `/project/` substring is a generic word token, not a machine-local absolute path.
- Upload readiness: ready to upload.
- Remaining manual action required: none.

### Final anonymization fix applied

- Removed `LICENSE` from the anonymous supplement top-level copy list because it contained a real author-name string; this avoids identity leakage while preserving reproducibility-critical files.

## Notes

- The anonymous supplement is built for reviewer reproducibility and claim-boundary clarity.
- The OpenAI-only real-model smoke run remains development/provenance-only and is not promoted as manuscript-facing headline evidence.
