# Active Validation Jobs Status (2026-05-23)

- Generated UTC: 2026-05-24T00:30:12Z
- Check type: read-only, non-invasive
- Jobs touched: none
- API calls launched by this check: none

## tmux Snapshot
```text
55: 1 windows (created Sat May 23 10:44:14 2026)
codex: 1 windows (created Mon May 11 00:05:32 2026)
cohere_seed23_completion_20260518: 1 windows (created Mon May 18 15:09:59 2026)
round2_monitor: 1 windows (created Wed May  6 10:11:41 2026)
```

## targeted_cohere_no_majority_fallback_rerun
- provider: cohere
- status: **completed**
- pid: None
- expected records: 188
- records written: 47 (25.0%)
- current method/example: direct_reserve_semantic_frontier_v2 / openai_gsm8k_train_927
- last update (UTC): 2026-05-24T00:05:45.001282+00:00
- seconds since update: 1467
- retry summary: {"api_retry_429": 0, "api_retry_500": 1, "api_retry_total": 1}
- error summary: {"timeout_mentions": 0, "error_mentions": 0, "done_marker_present": true, "incomplete_slices_rows": 3, "completion_per_method_rows": 1, "process_state": null, "process_elapsed": null, "process_cpu_percent": null, "process_mem_percent": null}
- ready_for_replay: False
- recommended_next_action: completed_but_incomplete_output_review_before_replay
- output root: `outputs/cohere_targeted_no_majority_fallback_rerun_20260523`
- log: `outputs/cohere_targeted_no_majority_fallback_rerun_20260523/cohere_targeted_live_20260523T235741Z.log`

## full_mistral_300_regime_selector_validation
- provider: mistral
- status: **completed**
- pid: None
- expected records: 1200
- records written: 300 (25.0%)
- current method/example: direct_reserve_semantic_frontier_v2 / openai_gsm8k_299
- last update (UTC): 2026-05-24T00:06:02.284294+00:00
- seconds since update: 1450
- retry summary: {"api_retry_429": 224, "api_retry_500": 0, "api_retry_total": 224}
- error summary: {"timeout_mentions": 0, "error_mentions": 0, "done_marker_present": true, "incomplete_slices_rows": 3, "completion_per_method_rows": 1, "process_state": null, "process_elapsed": null, "process_cpu_percent": null, "process_mem_percent": null}
- ready_for_replay: False
- recommended_next_action: completed_but_incomplete_output_review_before_replay
- output root: `outputs/mistral_full300_regime_selector_validation_20260523`
- log: `outputs/mistral_full300_regime_selector_validation_20260523/mistral_full300_live_20260523T233843Z.log`

## cerebras_validation_frozen_agreement_only_2of3
- provider: cerebras
- status: **running**
- pid: 2195513
- expected records: 1200
- records written: 236 (19.67%)
- current method/example: direct_reserve_semantic_frontier_v2 / openai_gsm8k_235
- last update (UTC): 2026-05-24T00:29:25.191625+00:00
- seconds since update: 47
- retry summary: {"api_retry_429": 0, "api_retry_500": 0, "api_retry_total": 0}
- error summary: {"timeout_mentions": 0, "error_mentions": 0, "done_marker_present": false, "incomplete_slices_rows": 0, "completion_per_method_rows": 0, "process_state": "Sl+", "process_elapsed": "09:45:57", "process_cpu_percent": "0.0", "process_mem_percent": "0.3"}
- ready_for_replay: False
- recommended_next_action: keep_running_non_invasive_monitoring
- output root: `outputs/cerebras_frozen_agreement_only_2of3_validation_20260523`
- log: `outputs/cerebras_frozen_agreement_only_2of3_validation_20260523/live_validation_20260523T144414Z.log`

