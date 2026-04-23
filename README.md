# adaptive-reasoning-budget-allocation

Repository for a **NeurIPS-facing research project** on **fixed-budget adaptive test-time compute allocation for LLM reasoning** (frontier allocation).

## 1) What this repository is about now

The current canonical question is:

> **Given a fixed budget, which active branch should receive the next unit of compute, and when should the controller continue vs commit?**

Current emphasis:
- branch-level frontier allocation under fixed budgets,
- answer-group evidence aggregation,
- anti-collapse tree-shape control,
- strict phased evaluation discipline,
- and conservative manuscript claim boundaries.

## 2) What this repository is *not* about

- It is **not** centered on the older binary revise-routing storyline.
- It is **not** a claim that external baseline closure is complete.
- It is **not** a claim that real-model confirmation is fully comprehensive.

## 3) What to read first (safe front door)

1. [`QUICKSTART.md`](QUICKSTART.md)
2. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
3. [`docs/PAPER_START_HERE.md`](docs/PAPER_START_HERE.md)
4. [`docs/PAPER_SOURCE_OF_TRUTH.md`](docs/PAPER_SOURCE_OF_TRUTH.md)
5. [`docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`](docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md)
6. [`docs/PAPER_ARTIFACT_MAP.md`](docs/PAPER_ARTIFACT_MAP.md)
7. [`docs/PAPER_REPRODUCTION_CHECKLIST.md`](docs/PAPER_REPRODUCTION_CHECKLIST.md)
8. [`docs/PAPER_BASELINE_HONESTY_STATUS.md`](docs/PAPER_BASELINE_HONESTY_STATUS.md)
9. [`docs/PAPER_OPEN_GAPS_AND_RISKS.md`](docs/PAPER_OPEN_GAPS_AND_RISKS.md)
10. [`docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`](docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md)

## 4) How to run basic checks

```bash
make setup
make smoke
make health
make lint
make test
make check
```

Use `make help` for the full checklist.

## 5) How to regenerate paper-facing artifacts

Canonical paper artifact pipeline:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Then inspect:
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_tables/`

And reconcile with:
- [`docs/PAPER_ARTIFACT_MAP.md`](docs/PAPER_ARTIFACT_MAP.md)
- [`docs/PAPER_REPRODUCTION_CHECKLIST.md`](docs/PAPER_REPRODUCTION_CHECKLIST.md)

## 6) Where safe manuscript claims come from

Use only canonical, artifact-backed documents:
- [`docs/PAPER_SOURCE_OF_TRUTH.md`](docs/PAPER_SOURCE_OF_TRUTH.md)
- [`docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`](docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md)
- [`docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`](docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md)
- [`docs/PAPER_BASELINE_HONESTY_STATUS.md`](docs/PAPER_BASELINE_HONESTY_STATUS.md)

Do not elevate isolated output folders to headline claims unless those folders are explicitly linked by canonical docs.

---

## Canonical two-surface distinction (must remain explicit)

- **Manuscript-facing matched-surface internal winner:** `strict_f3`
- **Broader operational default on a different surface:** `strict_gate1_cap_k6`

Reference:
- [`docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`](docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md)
- [`docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`](docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md)

## Repository map (roles by directory)

- `docs/`: canonical interpretation + exploratory + historical policy/navigation.
- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact experiment/result notes.
- `configs/`: machine-readable experiment/dataset/baseline contracts.
- `outputs/`: generated artifacts, including paper artifact outputs.
- `tests/`: lightweight health/regression checks.
- `references/`: bibliography and literature notes.
- `external/`: external baseline tracking and integration/provenance.
- `archive/`: historical/provenance-only preserved materials.
- `jobs/`: cluster/batch submission entry points.

For more detail, use:
- [`docs/README.md`](docs/README.md)
- [`docs/REPO_MAP.md`](docs/REPO_MAP.md)
- [`scripts/README.md`](scripts/README.md)
- [`outputs/README.md`](outputs/README.md)
