# Hundred-case three-gate design comparison (20260421T013933Z)

Mandatory balanced root-family discovery to depth 2 is always active before any depth-3 gate decision.
Within each level, ordering is controller-driven by normal scores/anti-collapse priorities/tie-breaks (no BFS replacement).

## Gate definitions and thresholds
```json
{
  "gate1": {
    "conditional_depth3_gate_design": "v1_optimistic_collapse_first",
    "depth3_gate_min_top_answer_support": 0.55,
    "depth3_gate_min_support_gap": 0.12,
    "depth3_gate_min_active_root_families": 2,
    "depth3_gate_max_family_share_trigger": 0.55,
    "depth3_gate_longest_run_trigger": 4,
    "depth3_gate_min_confident_frontier_score": 0.62,
    "depth3_gate_min_top_group_support_commit": 0.52,
    "depth3_gate_e_max_top_support": 0.48,
    "depth3_gate_e_min_answer_groups": 2,
    "gate_v1_family_concentration_share_trigger": 0.6,
    "gate_v1_longest_same_family_run_trigger": 4,
    "gate_v1_min_alive_families": 2,
    "gate_v1_min_answer_groups_rich": 3,
    "gate_v1_top_share_strong_incumbent": 0.64,
    "gate_v1_support_gap_strong_incumbent": 0.16,
    "gate_v1_best_frontier_score_strong": 0.66,
    "gate_v2_family_concentration_share_trigger": 0.66,
    "gate_v2_longest_same_family_run_trigger": 5,
    "gate_v2_max_top_support_for_weak_concentration": 0.57,
    "gate_v2_min_remaining_budget_for_depth3": 2,
    "gate_v3_max_top_share_ambiguous": 0.62,
    "gate_v3_max_top_minus_second_gap_ambiguous": 0.14,
    "gate_v3_max_best_frontier_margin_ambiguous": 0.08,
    "gate_v3_min_distinct_answer_groups_ambiguous": 2,
    "gate_v3_min_active_root_families_ambiguous": 2,
    "gate_v3_family_concentration_share_trigger": 0.6,
    "gate_v3_depth_asymmetry_trigger": 2,
    "gate_v3_ambiguity_signals_required": 3
  },
  "gate2": {
    "conditional_depth3_gate_design": "v2_budget_aware_rescue",
    "depth3_gate_min_top_answer_support": 0.55,
    "depth3_gate_min_support_gap": 0.12,
    "depth3_gate_min_active_root_families": 2,
    "depth3_gate_max_family_share_trigger": 0.55,
    "depth3_gate_longest_run_trigger": 4,
    "depth3_gate_min_confident_frontier_score": 0.62,
    "depth3_gate_min_top_group_support_commit": 0.52,
    "depth3_gate_e_max_top_support": 0.48,
    "depth3_gate_e_min_answer_groups": 2,
    "gate_v1_family_concentration_share_trigger": 0.6,
    "gate_v1_longest_same_family_run_trigger": 4,
    "gate_v1_min_alive_families": 2,
    "gate_v1_min_answer_groups_rich": 3,
    "gate_v1_top_share_strong_incumbent": 0.64,
    "gate_v1_support_gap_strong_incumbent": 0.16,
    "gate_v1_best_frontier_score_strong": 0.66,
    "gate_v2_family_concentration_share_trigger": 0.66,
    "gate_v2_longest_same_family_run_trigger": 5,
    "gate_v2_max_top_support_for_weak_concentration": 0.57,
    "gate_v2_min_remaining_budget_for_depth3": 2,
    "gate_v3_max_top_share_ambiguous": 0.62,
    "gate_v3_max_top_minus_second_gap_ambiguous": 0.14,
    "gate_v3_max_best_frontier_margin_ambiguous": 0.08,
    "gate_v3_min_distinct_answer_groups_ambiguous": 2,
    "gate_v3_min_active_root_families_ambiguous": 2,
    "gate_v3_family_concentration_share_trigger": 0.6,
    "gate_v3_depth_asymmetry_trigger": 2,
    "gate_v3_ambiguity_signals_required": 3
  },
  "gate3": {
    "conditional_depth3_gate_design": "v3_ambiguity_after_depth2",
    "depth3_gate_min_top_answer_support": 0.55,
    "depth3_gate_min_support_gap": 0.12,
    "depth3_gate_min_active_root_families": 2,
    "depth3_gate_max_family_share_trigger": 0.55,
    "depth3_gate_longest_run_trigger": 4,
    "depth3_gate_min_confident_frontier_score": 0.62,
    "depth3_gate_min_top_group_support_commit": 0.52,
    "depth3_gate_e_max_top_support": 0.48,
    "depth3_gate_e_min_answer_groups": 2,
    "gate_v1_family_concentration_share_trigger": 0.6,
    "gate_v1_longest_same_family_run_trigger": 4,
    "gate_v1_min_alive_families": 2,
    "gate_v1_min_answer_groups_rich": 3,
    "gate_v1_top_share_strong_incumbent": 0.64,
    "gate_v1_support_gap_strong_incumbent": 0.16,
    "gate_v1_best_frontier_score_strong": 0.66,
    "gate_v2_family_concentration_share_trigger": 0.66,
    "gate_v2_longest_same_family_run_trigger": 5,
    "gate_v2_max_top_support_for_weak_concentration": 0.57,
    "gate_v2_min_remaining_budget_for_depth3": 2,
    "gate_v3_max_top_share_ambiguous": 0.62,
    "gate_v3_max_top_minus_second_gap_ambiguous": 0.14,
    "gate_v3_max_best_frontier_margin_ambiguous": 0.08,
    "gate_v3_min_distinct_answer_groups_ambiguous": 2,
    "gate_v3_min_active_root_families_ambiguous": 2,
    "gate_v3_family_concentration_share_trigger": 0.6,
    "gate_v3_depth_asymmetry_trigger": 2,
    "gate_v3_ambiguity_signals_required": 3
  }
}
```

