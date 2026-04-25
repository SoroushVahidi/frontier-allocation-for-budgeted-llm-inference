# DETAILED_LOSS_CASE_ANALYSIS_20260425T_WULVER_COHERE_LONG_DETAIL

- Total paired cases analyzed: **720**.
- strict_f3 lost to external_l1_max: **150**.
- Among losses: absent-from-tree=106, present-not-selected=44.
- Present-not-selected mostly combinatorics/counting? **yes**.
- Top problem types among present-not-selected: [('counting_combinatorics', 34), ('multi_step_arithmetic', 14), ('ratio_percent', 9), ('unit_conversion', 5), ('comparison', 2)].
- Top problem types among absent-from-tree: [('counting_combinatorics', 143), ('ratio_percent', 36), ('multi_step_arithmetic', 28), ('unit_conversion', 17), ('comparison', 6)].
- Loss concentration by budget: {4: 53, 6: 41, 8: 56}.
- Repeated same-family expansion mean (losses): 0.2293.
- Max-family concentration mean (losses): 0.0000.
- Fields still unavailable for scoring diagnosis: ['answer_entropy', 'answer_group_support_counts', 'branch_score', 'commit_margin', 'external_final_answer', 'external_l1_max_final_answer', 'external_l1_max_final_answer_raw', 'our_final_answer', 'priority_score', 'selected_answer_group', 'strict_f3_final_answer', 'strict_f3_final_answer_raw', 'top2_support_gap', 'top_answer_group'].

Package: `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/`
