# Fair core4 paired comparison report

| Comparator | Our | Comparator | Delta | Our only | Comparator only | Both correct | Both wrong |
|---|---:|---:|---:|---:|---:|---:|---:|
| external_l1_max_fair_v1 | 39 | 31 | +8 | 9 | 1 | 30 | 10 |
| external_self_consistency_4_fair_v1 | 39 | 33 | +6 | 8 | 2 | 31 | 9 |
| external_s1_budget_forcing_faithful_v1 | 39 | 32 | +7 | 9 | 2 | 30 | 9 |
| external_tale_ep_prompt_budgeting_faithful_v1 | 39 | 34 | +5 | 6 | 1 | 33 | 10 |
| best_core4_oracle | 39 | 38 | +1 | 3 | 2 | 36 | 9 |

Strongest individual baseline: `external_tale_ep_prompt_budgeting_faithful_v1` (34/50).
Our margin over strongest individual baseline: `+5`.
Our margin over best_core4 oracle: `+1`.

Safe wording for paper/slides: "On a matched 50-case set, our patch-focused integrated method scores 39/50, exceeding each evaluated fair core baseline (31-34/50) and the best-of-core4 oracle (38/50), under known parsing and runtime-equivalence caveats."
Before claiming best among evaluated methods broadly: run production-equivalent live comparison on the same 50 cases and address parsing robustness.
