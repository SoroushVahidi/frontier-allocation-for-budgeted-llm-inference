# CEREBRAS_SUPPORT_SLOWNESS_DIAGNOSTICS_20260524

## 1. Executive summary
Cerebras GSM8K run is still running with 659/1200 effective rows (54.92%).
Observed throughput: 23.34 rows/hour overall, 154.22 sec/row overall.

## 2. Current job status
Latest row timestamp: 2026-05-24T19:01:39.878131+00:00
Latest heartbeat: 2026-05-24T19:01:39.879109+00:00 (age 122.1s)
Heartbeat status: running

## 3. Run configuration
Provider=cerebras model=llama3.1-8b dataset=openai/gsm8k seed=71 budget=6
Methods=direct_reserve_semantic_frontier_v2, external_l1_max, external_s1_budget_forcing, external_tale_prompt_budgeting
Retry settings={"api_retry_max_attempts": 5, "api_retry_base_delay_seconds": 1.0, "api_retry_backoff_multiplier": 2.0, "api_retry_max_delay_seconds": 20.0, "api_retry_jitter_seconds": 0.5}
Run command (redacted)=2195504    9002  1-04:13:14 Ss+   0.0  0.0 bash -lc set -euo pipefail; cd /home/soroush/frontier-allocation-for-budgeted-llm-inference; exec >"outputs/cerebras_frozen_agreement_only_2of3_validation_20260523/live_validation_20260523T144414Z.log" 2>&1; echo "[start] $(date -u +%Y-%m-%dT%H:%M:%SZ)"; python3 scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260523T144414Z --providers cerebras --datasets openai/gsm8k --seeds 71 --budgets 6 --methods direct_reserve_semantic_frontier_v2,external_l1_max,external_s1_budget_forcing,external_tale_prompt_budgeting --target-scored-per-slice 300 --max-examples 300 --cerebras-model llama3.1-8b --api-retry-max-attempts 5 --api-retry-base-delay-seconds 1.0 --api-retry-backoff-multiplier 2.0 --api-retry-max-delay-seconds 20.0 --api-retry-jitter-seconds 0.5 --max-recovery-passes 2 --output-root outputs/cerebras_frozen_agreement_only_2of3_validation_20260523; echo "[done] $(date -u +%Y-%m-%dT%H:%M:%SZ)"

## 4. Progress/throughput summary
Total rows written=660 effective unique rows=659 expected=1200 percent=54.92%
Rows/hour overall=23.34; rows/hour active-windows=50.31
Median/P90/P95/P99 inter-row seconds=61.135788, 121.9174356, 122.1483194, 3661.33838382

## 5. Method-by-method progress
                             method  rows_written  effective_unique_rows              first_timestamp_utc               last_timestamp_utc  avg_seconds_per_row_from_gaps  median_seconds_per_row  p90_seconds_per_row  p95_seconds_per_row  long_gap_count_gt10m  completed_300
direct_reserve_semantic_frontier_v2           301                    300 2026-05-23T14:45:17.218899+00:00 2026-05-24T03:47:51.419235+00:00                     156.514001               61.133639           121.572385           122.276517                     7           True
                    external_l1_max           300                    300 2026-05-24T03:48:52.356472+00:00 2026-05-24T16:50:22.361771+00:00                     156.822760               61.205470           121.513059           122.064229                     7           True
         external_s1_budget_forcing            59                     59 2026-05-24T16:51:23.276375+00:00 2026-05-24T19:01:39.878131+00:00                     134.768996               61.075346           122.066172           122.203633                     1          False

## 6. Pause windows and heartbeat gaps
                 pause_start_utc                    pause_end_utc  gap_seconds  gap_minutes  gt_10m  gt_30m  gt_60m  rows_before_pause  rows_after_pause                       method_before                        method_after   example_before    example_after
