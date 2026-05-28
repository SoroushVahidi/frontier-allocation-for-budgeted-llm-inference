# Repair Jobs Status 2026-05-24

- Generated at (UTC): `2026-05-24T01:17:37.812517+00:00`
- Read-only check only: no API calls launched, no restart/kill/attach, no replay/merge executed.

## cohere_missing_methods_repair_20260524T003751Z
- Provider: `cohere`
- Status: `completed`
- PID: `None`
- tmux session: `cohere_repair_missing_20260524T003751Z` (present: `False`)
- Records: `141/141` (100.0%)
- Method counts: `{"external_l1_max": 47, "external_s1_budget_forcing": 47, "external_tale_prompt_budgeting": 47}`
- Unexpected frontier rows: `False`
- Duplicate rows: `0`
- Unique examples: `47`
- Current method/example: `external_tale_prompt_budgeting` / `openai_gsm8k_train_927`
- Last update (UTC): `2026-05-24T01:07:18.756255+00:00`
- Seconds since last update: `592.09`
- 429/retry summary: `{"api_retry_total": 7, "http_429_total": 0, "recent_429_last_200_lines": 0}`
- Recent error summary: `{"api_retry_total": 7, "auth_error_total": 0, "done_marker": false, "error_total_token_count": 7, "exception_total": 0, "exists": true, "http_429_total": 0, "recent_429_last_200_lines": 0, "recent_error_like_last_200_lines": 14, "size_bytes": 26588, "timeout_total": 7}`
- Ready for merge: `True`
- Recommended next action: `ready_for_merge_with_original_frontier_rows`

## mistral_missing_methods_repair_20260524T003751Z
- Provider: `mistral`
- Status: `running`
- PID: `2281714`
- tmux session: `mistral_repair_missing_20260524T003751Z` (present: `True`)
- Records: `853/900` (94.78%)
- Method counts: `{"external_l1_max": 301, "external_s1_budget_forcing": 300, "external_tale_prompt_budgeting": 252}`
- Unexpected frontier rows: `False`
- Duplicate rows: `1`
- Unique examples: `300`
- Current method/example: `external_tale_prompt_budgeting` / `openai_gsm8k_252`
- Last update (UTC): `2026-05-24T01:17:10.670863+00:00`
- Seconds since last update: `0.18`
- 429/retry summary: `{"api_retry_total": 357, "http_429_total": 357, "recent_429_last_200_lines": 68}`
- Recent error summary: `{"api_retry_total": 357, "auth_error_total": 0, "done_marker": false, "error_total_token_count": 0, "exception_total": 0, "exists": true, "http_429_total": 357, "recent_429_last_200_lines": 68, "recent_error_like_last_200_lines": 0, "size_bytes": 179948, "timeout_total": 0}`
- Ready for merge: `False`
- Recommended next action: `continue_monitoring`

## cerebras_frozen_agreement_only_2of3_validation_20260523
- Provider: `cerebras`
- Status: `stalled_running`
- PID: `2195513`
- tmux session: `55` (present: `True`)
- Records: `247/1200` (20.58%)
- Method counts: `{"direct_reserve_semantic_frontier_v2": 247}`
- Unexpected frontier rows: `False`
- Duplicate rows: `0`
- Unique examples: `247`
- Current method/example: `direct_reserve_semantic_frontier_v2` / `openai_gsm8k_247`
- Last update (UTC): `2026-05-24T00:43:39.893547+00:00`
- Seconds since last update: `2010.95`
- 429/retry summary: `{"api_retry_total": 0, "http_429_total": 0, "recent_429_last_200_lines": 0}`
- Recent error summary: `{"api_retry_total": 0, "auth_error_total": 0, "done_marker": false, "error_total_token_count": 0, "exception_total": 0, "exists": true, "http_429_total": 0, "recent_429_last_200_lines": 0, "recent_error_like_last_200_lines": 0, "size_bytes": 47373, "timeout_total": 0}`
- Ready for merge: `False`
- Recommended next action: `investigate_stall_noninvasively_before_any_restart`

## Artifacts
- Structured status JSON: `outputs/repair_jobs_status_20260524/status_20260524T011710Z.json`
- Raw shell snapshot: `outputs/repair_jobs_status_20260524/raw_status_check_20260524T011401Z.txt`

## Safety Confirmation
- No jobs were touched, restarted, killed, or attached interactively.
- No API calls were launched by this check.
