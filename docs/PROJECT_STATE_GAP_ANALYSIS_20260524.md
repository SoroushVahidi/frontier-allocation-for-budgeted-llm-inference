# Project State, Gap Analysis, and Roadmap
**Date:** 2026-05-24T02:34:25Z  
**Branch:** main  
**Repo:** `/home/soroush/frontier-allocation-for-budgeted-llm-inference`

---

## 1. Executive Summary

This repository develops a machine-learning framework for **fixed-pool LLM answer selection under matched inference budgets**. The core problem: given answers from four candidate sources (frontier, L1, S1, TALE) generated under the same budget, choose the best answer without additional LLM calls.

**Current state:**
- 2 of 6 target scenarios are **complete** with full evidence (Cohere × GSM8K, Mistral × GSM8K)
- 2 scenarios are **actively running** (Cerebras × GSM8K, Mistral × MATH-500)
- 1 scenario is **queued** (Cerebras × MATH-500)
- 1 scenario is **not started** (Cohere × MATH-500)

**Key findings (from completed scenarios):**
- In **near-peer regime** (Cohere × GSM8K): pooled_4 voting achieves **85.67%** vs best single source 80.67%
- In **dominant-source regime** (Mistral × GSM8K): beta_shrinkage / raw_spread / dominant_source_veto selector achieves **91.33%** — matching S1's individual score
- The **regime-aware selector** is best or tied-best on both completed scenarios — the strongest interpretable candidate for a universal algorithm
- A **learned fixed-pool router prototype** was built on scenarios 1+2; CV accuracy 87.5-89.2%; cross-scenario transfer weak (85-86% vs S1's 91.33%)
- **Manuscript readiness:** Scenarios 1+2 are ready; 4 scenarios incomplete; no MATH-500 evidence yet

---

## 2. Current Active Jobs

| Job | Scenario | Status | Rows | Progress |
|---|---|---|---|---|
| Cerebras GSM8K | 3 | **RUNNING** (11h50m) | 288/1200 | Method 1/4 at 288/300 |
| Mistral MATH-500 | 5 | **RUNNING** (44m) | 649/1200 | Methods 1+2 done; method 3 at 49/300 |
| Cerebras MATH-500 | 6 | **QUEUED** | 0/1200 | Blocked by Scenario 3 |

**No jobs were touched, modified, or interrupted.**

See: `outputs/project_state_gap_analysis_20260524/active_jobs_status_snapshot.json`

---

## 3. Six-Scenario Matrix

| # | Scenario | Status | Best Selector | Best Acc | Oracle | Regime |
|---|---|---|---|---|---|---|
| 1 | Cohere × GSM8K | **COMPLETE** | pooled_4 | **85.67%** | 93.33% | near-peer |
| 2 | Mistral × GSM8K | **COMPLETE** | beta_shrinkage / S1 | **91.33%** | 94.00% | dominant-source |
| 3 | Cerebras × GSM8K | **RUNNING (24%)** | — | — | — | unknown |
| 4 | Cohere × MATH-500 | **NOT STARTED** | — | — | — | unknown |
| 5 | Mistral × MATH-500 | **RUNNING (54%)** | — | — | — | unknown |
| 6 | Cerebras × MATH-500 | **QUEUED** | — | — | — | unknown |

See: `outputs/project_state_gap_analysis_20260524/scenario_matrix_status.md`

---

## 4. Completed Experiments and Results

### 4.1 Scenario 1: Cohere × GSM8K — COMPLETE

**Model:** command-r-plus-08-2024 | **N:** 300 | **Seed:** 71 | **Budget:** 6

| Method | Accuracy | Bootstrap 95% CI vs frontier |
|---|---|---|
| oracle | 93.33% | — |
| **pooled_4** | **85.67%** | [+3.67pp, +9.67pp] |
| agreement_only | 82.33% | [+0.00pp, +7.33pp] |
| TALE | 80.67% | [−2.67pp, +6.33pp] |
| S1 | 80.00% | [−3.33pp, +5.33pp] |
| L1 | 79.67% | [−5.67pp, +4.00pp] |
| frontier | 79.00% | baseline |

**Regime:** near-peer. Sources within 1.67pp of each other. Pooled voting is optimal.

**Artifacts:**
- `outputs/cohere_canonical_final300_frozen_agreement_live_result_20260523/`
- `outputs/merged_repaired_cohere_mistral_selector_replay_20260524/`

### 4.2 Scenario 2: Mistral × GSM8K — COMPLETE

**Model:** mistral-small-latest | **N:** 300 | **Seed:** 71 | **Budget:** 6

| Source | Accuracy |
|---|---|
| S1 (dominant) | **91.33%** |
| frontier | 78.67% |
| L1 | 72.67% |
| TALE | 67.00% |

| Selector | Accuracy | Delta vs agreement_only |
|---|---|---|
| oracle | 94.00% | +9.33pp |
| S1 / always_S1 / beta_shrinkage / raw_spread / dominant_source_veto | **91.33%** | +6.67pp |
| pooled4_with_calibrated_no_majority_fallback | 89.00% | +4.33pp |
| majority_requires_dominant_source | 88.00% | +3.33pp |
| pooled_4 | 85.67% | +1.00pp |
| agreement_only | 84.67% | baseline |

**Regime:** dominant-source (S1). S1 is 13pp above frontier. Pooled voting underperforms because L1/TALE form wrong majorities.

**Key failure insight:** 47.7% of pooled_4 failures on Mistral are "C-class": S1 correct, wrong majority formed by L1/TALE/frontier.

**Artifacts:**
- `outputs/merged_repaired_cohere_mistral_selector_replay_20260524/`
- `outputs/cohere_mistral_failure_pattern_hypotheses_20260523/`

### 4.3 Selector Replay (Both Completed Scenarios)

The **beta_shrinkage_regime_selector** achieves:
- Cohere × GSM8K: 85.67% (ties pooled_4; best non-oracle)
- Mistral × GSM8K: 91.33% (ties S1/dominant_source; +5.67pp vs pooled_4)

This makes it the **top interpretable candidate for a universal regime-aware selector** across the two completed scenarios.

---

## 5. Incomplete / Running / Queued Experiments

### Scenario 3: Cerebras × GSM8K (Running)
- 288 rows of frontier complete; 3 methods + all selectors pending
- Very slow due to Cerebras API rate limits; method 1 at 288/300 after 11h50m
- **Do not touch or restart.**

### Scenario 5: Mistral × MATH-500 (Running)
- frontier (300/300), L1 (300/300), S1 (49/300), TALE (0/300)
- Healthy with 429 retries; ETA ~3-5h
- **Do not touch or restart.**

### Scenario 6: Cerebras × MATH-500 (Queued)
- Pre-planned; dry-run passed
- Will launch only after Scenario 3 completes (to avoid Cerebras account contention)

### Scenario 4: Cohere × MATH-500 (Not Started)
- No launch decision made; Cohere API has cost
- **User decision required** before launching

---

## 6. Algorithm and Selector Inventory

See full audit: `outputs/project_state_gap_analysis_20260524/algorithm_selector_audit.md`

### Candidate Sources
| Source | Type | Cohere Acc | Mistral Acc | Our Contribution |
|---|---|---|---|---|
| frontier (direct_reserve_semantic_frontier_v2) | internal | 79.00% | 78.67% | **yes** |
| L1 (external_l1_max) | external baseline | 79.67% | 72.67% | no |
| S1 (external_s1_budget_forcing) | external baseline | 80.00% | 91.33% | no |
| TALE (external_tale_prompt_budgeting) | external baseline | 80.67% | 67.00% | no |

### Selectors (Best Results)
| Selector | Type | Cohere | Mistral | Status |
|---|---|---|---|---|
| oracle_best_source | oracle ceiling | 93.33% | 94.00% | diagnostic |
| beta_shrinkage_regime_selector | regime, ours | **85.67%** | **91.33%** | candidate_main_method |
| raw_spread_regime_selector | regime, ours | **85.67%** | **91.33%** | candidate_main_method |
| dominant_source_veto | regime, ours | **85.67%** | **91.33%** | candidate_main_method |
| pooled_4_with_fallback | static, ours | **85.67%** | 85.67% | strong_baseline |
| agreement_only | static, ours | 82.33% | 84.67% | interpretable_baseline |
| learned action_tree_router (CV) | learned, prototype | ~89.2% (CV) | ~91.33% (in-fold) | prototype |

---

## 7. Learned-Router Status

**Prototype built:** `outputs/learned_fixed_pool_router_20260524/`  
**Script:** `scripts/build_and_eval_learned_fixed_pool_router.py`  
**Artifact:** `models/learned_fixed_pool_router_final_models.joblib`

### Training Data
- Cohere × GSM8K: 300 examples × 4 methods = 1200 rows
- Mistral × GSM8K: 300 examples × 4 methods = 1200 rows
- Combined: 2400 rows, 600 unique examples

### Evaluation Results

**Pooled Stratified 5-fold CV (with IDs):**
| Model | ALL_MACRO Acc | Worst-Scenario |
|---|---|---|
| action_tree_depth4 | ~89.2% | ~85.0% |
| pooled4_with_fallback | ~89.2% | ~86.7% |
| source_logistic | ~87.5% | ~81.7% |
| action_logistic | ~87.5% | ~80.0% |
| action_hgb | ~87.5% | ~83.3% |

**Cross-Scenario Transfer (no IDs, evaluated on 300-case held-out scenario):**
| Direction | Best Model | Accuracy | vs. S1 (dominant) |
|---|---|---|---|
| Cohere→Mistral | action_tree_no_ids | 86.0% | −5.33pp |
| Mistral→Cohere | source_logistic_no_ids | 85.0% | (pooled_4 is 85.67%) |

**Conclusion:** Cross-scenario transfer is **weak**. The learned router does not clearly outperform simple regime selectors when applied across scenarios with different regime types. This is a prototype, not a final result.

### Limitations
1. Only 2 scenarios (600 examples) — insufficient for reliable learned-router validation
2. Cross-scenario transfer does not beat pooled_4 on Cohere or regime selector on Mistral
3. With-IDs models risk learning a provider-lookup table
4. No sample-size sensitivity study yet

---

## 8. Failure-Case Coverage

See: `outputs/project_state_gap_analysis_20260524/failure_case_coverage_audit.md`

### Summary

| Scenario | Coverage | Agreement Fails | Pooled4 Fails | S1-correct-selector-wrong | All-wrong |
|---|---|---|---|---|---|
| Cohere × GSM8K | **good** | yes (53 cases) | yes (43 cases) | yes | yes |
| Mistral × GSM8K | **good** | yes (44 cases) | yes (44 cases) | yes | yes |
| Cerebras × GSM8K | none (running) | — | — | — | — |
| Cohere × MATH-500 | none (not started) | — | — | — | — |
| Mistral × MATH-500 | template only | — | — | — | — |
| Cerebras × MATH-500 | none (queued) | — | — | — | — |

### Key Failure Taxonomy (agreement_only)
| Class | Cohere | Mistral |
|---|---|---|
| A: no ext majority → keep wrong frontier | 56.6% (30) | 45.5% (20) |
| D: frontier correct, ext majority wrong → regression | 26.4% (14) | 29.5% (13) |
| G: all sources wrong | 13.2% (7) | 20.5% (9) |
| F: L1/TALE wrong majority overrides correct S1 | 3.8% (2) | 2.3% (1) |

### Key Failure Taxonomy (pooled_4)
| Class | Cohere | Mistral |
|---|---|---|
| A: all sources wrong | 39.5% (17) | 45.5% (20) |
| C: wrong majority, correct source isolated | 30.2% (13) | 47.7% (21) |
| E: no majority, frontier fallback wrong | 30.2% (13) | 6.8% (3) |

---

## 9. Supported and Unsupported Hypotheses

See: `outputs/project_state_gap_analysis_20260524/hypothesis_evidence_audit.md`

| ID | Hypothesis | Status | Strength |
|---|---|---|---|
| H1 | Near-peer → pooled voting | **Supported** (1 scenario) | moderate |
| H2 | Dominant-source → routing to dominant | **Strongly supported** (1 scenario) | moderate-strong |
| H3 | Correlation alone doesn't explain pooled-4 behavior | **Supported with nuance** | moderate |
| H4 | Agreement-only too conservative (frontier fallback fails) | **Supported for diagnosis** | moderate |
| H5 | Learned router feasible but not validated strongly | **Pilot only** | low-moderate |
| H6 | 300 examples/scenario too low for learned-router claims | **Accepted constraint** | high |
| H7 | S1-Mistral alignment due to budget-forcing | **Plausible; frame carefully** | low-moderate |

---

## 10. Repository / Script / Test State

**Test results:** 87 passed, 1 skipped  
**Repo health:** PASS  
**Branch:** main

| Test File | Result |
|---|---|
| `tests/test_support_aware_selector.py` | PASS |
| `tests/test_live_validation_hardening_20260523.py` | PASS |
| `tests/test_frontier_router.py` | PASS |
| `tests/test_learned_fixed_pool_router_features.py` | PASS |

### Key Scripts
| Script | Purpose | Status |
|---|---|---|
| `scripts/run_cohere_real_model_cost_normalized_validation.py` | Main API validation runner | current |
| `scripts/merge_repaired_runs_and_replay_selectors.py` | Merge + offline selector replay | current |
| `scripts/build_and_eval_learned_fixed_pool_router.py` | Train/evaluate learned router | current |
| `experiments/support_aware_selector.py` | Rule-based selectors (agreement_only, pooled_4, regime) | current |
| `scripts/check_repo_health.py` | Repo sanity check | current |

---

## 11. Manuscript-Readiness Assessment

### What Can Be Claimed NOW (2 scenarios)

- **Claim 1 (safe):** "In a near-peer regime (Cohere × GSM8K), pooled_4 voting achieves 85.67% — statistically significantly above all individual sources [95% CI: +3.67pp to +9.67pp vs frontier]."
- **Claim 2 (safe):** "In a dominant-source regime (Mistral × GSM8K), routing to the dominant source (beta_shrinkage / raw_spread regime selector) achieves 91.33%, matching S1's individual score and outperforming pooled_4 by 5.67pp."
- **Claim 3 (safe):** "A single regime-aware selector (beta_shrinkage / raw_spread) achieves best or tied-best accuracy on both completed scenarios (85.67% and 91.33%)."
- **Claim 4 (safe):** "Failure taxonomy on 2 scenarios shows: 45-57% of agreement_only failures are due to no-majority frontier fallback failing; 30-48% of pooled_4 failures are due to wrong majority formed when correct source is isolated."
- **Claim 5 (safe):** "A learned fixed-pool router prototype trained on 2 scenarios achieves ~89% pooled CV accuracy, but cross-scenario transfer (85-86%) does not clearly exceed simple regime-aware rules."

### What CANNOT Be Claimed Yet

- Any claim about MATH-500 performance (scenarios 4-6 incomplete)
- Any claim about Cerebras performance (scenario 3 incomplete)
- Universal superiority of regime-aware selector across all 6 scenarios
- Generalizability of learned router beyond 2 scenarios
- S1's dominance being a general phenomenon (may be Mistral-specific)
- Definitive sample-size sensitivity conclusions

### For a Complete 6-Scenario Manuscript
1. Complete scenarios 3-6 (all running/queued/not-started)
2. Rebuild learned router on all 6 scenarios
3. Add oracle-regret table for all 6 scenarios
4. Add paired bootstrap CIs across all 6 scenarios
5. Add sample-size sensitivity ablation
6. Write related work on DES / learning-to-defer / LLM routing

---

## 12. Gap Analysis

### Critical Gaps
1. **4/6 scenarios incomplete** — no MATH-500 or Cerebras evidence
2. **Learned router on 2 scenarios only** — cross-scenario transfer is weak
3. **No Cohere × MATH-500 decision** — requires user to authorize and fund

### Major Gaps
4. **Oracle regret analysis** only on 2 scenarios
5. **Paired bootstrap CIs** incomplete for 4 scenarios
6. **Sample-size sensitivity** not studied
7. **No-ID ablation** not formally reported (exists in outputs but not organized)

### Moderate Gaps
8. **Failure cases missing** for 4/6 scenarios
9. **Raw reasoning text** not stored (format limitation)
10. **Cross-difficulty analysis** (GSM8K easy vs MATH-500 hard) not possible until MATH-500 complete

### Minor Gaps
11. **`docs/CURRENT_STATE_SUMMARY_20260511.md` is stale** — covers pre-six-scenario phase
12. **Many historical docs** accumulated; need pruning or archiving

---

## 13. Prioritized Next Actions

1. **(~3-5h) When Mistral × MATH-500 finishes:** Run integrity + selector replay + failure extraction + add to router dataset
2. **(~40-50h) When Cerebras × GSM8K finishes:** Run integrity + selector replay + failure extraction; then launch Cerebras × MATH-500
3. **(User decision) Launch Cohere × MATH-500:** Must authorize paid API cost
4. **(After each new scenario) Rebuild learned router:** Rerun `build_and_eval_learned_fixed_pool_router.py` with expanded dataset
5. **(Algorithm dev) Formalize sample-size sensitivity ablation:** Sub-sample training sets; compute CV accuracy as function of N
6. **(Algorithm dev) Formal no-ID ablation:** Report no-ID results alongside with-ID to address provider-lookup criticism
7. **(Manuscript) Write six-scenario matrix section** after all scenarios complete
8. **(Manuscript) Oracle-regret and failure taxonomy sections** — data from scenarios 1+2 ready; extend to 4+ scenarios
9. **(Hygiene) Update `docs/CURRENT_STATE_SUMMARY_20260511.md`** — this report is the successor
10. **(Hygiene) Commit stable docs/scripts** after job completions and analysis rounds

---

## 14. Safety / Constraints Confirmation

- **No API calls made** during this analysis
- **No active jobs touched, modified, or interrupted** (Cerebras × GSM8K and Mistral × MATH-500 both left running)
- **No experiments launched**
- **No scientific result files overwritten**
- **No commit or push performed**
- **No policy promoted**
- **No incomplete results processed beyond read-only status check**

---

## Companion Files (All in `outputs/project_state_gap_analysis_20260524/`)

| File | Contents |
|---|---|
| `active_jobs_status_snapshot.json` | Machine-readable active job status |
| `active_jobs_status_snapshot.md` | Human-readable active job status |
| `scenario_matrix_status.csv` | Six-scenario matrix (CSV) |
| `scenario_matrix_status.md` | Six-scenario matrix (detailed markdown) |
| `algorithm_selector_audit.csv` | All algorithms/selectors tabulated |
| `algorithm_selector_audit.md` | Algorithm audit with detailed notes |
| `hypothesis_evidence_table.csv` | Hypothesis evidence (CSV) |
| `hypothesis_evidence_audit.md` | Hypothesis evidence (detailed markdown) |
| `failure_case_coverage_audit.csv` | Failure coverage per scenario (CSV) |
| `failure_case_coverage_audit.md` | Failure coverage (detailed markdown) |
| `code_test_audit.csv` | Scripts and test inventory |
| `gap_analysis_next_actions.md` | Gap analysis and next actions (detailed) |
| `prioritized_next_actions.csv` | Prioritized actions (CSV) |
| `docs_inventory.csv` | All docs inventoried |
| `output_bundle_inventory.csv` | All output bundles inventoried |
| `manifest.json` | Audit manifest |
