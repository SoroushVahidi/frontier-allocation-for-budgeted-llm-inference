# External L1 Loss Casebook

Total paired examples: 30

L1 beats counts per method: {'direct_reserve_semantic_frontier_v2': 9, 'direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1': 8, 'direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1': 10, 'direct_reserve_semantic_frontier_v2_selection_fix_v1': 6}

Loss taxonomy counts: {('direct_reserve_semantic_frontier_v2', 'present_but_not_selected'): 5, ('direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1', 'present_but_not_selected'): 4, ('direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1', 'absent_from_tree'): 4, ('direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1', 'present_but_not_selected'): 6, ('direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1', 'absent_from_tree'): 4, ('direct_reserve_semantic_frontier_v2_selection_fix_v1', 'present_but_not_selected'): 5, ('direct_reserve_semantic_frontier_v2_selection_fix_v1', 'absent_from_tree'): 1, ('direct_reserve_semantic_frontier_v2', 'absent_from_tree'): 4}

Distance categories (absent_from_tree): {('direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1', 'near_numeric'): 3, ('direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1', 'diverse_but_no_gold'): 1, ('direct_reserve_semantic_frontier_v2_selection_fix_v1', 'collapsed_wrong_answer_group'): 1, ('direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1', 'diverse_but_no_gold'): 1, ('direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1', 'collapsed_wrong_answer_group'): 3, ('direct_reserve_semantic_frontier_v2', 'near_numeric'): 3, ('direct_reserve_semantic_frontier_v2', 'collapsed_wrong_answer_group'): 1}

Representative failures:
- openai_gsm8k_0 | direct_reserve_semantic_frontier_v2 | present_but_not_selected | n/a
- openai_gsm8k_0 | direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1 | present_but_not_selected | n/a
- openai_gsm8k_1 | direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1 | absent_from_tree | near_numeric
- openai_gsm8k_2 | direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1 | present_but_not_selected | n/a
- openai_gsm8k_2 | direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1 | absent_from_tree | diverse_but_no_gold
- openai_gsm8k_3 | direct_reserve_semantic_frontier_v2_selection_fix_v1 | present_but_not_selected | n/a
- openai_gsm8k_3 | direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1 | absent_from_tree | near_numeric
- openai_gsm8k_5 | direct_reserve_semantic_frontier_v2 | present_but_not_selected | n/a
