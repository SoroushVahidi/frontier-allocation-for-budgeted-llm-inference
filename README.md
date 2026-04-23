# adaptive-reasoning-budget-allocation

NeurIPS-facing research codebase for **fixed-budget adaptive test-time compute allocation for LLM reasoning**.

## Project identity (current canonical scope)

This repository focuses on:
- branch-level frontier allocation under fixed budget,
- answer-group evidence aggregation,
- anti-collapse / repeated-same-family control,
- explicit manuscript claim-boundary discipline.

This repository is **not** currently centered on the older binary revise-routing storyline.

## Required two-surface distinction

Keep this explicit in docs, code comments, and paper text:
- **Manuscript-facing matched-surface internal winner:** `strict_f3`
- **Broader operational default on a different surface:** `strict_gate1_cap_k6`

Reference: [`docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`](docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md), [`docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`](docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md).

## Front door (read in order)

1. [`QUICKSTART.md`](QUICKSTART.md)
2. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
3. [`docs/CANONICAL_EXPERIMENT_STACK.md`](docs/CANONICAL_EXPERIMENT_STACK.md)
4. [`docs/PAPER_SOURCE_OF_TRUTH.md`](docs/PAPER_SOURCE_OF_TRUTH.md)
5. [`docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`](docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md)
6. [`docs/PAPER_BASELINE_HONESTY_STATUS.md`](docs/PAPER_BASELINE_HONESTY_STATUS.md)
7. [`docs/PAPER_OPEN_GAPS_AND_RISKS.md`](docs/PAPER_OPEN_GAPS_AND_RISKS.md)
8. [`docs/REPO_MAP.md`](docs/REPO_MAP.md)
9. [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md)

## Developer checks

```bash
make setup
make smoke
make health
make lint
make test
make check
```

## Paper artifact regeneration

Canonical runner:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Compatibility alias (kept intentionally):

```bash
python scripts/paper/run_all_neurips_artifacts.py
```

Artifact roots:
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_tables/`

## Claim-discipline rule

Only promote claims that are backed by canonical docs + canonical artifact families.
Do not elevate isolated exploratory output folders to headline evidence unless a canonical decision doc explicitly promotes them.
