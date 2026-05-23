# Cohere & Cerebras Validation Job Health Status — 2026-05-23

**Check timestamp:** 2026-05-23T21:56:29Z  
**Checked by:** Claude Code (non-invasive read-only inspection)  
**No jobs were touched, interrupted, restarted, killed, or modified.**  
**No API calls were made.**

---

## tmux Sessions at Check Time

| Session name | Created |
|---|---|
| `55` | 2026-05-23 10:44:14 |
| `codex` | 2026-05-11 00:05:32 |
| `cohere_seed23_completion_20260518` | 2026-05-18 15:09:59 |
| `round2_monitor` | 2026-05-06 10:11:41 |

Note: No session named `cohere_canon300_20260523T181948Z` found — Cohere canonical job completed and its process exited cleanly.

---

## Job 1 — Contract-Matched Cohere Canonical Final-300

**Status: `healthy_completed`**

| Field | Value |
|---|---|
| Provider | cohere |
| Model | command-r-plus-08-2024 |
| Dataset | openai/gsm8k |
| Seed | 71 |
| Output root | `outputs/canonical_final300_cohere_contract_matched_live_20260523T181948Z` |
| Log | `cohere_live_validation_20260523T181948Z.log` |
| tmux session | Not found (process already exited) |
| PID | None (process exited) |
| Target records | 1200 (300 examples × 4 methods) |
| per_example_records lines | **1200 (complete)** |
| attempted | 300 |
| scored | 300 |
| Last method at completion | `external_tale_prompt_budgeting` |
| Completion time (UTC) | 2026-05-23T20:21:36Z |
| Log size | 31K |

### Progress at Completion

All four methods completed 300 examples each (1200 records total):

- `direct_reserve_semantic_frontier_v2` — 300/300 ✓
- `external_l1_max` — 300/300 ✓
- `external_s1_budget_forcing` — 300/300 ✓
- `external_tale_prompt_budgeting` — 300/300 ✓

### Errors

| Type | Count | Detail |
|---|---|---|
| HTTP 502 transient | 1 | `api-retry attempt=1/5 wait_seconds=1.047 reason=http_502` — recovered automatically |

- No fatal errors
- No rate-limit/quota errors
- No 429/401/403/500 errors
- No recovery passes needed
- Completion summary CSVs present

### Health Classification

**`healthy_completed`** — All 1200 records written, log ends cleanly at `attempted=300 scored=300` for all methods, single transient 502 handled by retry mechanism. Ready for integrity check and replay analysis.

---

## Job 2 — Cerebras GSM8K Frozen Agreement-Only Validation

**Status: `possibly_stalled`**

| Field | Value |
|---|---|
| Provider | cerebras |
| Model | llama3.1-8b |
| Dataset | openai/gsm8k |
| Seed | 71 |
| Output root | `outputs/cerebras_frozen_agreement_only_2of3_validation_20260523` |
| Log | `live_validation_20260523T144414Z.log` |
| tmux session | `55` (most likely; process parent bash in session created 2026-05-23) |
| PID | 2195513 (parent: 2195504, elapsed: 07:11:13, stat: Sl+) |
| Target records | 1200 (300 examples × 4 methods) |
| per_example_records lines | **164 / 1200** |
| attempted_so_far | 164 |
| scored_so_far | 163 |
| failed_so_far | 1 |
| Current method | `direct_reserve_semantic_frontier_v2` (method 1 of 4) |
| Last completed example | `openai_gsm8k_163` at 2026-05-23T21:02:53Z |
| Stuck on | `openai_gsm8k_164` — started at 21:02:53Z, no output since |
| Time since last log update | ~52 minutes (as of check at 21:56Z) |
| Typical per-example latency | 60–122 seconds |
| Log size | 31K |

### Progress at Check Time

Only the first method (`direct_reserve_semantic_frontier_v2`) is in progress:

- `direct_reserve_semantic_frontier_v2` — 164/300 (163 scored, 1 failed)
- `external_l1_max` — 0/300 (not started)
- `external_s1_budget_forcing` — 0/300 (not started)
- `external_tale_prompt_budgeting` — 0/300 (not started)

Total records: 164/1200 (13.7%)

### Errors

