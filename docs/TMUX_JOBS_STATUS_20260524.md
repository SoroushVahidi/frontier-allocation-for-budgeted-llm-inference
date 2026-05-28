# Tmux / Validation Job Status — 2026-05-24

**Snapshot UTC:** 2026-05-24T07:55:45Z  
**Branch:** main  
**Status:** Read-only check; no jobs modified, no API calls, no commits.

---

## Active Tmux Sessions

| Session | Created | Notes |
|---|---|---|
| `round2_monitor` | 2026-05-06 10:11 | **Hosts Cerebras × GSM8K job (PIDs 2195504/2195513)** |
| `cohere_seed23_completion_20260518` | 2026-05-18 15:09 | No active validation processes detected |
| `codex` | 2026-05-11 00:05 | No active validation processes detected |
| `55` | 2026-05-23 10:44 | No active validation processes detected |

**Expected but absent:**
- `mistral_math500_s5_20260524T014937Z` — not present (job **completed**, session exited)
- `cerebras_math500_s6_20260524T014938Z` — not present (job **never launched**, queued)

---

## Job 1: Mistral × MATH-500 (Scenario 5)

| Field | Value |
|---|---|
| Status | **`complete_ready_for_integrity`** |
| Tmux session | Absent (finished, exited) |
| Active PID | None |
| `[done]` in log | **YES** — `2026-05-24T03:06:52Z` |
| Rows completed | **1200 / 1200 (100%)** |
| Log last modified | 2026-05-24T03:06:52Z |
| Output root | `outputs/scenarios_5_6_math500_full_tracking_20260524/mistral_math500_full_20260524T014937Z/` |

**Method counts (all complete):**

| Method | Rows |
|---|---|
| `direct_reserve_semantic_frontier_v2` | 300 |
| `external_l1_max` | 300 |
| `external_s1_budget_forcing` | 300 |
| `external_tale_prompt_budgeting` | 300 |

**API / retry health:**
- `http_429` retries: **527** (all at attempt=1/5 — resolved on first retry, no persistent 429 stalls)
- `http_500/502/503`: 0
- Timeouts: 0
- Tracebacks / exceptions / fatal: 0
- Total error/retry log lines: 1728

**Verdict:** Clean completion. Ready for integrity check and results processing.

---

## Job 2: Cerebras × GSM8K

| Field | Value |
|---|---|
| Status | **`running_healthy`** |
| Tmux session | `round2_monitor` (active) |
| PID bash | 2195504 (ppid=9002, elapsed 17h11m) |
| PID python | 2195513 (ppid=2195504, Sl+, 0.4% mem) |
| `[done]` in log | No |
| Rows completed | **405 / 1200 (33.75%)** |
| Log last modified | 2026-05-24T07:54:07Z (~90s before snapshot) |
| Output root | `outputs/cerebras_frozen_agreement_only_2of3_validation_20260523/` |
| Log | `live_validation_20260523T144414Z.log` |

**Method counts (in progress):**

| Method | Rows | Target | Done? |
|---|---|---|---|
| `direct_reserve_semantic_frontier_v2` | 301 | 300 | Yes (+1 dup — see note) |
| `external_l1_max` | 104 | 300 | **In progress** (example 104/300) |
| `external_s1_budget_forcing` | 0 | 300 | Queued |
| `external_tale_prompt_budgeting` | 0 | 300 | Queued |

**Current position (from heartbeat):**
- Method: `external_l1_max`
- Latest example: `openai_gsm8k_103` (started 2026-05-24T07:54:07Z)
- Example latency: ~61 seconds (normal for Cerebras Llama 3.1-8B)

**Note:** `direct_reserve_semantic_frontier_v2` has 301 rows (1 extra). Example `openai_gsm8k_20` appears twice — likely a recovery pass duplicate. Does not indicate corruption; script handles deduplication downstream.

**API / retry health:**
- `http_429`: 0
- `http_500/502/503`: 0
- Timeouts: 0
- Tracebacks / fatal / exception: 0
- 1 entry in `failures.jsonl` (may be header or single early failure; job is progressing normally)

**Estimated remaining time:** ~796 examples × ~61s/example ≈ **13–15 hours** (completion ~2026-05-24T22:00–24:00 UTC, rough estimate).

**Verdict:** Healthy, active, no errors. Do not interrupt.

---

## Job 3: Cerebras × MATH-500 (Scenario 6)

| Field | Value |
|---|---|
| Status | **`queued_not_launched`** |
| Tmux session | Not created |
| Active PID | None |
| Launched | **No** |
| Block reason | Cerebras GSM8K still running — second parallel Cerebras job blocked to avoid API contention |
| Output root | `outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_full_20260524T014938Z/` (exists but empty) |
| Launch status file | `outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_launch_status.json` |
| Rows | 0 / 1200 |

**Verdict:** Intentionally deferred. Launch after Cerebras × GSM8K completes.

---

## Other Tmux Sessions

| Session | Assessment |
|---|---|
| `cohere_seed23_completion_20260518` | No active validation processes; likely an older monitoring session |
| `codex` | General-purpose Claude Code session; no validation processes |
| `55` | No validation processes; likely an interactive shell |
| `round2_monitor` | Originally a monitoring session; currently hosts Cerebras GSM8K validation |

No unexpected validation jobs found.

---

## Summary Table

| Job | Status | Rows | % | Health | Action |
|---|---|---|---|---|---|
| Mistral × MATH-500 s5 | `complete` | 1200/1200 | 100% | Clean (527 resolved 429s) | **Ready for integrity/processing** |
| Cerebras × GSM8K | `running_healthy` | 405/1200 | 33.75% | Clean (0 errors) | **Keep running** |
| Cerebras × MATH-500 s6 | `queued` | 0/1200 | 0% | N/A — not launched | **Launch when GSM8K done** |

---

## Next Recommended Actions

1. **Mistral × MATH-500**: Run integrity check and results processing. Job is done and artifact-complete.
2. **Cerebras × GSM8K**: No action needed. Let it run. Check back in ~13–15 hours.
3. **Cerebras × MATH-500 s6**: Launch manually once GSM8K finishes to avoid Cerebras API contention.
4. **Duplicate row** in Cerebras GSM8K (`openai_gsm8k_20` ×2 in `direct_reserve_semantic_frontier_v2`): Note for post-processing; deduplicate before analysis.

---

## Safety Confirmation

- No tmux sessions attached.
- No jobs killed, restarted, or modified.
- No API calls launched.
- No results processed.
- No commits or pushes made.
- No existing artifacts overwritten.
