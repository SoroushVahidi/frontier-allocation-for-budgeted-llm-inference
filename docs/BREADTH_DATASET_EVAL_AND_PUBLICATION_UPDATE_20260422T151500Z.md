# Breadth dataset evaluation and publication update (20260422T151500Z)

## What was run

A targeted publication-facing breadth pass was executed via:

- `python scripts/run_breadth_dataset_eval.py`

Configuration used:

- Datasets (priority order):
  1. `allenai/drop`
  2. `TAUR-Lab/MuSR`
  3. `openeval/BIG-Bench-Hard`
  4. `deepmind/aqua_rat`
- Methods compared:
  - `strict_f3`
  - `external_l1_max`
  - `external_s1_budget_forcing` (optional lighter direct baseline included)
- Seeds: `11,23`
- Budgets: `6,8`
- Subset size: `24` examples per dataset/seed

Output bundle:

- `outputs/breadth_dataset_eval/20260422T150956Z/`

## What succeeded

All target datasets were runnable in this pass and produced method-level comparison artifacts.

Successful datasets:

- DROP (`allenai/drop`)
- MuSR (`TAUR-Lab/MuSR`)
- BIG-Bench Hard (`openeval/BIG-Bench-Hard`)
- AQuA (`deepmind/aqua_rat`)

Key strict comparison finding in this pass:

- `strict_f3` outperformed `external_l1_max` on all 4 evaluated breadth datasets in this run configuration.

## What failed / partial and why

No dataset was blocked or partial in this pass.

- `blocked_or_partial_datasets.csv` is intentionally empty for this run.

## Important caveats and claim boundary

1. This run is breadth-evaluation evidence on newly integrated datasets, not a replacement for the canonical main-table matched surface.
2. These evaluations use the repository's existing simulation/controller substrate and should be reported with scope discipline.
3. The claim remains **competitive and publication-worthy breadth evidence**, not universal dominance claims.

## Reviewer concern status: "too math-heavy"

Materially reduced compared with pre-pass state, because the package now contains actual evaluation outputs for non-math-heavy additions (DROP, MuSR, BIG-Bench Hard) plus AQuA.

## Manuscript-safe wording supported now

Use wording at this specificity level:

1. "Beyond the math-core canonical surface, we ran a targeted breadth pass on DROP, MuSR, BIG-Bench Hard, and AQuA under the same repository evaluation substrate."
2. "In this breadth pass configuration, `strict_f3` remained competitive and outperformed the strongest fair direct external baseline (`external_l1_max`) on each evaluated breadth dataset."
3. "These breadth results strengthen cross-domain evidence but are reported as expansion/appendix support rather than replacing the canonical main matched-surface table."

## Main-paper vs appendix placement recommendation

- **Main paper:** keep canonical matched near-direct table scope unchanged.
- **Appendix:** include breadth dataset results table and discussion of non-math expansion behavior.

## Publication package update performed

The publication package was rebuilt and extended with breadth artifacts:

- Package: `outputs/publication_tables_package/20260422T235959Z/`
- Added appendix table:
  - `appendix_f_breadth_dataset_results.csv`
  - `appendix_f_breadth_dataset_results.md`
- Updated:
  - `appendix_tables_index.csv`
  - `main_paper_dataset_plan.csv` / `.md`
  - `appendix_dataset_plan.csv` / `.md`
  - package `summary.json` and `status.json` breadth pointers

