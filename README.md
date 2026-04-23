# adaptive-reasoning-budget-allocation

NeurIPS-facing research codebase for **fixed-budget adaptive test-time compute allocation for LLM reasoning**.

## Project identity (canonical)

This repository centers on:
- branch-level frontier allocation under fixed budget,
- answer-group evidence aggregation,
- anti-collapse / repeated-same-family control,
- manuscript claim-boundary discipline.

## Non-negotiable two-surface distinction

- **Manuscript-facing matched-surface internal winner:** `strict_f3`
- **Broader operational default on a different surface:** `strict_gate1_cap_k6`

See:
- [`docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`](docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md)
- [`docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`](docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md)

## Fastest reliable path (front door)

1. [`QUICKSTART.md`](QUICKSTART.md)
2. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
3. [`docs/MANUSCRIPT_SUPPORT_DASHBOARD.md`](docs/MANUSCRIPT_SUPPORT_DASHBOARD.md)
4. [`docs/PAPER_SOURCE_OF_TRUTH.md`](docs/PAPER_SOURCE_OF_TRUTH.md)
5. [`docs/REPO_MAP.md`](docs/REPO_MAP.md)
6. [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md)

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

Compatibility alias (intentionally retained):

```bash
python scripts/paper/run_all_neurips_artifacts.py
```

Output roots:
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_tables/`

## Interpretation discipline

Use canonical docs + canonical artifact families for manuscript claims.
Do not elevate exploratory or historical outputs to headline evidence unless a canonical decision document explicitly promotes them.
