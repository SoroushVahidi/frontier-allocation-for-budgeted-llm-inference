# Quickstart

Shortest reliable onboarding path for this repository.

## 1) Understand the project in 5 minutes

Read:
1. `docs/CANONICAL_START_HERE.md`
2. `docs/CANONICAL_EXPERIMENT_STACK.md`
3. `docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
4. `docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`
5. `docs/PAPER_SOURCE_OF_TRUTH.md`

## 2) Keep this distinction explicit

- Manuscript-facing matched-surface internal winner: `strict_f3`
- Broader operational default on a different surface: `strict_gate1_cap_k6`

These are both valid, but they are **different decision surfaces**.

## 3) Setup and lightweight checks

```bash
python -m venv .venv
source .venv/bin/activate
make setup
make check
```

## 4) Canonical paper artifact pass

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Outputs:
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_tables/`

## 5) Before writing claims or summaries

Read:
- `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
- `docs/PAPER_BASELINE_HONESTY_STATUS.md`
- `docs/PAPER_OPEN_GAPS_AND_RISKS.md`
- `docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`

Rule: if a result is not promoted by canonical docs, treat it as supportive/provenance only.
