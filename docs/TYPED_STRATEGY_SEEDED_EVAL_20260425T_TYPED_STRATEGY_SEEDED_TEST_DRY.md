# TYPED_STRATEGY_SEEDED_EVAL_20260425T_TYPED_STRATEGY_SEEDED_TEST_DRY

1. Did typed strategy seeding reduce absent-from-tree failures on the 150 loss cases? no_or_neutral.
2. Did it reduce present-not-selected failures? no_or_neutral.
3. Did it improve counting/combinatorics accuracy? no_or_neutral.
4. Did it create genuinely different reasoning paths, or did branches still collapse to the same answer/direction? Check typed_strategy_diversity_summary.csv.
5. Which strategy family most often discovered the correct answer? Check answer_group_by_strategy_summary.csv and per_case_strategy_metadata.jsonl.
6. Which strategy family most often caused wrong high-confidence answers? Check answer_group_by_strategy_summary.csv + per_case_results.csv.
7. Did the commit guard repair any present-not-selected cases? Check present_not_selected_repairs.csv.
8. Did the commit guard hurt any cases? Check hurt_cases.csv.
9. Did typed seeding increase actions/cost/latency? avg_actions strict_f3=4.000, typed=4.000.
10. Should this become a real candidate method, or remain diagnostic? Diagnostic unless gains hold in real API runs.
11. What fields are still missing for deeper scoring diagnosis? See missing_fields_report.csv.
