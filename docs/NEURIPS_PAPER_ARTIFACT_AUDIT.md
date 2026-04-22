# NeurIPS Paper Artifact Audit (Historical)

This file is retained for historical provenance. It is not the canonical source for current paper artifact policy.

Use instead:
- `docs/NEURIPS_PAPER_ARTIFACTS.md`
- `docs/PAPER_ARTIFACT_CLEANUP_REPORT_2026_04_21.md`

## Canonical project identity

Current canonical identity (from `docs/CANONICAL_START_HERE.md` and `docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md`):
- fixed-budget adaptive test-time compute allocation,
- cross-controller/cross-family frontier allocation,
- next-step branch allocation over active branches,
- answer-group-aware commit control,
- anti-collapse controller refinement.

This repository is **not** centered on old binary cheap-vs-revise routing.

## Current promoted method line

Current promoted integrated line (repository docs):
- broad diversity-aware branch allocation with answer-support aggregation,
- anti-collapse answer-group-aware allocation,
- soft repeat-expansion control,
- deterministic output-layer repair stage.

In currently committed frontier-schema bundles, the promoted strict-coupled/tie-aware line appears as a **bridged alias row** (`strict_coupled_tie_aware_promoted`) sourced from `adaptive_budget_guarded`.

## Canonical method names for paper artifacts

Canonical method ids found in current frontier bundles:
- `strict_coupled_tie_aware_promoted` (bridged promoted line)
- `adaptive_budget_guarded`
- `reasoning_beam2`
- `self_consistency_3`
- `reasoning_greedy`
- `verifier_guided_search`
- `program_of_thought`
- `oracle_frontier_upper_bound`

## Strongest current baselines

From `outputs/imported_methodology_frontier_eval/20260420T_multidataset_frontier_v1`:
- strongest internal fixed baselines are generally `reasoning_beam2` and `self_consistency_3` on this bounded run surface.
- oracle remains the upper bound for all budgets/datasets.

## Current supported datasets and benchmark surface

For the canonical multi-dataset frontier bundle used for paper artifacts:
- `openai/gsm8k`
- `HuggingFaceH4/MATH-500`
- `Idavidrein/gpqa`

Additional broader comparison bundle exists in
`outputs/full_method_comparison_bundle/20260419T214335Z` with:
- `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`

## Budget definitions

Canonical frontier budgets in current multi-dataset imported bundle:
- budget 8
- budget 10

(Full comparison bundle also includes budgets 4/6/8 for robustness context.)

## Core metrics

Core frontier metrics:
- `accuracy`
- `avg_actions`
- `gap_to_oracle`
- `budget_exhaustion_rate`

Control/diagnostic metrics used in paper artifacts:
- expansion/verification action shares
- allocation entropy
- max-family-share concentration
- active-family-count proxy

Failure analysis fields (proxy decomposition basis):
- defeat-case `failure_subtype` groupings from `defeat_case_registry.csv`

## Canonical output bundles safe for paper-facing use

Primary paper-safe bundles:
- `outputs/imported_methodology_frontier_eval/20260420T_multidataset_frontier_v1`
- `outputs/imported_methodology_frontier_eval/20260417T000000Z`
- `outputs/full_method_comparison_bundle/20260419T214335Z` (for failure subtype and robustness context)

Supporting method-diagnostic bundle:
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_complementarity_audit_upgrade_20260417`

## Safe claims vs not-safe claims

Safe (from `docs/CURRENT_SAFE_CLAIMS.md` + current bundles):
- frontier framing is strong and distinct,
- oracle headroom remains meaningful,
- anti-collapse behavior is measurable and relevant,
- promoted line is promising and structurally motivated.

Not safe:
- universal-winner claim for promoted method,
- claim that external baseline comparisons are complete/apples-to-apples,
- claim that strict-coupled/tie-aware line is already decisive on headline metrics.

## Audit conclusion

Current repository evidence supports a strong NeurIPS artifact pipeline centered on:
- frontier curves,
- oracle-gap analysis,
- allocation/anti-collapse diagnostics,
- failure decomposition with explicit proxy caveats,
- and conservative reporting discipline.
