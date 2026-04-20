# NeurIPS Figures/Tables Status

## Successfully built

- Full text-only pipeline in `scripts/paper/` for plot-data and table generation.
- Canonical runner: `scripts/paper/run_all_neurips_paper_artifacts.py`.
- Main figure data CSV/JSON outputs in `outputs/paper_plot_data/`.
- Manuscript-ready table CSV/TeX outputs in `outputs/paper_tables/`.
- Canonical naming normalization documented in `docs/PAPER_NAMING_CANONICALIZATION.md`.

## Strongest figures/tables right now

- Main frontier and oracle-gap figures/tables (strongest canonical evidence).
- Anti-collapse diagnostics using action-family composition and concentration.
- Failure decomposition proxy view tied to signal-slice artifacts.

## Omitted or TODO-only items

- Appendix old-vs-current tree comparison: omitted (no committed canonical aligned artifact).
- Appendix output-layer repair effect: omitted (no committed canonical targeted repair bundle).

TODO note location:
- `outputs/paper_plot_data/appendix_missing_figures_todo.md`

## Cleaned inconsistencies

- Unified method naming map from script/raw ids to paper-facing names.
- Unified budget and metric key naming across scripts/CSV/TeX/docs.
- Explicitly marked proxy decomposition fields to avoid overclaiming.

## Remaining blockers

- Canonical multi-dataset matched frontier evidence is still sparse.
- External baselines remain mostly adjacent/import-validated rather than fully matched in this exact surface.
- Current canonical frontier run remains pilot-scale.
