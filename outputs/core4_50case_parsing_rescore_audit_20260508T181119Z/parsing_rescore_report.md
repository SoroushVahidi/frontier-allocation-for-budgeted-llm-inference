# Parsing rescore report

- Original exact by method: {'external_l1_max_fair_v1': 31, 'external_self_consistency_4_fair_v1': 33, 'external_s1_budget_forcing_faithful_v1': 32, 'external_tale_ep_prompt_budgeting_faithful_v1': 34}
- Rescored exact by method: {'external_l1_max_fair_v1': 31, 'external_self_consistency_4_fair_v1': 33, 'external_s1_budget_forcing_faithful_v1': 32, 'external_tale_ep_prompt_budgeting_faithful_v1': 34}
- Exact gains by method: {'external_l1_max_fair_v1': 0, 'external_self_consistency_4_fair_v1': 0, 'external_s1_budget_forcing_faithful_v1': 0, 'external_tale_ep_prompt_budgeting_faithful_v1': 0}
- Unresolved parsing failures by method: {'external_s1_budget_forcing_faithful_v1': 10, 'external_l1_max_fair_v1': 7, 'external_self_consistency_4_fair_v1': 6, 'external_tale_ep_prompt_budgeting_faithful_v1': 6}
- Main root causes: {'forced_continuation_artifact': 4, 'multiple_candidate_numbers': 7, 'unknown': 18}
- Baseline numbers should not be overwritten yet for headline reporting; treat rescored values as sensitivity analysis.
- Comparison against our method is possible with explicit caveat that parsing robustness remains a material confounder.
- Caveat: S1 raw text observability fields remain empty, limiting hard attribution for no-final-answer cases.
