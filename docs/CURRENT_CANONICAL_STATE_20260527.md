# Current Canonical State — 2026-05-27

**Last verified:** 2026-05-27  
**Branch:** `feat/d8-learning-d6-prep-20260526`  
**Supersedes:** `docs/CURRENT_STATE_SUMMARY_20260511.md` (historical background only)

This is the single canonical reference for the verified state of the project as of 2026-05-27.
Read this before `LATEST_RESULTS_AND_CLAIMS.md` for the most current orientation.

---

## 1. Canonical Paper Result

**Method:** Failure-Trace Allocator (FTA) / FIX-2+FIX-4  
**Implementation:** `experiments/support_aware_selector.py` — `apply_combined_fix24_to_row()`

| Metric | Value | N | Source |
|---|---|---|---|
| Final-300 accuracy | **86.67%** (260/300) | 300 | Seed=71, budget=6, Cohere × GSM8K |
| Aggregate-720 accuracy | **80.69%** (581/720) | 720 | Seeds 41+61+71, budget=6, Cohere × GSM8K |
| Leakage audit | **PASS** | — | Gate features gold-free at runtime |
| Post-generation model calls | **0** | — | Selection only; no new calls |

**Verification status:** Both numbers independently reproduced from raw per-example records using the actual implementation.  
**Artifact:** `outputs/fta_independent_verification_20260527/run_20260527T003000Z/`

### Gate decomposition (Final-300)

| Gate | Fires | Wins | Losses |
|---|---|---|---|
| FIX-2 (Low-Depth Guard) | 63 | 36 | 9 |
| FIX-4 (External-Consensus Fallback) | 3 | 3 | 0 |
| No gate | 234 | — | — |

### Baselines (Final-300)

| Method | Accuracy |
|---|---|
| Frontier (direct_reserve_semantic_frontier_v2) | 76.67% (230/300) |
| L1 (external_l1_max) | 83.00% (249/300) |
| S1 (external_s1_budget_forcing) | 82.00% (246/300) |
| TALE (external_tale_prompt_budgeting) | 78.33% (235/300) |
| Pooled ensemble (frontier+L1+S1+TALE majority) | 84.33% (253/300) |
| **FTA / FIX-2+FIX-4** | **86.67% (260/300)** |
| Oracle (upper bound only) | 92.00% (276/300) |

### Confidence intervals (Final-300, bootstrap 5000 resamples)

| Comparison | Delta | 95% CI | LCB > 0? |
|---|---|---|---|
| FTA vs L1 | +3.67pp | [+0.33, +7.00] | YES |
| FTA vs S1 | +4.67pp | [+1.00, +8.33] | YES |
| FTA vs TALE | +8.33pp | [+5.00, +12.00] | YES |
| FTA vs pooled ensemble | +2.33pp | [**−0.67, +5.67**] | **NO** |

### Multi-seed evidence (Aggregate-720)

| Seed | N | FTA acc | In Agg-720 | Notes |
|---|---|---|---|---|
| 31 | 100 | 82.00% | No | Disjoint additional evidence |
| 41 | 300 | 83.33% | Yes | |
| 61 | 120 | 59.17% | Yes | **Failure-enriched base run for FIX-6** — not typical |
| 71 | 300 | 86.67% | Yes | Canonical Final-300 |

Aggregate-720 source-stratified CI lower bounds vs L1/S1/TALE/best-external: all **strictly positive**.

---

## 2. Supporting Evidence — D9 Gated Selector

**Method:** D9 multi-provider gated selector (XGBoost, grouped 5-fold CV)  
**Artifact:** `outputs/job_d9_retrain_with_mistral_20260526/run_20260526T234411Z/`

| Metric | Value |
|---|---|
| CV accuracy | **50.18% ± 2.52%** |
| Frontier baseline | 34.36% |
| Delta vs frontier | +15.82pp |
| Gate false overrides | **0** (at all thresholds 0.3–0.8) |
| Total D6 pools | 550 |
| Training rows | 14,150 |
| Providers | Cohere=320, Cloudrift=80, Mistral=150 |
| Dataset mix | MATH-500=460, GSM8K=90 |

**Verdict:** D9_MISTRAL_RETRAIN_USE_D6_AS_GATED_MODULE

D6 standalone is **negative** across all 550 pools (27.45% vs frontier 34.36%, net=-38). D9 gate is required for a positive outcome. D9 is supporting multi-provider evidence, not the canonical main result.

---

## 3. Supporting Evidence — Cloudrift/Qwen Extraction Repair

**Artifact:** `outputs/job_cloudrift_qwen_extraction_repair_20260526/run_20260527T002012Z/`

| Metric | Value |
|---|---|
| Strict JSON compliance | 16.2% (13/80) |
| Prior extraction (ast_dict) | 63.7% (51/80) |
| Lenient extraction | **98.8%** (79/80) |
| Unrecoverable | 1 |
| D6 lenient accuracy | 55.0% (vs frontier 37.5%) |
| Rescue bucket D6 (40 cases) | 55.0%, **0 regressions** |

**Root cause:** Qwen echoes JSON schema in chain-of-thought. Fix: move JSON schema to system message before new API calls.  
**D9-ready with current data.** Prompt fix required before generating more rows.

