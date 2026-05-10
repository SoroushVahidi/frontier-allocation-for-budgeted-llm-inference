# Fair core4 vs our-method alignment report

- Fair 50-case set matches Stage-3 case IDs overlap: original_live=50/50, patch_focused=50/50.
- Existing our-method outputs sufficient for full 50-case comparison: yes (covered=50).
- Current fair baseline scores: {'external_l1_max_fair_v1': 31, 'external_self_consistency_4_fair_v1': 33, 'external_s1_budget_forcing_faithful_v1': 32, 'external_tale_ep_prompt_budgeting_faithful_v1': 34}.
- Best-core4 correct count on matched cases: 38/50.
- Existing our-method score on matched cases: 39/50; deltas vs L1/SC4/S1/TALE/best = 8/6/7/5/1.
- Previous 39/50 can be considered directly comparable at case level for this set, but reporting should note runtime differences (pilot-scaffolded vs production-equivalent).
- Recommended next command/query: compute and publish paired per-case win/loss matrix from existing_fair_comparison.csv (no new API calls).
- Caveat: production-equivalence dry-run does not provide live accuracy and cannot replace live comparison evidence.
