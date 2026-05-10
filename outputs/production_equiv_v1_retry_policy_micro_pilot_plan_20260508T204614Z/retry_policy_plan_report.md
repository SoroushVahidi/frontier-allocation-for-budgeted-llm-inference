# production_equiv_v1 retry policy micro-pilot plan
- selected_cases: 10
- planned_calls: 16 (<=40)
- variants used per case are risk-priority weighted (high priority gets 2 variants; others 1).
- prompt contract enforces strict `FINAL_ANSWER: <number>` output with no units/extra words.
- no_gold_leakage: True
- no_prediction_leakage: True
