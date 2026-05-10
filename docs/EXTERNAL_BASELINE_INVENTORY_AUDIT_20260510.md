# External Baseline Inventory Audit (2026-05-10)

## Executive Summary

This audit provides a definitive inventory of external baselines versus internal methods in the `frontier-allocation-for-budgeted-llm-inference` repository.

- **Final list of External Baselines**: `external_l1_max`, `external_l1_exact`, `external_tale_prompt_budgeting`, `external_s1_budget_forcing`, `external_zhai_cpo_mode_a`, `external_self_consistency_4_fair_v1`, `external_self_consistency_6_fair_v1`, `external_pal_pot_fair_v1`.
- **Final list of External-Adjacent Baselines**: `best_route_microsoft`, `when_solve_when_verify`, `rest_mcts`, `training_free_difficulty_proxies_mode_a` (DIPA).
- **Final list of Internal Methods**: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`, `direct_l1_anchor`, `direct_hybrid`, `production_equiv_v1`, `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`, `tot_bfs_matched_budget`, `tot_beam_matched_budget`, `tot_dfs_matched_budget`, `program_of_thought`.
- **Baseline Location**: All primary external baselines are implemented as controllers in `experiments/controllers.py` and registered in `experiments/frontier_matrix_core.py`.
- **PAL Status**: PAL is an **internal method**, not an external baseline. It is integrated into the core `DirectReserveFrontierGateController` and used as a generator/seed.

## Definitive Baseline Table

| method_id | category | role | implemented in code? | registered? | has tests? | has output artifacts? | has matched comparison? | has per-case outputs? | has trace metadata? | notes |
|-----------|----------|------|----------------------|-------------|------------|-----------------------|-------------------------|-----------------------|---------------------|-------|
| `external_l1_max` | external | Primary comparator | yes (`L1LengthControlController`) | yes | yes | yes | yes | yes | limited | Strongest external baseline. |
| `external_l1_exact` | external | Length-contract baseline | yes (`L1LengthControlController`) | yes | yes | yes | yes | yes | limited | Fairness/ablation reference. |
| `external_tale_prompt_budgeting` | external | Token-budget baseline | yes (`TALEPromptBudgetingController`) | yes | yes | yes | yes | yes | limited | TALE EP-style budgeting. |
| `external_s1_budget_forcing` | external | Budget-forcing baseline | yes (`S1BudgetForcingController`) | yes | yes | yes | yes | yes | limited | s1-style wait-token forcing. |
| `external_zhai_cpo_mode_a` | external | Constrained-policy baseline | yes (`AdaptiveController`) | yes | yes | yes | yes | yes | limited | Integrated via adapter. |
| `external_self_consistency_4_fair_v1` | external | Majority-vote baseline | yes (`SelfConsistencyFairController`) | yes | yes | yes | yes | yes | limited | n=4 fair SC. |
| `external_self_consistency_6_fair_v1` | external | Majority-vote baseline | yes (`SelfConsistencyFairController`) | yes | yes | yes | yes | yes | limited | n=6 fair SC. |
| `external_pal_pot_fair_v1` | external | Program-of-thought baseline | yes (`ProgramOfThoughtController`) | yes | yes | yes | yes | yes | limited | PoT/PAL fair baseline. |
| `best_route_microsoft` | external-adjacent | Import-only baseline | no (import-only) | yes (registry) | no | no | no | no | no | Adjacent comparison only. |
| `when_solve_when_verify` | external-adjacent | Import-only baseline | no (import-only) | yes (registry) | no | no | no | no | no | Adjacent comparison only. |
| `rest_mcts` | external-adjacent | Import-only baseline | no (import-only) | yes (registry) | no | no | no | no | no | Adjacent comparison only. |
| `training_free_difficulty_proxies_mode_a` | external-adjacent | DIPA-style baseline | no (adapter-only) | no | no | no | no | no | no | Appendix-only DIPA. |

## PAL Clarification Section

- **Is PAL an external baseline?** No.
- **What PAL method IDs exist?** `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`, `baseline_pal`, `external_pal_pot_fair_v1` (fair baseline variant).
- **Which PAL method is the current internal method?** `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`.
- **Why PAL should be treated as internal, not external**: PAL is a core component of the proposed method's generation stack. While PAL itself is a known technique, its specific integration, guarding, and retry logic in this repo constitute the internal research contribution.

## Missing Matched-Baseline Material Section

- **Which external baselines have complete matched evidence?** `external_l1_max`, `external_l1_exact`, `external_tale_prompt_budgeting`, `external_s1_budget_forcing`, `external_zhai_cpo_mode_a` on several 100-case and 300-case bundles.
- **Which baselines only have partial or pilot evidence?** `external_self_consistency_4_fair_v1`, `external_self_consistency_6_fair_v1`, `external_pal_pot_fair_v1` (mostly 10-case calibration).
- **Which baselines need materialization on the same case set as the current method?** `external_self_consistency_*` and `external_pal_pot_*` need 300-case runs to match the latest PAL-line evidence.
- **What exact matched bundle should be built later?** A unified 300-case bundle containing `external_l1_max`, `external_l1_exact`, `external_tale_prompt_budgeting`, `external_s1_budget_forcing`, `external_zhai_cpo_mode_a`, `external_self_consistency_6_fair_v1`, and `external_pal_pot_fair_v1` against the latest `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal` with `direct_l1_anchor` enabled.

## Safety / Claim Boundary Section

- **What can currently be claimed**: The latest internal method (`PAL+retry+tiebreak`) is competitive with and often exceeds `external_l1_max` on matched 300-case GSM8K slices.
- **What cannot currently be claimed**: Universal dominance across all external baselines and all datasets.
- **What evidence is needed**: A broad, multi-dataset, multi-baseline matched-surface evaluation with statistical significance testing (McNemar/Bootstrap) across all 8 primary external baselines.

## Recommended Import Plan

No baseline-like files were found in the archive that are missing from the repo. The repository is complete regarding baseline implementations.
