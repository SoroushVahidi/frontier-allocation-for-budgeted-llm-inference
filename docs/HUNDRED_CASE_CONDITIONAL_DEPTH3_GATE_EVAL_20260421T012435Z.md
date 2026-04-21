# Hundred-case conditional depth-3 gate eval (20260421T012435Z)

## Gate definition (exact)

- **Phase 1:** Balanced root-family coverage to **depth 2** (same mechanism as hard depth-2).
- **Phase 2 (gate):** When depth-2 forcing reaches a terminal state (all satisfied, or impossible under budget, etc.), evaluate criteria **A–E** with thresholds from controller metadata ``conditional_depth3_gate_thresholds``.
- **Combination rule:** Force depth 3 if **(≥2 of A–E)** OR **(A and B)**. If depth-3 lower bound is infeasible, status ``gated_on_but_released_impossible_under_budget``.
- **Within-level ordering:** Unchanged — still the controller ``scored`` priorities and anti-collapse adjustments; hard coverage only **restricts eligible root families**.

### Threshold snapshot (from first gated run metadata)

```json
{
  "depth3_gate_min_top_answer_support": 0.55,
  "depth3_gate_min_support_gap": 0.12,
  "depth3_gate_min_active_root_families": 2,
  "depth3_gate_max_family_share_trigger": 0.55,
  "depth3_gate_longest_run_trigger": 4,
  "depth3_gate_min_confident_frontier_score": 0.62,
  "depth3_gate_min_top_group_support_commit": 0.52,
  "depth3_gate_e_max_top_support": 0.48,
  "depth3_gate_e_min_answer_groups": 2
}
```

## Insertion point

``GlobalDiversityAggregationController.run`` immediately after ``_hard_early_root_coverage_forced_diagnostic`` and before ``_apply_hard_early_root_coverage_forced_override``; gate helper: ``_evaluate_conditional_depth3_gate``.

## RNG alignment

``fresh_our`` for A–D, ``fresh_best`` for ``reasoning_beam2``.

## Output directory: `outputs/hundred_conditional_depth3_gate_eval_20260421T012435Z`

## Aggregate comparison (baseline / depth-2 / depth-3 / gated)

| Metric | Baseline | Depth-2 | Depth-3 | Gated |
|--------|----------|---------|---------|-------|
| absent_from_tree | 78 | 20 | 15 | 21 |
| present_not_selected | 22 | 10 | 10 | 10 |
| repeated_same_family_present | 97 | 86 | 83 | 81 |
| gold_in_tree | 22 | 80 | 85 | 79 |
| mean actions | 11.48 | 9.73 | 9.54 | 9.48 |

### vs baseline (correctness)

- Depth-2: improved **70**, worsened **0**
- Depth-3: improved **75**, worsened **0**
- Gated: improved **69**, worsened **0**

### Head-to-head

- Gated vs depth-2: improved **21**, worsened **22**
- Gated vs depth-3: improved **14**, worsened **20**

### Gate

- Decision counts: {'gated_off': 51, 'gated_on': 13, 'gated_on_but_released_impossible_under_budget': 16, 'gated_on_but_run_ended_before_depth3_forcing': 20}
- Criteria fired (aggregate): {'C_early_collapse_risk': 74, 'A_weak_answer_support': 26, 'D_weak_commit_evidence': 32, 'E_weak_alternatives_shallow_maturity': 1, 'B_unresolved_family_ambiguity': 23}
- Depth-3 forcing completed: **8** / 100
- release_impossible_under_budget (gated run): **21**

## Honest conclusion (auto)

**Gated depth-3 is not clearly better than full depth-3 here** — consider keeping depth-2 as default or tuning gate thresholds.
