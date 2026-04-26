# Loss cases for manual inspection

count=15

| example_id | failure_type | method | external | strict_f3 | stratum |
|---|---|---|---|---|---|
| openai_gsm8k_1101 | other | 16 | 14 | 16 | fresh_gsm8k_unseen |
| openai_gsm8k_794 | gold_absent | 32 | 32 | 32 | fresh_gsm8k_unseen |
| openai_gsm8k_772 | present_not_selected | 0.5 | 50% | 50 | fresh_gsm8k_unseen |
| openai_gsm8k_1012 | gold_absent | 80 | 94% | 89 | fresh_gsm8k_unseen |
| openai_gsm8k_546 | gold_absent | 130 | 130 | 130 | fresh_gsm8k_unseen |
| openai_gsm8k_1028 | other | 200 | 300 | 300 | fresh_gsm8k_unseen |
| openai_gsm8k_822 | gold_absent | $1260 | 1260 | For a 7-day week, John earns 7 x $180 = $1260. | fresh_gsm8k_unseen |
| openai_gsm8k_942 | gold_absent | 178.75 | $183.75 | 193.75 | fresh_gsm8k_unseen |
| openai_gsm8k_1235 | gold_absent | 0.16666666666666666 | 2.5 | 30% | fresh_gsm8k_unseen |
| openai_gsm8k_272 | all_wrong | $5.00 | $20.00 - $15.00 = oxed{$5.00} | 15.00 | fresh_gsm8k_unseen |
| openai_gsm8k_659 | gold_absent | 2.5 | $6 | $4 | fresh_gsm8k_unseen |
| openai_gsm8k_883 | gold_absent | 25 | 25 | 25 | fresh_gsm8k_unseen |
| openai_gsm8k_844 | gold_absent | 150 | 240 | 150 | fresh_gsm8k_unseen |
| openai_gsm8k_299 | gold_absent | 15000 | 15000 | 15000 | fresh_gsm8k_unseen |
| openai_gsm8k_923 | gold_absent | 4 | 4.5 | 4.5 | fresh_gsm8k_unseen |
