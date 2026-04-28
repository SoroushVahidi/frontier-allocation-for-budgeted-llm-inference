# Semantic diversity loss-full result analysis (20260428T143500Z)

## Job / data inputs

- Run directory: `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z`
- Rows in `per_case_results.csv` (non-error): **360**
- Manifest `n_selected_cases`: **30**

## A. Did new ideas improve results?

- Aggregate: best method **`direct_reserve_semantic_frontier_v1`** at accuracy **0.7444** vs strict_f3 **0.4778** vs external_l1_max **0.7222**.
- Interpretation: **mixed / diagnostic only** unless paired deltas are consistent.

### Method accuracy summary

| method | n | accuracy | avg_actions | avg_est_cost_proxy | avg_latency |
|---|---|---|---|---|---|
| direct_reserve_semantic_frontier_v1 | 90 | 0.7444 | 4.64 | 0.000450 | nan |
| external_l1_max | 90 | 0.7222 | 1.04 | 0.000100 | nan |
| semantic_minimum_maturation_plus_direct_reserve_v1 | 90 | 0.7111 | 4.69 | 0.000449 | nan |
| strict_f3 | 90 | 0.4778 | 2.94 | 0.000274 | nan |

### Paired deltas

- strict_f3 vs external_l1_max: **n=48**, mean(delta strict - external)= **-0.1875**, wins/losses/ties={'win': 4, 'loss': 13, 'tie': 31}

- `direct_reserve_semantic_frontier_v1` vs strict_f3: n=48, mean_delta=0.2500, wins=15 losses=3 ties=30
  - vs external_l1_max: n=48, mean_delta=0.0625, wins=7 losses=4 ties=37
  - budgets with positive mean delta vs strict_f3: **3 / 3**
- `semantic_minimum_maturation_plus_direct_reserve_v1` vs strict_f3: n=48, mean_delta=0.2083, wins=15 losses=5 ties=28
  - vs external_l1_max: n=48, mean_delta=0.0208, wins=9 losses=8 ties=31
  - budgets with positive mean delta vs strict_f3: **3 / 3**

### strict_f3 vs external_l1_max by budget
- budget 6: n=16, mean(strict-external)=-0.2500
- budget 8: n=16, mean(strict-external)=-0.0625
- budget 4: n=16, mean(strict-external)=-0.2500

## B–H. Interpretation (see tables below)

### Rescue types (counts)

- **all_correct**: 14
- **both_rescue**: 10
- **other**: 8
- **semantic_plus_direct_reserve_rescue**: 5
- **all_wrong**: 4
- **strict_f3_regression**: 3
- **external_only_still_unsolved**: 2
- **direct_reserve_rescue**: 2

### Semantic diversity proxies (row-based means)
- `external_l1_max`: avg semantic_family_count=nan, avg redundancy=nan, share_ge2=nan, immediate_miss_rows=0, absent_from_tree_rows=0
- `strict_f3`: avg semantic_family_count=nan, avg redundancy=nan, share_ge2=nan, immediate_miss_rows=0, absent_from_tree_rows=0
- `direct_reserve_semantic_frontier_v1`: avg semantic_family_count=nan, avg redundancy=nan, share_ge2=nan, immediate_miss_rows=0, absent_from_tree_rows=9
- `semantic_minimum_maturation_plus_direct_reserve_v1`: avg semantic_family_count=2.144, avg redundancy=0.011, share_ge2=nan, immediate_miss_rows=0, absent_from_tree_rows=11
- `semantic_minimum_maturation_frontier_v1_d3`: avg semantic_family_count=nan, avg redundancy=nan, share_ge2=nan, immediate_miss_rows=0, absent_from_tree_rows=0
- `branching_necessity_gate_v1`: avg semantic_family_count=nan, avg redundancy=nan, share_ge2=nan, immediate_miss_rows=0, absent_from_tree_rows=0

### Failure taxonomy (aggregate)
- unknown_unclassified: 270
- not_applicable_or_correct: 43
- bad_seeding_absent_answer_group: 35
- correct_answer_group_present_but_underweighted: 11
- bad_selection_repair: 1

### Incumbent replacement (direct-reserve-related methods)

{'direct_reserve_semantic_frontier_v1': {'n': 90, 'incumbent_replaced_rows': 2}, 'semantic_minimum_maturation_plus_direct_reserve_v1': {'n': 90, 'incumbent_replaced_rows': 4}}

## I. Manuscript

- **Default:** no manuscript change; diagnostic cohort and trace-derived proxies only.

- Files written: `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/rescue_case_table.csv`, `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/final_decision_summary.csv`
