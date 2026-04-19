# Incumbent-vs-challenger commit stronger validation status (2026-04-19)

This note summarizes the first serious follow-up validation pass after the bounded feasibility result.

- Run artifacts: `outputs/incumbent_challenger_commit_validation_20260419/`
- Repro config: `configs/incumbent_challenger_commit_validation_20260419_v1.json`
- Runner: `scripts/run_incumbent_challenger_commit_validation_pass_20260419.py`

## Scope
- Stronger matched validation on the exact-answer math expansion bundle (`HuggingFaceH4/aime_2024`, `MathArena/aime_2025`, `MathArena/hmmt_feb_2025`, `MathArena/brumo_2025`).
- Matched seeds/budgets: seeds `[11,23,37,41,53]`, budgets `[4,6,8,10]`, subset size `30`.
- Methods compared:
  1. `broad_diversity_aggregation_strong_v1` (base)
  2. `broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_v1` (dependence-aware)
  3. `broad_diversity_aggregation_strong_v1_incumbent_challenger_raw_support_v1` (raw-support)

## Direct answers
- **Still improving on stronger validation?** Yes, modestly: dependence-aware ICC improved accuracy and reduced wrong-commit timing versus base.
- **Which wrong-commit subtype is fixed best?** In this run, reductions concentrated in `wrong_late_commit`.
- **What harmed cases remain?** Both variants still harm non-trivial counts, with case concentration analyzed in harmed registries.
- **Is dependence-aware truly better than raw-support?** Mixed but favorable on commit-timing reduction: dependence-aware reduced more wrong-commit timing than raw-support; raw-support did not surpass dependence-aware on this stronger run.
- **Leading next method line?** Yes, as the strongest bounded next integration candidate inside the current family.
- **Single best next step:** bounded calibration of dependence discount and margin thresholds, targeted at near-tie and fragmented-support harm while preserving wrong-late-commit gains.

## Key quantitative summary
- Accuracy delta vs base:
  - dependence-aware ICC: `+0.0067`
  - raw-support ICC: `+0.0013`
- wrong_commit_timing delta vs base:
  - dependence-aware ICC: `-49`
  - raw-support ICC: `-41`
- Improved/harmed/unchanged vs base:
  - dependence-aware ICC: `551 / 535 / 1314`
  - raw-support ICC: `552 / 549 / 1299`

## Produced artifacts
- Aggregate comparison metrics: `aggregate_comparison_metrics.json`
- Per-method metrics: `per_method_metrics.json`
- Improved/harmed/unchanged registries (dependence-aware + raw-support)
- Wrong-commit subtype summary + explicit subtype assignment rules
- Dependence-vs-raw diagnostics
- Run manifest
- Status note (`STATUS_NOTE_incumbent_challenger_commit_validation_20260419.md`)
