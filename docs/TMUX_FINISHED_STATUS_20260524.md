# TMUX Job Status Report — 2026-05-24T13:13:10Z

> **Read-only status check.** No jobs were modified, attached-to, killed, or relaunched. No API calls made. No commits or pushes.

---

## 1. Active TMUX Sessions

| Session | Created | Classification | Active PIDs |
|---|---|---|---|
| `overnight_cerebras_supervisor_20260524` | 2026-05-24 04:43 UTC | **active_supervisor** | 2361453, 2361455 |
| `55` | 2026-05-23 10:44 UTC | idle_shell | — |
| `codex` | 2026-05-11 00:05 UTC | idle_shell | — |
| `cohere_seed23_completion_20260518` | 2026-05-18 15:09 UTC | idle_shell | — |
| `round2_monitor` | 2026-05-06 10:11 UTC | idle_shell | — |

**Active API jobs in any session: 1**
- Cerebras × GSM8K (PIDs 2195504, 2195513) — attached to session `overnight_cerebras_supervisor_20260524` indirectly (supervisor is watching it)

---

## 2. Overnight Supervisor Status

**Status: RUNNING — monitoring_gsm8k**

- PID: 2361455 (supervisor python), 2361453 (bash wrapper)
- Elapsed time: 04:28:39
- Script: `scripts/overnight_cerebras_supervisor_20260524.py`
- Log: `outputs/overnight_cerebras_supervisor_20260524/supervisor.log`
- Last poll: `2026-05-24T13:03:52Z`
- Last event: `monitoring_ok`
- Last scored rows seen by supervisor: 511 (external_l1_max at 211/300)

**Supervisor did NOT detect GSM8K completion** — still polling every 600s.

**Supervisor has NOT processed GSM8K** — waiting for completion first.

**Supervisor has NOT launched Cerebras × MATH-500 Scenario 6** — blocked by active GSM8K job.

**Errors/tracebacks: NONE**

**Stall events: 1** (at 10:53:51 UTC, heartbeat_age=3641s; cleared at 11:03:51 when GSM8K resumed)

**Supervisor health: healthy, no errors.**

---

## 3. Cerebras × GSM8K Status

**Status: `running_healthy`**

- Output root: `outputs/cerebras_frozen_agreement_only_2of3_validation_20260523`
- Active PIDs: 2195504 (bash), 2195513 (python3)
- Elapsed time: 22h 28m (started ~2026-05-23T14:44 UTC)
- `[done]` in log: **NO**

### Progress
| Method | Scored | Target | Complete? |
|---|---|---|---|
| direct_reserve_semantic_frontier_v2 | **301** | 300 | YES (1 extra row — note below) |
| external_l1_max | **218** | 300 | In progress |
| external_s1_budget_forcing | 0 | 300 | Not started |
| external_tale_prompt_budgeting | 0 | 300 | Not started |
| **TOTAL** | **519** | **1200** | **43%** |

- Latest heartbeat: `2026-05-24T13:11:33Z` (age ~97s at check time — fresh)
- Latest example scored: `openai_gsm8k_217` (external_l1_max, ex_idx 217)
- Failure rows: 1
- Duplicate note: `direct_reserve_semantic_frontier_v2` has 301 rows (1 over expected 300); inspect during processing.

### Throughput Estimate
- Recent rate: ~1 example/min (60s latency per Cerebras API call observed)
- Remaining: 82 (l1_max) + 300 (s1_budget_forcing) + 300 (tale_prompt_budgeting) = **682 examples**
- Estimated remaining time: **~11–14 hours**
- Estimated completion: **~2026-05-25T01:00–03:00 UTC**

### Processing
- Processing output dir `outputs/cerebras_gsm8k_completed_processing_20260524/`: **DOES NOT EXIST**
- Processing has **not** been done.

---

## 4. Cerebras × MATH-500 Scenario 6 Status

**Status: `queued_not_launched`**

- Launched: **NO**
- Blocked: **YES** — supervisor is holding launch until GSM8K finishes, to avoid Cerebras API account-level contention.
- Queued tmux session name: `cerebras_math500_s6_20260524T014938Z` (not yet created)
- Output root exists: YES (`outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_full_20260524T014938Z/`)
- Log: does not exist yet
- Per-example rows: 0 / 1200
- Launch status file: `outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_launch_status.json`

The supervisor will automatically launch Scenario 6 once GSM8K completes and is successfully processed.

---

## 5. Other Notable Job: Mistral × MATH-500

**Status: `complete_ready_for_processing`**

- Output root: `outputs/scenarios_5_6_math500_full_tracking_20260524/mistral_math500_full_20260524T014937Z`
- Per-example rows: **1200 / 1200**
- `[done]` in log: **YES** — completed at `2026-05-24T03:06:52Z`
- Active processes: NONE
- Processing status: **Unknown** — not checked in this task (no processing output dir found in this scan)

---

## 6. Jobs Finished

| Job | Finished At | Rows |
|---|---|---|
| Mistral × MATH-500 | 2026-05-24T03:06:52Z | 1200/1200 |

---

## 7. Jobs Still Running

| Job | Progress | ETA |
|---|---|---|
| Cerebras × GSM8K | 519/1200 rows (43%) | ~2026-05-25T01:00–03:00 UTC |
| Overnight Supervisor | polling every 10min | Until GSM8K finishes |

---

## 8. Jobs Ready for Processing

| Job | Status |
|---|---|
| Mistral × MATH-500 | COMPLETE — check if processing was done; if not, process it |
| Cerebras × GSM8K | NOT READY — still running (~43% done) |

---

## 9. Blocked / Stalled Jobs

| Job | Block Reason |
|---|---|
| Cerebras × MATH-500 Scenario 6 | Blocked: waiting for GSM8K to finish (supervisor-managed queue) |

No jobs are detected as failed or permanently stalled. The GSM8K job had a transient stall (~51 min, 10:03–10:53 UTC) where heartbeat aged to 3641s, but it recovered and has been making steady progress since.

---

## 10. Exact Next Recommended Action

> **Current time: 2026-05-24T13:13 UTC**

1. **Check Mistral × MATH-500 processing**: Verify whether `outputs/scenarios_5_6_math500_full_tracking_20260524/mistral_math500_full_20260524T014937Z` has been processed. If not, run processing offline now (it completed 10+ hours ago).

2. **Keep waiting on Cerebras × GSM8K**: The job is healthy and making progress (~43% complete). Estimated to finish ~01:00–03:00 UTC on May 25. The supervisor will auto-detect completion and launch Scenario 6.

3. **No manual action needed for Scenario 6**: The supervisor will handle the launch automatically once GSM8K completes.

4. **After GSM8K completes**: The supervisor will process GSM8K and launch Scenario 6. You will need to monitor Scenario 6 once it starts.

---

## 11. Output Files Created

All in `outputs/tmux_finished_status_20260524/`:
- `raw_tmux_process_snapshot_20260524T131310Z.txt`
- `status_20260524T131310Z.json`
- `active_tmux_sessions_20260524T131310Z.csv`
- `job_readiness_table_20260524T131310Z.csv`
- `cerebras_gsm8k_status_20260524T131310Z.json`
- `cerebras_math500_status_20260524T131310Z.json`
- `supervisor_status_20260524T131310Z.json`
- `manifest.json`

Human-readable report: `docs/TMUX_FINISHED_STATUS_20260524.md`

---

## 12. Safety Confirmation

- No tmux sessions were attached to.
- No jobs were killed, restarted, or modified.
- No API calls were made.
- No result processing was run.
- No commits or pushes were made.
- All actions were read-only.
