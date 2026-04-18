# Intermediate-result failure fix status (2026-04-18)

## Scope of this pass

This was a **bounded targeted method-improvement pass** focused only on the observed failure pattern where a branch computes a correct intermediate quantity but has not yet answered the asked target quantity.

It was not a broad new-method search and did not replace continuation value as the global core.

## Targeted failure pattern

Observed concrete trap pattern from saved real casebook examples:
- subtotal-vs-final-difference (`65` sold vs asked `120-65=55` off target),
- leftover-vs-given-away (`5` left vs asked `15` given away),
- resource-total-vs-action-count (`45` eggs needed vs asked `5` babysitting sessions),
- one-more-operator-needed variants where the branch appears numerically complete but the target variable is unresolved.

### Minimal taxonomy used in this pass

From `outputs/intermediate_result_failure_fix_20260418/failure_taxonomy.json`:
- `subtotal_vs_final_difference`
- `leftover_vs_given_away`
- `resource_total_vs_action_count` (expected in pattern; not dominant in this bounded run labels)
- `one_more_operator_needed` fallback
- `none` (for already target-complete branches)

## Method change implemented

Implemented a bounded branch-level **semantic incompleteness signal** and a target-completion-sensitive **commit-quality score**:

1. **Semantic incompleteness signal (bounded, explainable rules):**
   - infer required final operator from the question (`difference_from_target`, `division_to_count`, `leftover_complement`, `generic`),
   - detect whether that operator appears in branch reasoning,
   - detect whether final answer matches an intermediate numeric value,
   - assign a bounded incompleteness score.

2. **Commit-quality score update:**
   - `commit_quality = 0.55*completion + 0.25*answer_evidence + 0.20*(1-incompleteness)`.
   - This keeps completion-awareness but now explicitly penalizes intermediate-answer traps.

3. **Controller policy integration (local only):**
   - continuation value remains default ranking core,
   - apply intermediate-trap correction only in **near-tie slices**,
   - only override continuation top branch when:
     - top branch has high incompleteness,
     - candidate alternatives are within bounded value-drop budget.

This was implemented in:
- `scripts/run_intermediate_result_failure_fix.py`.

## Evaluation setup

Bounded run used:
1. Generate fresh observability-enabled worst-failure data bundle:
   - `python scripts/run_worst_real_failure_casebook_with_reasoning.py ... --allow-sim-fallback --top-k 5`
2. Run targeted intermediate-result fix evaluation:
   - `python scripts/run_intermediate_result_failure_fix.py --run-id worst_real_failure_observability_20260418T032751Z`

Artifacts were written to:
- `outputs/intermediate_result_failure_fix_20260418/`

Required machine-readable files produced:
- `manifest.json`
- `failure_taxonomy.json`
- `semantic_incompleteness_signal_summary.json`
- `targeted_case_results.json`
- `aggregate_comparison_summary.json`
- `near_tie_slice_results.json`
- `oracle_alignment_results.json`
- `commands_assumptions_caveats.md`

## Results

## 1) Targeted failure cases

On the selected saved worst-case slice (`n=5`):
- `current_learned_branch_score`: match-oracle `0.0`, mean oracle regret `0.0348`.
- `intermediate_trap_aware_near_tie_v1`: match-oracle `1.0`, mean oracle regret `0.0`.

## 2) Near-tie disagreement slice

On near-tie states (`n=8` in this bounded run):
- `current_learned_branch_score`: match-oracle `0.375`, mean oracle regret `0.0118`.
- `intermediate_trap_aware_near_tie_v1`: match-oracle `1.0`, mean oracle regret `0.0`.

## 3) Aggregate bounded states in this run

Across all states in this bounded run (`n=18`):
- `current_learned_branch_score`: match-oracle `0.3889`, mean oracle regret `0.0305`.
- `intermediate_trap_aware_near_tie_v1`: match-oracle `1.0`, mean oracle regret `0.0`.

## 4) Comparison vs current completion-aware tie baseline

In this bounded run, `completion_tie_resolution_current` and `intermediate_trap_aware_near_tie_v1` tied on oracle-alignment metrics.

Interpretation:
- the new signal appears useful for explicit diagnosis and targeted guarding against intermediate-result traps,
- but this run does **not** show clear superiority over the strongest existing completion-aware near-tie policy,
- so this pass is a **targeted robustness improvement + diagnostic clarification**, not a broad new global winner claim.

## What improved vs what did not

Improved:
- explicit detection of intermediate-answer trap pattern,
- explicit commit-quality sensitivity to target-variable completion,
- strong recovery on targeted failure and near-tie slices versus current learned branch-score line.

Did not improve (in this bounded pass):
- no clear delta over existing completion-tie near-tie policy in this run,
- no broad claim on global accepted accuracy across canonical multistep validation from this pass alone.

## Hard conclusion

This is a **real bounded next method-improvement pass** for the concrete failure pattern (intermediate-result trap), with localized near-tie correction while preserving continuation-value core.

However, based on current bounded evidence, it is best treated as:
- a justified local correction and better commit-quality definition,
- not yet a demonstrated broad replacement of the current canonical completion-aware disagreement handling.
