# ICC refinement and subtype diagnosis status (2026-04-19)

Bounded refinement pass inside the incumbent-vs-challenger commit-controller family.

- Config: `configs/incumbent_challenger_refinement_pass_20260419_v1.json`
- Runner: `scripts/run_incumbent_challenger_refinement_pass_20260419.py`
- Artifacts: `outputs/incumbent_challenger_refinement_pass_20260419/`

## What was tested
Compared:
1. `broad_diversity_aggregation_strong_v1` (base)
2. `broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_v1` (dependence-aware ICC)
3. `broad_diversity_aggregation_strong_v1_incumbent_challenger_raw_support_v1` (raw ICC)
4. `broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_late_guard_v1` (refinement A)
5. `broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_switch_persistence_v1` (refinement B)

Both refinements were chosen as minimal, directly motivated attempts to reduce residual late wrong-commit behavior.

## Direct answers from this bounded pass
- **Main residual wrong-commit subtype:** `wrong_late_commit` remained dominant.
- **Which refinement helped most:** neither beat the current dependence-aware ICC.
- **Did any refinement beat dependence-aware ICC:** no.
- **Is ICC still a leading serious line:** yes, but this pass indicates these two minimal refinements did not improve it.
- **Single best next step:** do a small, targeted calibration around the current dependence-aware ICC focused only on the late-commit residual regime.

## Key outcomes
- Dependence-aware ICC still improved over base on this run (`wrong_commit_timing` lower than base).
- Raw-support ICC was stronger than dependence-aware ICC in this specific rerun.
- Both tested refinements degraded vs dependence-aware ICC on both accuracy and wrong-commit timing.

## Produced outputs
- `aggregate_comparison_metrics.json`
- `per_method_metrics.json`
- `subtype_shift_summary.json`
- `harmed_case_mining_dependence_aware_vs_base.json`
- `refinement_specific_diagnostics.json`
- refinement-vs-ICC improved/harmed/unchanged registries
- `run_manifest.json`
- `STATUS_NOTE_icc_refinement_pass_20260419.md`
