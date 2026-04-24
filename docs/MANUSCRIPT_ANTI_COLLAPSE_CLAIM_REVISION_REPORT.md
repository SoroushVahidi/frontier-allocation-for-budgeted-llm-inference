# MANUSCRIPT_ANTI_COLLAPSE_CLAIM_REVISION_REPORT

## Purpose
This report documents the text/table-only manuscript integration pass that resolves the Figure 7 anti-collapse contradiction using the targeted calibration sweep.

## Files modified (claim-revision scope)
- `docs/ANTI_COLLAPSE_CALIBRATION_SWEEP_REPORT.md`
- `docs/NEURIPS_FIGURE_CAPTION_STUBS.md`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/abstract_safe_revision.txt`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/README.md`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/method_operational_specification_insert.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/main_results_claim_safety_table_insert.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/appendix_claim_boundary_insert.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/limitations_rewrite.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/claim_box.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/FORBIDDEN_OVERCLAIMS.md`
- `outputs/anti_collapse_calibration_sweep_20260424T213046Z/summary.md`
- `outputs/anti_collapse_calibration_sweep_20260424T212621Z/summary.md`
- `outputs/anti_collapse_calibration_sweep_20260424TTESTACALZ/summary.md`
- `outputs/anti_collapse_calibration_sweep_20260424T213046Z/manifest.json`
- `outputs/anti_collapse_calibration_sweep_20260424T212621Z/manifest.json`
- `outputs/anti_collapse_calibration_sweep_20260424TTESTACALZ/manifest.json`
- `outputs/paper_tables/table_anti_collapse_calibration.csv`
- `outputs/paper_tables/table_anti_collapse_calibration.tex`
- `outputs/paper_plot_data/anti_collapse_calibration.csv`
- `scripts/paper/build_anti_collapse_calibration_table.py`
- `scripts/run_anti_collapse_calibration_sweep.py`

## Old claim patterns removed
- “weak-or-conditional jointly favored” (ambiguous shorthand)
- language implying anti-collapse as independently validated or universally helpful
- language implying the full controller is validated component-by-component
- wording that Figure 7 proves anti-collapse benefit

## New safe claim wording
- Weak anti-collapse is favored on the matched six-seed calibration surface.
- Off also beats default.
- Strong is approximately similar/slightly above default.
- Conditional is worse than default.
- Therefore default anti-collapse appears overactive/miscalibrated on this surface.
- Anti-collapse is framed as a calibration-sensitive design axis (answer-distinct preservation heuristic), not a universally validated independent gain.
- Early tree-shape control remains important; repeat-expansion moderation and answer-support aggregation are safer mechanism anchors.

## Key calibration numbers (six-seed matched surface)
- default: 0.5972
- off: 0.6241 (+0.0269 vs default)
- weak: 0.6407 (+0.0435 vs default)
- strong: 0.5991 (+0.0019 vs default)
- conditional: 0.5861 (-0.0111 vs default)

## How this resolves the reviewer concern
The contradiction is resolved by reframing anti-collapse as a calibration tradeoff, not a monotonic component gain. Figure 7's non-monotonic ablation (default anti-collapse removal helps on original surface) is now explicitly aligned with calibration follow-up evidence showing weak anti-collapse outperforms default while conditional underperforms. This removes component-wise overclaiming while preserving the broader upstream-tree-shape narrative.

## Forbidden wording (still disallowed)
- Any wording asserting anti-collapse as universally performance-improving.
- Any wording asserting anti-collapse as always improving accuracy.
- Any wording asserting every Strict-F3 component independently improves accuracy.
- Any wording asserting Figure 7 proves anti-collapse benefit.
- Any wording asserting full-controller component-by-component validation.
