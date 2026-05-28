# Search: Existing Cohere × MATH-500 / Scenario 4 Results

**Search timestamp UTC:** 2026-05-24T08:30:00Z  
**Branch:** main  
**Status:** Read-only search; no API calls, no job interference, no commits.

---

## 1. Active Jobs Observed (Non-Invasive)

| Job | Status | Notes |
|---|---|---|
| Cerebras × GSM8K | `running_healthy` | PIDs 2195504/2195513 in `round2_monitor` — **not touched** |
| Mistral × MATH-500 | `complete` | Session exited; artifact ready |
| Cerebras × MATH-500 | `queued` | Not launched |
| Cohere × MATH-500 (Scenario 4) | `not_started` | Confirmed by `docs/PROJECT_STATE_GAP_ANALYSIS_20260524.md` |

---

## 2. Search Method Summary

- **Path/directory search**: `find outputs docs scripts tests experiments` with Cohere × MATH-500 patterns
- **Content search**: `grep -RIn` for `HuggingFaceH4/MATH-500`, `MATH-500`, `math500`, `command-r-plus-08-2024`, `cohere`
- **Per-example inventory**: All 126 `per_example_records.jsonl` files scanned with Python (row counts, providers, datasets, models, method counts)
- **Docs search**: All docs/ and outputs/ for `Scenario 4`, `Cohere.*MATH`, `cohere_math500`, `command-r-plus-08-2024.*MATH`
- **Call plan / launch status search**: All `*call_plan*.json`, `*launch_status*.json`, `manifest.json` with Cohere/MATH-500 patterns

---

## 3. All Candidate Cohere × MATH-500 Paths Found

### Primary Candidate (Substantial Run)
```
outputs/cohere_real_model_cost_normalized_validation_mlj_math500_b6_20260520T220928Z/
```
- Provider: cohere / `command-r-plus-08-2024`
- Dataset: `HuggingFaceH4/MATH-500`
- Seed: **11** (Scenario 4 standard is seed=71)
- Budget: 6
- N_examples target: **500** (Scenario 4 standard is 300)
- Methods: `direct_reserve_semantic_frontier_v2`, `external_l1_max`, **`s1`**, **`tale`** (short aliases, not full names)
- Total rows: 2000; scored rows: **1969**; unique examples with all 4 methods: **479/500**
- 15 permanent failures; no `[done]` in run.log

### Recovery Run (Supplemental)
```
outputs/cohere_real_model_cost_normalized_validation_mlj_math500_b6_recovery_failed31_20260521T124545Z/
```
- 31 attempted (the failed rows from the main run); 16 recovered, 15 permanently failed
- Not standalone; seed=11; method aliases

### Dry Run (Non-Result)
```
outputs/cohere_real_model_cost_normalized_validation_dryrun_math500_b6/
```
- max_examples=30, target_scored_per_slice=10; dry run only; seed=11

### April Canonical Diagnostics (Empty)
```
outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_4_HuggingFaceH4_MATH-500/
outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_6_HuggingFaceH4_MATH-500/
outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_8_HuggingFaceH4_MATH-500/
outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_23_4_HuggingFaceH4_MATH-500/
outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_23_6_HuggingFaceH4_MATH-500/
outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_23_8_HuggingFaceH4_MATH-500/
(+ PATCH variants of the above)
```
- All April 2026 diagnostic sweeps: `per_example_records.jsonl` has **0 scored rows**
- Only contain `seed_summary.csv` aggregates; not per-example data at scale

---

## 4. Per-Example Artifacts That Might Match

From the 126-file inventory, exactly **2** files contain both `cohere` and `MATH-500` with scored rows:

| File | Rows | Scored | Examples (all-4) | Notes |
|---|---|---|---|---|
| `cohere_real_model_cost_normalized_validation_mlj_math500_b6_20260520T220928Z/per_example_records.jsonl` | 2000 | 1969 | 479 | Main run; seed=11; method aliases |
| `cohere_real_model_cost_normalized_validation_mlj_math500_b6_recovery_failed31_20260521T124545Z/per_example_records.jsonl` | 31 | 16 | N/A | Recovery only |

---

## 5. Does a Complete 300×4 Cohere MATH-500 Result Exist?

**No.** No artifact with exactly 300 unique examples × 4 methods (1200 rows), seed=71, and full method names (`external_s1_budget_forcing`, `external_tale_prompt_budgeting`) exists.

---

## 6. Does a Partial Result Exist?

**Yes, substantially.** The MLJ math500 run (`cohere_real_model_cost_normalized_validation_mlj_math500_b6_20260520T220928Z`) has:
- 479 examples with complete 4-method coverage
- Cohere / `command-r-plus-08-2024` / `HuggingFaceH4/MATH-500`
- Budget=6 (same as Scenario 4)

However, it differs from the canonical Scenario 4 spec in three ways:
1. **Seed=11** (Scenario 4 standard: seed=71)
2. **500 examples** attempted (Scenario 4: 300)
3. **Method aliases** `s1`, `tale` instead of `external_s1_budget_forcing`, `external_tale_prompt_budgeting`

---

## 7. Prior Call Plans and Launch Status

