# Quickstart

Shortest reliable onboarding path.

## 1) Read first (10-minute orientation)

1. `docs/CANONICAL_START_HERE.md`
2. `docs/MANUSCRIPT_SUPPORT_DASHBOARD.md`
3. `docs/PAPER_SOURCE_OF_TRUTH.md`
4. `docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
5. `docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`

## 2) Keep this explicit in every summary

- Manuscript-facing matched-surface internal winner: `strict_f3`
- Broader operational default on a different surface: `strict_gate1_cap_k6`

These are valid on different decision surfaces and should not be merged.

## 3) Setup + lightweight checks

```bash
python -m venv .venv
source .venv/bin/activate
make setup
make check
```

## 4) Regenerate canonical paper artifacts

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Output roots:
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_tables/`

## 5) Before writing manuscript-facing claims

Read:
- `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
- `docs/PAPER_BASELINE_HONESTY_STATUS.md`
- `docs/MAIN_TABLE_EXTERNAL_BASELINE_FAIRNESS_AUDIT_20260423T205134Z.md`
- `docs/PAPER_OPEN_GAPS_AND_RISKS.md`

Rule: if a result is not promoted by canonical docs, treat it as supportive or historical.
