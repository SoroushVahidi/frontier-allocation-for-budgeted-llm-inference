# Difference cases for manual inspection

count=9

| example_id | failure_type | method | external | strict_f3 | stratum |
|---|---|---|---|---|---|
| openai_gsm8k_1101 | other | 16 | 14 | 16 | fresh_gsm8k_unseen |
| openai_gsm8k_772 | present_not_selected | 0.5 | 50% | 50 | fresh_gsm8k_unseen |
| openai_gsm8k_1012 | gold_absent | 80 | 94% | 89 | fresh_gsm8k_unseen |
| openai_gsm8k_1028 | other | 200 | 300 | 300 | fresh_gsm8k_unseen |
| openai_gsm8k_942 | gold_absent | 178.75 | $183.75 | 193.75 | fresh_gsm8k_unseen |
| openai_gsm8k_1235 | gold_absent | 0.16666666666666666 | 2.5 | 30% | fresh_gsm8k_unseen |
| openai_gsm8k_659 | gold_absent | 2.5 | $6 | $4 | fresh_gsm8k_unseen |
| openai_gsm8k_844 | gold_absent | 150 | 240 | 150 | fresh_gsm8k_unseen |
| openai_gsm8k_923 | gold_absent | 4 | 4.5 | 4.5 | fresh_gsm8k_unseen |
