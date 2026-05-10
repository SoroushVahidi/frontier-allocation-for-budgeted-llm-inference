# Core4 10-case checkpoint plan

- Patch S1 parser first?: **No immediate parser patch**; first improve observability to capture raw final text on failures.
- Run shape: **two 5-case slices** (preferred) with cap 100 each, instead of one 10-case cap-150 run.
- Methods: keep same core4 (`external_l1_max_fair_v1`, `external_self_consistency_4_fair_v1`, `external_s1_budget_forcing_faithful_v1`, `external_tale_ep_prompt_budgeting_faithful_v1`).
- Temperature: keep `0.0` for deterministic call-accounting calibration.
- SC-6 / PAL: keep deferred for this 10-case calibration step.
- Claim supported: stable live execution + bounded call accounting + preliminary quality trend on core4.
- Before 25/50 cases: require no cap hits, no API/method errors, and <=1 parsing failure in 10 cases (with diagnosed cause).