## Six-way aggregate table
| Metric | baseline | depth2 | depth3 | gate1 | gate2 | gate3 |
|---|---:|---:|---:|---:|---:|---:|
| absent_from_tree | 78 | 20 | 15 | 18 | 20 | 22 |
| present_not_selected | 22 | 10 | 10 | 9 | 8 | 11 |
| repeated_same_family_present | 97 | 86 | 83 | 77 | 84 | 80 |
| gold_in_tree | 22 | 80 | 85 | 82 | 80 | 78 |

## Head-to-head summary
- gate1 vs depth2: {'unchanged_correct': 52, 'improved': 20, 'unchanged_still_wrong': 10, 'worsened': 18}
- gate1 vs depth3: {'unchanged_correct': 51, 'worsened': 24, 'improved': 21, 'unchanged_still_wrong': 4}
- gate2 vs depth2: {'unchanged_correct': 52, 'improved': 19, 'unchanged_still_wrong': 11, 'worsened': 18}
- gate2 vs depth3: {'unchanged_correct': 52, 'worsened': 23, 'improved': 19, 'unchanged_still_wrong': 6}
- gate3 vs depth2: {'worsened': 23, 'unchanged_still_wrong': 10, 'improved': 20, 'unchanged_correct': 47}
- gate3 vs depth3: {'worsened': 26, 'unchanged_correct': 49, 'improved': 18, 'unchanged_still_wrong': 7}
- gate1 vs gate2: {'unchanged_correct': 49, 'unchanged_still_wrong': 6, 'worsened': 22, 'improved': 23}
- gate1 vs gate3: {'improved': 23, 'worsened': 18, 'unchanged_correct': 49, 'unchanged_still_wrong': 10}
- gate2 vs gate3: {'improved': 26, 'worsened': 22, 'unchanged_correct': 45, 'unchanged_still_wrong': 7}

## Representative wins/losses
- cases retaining depth3 gains with lower budget stress: 60
- clearly wrong gate decisions count: 55

## Honest conclusion
Use aggregate_summary.json head-to-head + outcomes_vs_baseline to decide best compromise.
If all gates trail fixed depth-2 or depth-3, prefer fixed-force baseline (as required).