# Cohere × MATH-500 Failure Pool Audit

**Audit date:** 2026-05-28  
**Type:** Offline artifact audit — no APIs called, no training run, no files deleted.

---

## Executive Summary

| Question | Answer |
|---|---|
| Total fully tracked Cohere MATH-500 examples | **498 unique** (300 seed-71 official + 488 seed-11 auxiliary, 290 overlap) |
| Usable for failure-pattern mining (seed-71 official) | **135 examples** (oracle ceiling: pool has correct answer) |
| "Frontier correct, FTA wrong" regression cases | **0** using `fta_selected_answer`; **13** using `agreement_only` as system proxy (seed-71) |
| Are the "20 inspected" cases the only available data? | **No.** Raw artifacts contain 300 (canonical) or 488 (auxiliary) fully tracked examples. The "20" refers to the `agreement_only_recovers_vs_pooled4_cases.csv` inspection subset. |
| Additional collection needed for ≥1500-case router training? | **Yes.** Current unique examples = 498. Need ~1000 more from Azure/Mistral/Fireworks or additional seeds. |

---

## 1. Artifact Inventory

### 1.1 Fully Usable Artifacts (have question + gold + frontier + L1/S1/TALE)

| Artifact | Seed | Budget | N examples | FTA fields | Status |
|---|---|---|---|---|---|
| `official_four_scenario_case_level_replay.csv` | 71 | 6 | **300** | ✓ full | CANONICAL, PRIMARY |
| `cohere_math500_auxiliary_complete_4method_records.jsonl` | 11 | 6 | **488** | ✓ (in result_metadata) | diagnostic_only, not_canonical |
| `scenario4_case_level_selector_replay.csv` | 71 | 6 | 300 | partial (no override_reason) | derived from primary |
| `cohere_math500_case_table_base.csv` | 71 | 6 | 300 | partial | derived from primary |
| `cohere_real_model_cost_normalized_validation_mlj_math500_b6.../per_example_records.jsonl` | 11 | 6 | 500 | ✓ (result_metadata) | raw source for auxiliary |

**Union of unique examples across seeds 71 and 11: 498**  
- Overlap between seeds: 290  
- Seed-71 only: 10  
- Seed-11 only: 198  

### 1.2 Empty / Non-Usable Artifacts

All 12 canonical pilot runs (`canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_{11|23}_{4|6|8}_HuggingFaceH4_MATH-500`) have **zero-byte `per_example_rows.csv`** files. They produced no per-example data despite having `subset_size: 20` in their manifests. These are the source of the phrase "20 inspected" — but they contain no actual data.

| Dir name | Seed | Budget | Status |
|---|---|---|---|
| cohere_11_4_HuggingFaceH4_MATH-500 | 11 | 4 | 0-byte CSV, 100 API errors |
| cohere_11_6_HuggingFaceH4_MATH-500 | 11 | 6 | 0-byte CSV |
| cohere_11_8_HuggingFaceH4_MATH-500 | 11 | 8 | 0-byte CSV |
| cohere_23_4_HuggingFaceH4_MATH-500 | 23 | 4 | 0-byte CSV |
| cohere_23_6_HuggingFaceH4_MATH-500 | 23 | 6 | 0-byte CSV |
| cohere_23_8_HuggingFaceH4_MATH-500 | 23 | 8 | 0-byte CSV |
| (+ 6 PATCH variants with same seeds/budgets) | | | 0-byte CSVs |

---

## 2. Field Completeness (Primary Artifact: seed-71 official)

Source: `official_four_scenario_case_level_replay.csv`, cohere_math500 rows (N=300)

| Field | Present | Notes |
|---|---|---|
| question | 300/300 | ✓ complete |
| gold_answer | 300/300 | ✓ complete |
| frontier_answer | 297/300 | 3 frontier calls failed |
| fta_selected_answer | 297/300 | same 3 failures |
| l1_answer | 300/300 | ✓ complete |
| s1_answer | 298/300 | 2 S1 failures |
| tale_answer | 299/300 | 1 TALE failure |
| override_reason | 297/300 | matches frontier failures |
| frontier_support | 300/300 | ✓ complete |
| candidate_pool_answer_group_count | 300/300 | ✓ complete |

Override reason values observed: `direct_frontier_agree`, `single_weak_frontier_branch`, `frontier_support_margin_override`, `insufficient_support_margin`, `frontier_not_run_or_budget_exhausted`

---

## 3. Failure Category Counts

### 3.1 Seed-71 Official (N=300, canonical)

| Category | Count | Rate |
|---|---|---|
| All sources wrong (pool failure, unfixable by any selector) | 165 | 55.0% |
| Oracle correct (at least one source has the right answer) | 135 | 45.0% |
| Frontier correct | 87 | 29.0% |
| FTA correct (fta_selected_answer) | 87 | 29.0% |
| Agreement_only correct | 99 | 33.0% |
| L1 correct | 73 | 24.3% |
| S1 correct | 84 | 28.0% |
| TALE correct | 76 | 25.3% |
| Pool has correct answer, FTA does not select it | 48 | 16.0% |
| Pool has correct answer, agreement_only does not select it | 36 | 12.0% |
| **Frontier wrong AND FTA correct (FTA recovery)** | **0** | 0.0% |
| **Frontier correct AND FTA wrong (FTA regression)** | **0** | 0.0% |
| Frontier wrong AND agreement_only correct (AO recovery) | 25 | 8.3% |
| Frontier correct AND agreement_only wrong (AO regression) | 13 | 4.3% |