- **No Scenario 4-specific call plan found** (`cohere_math500_scenario4_call_plan.json` or similar does not exist)
- The `scenarios_5_6_math500_full_tracking_20260524/manifest.json` covers Mistral and Cerebras MATH-500 only; no Cohere MATH-500 entry
- `cohere_real_model_cost_normalized_validation_dryrun_math500_b6/manifest.json` confirms a dry-run config was prepared (seed=11, 30 examples); no full launch status file exists for a 300-example seed=71 run
- **No launch status file** for a "Scenario 4" Cohere MATH-500 300×4 seed=71 run was found anywhere

---

## 8. Docs Mentions of Scenario 4

### `docs/PROJECT_STATE_GAP_ANALYSIS_20260524.md` (line 132)
```
### Scenario 4: Cohere × MATH-500 (Not Started)
- No launch decision made; Cohere API has cost
- **User decision required** before launching
```
**Assessment: Not started; user decision required.**

### Other docs mentions
- Multiple docs reference the MLJ math500 run results (accuracy figures, method analysis)
- No doc marks Scenario 4 as complete or in-progress
- The April canonical runs are referenced as diagnostic sweeps (20-sample), not full scenarios

---

## 9. Recommendation

### Decision: **E — `ambiguous_needs_manual_review`**

**Primary reason:** A substantial Cohere × MATH-500 artifact exists (479 complete examples, seed=11) but does not match the canonical Scenario 4 spec (300 examples, seed=71, full method names). Project documentation explicitly marks Scenario 4 as "Not Started."

**Two options for user decision:**

**Option A — Launch canonical Scenario 4 (clean slate)**
- Launch: `--providers cohere --datasets HuggingFaceH4/MATH-500 --seeds 71 --budgets 6 --methods direct_reserve_semantic_frontier_v2,external_l1_max,external_s1_budget_forcing,external_tale_prompt_budgeting --target-scored-per-slice 300 --max-examples 300`
- Same shared exact-cases file as Mistral/Cerebras MATH-500 (`math500_shared_exact_cases.jsonl`)
- Produces clean 300×4 = 1200-row artifact; consistent with Scenarios 5 and 6
- **Cost: ~$15-25 estimated for 1200 Cohere command-r-plus calls at budget=6**

**Option B — Reprocess existing MLJ run (no new API cost)**
- The 479-example seed=11 MLJ run can be subset to any 300-example slice
- Requires method-alias normalization (`s1` → `external_s1_budget_forcing`, `tale` → `external_tale_prompt_budgeting`)
- Different seed/subset from Scenarios 5 and 6 (which use seed=71 and the shared `math500_shared_exact_cases.jsonl`)
- Limits cross-scenario comparability on the same exact cases
- **Cost: $0**

**Recommendation if consistency across scenarios is important:** Launch canonical Scenario 4 (Option A).  
**Recommendation if cost is prohibitive:** Reprocess the MLJ run with alias normalization (Option B), but document the seed/subset mismatch.

---

## 10. Exact Reason for Recommendation

The project is tracking a six-scenario validation set. Scenarios 5 and 6 were launched using a shared case file (`math500_shared_exact_cases.jsonl`) with seed=71. The MLJ math500 run predates this (seed=11, 500 examples, older method aliases). Reusing it as Scenario 4 creates an inconsistency: Scenario 4 would test different examples than Scenarios 5 and 6, making direct comparison unreliable. A fresh seed=71 300-example Cohere run is the cleanest path. The decision hinges on whether the user wants strict per-example cross-scenario consistency.

---

## 11. Safety Confirmation

- No tmux sessions attached or modified.
- No jobs killed, restarted, or interrupted.
- **No API calls launched.** (Zero paid API calls.)
- No existing artifacts overwritten.
- No commits or pushes made.
- The Cerebras × GSM8K active job (`round2_monitor`, PIDs 2195504/2195513) was observed only; not touched.

---

## Files Created in This Search Bundle

| File | Description |
|---|---|
| `outputs/search_existing_cohere_math500_results_20260524/path_hits_cohere_math500.txt` | File/path search results |
| `outputs/search_existing_cohere_math500_results_20260524/dir_hits_cohere_math500.txt` | Directory search results |
| `outputs/search_existing_cohere_math500_results_20260524/all_per_example_files.txt` | All 126 per_example_records.jsonl paths |
| `outputs/search_existing_cohere_math500_results_20260524/per_example_artifact_inventory.csv` | Full inventory of 126 files |
| `outputs/search_existing_cohere_math500_results_20260524/content_hits_cohere_math500.txt` | Content grep hits |
| `outputs/search_existing_cohere_math500_results_20260524/scenario4_doc_mentions.txt` | Docs/outputs Scenario 4 mentions |
| `outputs/search_existing_cohere_math500_results_20260524/callplan_launch_manifest_candidates.txt` | Call plan and manifest candidates |
| `outputs/search_existing_cohere_math500_results_20260524/candidate_cohere_math500_artifacts.csv` | Deep inspection of matching candidates |
| `outputs/search_existing_cohere_math500_results_20260524/manifest.json` | Search bundle manifest |
| `docs/SEARCH_EXISTING_COHERE_MATH500_RESULTS_20260524.md` | This report |
