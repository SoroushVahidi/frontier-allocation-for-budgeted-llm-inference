# Canonical Matched-Surface Regime Breakdown (20260423T012859Z)

## Purpose
Answer whether current aggregate matched-surface results hide a cleaner regime-specific paper story, without running new experiments.

## Inputs (canonical only)
- `outputs/matched_surface_multiseed_main_comparison_20260423T002000Z/raw_case_results.csv`.
- Companion summary/significance files from the same canonical bundle.

## Regime definition
- Primary regimes: dataset × budget (3 datasets × 3 budgets = 9 regimes).
- Secondary rollups: dataset-only and budget-only.

## Main result
- `strict_f3` beats the strongest available external comparator mean accuracy in **all 9/9** dataset×budget regimes on the canonical matched surface.
- Therefore, a **regime-qualified claim is supported** at the regime-mean level.

## Required qualification
- Seed-level deltas are not universally positive inside every regime, so avoid universal per-seed wording.
- Recommended wording should explicitly anchor to regime means on this canonical surface.

## Recommended manuscript-facing wording
> On the canonical matched surface (datasets × budgets 4/6/8), strict_f3 outperforms the strongest available external comparator in every dataset–budget regime at the regime-mean level. We report this as regime-qualified dominance on matched means and do not claim universal per-seed dominance within each regime.

## Recommendation
- **Use regime-qualified claims** in paper-facing text.
- Keep scope bounded to the canonical matched surface and include the seed-variability caveat.

## Artifact bundle
- `outputs/canonical_matched_surface_regime_breakdown_20260423T012859Z/`
