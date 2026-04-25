# STRICT_F3_EXTERNAL_L1_MAX_RICH_FAILURE_TRACES_20260425T051500Z

## Required answers
1. Matched examples collected: **30**.
2. strict_f3 wrong / external_l1_max correct cases: **9**.
3. Reached 100 loss cases: **False**.
4. Dominant failure modes: unknown (7), correct_answer_absent_from_explored_tree (2).
5. Among absent-from-tree losses, median nearest-gold-path depth: **1.0**.
6. Failure mechanism mix (loss cases): never entered region=8, abandoned promising branch=1, committed early=0, selected poorly/other=0.
7. Most useful features for controller design (empirical separability in this run): strict_f3_nearest_gold_path_score, strict_f3_correct_region_entered, strict_f3_abandoned_promising_branch, strict_f3_answer_entropy, strict_f3_top2_support_gap, strict_f3_selected_answer_support_fraction, and cost/latency ratios.
8. Concrete algorithmic changes are in `candidate_algorithm_implications.md` (8 hypotheses).

## Analysis prompts addressed
- Share of strict_f3 losses with gold final answer absent from tree: 1.0.
- Counting/combinatorics average nearest-path score in losses: NA.
- Low-budget (4/6) shallow-nearest-path loss share: 0.2857142857142857.
- High entropy / low support / small top2-gap exploratory signal available in rich_feature_table (rows=30).

## Outputs
- `outputs/strict_f3_vs_external_l1_max_rich_failure_traces_20260425T051500Z/`