---

## 4. Scenario Ranking Summary

| Scenario | FTA/Our Method | Rank | Notes |
|---|---|---|---|
| **Cohere × GSM8K (Final-300)** | FTA 86.67% | **#1** | Canonical verified |
| **Cohere × GSM8K (Agg-720)** | FTA 80.69% | **#1** | Source-stratified CI lo > 0 vs all externals |
| Cohere × MATH-500 | FTA=frontier=29.0% | — | Pool failure (53.7% all-wrong); gate does not fire |
| Mistral × GSM8K | FTA=frontier=78.67% | — | S1 dominant (91.33%); regime mismatch |
| Mistral × MATH-500 | FTA=frontier=40.0% | — | Same regime mismatch |
| **Cloudrift × MATH-500 pilot** | D6 lenient 55.0% | **#1** | 80-case pilot only; rescue bucket 0 regressions |
| **D9 multi-provider (550 pools)** | D9 CV 50.18% | **#1** | CV not independent holdout |

**Full report:** `outputs/repository_situation_and_scenario_ranking_20260527/run_20260527T010000Z/`

---

## 5. Required Paper Disclosures

1. **CI vs pooled ensemble includes zero** — Final-300 delta [−0.67, +5.67]; Agg-720 delta [−1.11, +2.78]. Do not claim statistical superiority over pooled ensembles.
2. **Budget accounting** — FTA adds zero post-generation model calls, but full pool generation costs 4×B=6 = 24 logical calls per example.
3. **Scope** — Evaluation is Cohere × GSM8K only. Do not extrapolate to MATH-500 or other settings.
4. **Seed=61 disclosure** — The 59.17% seed=61 component in aggregate-720 was a failure-enriched base run for FIX-6 testing, not a random sample.

---

## 6. Safe vs Unsafe Claims

### Safe main claims
- FTA achieves 86.67% (260/300) on Final-300 (seed=71, Cohere × GSM8K, budget=6)
- FTA achieves 80.69% (581/720) on Aggregate-720 (seeds 41+61+71)
- FTA CI lower bounds vs L1/S1/TALE/best-external are all strictly positive on Aggregate-720
- FTA gate features are gold-free at runtime (leakage audit PASS)
- FTA adds zero model calls at selection time
- FIX-2 fires=63, FIX-4 fires=3, no-gate=234 (Final-300)
- FIX-4 causes zero regressions (3 wins, 0 losses)

### Safe supporting claims
- D9 CV 50.18%±2.52% vs frontier 34.36% (+15.82pp) on 550 multi-provider D6 pools
- D9 gate has zero false overrides at any tested threshold (0.3–0.8)
- Cloudrift rescue bucket: D6 55% accuracy, 0 regressions (40 MATH-500 cases)
- Lenient extraction recovers 98.8% of Cloudrift/Qwen D6 responses

### Unsafe — do not claim
- FTA statistically superior to pooled ensemble (CI includes zero at both n=300 and n=720) — **MUST DISCLOSE**
- Full pool generation costs only B=6 calls (it costs 24)
- FTA achieves 86.67% on MATH-500 or any benchmark other than Cohere × GSM8K
- D8.1 selector results are independent held-out end-to-end accuracy claims (they are test-split only)
- D6 net gain is positive standalone across all pools (it is negative: net=-38)

---

## 7. Next Actions

| Priority | Action | API calls needed |
|---|---|---|
| **HIGH** | Paper finalization — FTA as canonical, D9 as supporting | NO |
| Medium | Fix Cloudrift/Qwen prompt (move JSON to system message) before new Cloudrift generation | NO (offline fix only) |
| Medium | Targeted Mistral D6 generation on rescue-bucket cases | YES |
| Low | D9 refresh with repaired Cloudrift extraction (6 additional correct labels) | NO |
| Low | D8.1 independent validation on Mistral × GSM8K | YES |

---

## 8. Key Artifact Paths

| Artifact | Path |
|---|---|
| FTA independent verification | `outputs/fta_independent_verification_20260527/run_20260527T003000Z/` |
| FTA Final-300 validation | `outputs/final_fix24_all_external_validation_20260519_20260520T000902Z/` |
| FTA postrun metrics | `outputs/final_fix24_all_external_postrun_20260520_20260520T025349Z/` |
| D9 with Mistral | `outputs/job_d9_retrain_with_mistral_20260526/run_20260526T234411Z/` |
| D9 with Cohere+MATH-500 | `outputs/job_d9_retrain_with_cohere_math500_expansion_20260526/run_20260526T144632Z/` |
| Cloudrift extraction repair | `outputs/job_cloudrift_qwen_extraction_repair_20260526/run_20260527T002012Z/` |
| Mistral D6 eval | `outputs/job_d6_mistral_eval_20260526/run_20260526T232755Z/` |
| Consolidated evidence summary | `outputs/current_research_evidence_summary_20260527/run_20260527T003000Z/` |
| Scenario ranking report | `outputs/repository_situation_and_scenario_ranking_20260527/run_20260527T010000Z/` |
| Implementation | `experiments/support_aware_selector.py` |