| Type | Count | Example | Detail |
|---|---|---|---|
| Cerebras 429 `queue_exceeded` | 1 | `openai_gsm8k_20` | At 15:09:50Z; 127s wait before failure; written to failures.jsonl; no retry after max attempts |

- 1 early 429 failure recorded in `failures.jsonl` (example 20)
- No subsequent 429 or rate-limit errors logged
- No fatal Python exceptions
- No timeout/500/503 errors logged

### Stall Analysis

| Signal | Observation |
|---|---|
| Process in ps? | YES — PID 2195513, stat=Sl+ (sleeping, foreground) |
| Log updating? | NO — 52 minutes since last update |
| Heartbeat updating? | NO — last event was `example_start openai_gsm8k_164` at 21:02:53Z |
| per_example updating? | NO — last update at 21:02:53Z |
| CPU usage | 0.0% (sustained, for 7h+ elapsed process) |
| Progress? | NONE — stuck between `example_start` and `example_end` for openai_gsm8k_164 |

**Stall diagnosis:** Process is alive (stat=Sl+, foreground) but 0% CPU for 52+ minutes while expected latency is 60–122s per example. The most probable cause is a **silent network hang** on the Cerebras API call for `openai_gsm8k_164` with no server response and no timeout mechanism firing. A secondary possibility is an extended rate-limit backoff not yet written to the log (but max retry delay is 20s, so 52 min is unexplainable by the retry config alone).

### Health Classification

**`possibly_stalled`** — Process alive, 0% CPU, no log output for 52 minutes while stuck on method 1 example 164. May recover spontaneously if the network call eventually returns. May be permanently hung if no server response ever arrives.

---

## Summary Table

| Job | Provider | Status | Progress | Fatal Errors | Rate Limits | Action Needed |
|---|---|---|---|---|---|---|
| Contract-matched Cohere Final-300 | cohere | `healthy_completed` | 1200/1200 (100%) | None | 1 transient 502 (recovered) | Integrity check + replay when ready |
| Cerebras GSM8K | cerebras | `possibly_stalled` | 164/1200 (13.7%) | None | 1 early 429 (failed example 20) | Monitor; check tmux `55` if no recovery in 30-60 min |

---

## Recommended Next Actions

### Cohere Canonical (completed)

1. Verify artifact integrity: check all 1200 per_example_records match expected canonical example IDs.
2. Run replay analysis when ready — no job action needed, artifact is complete.
3. Cross-check contract-matching: verify example IDs match `canonical_final300_exact_cases.jsonl` and `canonical_final300_allowed_ids.jsonl`.

### Cerebras (possibly stalled)

1. **Monitor** — check if log/heartbeat/per_example update in the next 30–60 minutes.
2. If no progress after 60 more minutes: user should inspect tmux session `55` to confirm whether the process is alive and what state it's in.
3. **Do not kill, restart, or interrupt** without user authorization and without first checking tmux `55`.
4. If the stall is confirmed permanent, the job would need to be restarted from checkpoint (163 scored examples on method 1). The recovery mechanism (`--max-recovery-passes 2`) should be able to re-run failed/missing examples on a restart.
5. The 1 failed example (openai_gsm8k_20, 429 queue_exceeded) is written in failures.jsonl and will need a recovery pass regardless.

---

## Logs to Monitor

| Log | Priority |
|---|---|
| `outputs/cerebras_frozen_agreement_only_2of3_validation_20260523/live_validation_20260523T144414Z.log` | HIGH — watch for resumption or further errors |
| `outputs/cerebras_frozen_agreement_only_2of3_validation_20260523/cohere_real_model_cost_normalized_validation_20260523T144414Z/progress_heartbeat.jsonl` | HIGH — watch for `example_end` for openai_gsm8k_164 |
| `outputs/canonical_final300_cohere_contract_matched_live_20260523T181948Z/cohere_live_validation_20260523T181948Z.log` | LOW — job complete, no action needed |

---

## Constraints Confirmed

- No jobs were touched, killed, restarted, interrupted, or attached to.
- No API calls were made.
- No frozen policy logic was modified.
- No replay was run.
- No existing artifacts were overwritten.
- This report is read-only status/health checking only.
