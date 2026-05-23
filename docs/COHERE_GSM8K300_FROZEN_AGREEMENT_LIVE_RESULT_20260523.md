Cohere GSM8K-300 — Frozen Agreement Live Result (2026-05-23)

Output root:
- outputs/live_validation_hardening_frozen_agreement_policy_20260523/cohere_real_model_cost_normalized_validation_20260523T131849Z

Integrity
- manifest target_scored_per_slice: 300
- unique examples: 300
- duplicate records: 0
- failed rows: 0
- skipped rows: 0
- recovery passes observed: 0
- per-example completeness: all 300 examples have all 4 methods

Per-method completion (scored rows and accuracy):
- direct_reserve_semantic_frontier_v2: 300 scored, accuracy 0.743333
- external_l1_max: 300 scored, accuracy 0.720000
- external_s1_budget_forcing: 300 scored, accuracy 0.733333
- external_tale_prompt_budgeting: 300 scored, accuracy 0.683333

Agreement and pooled policies (from replay):
- agreement_only_2of3: agreement_only_2of3,261,216,0.827586,39,300
- pooled_4_majority: pooled_4_majority,262,222,0.847328,38,300

Paired comparison (agreement-only 2-of-3 vs frontier)
- paired sample n: N/A
- agreement mean: N/A
- 95% bootstrap CI: [N/A, N/A]

Live job heartbeat (non-invasive):
- Cerebras progress (attempted,scored): 41,39
- Mistral progress (attempted,scored): missing

Files created under outputs/cohere_gsm8k300_frozen_agreement_live_result_20260523:
- integrity_summary.json
- method_accuracy_summary.csv
- frozen_replay_summary.csv
- win_loss_tie_summary.csv
- paired_ci_summary.csv
- manifest.json (copy)

Notes
- Integrity checks passed; no duplicates/failures observed. All 300 examples scored for all four methods.
- No changes made to running Cerebras or Mistral jobs.