2026-05-24T13:31:55.080623+00:00 2026-05-24T14:32:57.229568+00:00  3662.148945    61.035816       1       1       1                536               537                     external_l1_max                     external_l1_max openai_gsm8k_234 openai_gsm8k_235
2026-05-24T08:02:15.117925+00:00 2026-05-24T09:03:17.263360+00:00  3662.145435    61.035757       1       1       1                412               413                     external_l1_max                     external_l1_max openai_gsm8k_110 openai_gsm8k_111
2026-05-24T02:32:34.039986+00:00 2026-05-24T03:33:36.183392+00:00  3662.143406    61.035723       1       1       1                288               289 direct_reserve_semantic_frontier_v2 direct_reserve_semantic_frontier_v2 openai_gsm8k_287 openai_gsm8k_288
2026-05-24T04:23:25.996401+00:00 2026-05-24T05:24:28.127419+00:00  3662.131018    61.035517       1       1       1                330               331                     external_l1_max                     external_l1_max  openai_gsm8k_28  openai_gsm8k_29
2026-05-23T15:33:09.554889+00:00 2026-05-23T16:34:11.640934+00:00  3662.086045    61.034767       1       1       1                 40                41 direct_reserve_semantic_frontier_v2 direct_reserve_semantic_frontier_v2  openai_gsm8k_39  openai_gsm8k_40
2026-05-23T21:02:53.175864+00:00 2026-05-23T22:03:55.225226+00:00  3662.049362    61.034156       1       1       1                164               165 direct_reserve_semantic_frontier_v2 direct_reserve_semantic_frontier_v2 openai_gsm8k_163 openai_gsm8k_164
2026-05-24T09:53:10.331403+00:00 2026-05-24T10:54:11.899885+00:00  3661.568482    61.026141       1       1       1                454               455                     external_l1_max                     external_l1_max openai_gsm8k_152 openai_gsm8k_153
2026-05-23T22:53:47.295738+00:00 2026-05-23T23:54:48.467499+00:00  3661.171761    61.019529       1       1       1                206               207 direct_reserve_semantic_frontier_v2 direct_reserve_semantic_frontier_v2 openai_gsm8k_205 openai_gsm8k_206
2026-05-23T17:24:06.193077+00:00 2026-05-23T18:25:07.310549+00:00  3661.117472    61.018625       1       1       1                 82                83 direct_reserve_semantic_frontier_v2 direct_reserve_semantic_frontier_v2  openai_gsm8k_81  openai_gsm8k_82
2026-05-24T15:21:51.229547+00:00 2026-05-24T16:22:52.255195+00:00  3661.025648    61.017094       1       1       1                577               578                     external_l1_max                     external_l1_max openai_gsm8k_275 openai_gsm8k_276

## 7. API/retry/error evidence
{
  "error_counts": {
    "http_429": 2,
    "http_500": 0,
    "http_502": 0,
    "http_503": 0,
    "http_504": 0,
    "timeout": 0,
    "temporary_unavailable": 2,
    "queue_exceeded": 2,
    "rate_limit": 2,
    "http_403": 0,
    "code_1010": 0,
    "traceback": 0,
    "fatal": 0,
    "exception": 2,
    "retry": 0
  },
  "failures_jsonl_rows": 1,
  "rows_with_nonempty_error_field": 1,
  "retry_attempts_total": 0,
  "retry_attempts_max": 0,
  "rows_with_retry_attempts_gt0": 0,
  "max_recovery_pass_index_seen": 1,
  "recovery_pass_rows_gt0": 1,
  "total_error_events_extracted": 10
}

## 8. Duplicate/integrity notes
{
  "duplicate_key_count": 1,
  "duplicate_row_overage": 1,
  "duplicate_keys": [
    "openai_gsm8k_20||direct_reserve_semantic_frontier_v2"
  ],
  "duplicates_include_failed_rows": true
}

## 9. Comparison with Cohere/Mistral throughput
                   label provider                dataset   rows              first_timestamp_utc               last_timestamp_utc  elapsed_hours  rows_per_hour  seconds_per_row                status
   cerebras_gsm8k_active cerebras           openai/gsm8k  660.0 2026-05-23T14:45:17.218899+00:00 2026-05-24T19:01:39.878131+00:00      28.272961      23.343859       154.216150             available
   cohere_gsm8k_official   cohere           openai/gsm8k 1200.0 2026-05-23T18:19:57.016892+00:00 2026-05-23T20:21:36.378760+00:00       2.027601     591.832557         6.082802             available
  mistral_gsm8k_official  mistral           openai/gsm8k 1200.0 2026-05-23T23:38:47.978390+00:00 2026-05-24T01:19:03.584095+00:00       1.671002     718.132174         5.013005             available
mistral_math500_official  mistral HuggingFaceH4/MATH-500 1200.0 2026-05-24T01:50:08.199823+00:00 2026-05-24T03:06:52.067690+00:00       1.278852     938.341439         3.836557             available
 cohere_math500_official      NaN                    NaN    NaN                              NaN                              NaN            NaN            NaN              NaN missing_or_incomplete

## 10. Support-ready facts
See `outputs/cerebras_support_slowness_diagnostics_20260524/cerebras_support_message_facts.md`.

## 11. Suggested support message
See `outputs/cerebras_support_slowness_diagnostics_20260524/suggested_cerebras_support_email.md`.

## 12. Safety confirmation
Read-only diagnostics only; no API calls; no tmux attach; no active-job modification; no commit/push.