# Completed TMUX Jobs Audit — 2026-05-24T13:17:45Z

> **Read-only audit only.** No jobs were modified, attached-to, killed, or relaunched. No API calls made. No result processing run. No commits or pushes.

---

## 1. Executive Summary

As of 2026-05-24T13:17 UTC:

- **5 major jobs are complete and fully processed** — no further action needed for them.
- **1 job (Cerebras × GSM8K) is still actively running** — ~43% complete; protected, not touched.
- **1 job (Cerebras × MATH-500 Scenario 6) is queued** — supervisor will auto-launch after GSM8K.
- **0 completed jobs need immediate processing.**
- **1 medium-priority decision pending:** whether to launch a canonical full Cohere MATH-500 run.
- **Current canonical learned router: 4-dataset version** (cohere_gsm8k + mistral_gsm8k + mistral_math500 + cohere_math500_aux).

---

## 2. Active Jobs (Protected — Ignored for This Audit)

| Job | Status | PIDs | Progress |
|---|---|---|---|
| Cerebras × GSM8K | `active_running_ignore_for_now` | 2195504, 2195513 | 519/1200 rows (~43%) |
| Overnight Supervisor | running, monitoring | 2361453, 2361455 | polling every 10min |

---

## 3. Completed Jobs — Already Processed

### A. Cohere × GSM8K Canonical (Scenario 2)

- **Run root:** `outputs/canonical_final300_cohere_contract_matched_live_20260523T181948Z`
- **Processing root:** `outputs/cohere_canonical_final300_frozen_agreement_live_result_20260523`
- **Report:** `docs/COHERE_CANONICAL_FINAL300_FROZEN_AGREEMENT_LIVE_RESULT_20260523.md`
- **Rows:** 1200/1200 — integrity_pass=true, all 4 methods, 300 unique examples, 0 duplicates
- `[done]` in log: absent (bash wrapper did not emit it), but integrity confirms completion
- Selector replay: YES (`frozen_replay_summary.csv`)
- Failure taxonomy: YES (`failure_taxonomy_summary.json`)
- Learned router: YES — used as `cohere_gsm8k` source in v1/v3/v4 router
- **Next action: none**

### B. Mistral × GSM8K Repair + Merge/Replay (Scenario 3)

- **Repair root:** `outputs/repair_incomplete_cohere_mistral_runs_20260524/mistral_missing_methods_repair_20260524T003751Z`
  - 901 rows (1 duplicate in l1_max — resolved in merge step)
  - PID 2281714 exited; log ends at scored=300 for last method
- **Merged root:** `outputs/merged_repaired_cohere_mistral_selector_replay_20260524`
- **Report:** `docs/MERGED_REPAIRED_COHERE_MISTRAL_SELECTOR_REPLAY_20260524.md`
- **Final merged rows:** 1200/1200
- Selector replay: YES
- Failure taxonomy: YES
- Learned router: YES — used as `mistral_gsm8k` source in v1/v3/v4 router
- **Next action: none**

### C. Cohere × GSM8K Repair (partial, Scenario 2)

- **Repair root:** `outputs/repair_incomplete_cohere_mistral_runs_20260524/cohere_missing_methods_repair_20260524T003751Z`
- **Rows:** 141/141 (3 missing methods × 47 examples — correct)
- Incorporated into cohere_canonical processing
- **Next action: none**

### D. Mistral × MATH-500 (Scenario 5)

- **Run root:** `outputs/scenarios_5_6_math500_full_tracking_20260524/mistral_math500_full_20260524T014937Z`
- **Processing root:** `outputs/mistral_math500_scenario5_processing_20260524`
- **Report:** `docs/MISTRAL_MATH500_SCENARIO5_PROCESSING_20260524.md`
- **Rows:** 1200/1200 — `[done]` at 2026-05-24T03:06:52Z
- Selector replay: YES (`mistral_math500_selector_replay_summary.csv`)
- Failure taxonomy: YES (`mistral_math500_failure_taxonomy_summary.csv`)
- Cross-scenario interpretation: YES (`mistral_math500_cross_scenario_interpretation.md`)
- Learned router: YES — 3-dataset router built (`learned_router_three_scenarios/`)
- **Next action: none**

### E. Cohere × MATH-500 Auxiliary MLJ Reprocess

- **Source runs merged:** `cohere_real_model_cost_normalized_validation_mlj_math500_b6_20260520T220928Z` + `_recovery_failed31_20260521T124545Z`
- **Processing root:** `outputs/cohere_math500_auxiliary_mlj_reprocess_20260524`
- **Report:** `docs/COHERE_MATH500_AUXILIARY_MLJ_REPROCESS_20260524.md`
- **Complete examples:** 1200 (inferred from `cohere_math500_auxiliary_complete_4method_records.jsonl`)
- Selector replay: YES (`cohere_math500_auxiliary_selector_replay_summary.csv`)
- Failure taxonomy: YES
- Cross-scenario interpretation: YES
- Learned router: YES — 4-dataset router built (`learned_router_four_datasets/`) — **current canonical**
- Canonical launch decision: PENDING (see `canonical_cohere_math500_launch_decision.md`)
- **Next action: decide whether to launch full canonical Cohere MATH-500 run**

