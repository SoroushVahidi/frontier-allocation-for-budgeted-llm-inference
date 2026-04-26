# Reviewer Repro And Scope Guide

This note is a reviewer-facing quick reference for reproducibility and claim scope.

## 1) Canonical reproduction commands

Run from repository root:

```bash
python scripts/check_repo_health.py
python -m pytest
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Canonical paper-facing outputs:

- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

## 2) What is and is not recomputed by the canonical paper runner

- Recomputed by `run_all_neurips_paper_artifacts.py`:
  - paper plot-data packaging,
  - paper table rendering (CSV/TeX),
  - paper figure binaries.
- Not a full raw experiment recomputation pipeline:
  - it consumes committed canonical machine-readable evidence bundles.

## 3) Method-surface distinction required for safe interpretation

- Manuscript-facing matched-surface representative: `strict_f3`.
- Broader operational default on a different surface: `strict_gate1_cap_k6`.
- `strict_f3` vs `strict_gate1_cap_k6` margin on matched-surface slices is currently fragile/non-decisive.

## 4) Baseline scope

- Main-table-ready baselines are those promoted by canonical baseline-readiness docs and tables.
- Appendix-only or diagnostic baselines should remain explicitly labeled as such.

## 5) Real-model evidence scope

- OpenAI/Cohere real-model runs are diagnostic/supporting evidence.
- They should not be framed as universal dominance evidence.
- Any claim using them must include provider/model/dataset/budget/seed contract and matching caveats.

## 6) Artifact classes

- Canonical paper-facing evidence: promoted output roots and docs.
- Appendix/supporting evidence: robustness and diagnostics scoped by docs.
- Exploratory/provenance-only evidence: historical or partial packages.
- Non-review/private/local-only artifacts: never claim-bearing.
