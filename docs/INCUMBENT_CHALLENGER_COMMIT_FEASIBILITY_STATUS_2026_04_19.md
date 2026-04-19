# Incumbent-vs-challenger commit feasibility status (2026-04-19)

## Scope
Bounded feasibility pass inside the current broad diversity-aware family (no full controller replacement).

Compared methods:
- base: `broad_diversity_aggregation_strong_v1`
- incumbent/challenger commit (dependence-aware): `broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_v1`
- incumbent/challenger commit (raw-support-only): `broad_diversity_aggregation_strong_v1_incumbent_challenger_raw_support_v1`
- canonical baselines for context: `self_consistency_3`, `adaptive_min_expand_1`, `selective_sc_hybrid_v1`, `broad_diversity_aggregation_v1`
- diagnostic reference: `broad_diversity_aggregation_strong_v1_diversity_needed_gate`

Artifacts: `outputs/incumbent_challenger_commit_feasibility_20260419/`

## Direct answers

### Is incumbent-vs-challenger commit control a serious next integration candidate?
**Yes, as a bounded next integration candidate.**
It improved accuracy over the base (+0.0255) and reduced `wrong_commit_timing` by 30 cases on this matched pass.

### Did it reduce wrong commit timing?
**Yes.**
`wrong_commit_timing` went from **275** (base) to **245** (dependence-aware ICC).

### Did dependence-aware support help?
**Mixed.**
- Dependence-aware ICC had better commit-timing reduction (245 vs 248 wrong-commit cases)
- Raw-support ICC had slightly higher accuracy (0.6435 vs 0.6343)
So dependence-aware support appears useful for commit control but needs calibration to recover some accuracy.

### Best next step after this pass
Run one deeper bounded calibration pass on the incumbent/challenger rule:
- tune margin + stability thresholds,
- keep dependence discounting,
- specifically target near-tie harm while preserving the wrong-commit reduction.

## Short interpretation
The pass supports answer-group-level incumbent/challenger control as a real direction: it attacks the newly dominant bottleneck (`wrong_commit_timing`) with measurable gains. However, dependence-aware support requires additional calibration to beat raw-support ICC on overall accuracy.

