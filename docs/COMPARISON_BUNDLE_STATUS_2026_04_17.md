# Conservative comparison bundle status (2026-04-17)

## Scope

Bounded, artifact-grounded comparison bundle for the canonical fixed-budget branch-allocation direction, separating:
- fully matched runnable comparisons,
- runnable-adjacent/import-validated comparisons,
- blocked/not-yet-comparable baselines.

## Our method selection

Selected method: `strict_coupled_near_tie_specialized_pointwise_v1` from `outputs/branch_label_bruteforce_learning/near_tie_pointwise_expert_comparison_bundle_20260417/`.

Reason (conservative): it matches the strongest hard-slice metrics of prior specialized near-tie policy while preserving stricter routing spillover behavior under the strict-coupled gate.

## A) Fully matched internal table (our method vs strongest internal baselines)

| Method | Accepted | Coverage | Forced | Top-1 | Near-tie forced | Adjacent forced | Strict-routed forced | Strict-routed near-tie |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| binary_forced_baseline | 0.4665 | 1.0000 | 0.4665 | 0.5345 | 0.0833 | 0.4630 | 0.2500 | 0.0833 |
| abstain_calibrated_pairwise_backup | 0.6111 | 0.6154 | 0.4665 | 0.5345 | 0.0833 | 0.4630 | 0.2500 | 0.0833 |
| near_tie_specialized_pointwise | 0.5309 | 1.0000 | 0.5309 | 0.6077 | 0.5000 | 0.5423 | 0.5556 | 0.5000 |
| strict_coupled_near_tie_specialized_pointwise_v1 | 0.5309 | 1.0000 | 0.5309 | 0.6077 | 0.5000 | 0.5423 | 0.5556 | 0.5000 |
| strict_coupled_near_tie_specialized_pointwise_improved_v1 | 0.5151 | 1.0000 | 0.5151 | 0.5857 | 0.2500 | 0.5238 | 0.4722 | 0.2500 |

## B) External baseline comparison table with comparability labels

| Baseline | Comparison type | Category | Direct/adjacent | Usable now | Mean accuracy | Δ vs our forced | Notes |
|---|---|---|---|---|---:|---:|---|
| s1_simple_test_time_scaling | runnable_matched_lightweight | mode_b_partial | direct | yes_mode_a | 0.4861 | -0.0448 | Measured via local lightweight frontier benchmark; adjacent to strict-coupled branch-allocation setting. |
| tale_token_budget_aware_reasoning | runnable_matched_lightweight | mode_b_partial | adjacent | yes_mode_a | 0.4583 | -0.0726 | Measured via local lightweight frontier benchmark; adjacent to strict-coupled branch-allocation setting. |
| l1_length_control_rl | status_only_adjacent_or_blocked | mode_b_partial | direct | yes_mode_a |  |  | mode_a_runnable=True |
| best_route_microsoft | status_only_adjacent_or_blocked | runnable_adjacent | adjacent | yes_verified_import |  |  | adjacent_fixture_valid=True |
| compute_optimal_tts | status_only_adjacent_or_blocked | blocked | adjacent | no |  |  | Paper↔repo official mapping for target OpenReview 4FWAwZtd2n is unverified and no fair matched adapter protocol exists yet. |
| when_solve_when_verify | status_only_adjacent_or_blocked | runnable_adjacent | adjacent | yes_verified_import |  |  | adjacent_fixture_valid=True |
| cascade_routing | status_only_adjacent_or_blocked | runnable_adjacent | adjacent | yes_verified_import |  |  | adjacent_fixture_valid=True |
| mob_majority_of_bests | status_only_adjacent_or_blocked | runnable_adjacent | adjacent | yes_verified_import |  |  | adjacent_fixture_valid=True |
| rest_mcts | status_only_adjacent_or_blocked | runnable_adjacent | adjacent | yes_verified_import |  |  | adjacent_fixture_valid=True |
| mcts_llm_community | status_only_adjacent_or_blocked | link_only | adjacent | no |  |  | Optional/community reference; no canonical in-repo adapter. |
| openr | status_only_adjacent_or_blocked | runnable_adjacent | adjacent | yes_verified_import |  |  | adjacent_fixture_valid=True |
| tree_plv | status_only_adjacent_or_blocked | discuss_only | adjacent | no |  |  | Official code/repro path not confirmed for this repo's integration policy. |
| pgts | status_only_adjacent_or_blocked | discuss_only | adjacent | no |  |  | No verified official code path for reproducible integration. |
| scaling_automated_process_verifiers | status_only_adjacent_or_blocked | discuss_only | adjacent | no |  |  | No verified official repo integration path under current policy. |
| llm_tree_search_waterhorse | status_only_adjacent_or_blocked | discuss_only | adjacent | no |  |  | License uncertainty and no approved in-repo adapter. |

## C) Safe-claim boundary summary

Safe to claim from this bundle:
- Strict-coupled near-tie specialized pointwise v1 is the strongest internal method in this bounded matched branch-comparison bundle (equal hardest-slice metrics to prior specialized with stricter routing spillover behavior).
- s1 and TALE have runnable lightweight matched comparisons in-repo.
- BEST-Route, when_solve_when_verify, cascade_routing, MoB, ReST-MCTS, OpenR are runnable-adjacent via import validators only.

Not safe to claim from this bundle:
- No apples-to-apples superiority claim against status-only adjacent or blocked external baselines.
- No universal-winner claim across datasets/settings.
- No claim for blocked baselines without runnable matched metrics.

## D) Machine-readable outputs

- `outputs/comparison_bundle_20260417/internal_matched_comparison.{json,csv}`
- `outputs/comparison_bundle_20260417/external_comparability_table.{json,csv}`
- `outputs/comparison_bundle_20260417/safe_claims_boundary_summary.json`
- `outputs/external_baseline_runnability/20260417T013117Z/verification_summary.{json,csv}`
- `outputs/external_baseline_completeness_summary.{json,csv}`
- `outputs/light_external_style_baseline_comparison/20260417T013152Z/{method_summary.csv,pairwise_vs_anchor.csv}`
- `outputs/light_anchor_vs_s1_comparison/20260417T013200Z/pairwise_anchor_vs_s1.csv`

## E) Claim boundaries for manuscript writing

- Keep fully matched internal claims confined to table A setting (strict-coupled near-tie branch-comparison pipeline).
- Keep external claims split by comparability label (runnable matched-lightweight vs adjacent import-validated vs blocked).
- Avoid mixing status-only adjacent baselines into headline performance claims.
