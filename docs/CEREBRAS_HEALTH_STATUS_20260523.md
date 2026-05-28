# Cerebras Validation Job Health Status — 2026-05-23

**Check timestamp:** 2026-05-23T22:56:50Z  
**Checked by:** Claude Code (read-only; no API calls; job not touched)

---

## Status: `healthy_slow_running`

| Field | Value |
|---|---|
| PID | 2195513 (alive, `Sl+` state) |
| Elapsed time | ~8h 11m |
| Status | **HEALTHY — progressing normally** |
| Current method | `direct_reserve_semantic_frontier_v2` (method 1 of 4) |
| Current example | `openai_gsm8k_206` |
| Attempted so far | 207 |
| Scored so far | 205 |
| Records written | 206 / 1200 expected (17.2%) |
| Methods completed | none |
| Methods started | `direct_reserve_semantic_frontier_v2` only |

---

## Progress Detail

| Metric | Value |
|---|---|
| Last log update | 2026-05-23T22:53:47Z |
| Seconds since last update | ~183s at time of check |
| Avg latency (last 20 examples) | 73.2s |
| Last example latency | 61.2s |
| Max latency (last 20) | 122.1s (one double-attempt) |
| No-error streak | All 206 records: `status=scored` |
| Rate limits / 429s | **None** |
| Timeouts / quota errors | **None** |
| Fatal errors / tracebacks | **None** |
| Failure count | 0 |

---

## Time Estimates

| Segment | Estimate |
|---|---|
| Method 1 remaining (95 examples × 73s) | ~116 min (~2 hours) |
| Methods 2–4 (external: L1/S1/TALE, 900 examples) | Unknown — likely faster than frontier (~10–30s/example) |
| Total estimated completion | ~5–8 hours from now |

---

## Interpretation

The job is progressing steadily and correctly. The 183-second gap since the last log update is entirely within the expected per-example latency range (~61–122s). Example `openai_gsm8k_206` was started at 22:53:47Z and should complete shortly.

The method 1 latency of ~73s/example reflects the tree-search nature of `direct_reserve_semantic_frontier_v2` under Cerebras's llama3.1-8b model. External methods (L1, S1, TALE) typically run faster because they do not require multi-step tree exploration.

**No intervention is needed.** The job is safe to leave running.

---

## Files to Monitor

| File | What to watch |
|---|---|
| `outputs/cerebras_frozen_agreement_only_2of3_validation_20260523/live_validation_20260523T144414Z.log` | Progress lines, error lines, `[done]` marker |
| `.../cohere_real_model_cost_normalized_validation_20260523T144414Z/per_example_records.jsonl` | Line count approaching 1200 |
| `.../progress_heartbeat.jsonl` | `example_end` events, latency trends, `scored_so_far` |

**Warning signs** (none currently present):
- Log not updated for > 10 min AND process still alive → possible stall
- `429` / `quota` / `rate` lines → rate limiting
- `traceback` / `fatal` lines → crash
- `scored_so_far` not increasing over 15+ min → silent hang

---

## When Job Completes

When the process exits and `[done]` appears in the log, run:

1. Integrity check: verify 1200 records (300 × 4 methods), 0 failures, all `status=scored`.
2. Canonical ID check: verify all 300 example IDs match canonical Final-300 set (if applicable).
3. Compute per-method accuracies and accuracy spread.
4. Run `regime_selector_accuracy_spread_rule` 5-fold CV to determine: near-peer vs dominant-source.
5. Compare to Cohere (pooled-4 = 85.67%) and Mistral (S1 = 89.67%).

---

## Constraints Confirmed

- Job not touched, killed, interrupted, restarted, or attached to.
- No API calls made.
- No policy logic modified.
- No artifacts overwritten.
- Read-only status check only.
