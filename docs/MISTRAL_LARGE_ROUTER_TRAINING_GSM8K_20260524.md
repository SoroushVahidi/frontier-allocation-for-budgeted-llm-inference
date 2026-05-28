# Mistral Large Router Training × GSM8K — Launch Report

> Created: 2026-05-24T15:21:00Z | Mistral API job, detached TMUX. No Cohere/Cerebras jobs touched.

---

## 1. Executive Summary

Large auxiliary Mistral × GSM8K router-training corpus (seed=71, 1,000 training examples, 4 methods = 4,000 rows) has been **successfully launched** in tmux session `mistral_large_gsm8k_router_train_20260524T151853Z`. The job is running healthy with 6+ examples scored. Estimated completion: ~4–8 hours.

---

## 2. Was a Large Mistral Router-Training Run Already Running or Complete?

**NO.** A thorough search of `outputs/` found no existing 1,000-example × 4-method Mistral GSM8K training run. Existing Mistral artifacts:
- `outputs/mistral_gsm8k_frozen_agreement_result_20260523/` — 300-example **test split** evaluation (seed=71), NOT a training corpus
- `outputs/mistral_math500_scenario5_processing_20260524/` — MATH-500 evaluation

Neither qualifies as the needed training corpus (different split, different purpose, different size).

---

## 3. API Key Status

`MISTRAL_API_KEY`: **PRESENT** — confirmed before launch.

---

## 4. Runner Support for GSM8K Training Split

The runner's default for `openai/gsm8k` is the **test split** (`default_split="test"`, 1319 examples). The train split is not natively supported via `--datasets openai/gsm8k`.

**Solution:** Used `--exact-cases-jsonl` to bypass dataset loading entirely. The runner's `resolve_examples_for_dataset()` function uses exact-case rows directly when provided, without calling `load_pilot_examples()`. This is the correct and safe approach for training-split examples.

---

## 5. Exact Cases — Training Split Sampling

- **File:** `outputs/mistral_large_router_training_gsm8k_20260524/mistral_gsm8k_train_1000_exact_cases.jsonl`
- **Examples:** 1,000 (unique, no duplicates)
- **Dataset:** `openai/gsm8k`, split=`train` (7,473 total examples)
- **Sampling:** Stable shuffle with `random.Random(71)`, first 1,000 selected
- **IDs:** `openai_gsm8k_train_0` through `openai_gsm8k_train_999`
- **Gold answers:** Extracted with `extract_final_answer()` (canonical numeric form)
- **Original train indices:** Stored for reproducibility

---

## 6. Overlap Check with Official Evaluation Subset

- **Official eval:** 300 examples from GSM8K **test** split (seed=71)
- **Training corpus:** 1,000 examples from GSM8K **train** split

**Result: ZERO overlap** — GSM8K train and test are completely disjoint HuggingFace splits.
Verified: 0 matching questions (first 80 chars) between the 7,473 train and 1,319 test examples.

---

## 7. Allowed IDs Safety Check

- **File:** `outputs/mistral_large_router_training_gsm8k_20260524/mistral_gsm8k_train_1000_allowed_ids_all_methods.jsonl`
- **Total entries:** 4,000 (1,000 × 4 methods)
- **Methods present:** `direct_reserve_semantic_frontier_v2`, `external_l1_max`, `external_s1_budget_forcing`, `external_tale_prompt_budgeting`
- **Allowlist bug:** NOT PRESENT — all 4 methods have explicit `method` field in every entry. Prior bug was when method field was absent, causing only the first method to run.

---

## 8. Expected Rows and Calls

| Item | Count |
|---|---|
| Expected rows | 4,000 |
| Methods | 4 × 1,000 = 4,000 |
| Estimated Mistral API calls | ~4,000 logical (frontier may use multiple internal calls per example) |
| Retry upper bound | ~20,000 |

---

## 9. Dry-Run / Call Plan Result

**PASSED.** Dry-run confirmed:
- 4 method slices × 1,000 = 4,000 planned cases
- All 4 methods with canonical names
- Seed=71, `openai/gsm8k`, budget=6
- No method scheduling gap

---

## 10. Preflight Checks

| Check | Result |
|---|---|
| Repo health (`check_repo_health.py`) | PASS |
| Test suite | PASS — 93 passed, 1 skipped (pandas-absent C1 test; unrelated to runner) |
| Mistral API key | PRESENT |
| Exact cases validated | 1,000 cases, all gold answers extracted |
| Allowed IDs validated | 4,000 rows, all 4 methods |
| No existing router training run | CONFIRMED |
| Train/test disjoint | CONFIRMED — 0 overlap |
| No active Mistral generation job | CONFIRMED before launch |

---

## 11. Launch Details

| Parameter | Value |
|---|---|
| tmux session | `mistral_large_gsm8k_router_train_20260524T151853Z` |
| bash PID | 2403206 |
| python PID | 2403216 |
| Launch time | 2026-05-24T15:19:50Z |
| Log | `outputs/mistral_large_router_training_gsm8k_20260524/mistral_gsm8k_train1000_full_20260524T151853Z.log` |
| Output root | `outputs/mistral_large_router_training_gsm8k_20260524/mistral_gsm8k_train1000_full_20260524T151853Z/` |

---

## 12. Immediate Progress (at ~15:21 UTC)

- **Status:** `running_healthy`
- **Examples scored:** 6+ (frontier method, examples 0–5)
- **Current method:** `direct_reserve_semantic_frontier_v2` (first method, correct)
- **Auth errors:** None
- **Dataset errors:** None
- **Method scheduling errors:** None

---

## 13. Active Jobs — UNTOUCHED

| Job | PIDs | Session | Status |
|---|---|---|---|
| Cohere MATH-500 Scenario 4 | 2399424/2399431 | `cohere_math500_s4_official_20260524T144902Z` | RUNNING, NOT TOUCHED |
| Cerebras GSM8K | 2195504/2195513 | `55` | RUNNING, NOT TOUCHED |
| Overnight supervisor | 2361453/2361455 | `overnight_cerebras_supervisor_20260524` | RUNNING, NOT TOUCHED |

---

## 14. Failure Tracking / Processing Plan

See: `outputs/mistral_large_router_training_gsm8k_20260524/mistral_large_router_training_failure_tracking_plan.md`

Processing steps after `[done]`:
1. Integrity check (4,000 rows, 4 methods × 1,000, 0 duplicates)
2. Method accuracy summary on training examples
3. Feature generation for router training (answer patterns, agreement, majority presence)
4. Router training corpus validation (no data leakage, correct gold labels)
5. Integrate with learned router (combine with other scenarios, retrain)

---

## 15. Next Monitoring Command

```bash
# Quick progress check
tail -5 outputs/mistral_large_router_training_gsm8k_20260524/mistral_gsm8k_train1000_full_20260524T151853Z.log

# Row count by method
python3 -c "
import json
from collections import Counter
path = 'outputs/mistral_large_router_training_gsm8k_20260524/mistral_gsm8k_train1000_full_20260524T151853Z/cohere_real_model_cost_normalized_validation_20260524T151853Z/per_example_records.jsonl'
with open(path) as f:
    recs = [json.loads(l) for l in f if l.strip()]
mc = Counter(r['method'] for r in recs)
print(f'Total: {len(recs)}/4000')
for m, c in sorted(mc.items()): print(f'  {m}: {c}')
"
```

---

## 16. Safety Confirmation

- No TMUX sessions attached to.
- Active Cohere/Cerebras/supervisor jobs observed only — not touched.
- Gold labels used offline only — not passed to API.
- No commit or push made.
- Training examples are disjoint from all official evaluation subsets.
