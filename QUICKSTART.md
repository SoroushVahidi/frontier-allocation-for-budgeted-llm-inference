# Quickstart

Shortest reliable onboarding path.

## 1) Read first (10-minute orientation)

1. `docs/CANONICAL_START_HERE.md`
2. `docs/REPO_MAP.md`
3. `docs/OUTPUTS_ARTIFACT_INDEX.md` (canonical vs diagnostic vs provenance; OV rerank timestamps)
4. `docs/MANUSCRIPT_SUPPORT_DASHBOARD.md`
5. `docs/PAPER_SOURCE_OF_TRUTH.md`
6. `docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
7. `docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`
8. `docs/SELECTOR_AND_COVERAGE_CONTROLLER_ROADMAP_20260429.md` (selector vs coverage sequencing)

## 2) Keep this explicit in every summary

- Manuscript-facing matched-surface internal winner: `strict_f3`
- Broader operational default on a different surface: `strict_gate1_cap_k6`
- The `strict_f3` vs `strict_gate1_cap_k6` margin on matched-surface slices is currently fragile/non-decisive.

These are valid on different decision surfaces and should not be merged.

## 3) Setup + lightweight checks

```bash
python -m venv .venv
source .venv/bin/activate
make setup
make health
make reviewer-test
python -m pytest -q tests/test_frontier_router.py tests/test_check_repo_health_paths.py
```

Optional full-suite command (environment-dependent):
```bash
python -m pytest -q
```

## 4) Regenerate canonical paper artifacts

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Output roots:
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_tables/`

Only these canonical roots are headline-claim eligible by default.

## 5) Before writing manuscript-facing claims

Read:
- `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
- `docs/PAPER_BASELINE_HONESTY_STATUS.md`
- `docs/MAIN_TABLE_EXTERNAL_BASELINE_FAIRNESS_AUDIT_20260423T205134Z.md`
- `docs/PAPER_OPEN_GAPS_AND_RISKS.md`

Rule: if a result is not promoted by canonical docs, treat it as supportive, diagnostic, or provenance-only.

## 6) Reviewer-facing scope check

Before final narrative edits, use:

- `docs/REVIEWER_REPRO_AND_SCOPE_GUIDE.md`
- `docs/REVIEWER_10_MINUTE_REPRODUCTION.md`
- `docs/REPO_MAP.md`
