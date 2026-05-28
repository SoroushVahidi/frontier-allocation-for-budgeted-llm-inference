# Cohere MATH Training Auxiliary Corpus Generation — 2026-05-24/25

**Status:** RUNNING in detached TMUX

## 1. Executive Summary

Generating a Cohere×MATH-500 auxiliary labeled corpus for router-v2 improvement.
The XGB53 model (83.21% pooled CV) shows dataset-heldout weakness that new MATH training
data can address. Target: 200 non-official MATH-500 examples × 4 methods = 800 Cohere API calls.

| Parameter | Value |
|---|---|
| Provider | Cohere |
| Dataset | HuggingFaceH4/MATH-500 |
| Cases | 200 (all non-official) |
| Methods | 4 |
| Planned calls | 800 |
| Call cap | 2000 |
| Estimated runtime | 30–60 min |

## 2. Dataset/Source Decision

**Source:** `HuggingFaceH4/MATH-500` (test split, 500 total examples)

MATH-500 has no separate train split. Hendrycks MATH alternatives are subject-config-specific.
Since the runner supports `--exact-cases-jsonl` (bypasses dataset loading), we use exact cases
for precise overlap control.

**Strategy:**
- Load all 500 MATH-500 examples
- Exclude 300 official test examples (seed=71, used in Cohere Scenario 4 and Mistral Scenario 5)
- Remaining 200 non-official examples → new auxiliary corpus

## 3. Overlap Checks

| Category | Count |
|---|---|
| Total MATH-500 examples | 500 |
| Official test (seed=71, Cohere+Mistral) | 300 |
| **Non-official pool (new corpus)** | **200** |
| Also in previous auxiliary (seed=11) | 198 |
| Truly new (not in any prior run) | 2 |
| Official overlap in new corpus | **0** |

**Compliance:**
- ✓ No overlap with official Cohere MATH-500 Scenario 4 (seed=71)
- ✓ No overlap with official Mistral MATH-500 Scenario 5 (seed=71)
- 198 of 200 examples were in previous auxiliary seed=11 (unavoidable — MATH-500 only has 500 total)
- Reported and documented in `cohere_math_train_aux_overlap_report.md`

## 4. Call Plan and Cost Estimate

| Method | Calls |
|---|---|
| `direct_reserve_semantic_frontier_v2` | 200 |
| `external_l1_max` | 200 |
| `external_s1_budget_forcing` | 200 |
| `external_tale_prompt_budgeting` | 200 |
| **Total** | **800** |

- Budget per call: 6
- Within 2000-call cap: ✓ YES (800 ≤ 2000)
- No duplicate (example_id, method) pairs: ✓ verified
- Estimated cost: ~2/3 of a full Cohere MATH-500 scenario run
- Estimated runtime: **30–60 minutes**

## 5. Dry-Run / Preflight Result

| Check | Status |
|---|---|
| COHERE_API_KEY present | ✓ Yes |
| Exact-case validation (200 cases, 0 mismatches) | ✓ PASS |
| All 4 methods resolved | ✓ PASS |
| Official overlap = 0 | ✓ PASS |
| Planned calls ≤ 2000 | ✓ PASS (800) |
| Active Cohere conflicts | ✓ None |
| Dry-run API calls | ✓ 0 |
| **Overall decision** | **PASS** |

## 6. TMUX Launch Details

| Parameter | Value |
|---|---|
| Session name | `cohere_math_train_aux_20260525T001141Z` |
| Launch UTC | 2026-05-25T00:11:41Z |
| PID (bash) | 2517451 |
| PID (Python) | 2517453 |
| Log | `outputs/cohere_math_train_aux_generation_20260524/cohere_math_train_aux_full_20260525T001141Z.log` |
| Output root | `outputs/cohere_math_train_aux_generation_20260524/cohere_math_train_aux_full_20260525T001141Z/` |

## 7. Initial Progress

First lines from log:
```
Cohere readiness check passed: tiny authenticated request succeeded.
[progress] provider=cohere dataset=HuggingFaceH4/MATH-500 seed=20260524 budget=6 method=direct_reserve_semantic_frontier_v2 attempted=1 scored=1 status=scored recovery_pass=0 example_id=HuggingFaceH4_MATH-500_300
```

No auth errors, no dataset errors, no allowlist errors. Job is running normally.

## 8. Monitoring Commands

```bash
# Tail log
tail -f outputs/cohere_math_train_aux_generation_20260524/cohere_math_train_aux_full_20260525T001141Z.log

# Count scored (total)
grep "status=scored" outputs/cohere_math_train_aux_generation_20260524/cohere_math_train_aux_full_20260525T001141Z.log | wc -l

# Progress by method
grep "status=scored" outputs/cohere_math_train_aux_generation_20260524/cohere_math_train_aux_full_20260525T001141Z.log | awk -F'method=' '{print $2}' | awk '{print $1}' | sort | uniq -c

# Check done
grep "\[done\]" outputs/cohere_math_train_aux_generation_20260524/cohere_math_train_aux_full_20260525T001141Z.log
```

## 9. Safety Confirmation

| Safety Check | Status |
|---|---|
| Non-Cohere API calls (Azure/Mistral/Cerebras/Google) | ✗ None |
| Cohere calls within authorized cap (≤ 2000) | ✓ 800 planned |
| Active Cerebras jobs touched | ✗ Not touched (PIDs 2195513, 2361455 preserved) |
| Active TMUX sessions killed/modified | ✗ None |
| Commit/push to git | ✗ None |
| Original artifacts overwritten | ✗ None |
| API keys printed | ✗ Never |
| Gold answers as runtime features | ✗ Never |
| Official test set overlap | ✗ 0 |

## Output Files

All in `outputs/cohere_math_train_aux_generation_20260524/`:

- `cohere_math_train_aux_exact_cases.jsonl` — 200 exact-case rows
- `cohere_math_train_aux_case_inventory.csv` — case inventory with provenance
- `cohere_math_train_aux_overlap_report.csv` — overlap check per example
- `cohere_math_train_aux_overlap_report.md` — overlap narrative
- `cohere_math_train_aux_allowed_ids.jsonl` — 800-row call plan (allowed IDs)
- `cohere_math_train_aux_call_plan.csv` — call plan as CSV
- `cohere_math_train_aux_call_plan_summary.json` — call plan summary
- `cohere_math_train_aux_call_plan_summary.md` — call plan narrative
- `cohere_math_train_aux_preflight.json` — preflight results
- `cohere_math_train_aux_preflight.md` — preflight narrative
- `cohere_math_train_aux_monitoring.md` — monitoring guide
- `dataset_runner_capability_audit.json` — runner/dataset audit
- `dataset_runner_capability_audit.md` — runner/dataset audit narrative
- `manifest.json` — job manifest
- `launch_status.json` — TMUX launch record
- `runtime_snapshot.json` — initial process snapshot
- `initial_progress_status.json` — initial progress
- `cohere_math_train_aux_full_20260525T001141Z.log` — live log
- `cohere_math_train_aux_full_20260525T001141Z/` — runner output root (per_example_records.jsonl etc.)
