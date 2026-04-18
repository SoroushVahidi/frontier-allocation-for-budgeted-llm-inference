# Self-consistency-inspired hybrid status (2026-04-18)

## Scope

This pass is a **bounded targeted hybridization** of the canonical branch-allocation method.

It does **not** replace the canonical objective or default continuation-value ranking.
It imports only the strongest useful self-consistency ideas identified in the repository casebook:
1. local diversity in hard close-call states,
2. answer-level aggregation as a bounded decision aid,
3. reduced premature one-branch commitment.

## What was imported from self-consistency

From `outputs/self_consistency_advantage_casebook_20260418/self_consistency_advantage_taxonomy.json` and the paired casebook note:
- `multi_path_answer_aggregation`,
- `reduced_premature_commitment`,
- and dominant failure subtype `premature_commit_or_wrong_path`.

Imported mechanism in this pass:
- **Selective activation only in hard states**,
- **small local diversity budget** (`top-k` local candidate set, bounded value-drop),
- **answer normalization + grouping + support score**,
- **consensus-gated override** only when support is sufficient.

## Canonical decomposition compatibility

The canonical stack is preserved:
- `process_quality(b)`,
- `target_completion(b)`,
- `continuation_value(b)`.

Added bounded hard-case term:
- `answer_support` computed from local answer-group support (`support_fraction` + `support_weighted_value`).

Role of `answer_support`:
- hard-case commit/selection modifier,
- **not** a universal replacement objective.

## Activation and local budget

Hybrid hard-case mode is activated when **any** of:
- near-tie (`top2_gap <= near_tie_gap`),
- low top-branch completion,
- continuation-vs-completion disagreement,
- intermediate-result trap suspicion on the top branch.

Local diversity budget in hard-case mode:
- expand/select local top candidates only (default `k=3`),
- constrain to bounded continuation-value drop (default `<= 0.03`),
- no global sample-everything behavior.

## Answer aggregation schema

In hard-case mode:
1. normalize recoverable branch answers,
2. group branches by normalized answer,
3. compute support per answer:
   - `support_fraction = supporters / diversity_branches`,
   - `support_weighted_value = mean(continuation_value of supporters) / top_continuation_value`,
   - `answer_support = 0.70*support_fraction + 0.30*support_weighted_value`,
4. if consensus support passes threshold and disagrees with top continuation answer, allow bounded local override.

## Variants compared

This pass compares:
- `current_learned_branch_score` (current canonical representative),
- `intermediate_trap_aware_near_tie_v1` (current intermediate-result-trap-aware variant),
- `selective_sc_hybrid_v1` (new selective self-consistency hybrid),
- plus `continuation_oracle` reference.

## Bounded evaluation focus and results

Primary run:
- `run_id`: `worst_real_failure_observability_20260418T091750Z`
- states evaluated: `40`

Outputs:
- `outputs/self_consistency_hybrid_pass_20260418/aggregate_comparison_summary.json`
- `outputs/self_consistency_hybrid_pass_20260418/self_consistency_gap_reduction_summary.json`
- `outputs/self_consistency_hybrid_pass_20260418/targeted_case_results.json`
- `outputs/self_consistency_hybrid_pass_20260418/failure_taxonomy_shift.json`

Key bounded findings:
- vs `current_learned_branch_score`, `selective_sc_hybrid_v1` improved:
  - match-oracle rate by `+0.425`,
  - mean oracle regret by `-0.0182`,
  - near-tie match-oracle by `+0.4138`.
- hard-case activation rate was high on this targeted run (`0.85`), with bounded consensus override rate (`0.10`).
- premature-commit proxy errors in near-tie/trap slices dropped strongly vs current learned branch score, but `selective_sc_hybrid_v1` and `intermediate_trap_aware_near_tie_v1` tied on this bounded run.

## What improved

- We now explicitly import self-consistency’s strongest local strengths where the repo says they matter:
  - local path diversity,
  - answer aggregation,
  - reduced early lock-in.
- The method remains canonically aligned with continuation-value-default allocation.
- Hard-case oracle alignment improves materially in this bounded run.

## What did not improve (yet)

- In this bounded run, the new hybrid did **not** exceed the already strong `intermediate_trap_aware_near_tie_v1` aggregate; they tied.
- This pass does not, by itself, establish broad all-dataset accepted-accuracy dominance over `self_consistency_3`.
- Some self-consistency advantage evidence remains taxonomy-level due to unavailable branch-level self-consistency traces in historical artifacts.

## Bottom line

This is a **real targeted next method step** (not just diagnostic), because it introduces a bounded selective-SC mechanism integrated with the canonical objective stack and demonstrates strong targeted hard-case gains over the current learned branch-score baseline.

However, current evidence supports describing it as:
- a robust bounded hard-case hybridization,
- not yet a broad global replacement claim over all prior strongest methods.
