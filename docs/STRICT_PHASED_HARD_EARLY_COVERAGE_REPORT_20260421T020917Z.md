# Strict phased hard early root coverage report (20260421T020917Z)

## Scope
This report documents the strict phased correction for hard early root-family coverage and its measured impact on the existing hundred-case depth2/depth3 evaluation surface.

## Exact strict phase definition
For forced root-family early coverage, the controller now uses a strict phase machine:

1. `phase_depth1`
   - Only families still below depth 1 are eligible for forced redirection.
   - Depth-2 work is blocked while any required root family is below depth 1.
2. `phase_depth2`
   - Only families still below depth 2 are eligible for forced redirection.
   - Depth-3 work is blocked while any required root family is below depth 2.
3. `phase_depth3`
   - Only families still below depth 3 are eligible for forced redirection.
4. `phase_normal`
   - Forced phase barrier is complete (or released under budget fallback) and normal controller allocation resumes.

Within each phase, branch choice remains score/priorities driven (anti-collapse, tie-breaks, etc.); only eligibility is phase-gated.

## Insertion point in code
The strict phased logic is implemented in:
- `GlobalDiversityAggregationController._hard_early_root_coverage_forced_diagnostic` (`experiments/controllers.py`): computes current phase, pending families for that phase, per-depth status, release checks tied to current phase.
- `GlobalDiversityAggregationController.run` (`experiments/controllers.py`): logs per-step phase telemetry, transitions, blocked-by-phase redirects, and final phase status metadata.

## Required question: was previous implementation weaker?
Yes. The previous hard depth-3 forcing used a single min-depth target and could still keep selecting already-deep families while another family was still below depth 2, because both families could be simultaneously “pending” under the same depth-3 target.

## Required question: does new implementation prevent depth3-before-depth2?
Yes. The new phased diagnostic exposes `current_phase=phase_depth2` whenever any required root family is below depth 2, and forced override is restricted to `phase_pending_families` only, blocking depth-3 progression until depth-2 completion (or budget release for the current phase).

## Diagnostics and telemetry added
Per-step trace now includes:
- `hard_early_coverage_current_phase`
- `hard_early_coverage_current_phase_depth_requirement`
- `hard_early_coverage_phase_transition_happened`
- `hard_early_coverage_phase_transition_reason`
- `hard_early_coverage_phase_pending_families`
- `hard_early_coverage_phase_max_realized_depth_per_root_family`
- `hard_early_coverage_action_blocked_by_phase_incomplete`
- `hard_early_coverage_release_impossible_under_budget`

Final metadata adds:
- `hard_early_root_strict_phased_v1_enabled`
- `hard_early_coverage_phase_transition_count`
- `hard_early_coverage_phase_transition_log`
- `hard_early_coverage_phase_final`
- `hard_early_coverage_final_phase_status`

## Tests added/updated
Updated `tests/test_hard_early_root_depth2_coverage.py` with explicit strict-phasing checks:
1. depth1 barrier before entering depth2
2. depth2 barrier before entering depth3
3. no depth3 start while any family remains below depth2
4. stays in depth3 phase while depth3 incomplete (unless release/terminal)
5. same-level ordering remains score-driven (no rigid BFS ordering)

## Evaluation executed
Re-ran:
- `scripts/run_hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421.py`

Output directory:
- `outputs/hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421T020917Z`

Machine-readable strict rule manifest:
- `outputs/hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421T020917Z/strict_phased_rule_manifest.json`

## Aggregate baseline vs strict depth2 vs strict depth3
From `aggregate_summary.json` in the new output:
- baseline correct: 0/100 (the input slice is baseline failures)
- strict depth2 correct: 61/100
- strict depth3 correct: 64/100
- improved vs baseline: depth2=63, depth3=66

Depth3 vs depth2:
- improved: 25
- worsened: 22

## Comparison vs earlier non-strict depth2/depth3 artifact
Compared against:
- `outputs/hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421T010733Z`

Headline deltas (strict minus earlier non-strict):
- depth2 improved-vs-baseline: -7
- depth3 improved-vs-baseline: -9
- depth2 impossible-release count: -7
- depth3 impossible-release count: -21

## Honest conclusion
The strict phased interpretation is behaviorally cleaner and now enforces the requested level barriers unambiguously. On this hundred-case surface, strict phasing remains strongly beneficial over baseline for both depth2 and depth3, but it does not improve over the earlier non-strict implementation in raw corrected-case counts; it trades some wins for stricter barrier fidelity.
