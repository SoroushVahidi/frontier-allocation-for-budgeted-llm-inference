# Domain-Aware 30-Case Failure Triage

Source run: `/tmp/cohere_exact_case_domain_detection_fixed_30case_20260510/cohere_real_model_cost_normalized_validation_cohere_exact_domain_detection_fixed_30case_20260510`

## Summary

- Old method exact: `9/30 = 30.0%`
- New domain-aware diverse-anchor exact: `14/30 = 46.7%`
- Net change: `+5`
- Regression count: `1`
- Still-failed count: `15`
- `domain_detection_source=exact_case_metadata` for `30/30`
- No paid/API calls were made in this triage pass; analysis used existing artifacts only.

## Regression: `openai_gsm8k_213`

- Gold: `24`
- Old prediction: `24`
- New prediction: `18`
- Old candidate pool: `24`, `20`
- New candidate pool: `18`, `80`, `48`, `20`
- `gold_in_tree` changed from `1` to `0`
- Wrong selected answer was introduced by `direct_l1_anchor` (`18`)
- `unit_ledger_money_anchor` and `equation_first_anchor` contributed only wrong alternatives (`80`, `48`)
- Diagnosis: generation failure plus anchor-induced regression; not parse or metadata

## Still-Failed Cases

Classification of the 15 still-failed cases:

- `a) gold absent from new candidate pool`: `14`
- `b) gold present but not selected`: `0`
- `c) parse/surfacing issue`: `1`
- `d) API/runtime issue`: `0`
- `e) unknown`: `0`

Case-by-case:

- `openai_gsm8k_162` — `a`
- `openai_gsm8k_168` — `a`
- `openai_gsm8k_180` — `a`
- `openai_gsm8k_184` — `a`
- `openai_gsm8k_217` — `a`
- `openai_gsm8k_22` — `a`
- `openai_gsm8k_239` — `a`
- `openai_gsm8k_262` — `a`
- `openai_gsm8k_324` — `a`
- `openai_gsm8k_367` — `a`
- `openai_gsm8k_450` — `a`
- `openai_gsm8k_508` — `a`
- `openai_gsm8k_51` — `a`
- `openai_gsm8k_73` — `a`
- `openai_gsm8k_70` — `c` (`model_step_missing` surfaced as the selected answer)

Domain breakdown of remaining failures:

- `multi_step_arithmetic`: `6`
- `ratio_percent`: `5`
- `money_cost_revenue`: `4`

## Why the Failures Persist

- Most remaining misses are generation failures: the gold answer is absent from the explored tree/candidate pool.
- The one surfacing issue is `openai_gsm8k_70`, where the gold was present in-tree but the selected answer surfaced as `model_step_missing`.
- There are no clear API/runtime failures in the 15 still-failed cases.

## Useful Near-Misses / Gold Candidates

- `direct_l1_anchor` is still the dominant producer of candidate answers in both successes and failures.
- `equation_first_anchor` helped on several improved cases, but on remaining failures it mostly emitted near-misses or malformed text.
- `unit_ledger_money_anchor` and `ratio_percentage_anchor` produced domain-shaped near-misses on several failures, but not the gold answer.
- `backward_check_anchor` helped on some improved multi-step cases, but the remaining multi-step failures still missed gold in-tree.

## Improved Cases

- `openai_gsm8k_17` — improvement came from `direct_l1_anchor`
- `openai_gsm8k_6` — improvement came from selection/support interaction; `direct_l1_anchor` already had the gold candidate and `equation_first_anchor` + `backward_check_anchor` reinforced it
- `openai_gsm8k_36` — improvement came from `direct_l1_anchor`
- `openai_gsm8k_166` — improvement came from `direct_l1_anchor`
- `openai_gsm8k_433` — improvement came from `direct_l1_anchor` plus selection/support interaction
- `openai_gsm8k_458` — improvement came from `direct_l1_anchor`

## Recommendation

- Keep the current anchor ordering.
- Add a regression guard for cases where `direct_l1_anchor` dominates with a wrong consensus and the gold falls out of the candidate pool.
- Do not increase budget yet; the remaining failures are mostly generation misses, not budget exhaustion.
- Run 50 cases only after the regression guard is added or after one more anchor-generation fix reduces the gold-absent failures.

