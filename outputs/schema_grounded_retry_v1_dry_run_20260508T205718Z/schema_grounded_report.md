# schema_grounded_retry_v1 dry-run
- case_count: 15
- planned_calls: 15
- schema_distribution: {'before_after_state_schema': 4, 'quantity_ledger_schema': 3, 'ratio_equation_schema': 4, 'target_difference_schema': 1, 'rate_table_schema': 1, 'average_total_count_schema': 2}
- no_gold_in_prompts_verified: True
- no_prediction_leakage_verified: True
- every_prompt_contains_final_answer_literal: True
- every_prompt_contains_schema_block_labels: True
- ready_for_5case_live_probe: True
