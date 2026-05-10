# Stage-2 disagreement analysis

Stage-2 paired result: integrated 86/100 vs external_l1 85/100 (delta +1).

## External_l1-only (7) one-line diagnosis
| case_id | integrated_action | mechanism_label | derived_problem_family | why_integrated_won_or_lost_hypothesis |
|---|---|---|---|---|
| openai_gsm8k_674 | base_method_no_retry | gold_absent_discovery | rate_ratio | carryover base prediction underperformed against external baseline |
| openai_gsm8k_683 | base_method_no_retry | gold_absent_discovery | rate_ratio | carryover base prediction underperformed against external baseline |
| openai_gsm8k_746 | base_method_no_retry | unknown | unknown | carryover base prediction underperformed against external baseline |
| openai_gsm8k_752 | base_method_no_retry | gold_absent_discovery | counting_combinatorics | carryover base prediction underperformed against external baseline |
| openai_gsm8k_758 | base_method_no_retry | gold_absent_discovery | average | carryover base prediction underperformed against external baseline |
| openai_gsm8k_765 | base_method_no_retry | unknown | unknown | carryover base prediction underperformed against external baseline |
| openai_gsm8k_769 | base_method_no_retry | gold_absent_discovery | rate_ratio | carryover base prediction underperformed against external baseline |

## Integrated-only (8) one-line diagnosis
| case_id | integrated_action | mechanism_label | derived_problem_family | why_integrated_won_or_lost_hypothesis |
|---|---|---|---|---|
| openai_gsm8k_675 | base_method_no_retry | unknown |  | integration-side selection/parsing appears more robust than external for this case |
| openai_gsm8k_714 | base_method_no_retry | unknown |  | integration-side selection/parsing appears more robust than external for this case |
| openai_gsm8k_721 | base_method_no_retry | unknown |  | integration-side selection/parsing appears more robust than external for this case |
| openai_gsm8k_728 | base_method_no_retry | unknown |  | integration-side selection/parsing appears more robust than external for this case |
| openai_gsm8k_738 | base_method_no_retry | unknown |  | integration-side selection/parsing appears more robust than external for this case |
| openai_gsm8k_739 | base_method_no_retry | unknown |  | integration-side selection/parsing appears more robust than external for this case |
| openai_gsm8k_754 | base_method_no_retry | unknown |  | integration-side selection/parsing appears more robust than external for this case |
| openai_gsm8k_768 | base_method_no_retry | unknown |  | integration-side selection/parsing appears more robust than external for this case |

## Both-wrong (7) one-line diagnosis
| case_id | integrated_action | mechanism_label | derived_problem_family | likely_new_failure_pattern |
|---|---|---|---|---|
| openai_gsm8k_687 | base_method_no_retry | unknown |  | unknown_general_math_error |
| openai_gsm8k_695 | base_method_no_retry | unknown |  | unknown_general_math_error |
| openai_gsm8k_702 | base_method_no_retry | unknown |  | unknown_general_math_error |
| openai_gsm8k_706 | base_method_no_retry | unknown |  | unknown_general_math_error |
| openai_gsm8k_707 | base_method_no_retry | unknown |  | unknown_general_math_error |
| openai_gsm8k_725 | base_method_no_retry | unknown |  | unknown_general_math_error |
| openai_gsm8k_726 | base_method_no_retry | unknown |  | unknown_general_math_error |

## Pattern interpretation
- Remaining external_l1-only cases are mostly base/no-retry carryover and non-covered pattern pockets rather than systemic targeted-retry collapse.
- Both-wrong cases indicate unresolved mechanism families that need new pattern-specific scaffolds or selector diagnostics.

## Decision framing
- A) Iterate failure patterns first: recommended for robustness.
- B) Stage 3 TALE/S1 exploratory: reasonable in parallel after documenting current bottlenecks.
- C) Expand to 300-case vs L1: lower priority until external_l1-only and both-wrong clusters are better explained.
- D) Stop at parity: not preferred yet because there is directional +1 and identifiable next bottlenecks.