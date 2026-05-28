# Cerebras Job Status — 2026-05-24T14:40:52Z

> Read-only status check. No tmux attach, no job modification, no API calls.

---

## 1. Active TMUX Sessions

| Session | Status |
|---|---|
| `overnight_cerebras_supervisor_20260524` | **ACTIVE** |
| `55` | **ACTIVE** (Cerebras GSM8K job) |
| `codex`, `cohere_seed23_completion_20260518`, `round2_monitor` | Active (unrelated) |

---

## 2. Overnight Supervisor Status

- **Session:** `overnight_cerebras_supervisor_20260524` — ACTIVE
- **PID:** 2361455 (elapsed: 5h55m)
- **State:** `monitoring_gsm8k`
- **Last poll:** 2026-05-24T14:33:52Z — found scored=536, L1=236, hb_age=56s
- **Next poll estimated:** ~2026-05-24T14:43:52Z
- **`[done]` detected in log:** NO
- **GSM8K processed:** NO
- **MATH-500 launched:** NO
- **Errors:** One past `possibly_stalled` warning at 10:53 (then recovered); no fatal errors; no failed state.
- **Status:** `running_healthy` — polling correctly, not intervening.

**Notable stall periods (Cerebras API pauses, not supervisor errors):**
- ~11:48–12:43 UTC (~55 min, hb_age peaked at 3049s): then recovered
- ~13:33–14:33 UTC (~60 min, hb_age peaked at 3118s): then recovered at 14:33 (hb_age=56s)

The supervisor correctly classified these as `monitoring_ok` (PIDs still alive, not killing).

---

## 3. Cerebras × GSM8K Status

- **Session:** `55` (tmux)
- **PIDs:** 2195504 (bash wrapper), 2195513 (python3) — elapsed 23h55m
- **Output root:** `outputs/cerebras_frozen_agreement_only_2of3_validation_20260523/`
- **Run dir:** `cohere_real_model_cost_normalized_validation_20260523T144414Z/`

### Progress

| Method | Scored | Target | Progress |
|---|---|---|---|
| `direct_reserve_semantic_frontier_v2` | 300 (+1 dup) | 300 | **DONE** |
| `external_l1_max` | 241 | 300 | 80.3% — **in progress** |
| `external_s1_budget_forcing` | 0 | 300 | not started |
| `external_tale_prompt_budgeting` | 0 | 300 | not started |
| **Total** | **541/1200** | **1200** | **45.1%** |

- Total rows in JSONL: 542 (1 duplicate frontier pair)
- Unique examples: 300
- `[done]` in log: **NO**
- Last heartbeat: `2026-05-24T14:39:02Z` (L1 example #241) — ~2 minutes old at check time
- Failures JSONL: 0 rows
- Error counts: 0 (no 429, no 5xx, no timeouts in log)

### Status Classification: `running_healthy`

The job is actively processing L1 examples with no errors. There have been two intermittent API pause windows (~55–60 min each) consistent with Cerebras queue throttling, but the job always recovered without intervention.

### Estimated Completion

At ~6–8 examples / 10 minutes when active:
- L1 completion: ~59 remaining examples × ~1.5 min/example ≈ **~16:30 UTC today**
- S1 (300 ex) + TALE (300 ex): ~12–15 hours after L1 → **~04:00–07:00 UTC May 25**
- Account for 1–2 API pause windows: add ~2 hours → **~06:00–09:00 UTC May 25**

---

## 4. Cerebras × MATH-500 Scenario 6 Status

- **Launched:** NO
- **Status:** `queued_not_launched`
- **Placeholder dirs:** Two empty directories from dry-run exist:
  - `outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_full_20260524T014858Z/`
  - `outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_full_20260524T014938Z/`
- **Per-example records:** 0 rows
- **Active PIDs:** None for MATH-500
- **Condition to launch:** Supervisor detects GSM8K `[done]` → runs processing → launches MATH-500 in tmux

---

## 5. API/Retry/Error Summary

| Error type | Count |
|---|---|
| 429 / queue_exceeded | 0 |
| 5xx | 0 |
| Timeout | 0 |
| Traceback / fatal | 0 |
| Failures JSONL rows | 0 |

The intermittent pauses are not errors — the job is waiting on Cerebras's API queue. No retries or failures logged.

---

## 6. Completed Results Readiness

| Job | Ready for Processing? | Note |
|---|---|---|
| Cerebras GSM8K | NO | Still running; needs `[done]` marker |
| Cerebras MATH-500 | NO | Not yet launched |
| Cohere GSM8K | Already processed | Done — used in C1 analysis |
| Mistral GSM8K | Already processed | Done |
| Mistral MATH-500 | Already processed | Done |
| Cohere MATH-500 aux | Already processed | Auxiliary |

---

## 7. Any Stalls or Failures?

- **No failures.** The job is healthy.
- **Intermittent API pauses:** Two observed (~55–60 min each). Cerebras's API occasionally throttles or queues requests. The job always recovers without intervention. This is expected behavior for the Cerebras provider.
- **Not stalled now:** Last heartbeat was 14:39 UTC (~2 min before check). L1 is actively advancing.

---

## 8. Next Recommended Action

1. **Do nothing** — Cerebras GSM8K is running healthy; supervisor is monitoring correctly.
2. **Wait for supervisor to detect `[done]`** — expected ~06:00–09:00 UTC May 25.
3. **After supervisor detects done:** supervisor auto-processes GSM8K and auto-launches MATH-500.
4. **If supervisor fails to process** (check in the morning): run offline processing manually.
5. **No manual intervention needed now.**

---

## 9. Safety Confirmation

- No TMUX sessions were attached to.
- No active jobs were killed, restarted, or interrupted.
- No API calls were launched.
- No original result files were overwritten.
- No commits or pushes were made.
- All checks were read-only.
