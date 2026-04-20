# NeurIPS Figures and Tables Status

## Successfully built

- Full manuscript pipeline under `scripts/paper/` with shared canonical style/config.
- All main-paper figures (1-7) exported as PDF/PNG.
- All requested main tables (1-6) exported as CSV/TeX.
- Canonical naming map and artifact audit docs refreshed.

## Strongest artifacts right now

- Figure 2 / Figure 3 + Table 2 / Table 3:
  clear frontier and oracle-gap story over multi-dataset canonical run.
- Figure 4 / Figure 5 + Table 4:
  anti-collapse and allocation-composition diagnostics tied to action-level metrics.
- Figure 7 + Table 6:
  per-dataset behavior and explicit robustness/limitations framing.

## Omitted or caveated artifacts

- Old-vs-current tree comparison appendix figure:
  omitted from automatic build due missing canonical plot-ready bundle under current naming schema.
- Output-layer repair effect appendix figure:
  omitted from automatic build due missing canonical multi-dataset frontier-aligned repair bundle.
- Figure 6 failure decomposition is explicitly marked as subtype-proxy decomposition from defeat-case registry, not direct tree-membership telemetry.

## Naming conflicts cleaned up

- Unified method labels across scripts/CSVs/tables/figures via `docs/PAPER_NAMING_CANONICALIZATION.md`.
- Explicitly marked promoted method as `Promoted (Strict-Coupled Tie-Aware, bridged)` to avoid overclaiming native controller integration in frontier schema.
- Harmonized metric capitalization and axis labels (`Accuracy`, `Gap to Oracle`, `Average Actions`).

## Remaining blockers

- Promoted strict-coupled/tie-aware controller needs native integration into frontier evaluator.
- External baseline completeness remains uneven for direct apples-to-apples claims.
- Current multi-dataset frontier run remains bounded scale (single seed per dataset in this canonical run).
