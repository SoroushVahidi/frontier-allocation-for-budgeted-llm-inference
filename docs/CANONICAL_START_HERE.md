# Canonical start here

Fastest reliable orientation for collaborators, reviewers, and manuscript-writing agents.

## Current repository identity

Canonical scope:
- fixed-budget adaptive test-time compute allocation,
- branch-level frontier allocation,
- answer-group evidence aggregation,
- anti-collapse / repeated-family control,
- conservative claim boundaries.

## Non-negotiable method-surface distinction

- **Manuscript-facing matched-surface internal winner:** `strict_f3`
- **Broader operational default on a different surface:** `strict_gate1_cap_k6`
- **Matched-surface margin status:** fragile/non-decisive unless canonical statistical evidence explicitly supports a stronger statement.

See:
- [`INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`](INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md)
- [`MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`](MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md)

## Evidence classes (do not merge)

| Class | Meaning |
|-------|---------|
| **Canonical paper-facing** | `outputs/paper_tables/`, `outputs/paper_plot_data/`, `outputs/paper_figures/` produced via canonical paper runners; claim-eligible only with `PAPER_SOURCE_OF_TRUTH.md` alignment. |
| **Diagnostic real-model** | API-backed runs under `outputs/` (e.g. real-model validation bundles); supporting/appendix unless promoted. |
| **Mock-backed diagnostic** | Runs where an optional backend (e.g. OV rerank verifier) stayed on **mock** defaults — **not** evidence for “real Cohere verifier improved accuracy.” |
| **Active / in-flight** | A job currently writing an output directory — **read-only** inspection; do not delete or overwrite artifacts mid-run. |
| **Provenance-only** | Interrupted, partial, or superseded timestamps kept for traceability — not current headline truth. |

**OV rerank timestamps:** mock-only provenance `20260429T_OV_RERANK_100CASE`; Cohere verifier backend run `20260429T_OV_RERANK_100CASE_COHERE_BACKEND` (interpret only when complete). Detail: [`OUTPUTS_ARTIFACT_INDEX.md`](OUTPUTS_ARTIFACT_INDEX.md).

## Read in this order

1. [`CANONICAL_EXPERIMENT_STACK.md`](CANONICAL_EXPERIMENT_STACK.md)
2. [`MANUSCRIPT_SUPPORT_DASHBOARD.md`](MANUSCRIPT_SUPPORT_DASHBOARD.md)
3. [`PAPER_SOURCE_OF_TRUTH.md`](PAPER_SOURCE_OF_TRUTH.md)
4. [`PAPER_CLAIMS_AND_EVIDENCE_MAP.md`](PAPER_CLAIMS_AND_EVIDENCE_MAP.md)
5. [`FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`](FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md)
6. [`MAIN_TABLE_EXTERNAL_BASELINE_FAIRNESS_AUDIT_20260423T205134Z.md`](MAIN_TABLE_EXTERNAL_BASELINE_FAIRNESS_AUDIT_20260423T205134Z.md)
7. [`REPO_MAP.md`](REPO_MAP.md)
8. [`OUTPUTS_ARTIFACT_INDEX.md`](OUTPUTS_ARTIFACT_INDEX.md)
9. [`SELECTOR_AND_COVERAGE_CONTROLLER_ROADMAP_20260429.md`](SELECTOR_AND_COVERAGE_CONTROLLER_ROADMAP_20260429.md)
10. [`CANONICAL_INSTALL_AND_DEV.md`](CANONICAL_INSTALL_AND_DEV.md)
11. [`../scripts/CANONICAL_START_HERE.md`](../scripts/CANONICAL_START_HERE.md)
12. [`REVIEWER_REPRO_AND_SCOPE_GUIDE.md`](REVIEWER_REPRO_AND_SCOPE_GUIDE.md)
13. [`REVIEWER_10_MINUTE_REPRODUCTION.md`](REVIEWER_10_MINUTE_REPRODUCTION.md)

## Canonical first commands

Run from **repository root**:

```bash
make setup
make health
make reviewer-test
python -m pytest -q tests/test_frontier_router.py tests/test_check_repo_health_paths.py
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Interpretation rules

- Canonical docs are interpretation authority.
- Supportive/appendix artifacts remain bounded unless canonically promoted.
- Historical materials are preserved for provenance, not current default truth.
- Real-model and diagnostic runs are supporting evidence unless promoted by canonical decision docs.
- Do **not** claim **`external_l1_max` is beaten** by DR-v2 variants unless a completed, claim-safe evaluation doc supports it (completed paired rows, policy note).
