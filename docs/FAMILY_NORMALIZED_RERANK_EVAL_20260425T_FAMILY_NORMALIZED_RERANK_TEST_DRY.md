# FAMILY_NORMALIZED_RERANK_EVAL_20260425T_FAMILY_NORMALIZED_RERANK_TEST_DRY

1. Did family-normalized reranking reduce present-not-selected failures? no_or_neutral.
2. Did it repair cases where gold was present but under-scored? See present_not_selected_repairs.csv and gold_vs_selected_diagnostics.csv.
3. Did it hurt cases where raw support was already correct? See hurt_cases.csv.
4. Did it improve counting/combinatorics accuracy? no_or_neutral.
5. Was improvement from family normalization, verifier, process, or diversity? Inspect selection_ablation_summary.csv.
6. In repaired cases, was gold supported by fewer raw branches but more independent families? Check family_vote_diagnostics.csv + per_answer_group_scores.jsonl.
7. In unrepaired cases, why did gold still lose? Check selection_failure_reason in gold_vs_selected_diagnostics.csv.
8. How many cases are theoretically fixable by oracle-if-gold-present? See selection_ablation_summary.csv.
9. Is bottleneck now selection or generation? Compare gold_group_present and oracle ceilings in selection_ablation files.
10. Should this be candidate method or remain diagnostic? Keep diagnostic until real-API validation and broader slices improve.
