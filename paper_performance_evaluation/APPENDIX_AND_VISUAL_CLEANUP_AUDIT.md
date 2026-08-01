# Appendix and Visual Cleanup Audit

Date: 2026-08-01

## Visual Review

The identified PDF was rendered page by page for visual inspection. The corrected identified build
has 33 pages.

## Figure and Table Changes

- Figure 4 retained in the main text. The include width was increased slightly and minimal LaTeX
  trimming was applied to reduce whitespace without changing the figure file or plotted data.
- Figure 4 caption revised to state that Frontier cost positions are lower bounds under incomplete
  challenger-phase token telemetry.
- Appendix discovery-selection scatter retained, but moved into a dedicated
  "Discovery-Selection Scatter Diagnostic" appendix section so the float no longer interrupts the
  additional-compute-detail section.
- Historical appendix tables for component diagnostics, non-math pilots, and partial
  self-consistency checks were removed from the manuscript and preserved in the supplementary note.
- `tables/table4_baseline_fidelity.tex` note revised from symbolic shorthand to prose.

## Appendix Material Retained

- gold-free runtime features;
- bounded repair;
- full baseline-fidelity explanation;
- provenance and trust tiers;
- statistical testing;
- Frontier/Pooled-4/FTA pseudocode;
- gate details and incumbent ablation;
- reproducibility records;
- discovery-selection scatter diagnostic;
- additional compute detail.

## Appendix Material Moved to Supplement

Moved to `supplementary_material/HISTORICAL_DIAGNOSTICS_SUPPLEMENT.md`:

- researcher-adaptation chronology;
- historical negative variants;
- historical component diagnostics;
- Natural Plan and GPQA pilot details;
- historical partial same-model self-consistency checks;
- raw held-out-selector protocol identifier.

## Layout Status

The compile leaves one small 2.608 pt output-routine overfull warning and underfull warnings in
dense tables, appendix prose, and bibliography lines. No material overfull boxes, clipping, missing
figures, or unreadable revised floats were observed in the visual review.