**Critical finding:** `fta_correct == frontier_correct` for all 300 cases. The FTA controller (`direct_reserve_semantic_frontier_v2`) never successfully overrides frontier with an external answer on MATH-500. Every override attempt selects a wrong external answer, so the net FTA accuracy equals raw frontier accuracy (87/300 = 29%).

The simpler `agreement_only` selector outperforms FTA by +12 cases (99 vs 87, +4pp).

### 3.2 Seed-11 Auxiliary (N=488, diagnostic_only)

| Category | Count | Rate |
|---|---|---|
| All sources wrong (pool failure) | 268 | 54.9% |
| Oracle correct | 220 | 45.1% |
| Frontier correct | 129 | 26.4% |
| Agreement_only / pooled4 correct | 147 | 30.1% |
| Frontier wrong AND agreement_only correct (recovery) | 26 | 5.3% |
| Frontier correct AND agreement_only wrong (regression) | 8 | 1.6% |
| Pool has correct AND agreement_only wrong | 73 | 15.0% |

Oracle ceiling (~45%) is consistent across both seeds, confirming the 55% true pool failure rate is a stable property of the Cohere command-r-plus-08-2024 × MATH-500 combination.

---

## 4. Specifically Answering the Five Key Questions

### Q1: How many fully tracked Cohere MATH-500 examples do we have?

**498 unique examples** across two seeds:
- Seed 71 (canonical): 300 examples, 297 fully complete (3 frontier failures)
- Seed 11 (auxiliary/diagnostic): 488 examples, all complete with FTA metadata in result_metadata
- Union = 498 unique; 290 overlap

For the canonical, production-safe count: **300 examples (seed 71)**.

### Q2: How many fully tracked failure instances are available for pattern discovery?

**135 examples** (seed 71) where `oracle_source_correct = True` — i.e., the pool contains a correct answer and failure is a selector/algorithm problem, not a pool deficiency.

Of these 135 selector-fixable failures:
- 48 cases: pool has correct answer, FTA still picks wrong
- 36 cases: pool has correct answer, agreement_only still picks wrong
- 25 cases: frontier wrong, agreement_only recovers (recovery pattern)
- 13 cases: frontier correct, agreement_only wrong (regression pattern)

For the auxiliary (seed 11): **220 oracle-correct examples** available for mining.

### Q3: Are there only 20 inspected "frontier correct, FTA wrong" cases, or more available?

**There are NOT only 20 such cases.** The "20" originates from `agreement_only_recovers_vs_pooled4_cases.csv` — the 20 cases where agreement_only recovers over pooled4 — which was the primary inspection set in the workbench analysis. This is a SUBSET of a larger available set.

The actual counts:
- `frontier_correct AND fta_wrong`: **0** (FTA never fires successfully, so it always matches frontier)
- `frontier_correct AND agreement_only_wrong` (regression): **13** (seed 71) or **8** (seed 11)
- Cases available for any pattern analysis: **300** (seed 71 canonical) or **488** (seed 11 auxiliary)

### Q4: If only ~20 usable cases exist, what missing fields prevent using more?

**No fields are missing.** The 300 official and 488 auxiliary examples are all available. There is no field-level blocker. The 20-case limit was a deliberate scope decision (inspecting only the agreement_only recovery cases), not a data availability constraint.

### Q5: What additional collection is needed for a larger failure-pattern discovery set?

The `cohere_math500_failure_learning_20260525/cohere_math500_learned_selector_results.md` explicitly states: **≥1500 cross-provider cases** needed before training a reliable meta-router.

Current status: 498 unique Cohere MATH-500 examples. Gap: ~1000 additional.

Options:
1. **Expand seeds** — Run seed 23 for 300–500 more Cohere MATH-500 examples (offline target, does not require new budget allocations beyond the API call cost).
2. **Add Mistral MATH-500** — Mistral MATH-500 Scenario 5 already exists (300 examples). Cross-provider patterns may generalize.
3. **Add Azure/Fireworks** — As identified in the failure_learning promotion decision.
4. **Use the 198 seed-11-only examples** — The 198 examples in the auxiliary that are NOT in the seed-71 official set can be used as independent validation.

No new live API calls are needed to expand the analysis pool from 300 to 498 — the seed-11 auxiliary already exists offline.

---

## 5. Files Created

| File | Description |
|---|---|
| `README.md` | This report |
| `artifact_inventory.csv` | Per-artifact inventory with field coverage status |
| `failure_pool_counts.csv` | Failure category counts by seed |
| `usable_failure_cases.csv` | 300 seed-71 cases with failure category labels |

---

## 6. Commit and Git Status

See commit hash and final git status in the commit log.
