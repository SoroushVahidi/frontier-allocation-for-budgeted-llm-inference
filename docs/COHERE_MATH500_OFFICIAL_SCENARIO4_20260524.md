# Cohere × MATH-500 Official Scenario 4 — Launch Report

> Created: 2026-05-24T14:51:45Z | Offline + paid API launch. No Cerebras/Mistral jobs touched.

---

## 1. Executive Summary

Official Cohere × MATH-500 Scenario 4 (seed=71, 300 examples, 4 methods) has been **successfully launched** in tmux session `cohere_math500_s4_official_20260524T144902Z`. The job is running healthy with 9+ examples scored. Estimated completion: ~3–5 hours.

---

## 2. Did an Official Scenario 4 Artifact Already Exist?

**NO.** A thorough search confirmed:

| Artifact | Seed | N | Status |
|---|---|---|---|
| `cohere_real_model_cost_normalized_validation_mlj_math500_b6_20260520T220928Z` | 11 | 500 | Not official (wrong seed/size) |
| `cohere_math500_auxiliary_mlj_reprocess_20260524` | 11 | 488 | Auxiliary — not official |
| `canonical_real_model_validation_..._HuggingFaceH4_MATH-500` (×2) | 11/23 | 0 | Empty diagnostic sweeps |
| `cohere_real_model_cost_normalized_validation_dryrun_math500_b6` | 11 | 30 | Dry-run only |
| **New official run** `cohere_math500_full_20260524T144902Z` | **71** | **300** | **Launched ✓** |

---

## 3. Why Auxiliary Seed=11 Does Not Count as Official

- **Different seed:** Seed=11 produces a different random subset selection than seed=71
- **Different size:** 488 or 500 examples ≠ 300 canonical examples
- **Not the shared subset:** Official Scenario 4 must use exactly the same 300 examples as Mistral MATH-500 Scenario 5 (seed=71)
- **Method name aliases:** The MLJ run used `s1`/`tale` aliases, not canonical method names
- **No `[done]` in log:** The MLJ run had 15 permanent failures

---

## 4. API Key Status

`COHERE_API_KEY`: **PRESENT** — readiness check passed at launch.

---

## 5. Exact Cases Used

- **File:** `outputs/scenarios_5_6_math500_full_tracking_20260524/math500_shared_exact_cases.jsonl`
- **Cases:** 300 exactly (HuggingFaceH4_MATH-500_0 to _299)
- **Dataset:** `HuggingFaceH4/MATH-500`
- **Has gold answers:** YES
- **Shared with:** Mistral MATH-500 Scenario 5 (same 300 examples)
- **Seed embedded in allowed_ids:** 71

---

## 6. Allowed IDs Safety Check

- **File:** `outputs/scenarios_5_6_math500_full_tracking_20260524/math500_shared_allowed_ids.jsonl`
- **Total entries:** 1200 (300 × 4 methods)
- **Methods present:** `direct_reserve_semantic_frontier_v2`, `external_l1_max`, `external_s1_budget_forcing`, `external_tale_prompt_budgeting`
- **Allowlist bug:** NOT PRESENT — all 4 methods have explicit named entries. Prior bug occurred when methods were missing from allowed_ids; here all are present.
- **Seed:** 71

---

## 7. Expected Rows and Calls

| Item | Count |
|---|---|
| Expected rows | 1200 |
| Methods | 4 × 300 = 1200 |
| Estimated Cohere API calls | ~1200 logical (frontier may use multiple internal calls) |
| Retry upper bound | ~6000 |
| Estimated cost | ~$5–15 USD |

---

## 8. Dry-Run / Call Plan Result

**PASSED.** Dry-run confirmed:
- 4 method slices × 300 = 1200 planned cases
- All 4 methods with canonical names
- Seed=71, HuggingFaceH4/MATH-500, budget=6
- No method scheduling gap

---

## 9. Preflight Checks

| Check | Result |
|---|---|
| Repo health (`check_repo_health.py`) | PASS |
| Test suite (130 tests) | PASS (130 passed) |
| API key | PRESENT |
| Exact cases validated | 300 cases, all gold answers present |
| Allowed IDs validated | 1200 rows, all 4 methods |
| No existing official artifact | CONFIRMED |
| No active Cohere MATH-500 job | CONFIRMED |
| Cerebras jobs observed only | CONFIRMED |

---

## 10. Launch Details

| Parameter | Value |
|---|---|
| tmux session | `cohere_math500_s4_official_20260524T144902Z` |
| bash PID | 2399424 |
| python PID | 2399431 |
| Launch time | 2026-05-24T14:49:37Z |
| Log | `outputs/cohere_math500_official_scenario4_20260524/cohere_math500_full_20260524T144902Z.log` |
| Output root | `outputs/cohere_math500_official_scenario4_20260524/cohere_math500_full_20260524T144902Z/` |

---

## 11. Immediate Progress (at ~14:51 UTC)

- **Status:** `running_healthy`
- **Examples scored:** 9+ (frontier method, examples 0–8)
- **Method:** `direct_reserve_semantic_frontier_v2` (first method, correct)
- **Last heartbeat:** 2026-05-24T14:51:37Z (~8s old)
- **Auth errors:** None
- **Dataset errors:** None
- **Method scheduling errors:** None
- **http_500 retries:** 2 (both recovered on first retry — normal Cohere transient behavior)

---

## 12. Active Cerebras Jobs — UNTOUCHED

- **Cerebras GSM8K:** PIDs 2195504/2195513, session `55` — STILL RUNNING, NOT TOUCHED
- **Overnight supervisor:** PIDs 2361453/2361455, session `overnight_cerebras_supervisor_20260524` — STILL RUNNING, NOT TOUCHED

---

## 13. Failure Tracking / Processing Plan

See: `outputs/cohere_math500_official_scenario4_20260524/cohere_math500_official_failure_tracking_plan.md`

Processing steps after `[done]`:
1. Integrity check (1200 rows, 4 methods, 0 duplicates)
2. Method accuracy summary (frontier/L1/S1/TALE)
3. Selector replay (pooled4, beta-shrinkage, agreement-only, always-S1, C1d, oracle)
4. C1d / C1a comparison (within-scenario CV on official Scenario 4)
5. Learned router update (5-dataset)
6. Failure taxonomy (all-sources-wrong rate — expect ~55%)
7. Representative failure casebook
8. Comparison vs auxiliary seed=11 run
9. Update official 4-scenario matrix

---

## 14. Next Monitoring Command

```bash
# Quick progress check
tail -5 outputs/cohere_math500_official_scenario4_20260524/cohere_math500_full_20260524T144902Z.log

# Row count by method
python3 -c "
import json
from collections import Counter
path = 'outputs/cohere_math500_official_scenario4_20260524/cohere_math500_full_20260524T144902Z/cohere_real_model_cost_normalized_validation_20260524T144902Z/per_example_records.jsonl'
with open(path) as f:
    recs = [json.loads(l) for l in f if l.strip()]
mc = Counter(r['method'] for r in recs)
print(f'Total: {len(recs)}/1200')
for m,c in sorted(mc.items()): print(f'  {m}: {c}')
"
```

---

## 15. Safety Confirmation

- No TMUX sessions attached to.
- Active Cerebras/supervisor jobs observed only — not touched.
- Auxiliary seed=11 artifacts untouched and in their original directories.
- No commit or push made.
- Gold labels will only be used in offline post-processing, not in the live API calls.
