# Loss cases for manual inspection

count=4

| example_id | failure_type | method | external | strict_f3 | stratum |
|---|---|---|---|---|---|
| openai_gsm8k_2 | other | 450 | 350 | 450 | absent_from_tree |
| openai_gsm8k_6 | gold_absent | oxed{39} | 38 | 1 * 5 + 0.5 * 12 + 3 * 7 = 40 | absent_from_tree |
| openai_gsm8k_13 | gold_absent | 10 | 10 | 10 | control_correct |
| openai_gsm8k_14 | other | 38 | x = 40 | 38 | control_correct |
