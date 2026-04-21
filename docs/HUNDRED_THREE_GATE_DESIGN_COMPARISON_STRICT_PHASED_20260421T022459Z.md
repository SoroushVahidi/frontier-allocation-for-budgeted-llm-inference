# Hundred-case three-gate design comparison under strict phased law (20260421T022459Z)

Strict phased law: finish F1 completely, then F2 completely, then (optional) F3 completely before phase_normal.
No gate evaluates depth-3 decisions before F2 is terminal for all required root families.
Within each level, ordering is controller-driven by normal scores/anti-collapse priorities/tie-breaks (no BFS replacement).

## Gate definitions and thresholds
```json
{
  "strict_gate1": {
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
  "strict_gate2": {
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
  "strict_gate3": {
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
| Metric | baseline | strict_f2 | strict_f3 | strict_gate1 | strict_gate2 | strict_gate3 |
|---|---:|---:|---:|---:|---:|---:|
| absent_from_tree | 78 | 24 | 21 | 21 | 19 | 26 |
| present_not_selected | 22 | 13 | 13 | 8 | 11 | 9 |
| repeated_same_family_present | 97 | 86 | 83 | 77 | 84 | 80 |
| gold_in_tree | 22 | 76 | 79 | 79 | 81 | 74 |

## Head-to-head summary
- strict_f3 vs strict_f2: {'unchanged_correct': 41, 'improved': 25, 'worsened': 22, 'unchanged_still_wrong': 12}
- strict_gate1 vs strict_f2: {'unchanged_correct': 47, 'improved': 23, 'unchanged_still_wrong': 14, 'worsened': 16}
- strict_gate1 vs strict_f3: {'unchanged_correct': 45, 'worsened': 21, 'improved': 25, 'unchanged_still_wrong': 9}
- strict_gate2 vs strict_f2: {'unchanged_correct': 48, 'improved': 22, 'unchanged_still_wrong': 15, 'worsened': 15}
- strict_gate2 vs strict_f3: {'unchanged_correct': 46, 'worsened': 20, 'improved': 24, 'unchanged_still_wrong': 10}
- strict_gate3 vs strict_f2: {'worsened': 21, 'unchanged_still_wrong': 14, 'improved': 23, 'unchanged_correct': 42}
- strict_gate3 vs strict_f3: {'worsened': 28, 'unchanged_correct': 38, 'improved': 27, 'unchanged_still_wrong': 7}
- strict_gate1 vs strict_gate2: {'unchanged_correct': 49, 'unchanged_still_wrong': 9, 'worsened': 21, 'improved': 21}
- strict_gate1 vs strict_gate3: {'improved': 25, 'worsened': 20, 'unchanged_correct': 45, 'unchanged_still_wrong': 10}
- strict_gate2 vs strict_gate3: {'improved': 25, 'worsened': 20, 'unchanged_correct': 45, 'unchanged_still_wrong': 10}

## Representative wins/losses
- cases retaining depth3 gains with lower budget stress: 48
- clearly wrong gate decisions count: 50

## Honest conclusion
Use aggregate_summary.json head-to-head + outcomes_vs_baseline to decide best compromise.
If all gates trail fixed depth-2 or depth-3, prefer fixed-force baseline (as required).