---

## 4. Completed Jobs Needing Processing

**None.** All completed, exited jobs have been processed.

---

## 5. Exited Incomplete / Partial Jobs

None detected. The two repair jobs (Mistral, Cohere) exited without `[done]` markers but are confirmed complete by row counts and method counts, and were subsequently merged.

---

## 6. Queued / Not Launched Jobs

| Job | Queue Reason |
|---|---|
| Cerebras × MATH-500 Scenario 6 | Supervisor holding launch until Cerebras GSM8K finishes |

---

## 7. Scenario Matrix Impact

| Scenario | Provider | Dataset | Status |
|---|---|---|---|
| Scenario 2 | Cohere | GSM8K | Complete + Processed |
| Scenario 3 | Mistral | GSM8K | Complete + Processed |
| Scenario 4 | Cerebras | GSM8K | **Running (~43%)** |
| Scenario 5 | Mistral | MATH-500 | Complete + Processed |
| Scenario 5 (aux) | Cohere | MATH-500 (auxiliary MLJ) | Complete + Processed (canonical not launched) |
| Scenario 6 | Cerebras | MATH-500 | **Queued — supervisor will launch** |

---

## 8. Learned Router Dataset Impact

| Router Version | Datasets | Location | Status |
|---|---|---|---|
| v1 (2-dataset) | cohere_gsm8k, mistral_gsm8k | `outputs/learned_fixed_pool_router_20260524/` | **Superseded** |
| v2 (3-dataset) | + mistral_math500 | `outputs/mistral_math500_scenario5_processing_20260524/learned_router_three_scenarios/` | **Superseded** |
| v3 (4-dataset) | + cohere_math500_aux | `outputs/cohere_math500_auxiliary_mlj_reprocess_20260524/learned_router_four_datasets/` | **Current canonical** |
| v4 (5-dataset) | + cerebras_gsm8k | TBD — will be built when cerebras_gsm8k processing runs | **Pending** |

**Use the v3 4-dataset router for all current comparisons.** Do not use the stale top-level v1 router.

---

## 9. Inconsistencies Found

| Issue | Severity | Status |
|---|---|---|
| Missing `[done]` markers in cohere_canonical and repair logs | Low | Confirmed complete via integrity; no action needed |
| Mistral repair extra row (l1_max=301) | Medium | Already resolved in merge dedup step |
| Stale top-level router (2-dataset only) | Medium | Superseded; use 4-dataset version |
| Canonical Cohere MATH-500 decision pending | Low | Known; awaiting explicit decision |
| Cerebras MATH-500 dir pre-created with 0 rows | Low | Expected supervisor behavior |

---

## 10. Recommended Next Actions

**Priority 1 — Nothing blocking (all done):**
All completed jobs are fully processed. No emergency processing needed.

**Priority 2 — Decide canonical Cohere MATH-500 launch:**
The auxiliary MLJ run is processed. A full canonical Cohere MATH-500 run (matching Mistral Scenario 5 setup) may be warranted. Review `outputs/cohere_math500_auxiliary_mlj_reprocess_20260524/canonical_cohere_math500_launch_decision.md` and decide.

**Priority 3 — Wait for Cerebras GSM8K:**
Once the overnight supervisor detects completion, it will auto-process GSM8K and launch Cerebras MATH-500 Scenario 6. After GSM8K processing, rebuild the learned router to 5-dataset.

**Priority 4 — After Cerebras MATH-500 Scenario 6 completes:**
Process Scenario 6, run selector replay, build the 6-dataset learned router.

---

## 11. Output Files Created

All in `outputs/completed_tmux_jobs_audit_20260524/`:
- `raw_tmux_process_snapshot_20260524T131745Z.txt`
- `all_candidate_run_files.txt` (746 run artifact paths)
- `completion_mentions.txt` (37304 matches)
- `completed_tmux_job_inventory.csv`
- `completed_tmux_job_inventory.json`
- `completed_jobs_inconsistencies.csv`
- `completed_jobs_inconsistencies.md`
- `completed_jobs_readiness_table.csv`
- `manifest.json`

Human-readable report: `docs/COMPLETED_TMUX_JOBS_AUDIT_20260524.md`

---

## 12. Safety Confirmation

- No tmux sessions attached to.
- No active jobs killed, restarted, or modified.
- No API calls launched.
- No result processing executed.
- No commits or pushes made.
- All actions read-only.
