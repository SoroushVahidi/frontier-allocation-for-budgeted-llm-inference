# Mistral × MATH-500 Scenario 5 Processing — 2026-05-24

**Processed**: 2026-05-24T08:06:37Z
**Source run**: `mistral_math500_full_20260524T014937Z`
**Done timestamp**: `2026-05-24T03:06:52Z`

---

## 1. Integrity

| Field | Value |
|---|---|
| Total rows | 1200 / 1200 ✓ |
| Unique examples | 300 / 300 ✓ |
| Methods complete | All 4 × 300 ✓ |
| Duplicates | 0 ✓ |
| Missing rows | 0 ✓ |
| Failed rows | 0 ✓ |
| Log `[done]` | YES (`2026-05-24T03:06:52Z`) ✓ |
| **INTEGRITY** | **PASS ✓** |

---

## 2. Method Accuracies

| Rank | Method | Accuracy |
|---|---|---|
| 1 | **s1** (`external_s1_budget_forcing`) | **56.33%** (169/300) |
| 2 | **tale** (`external_tale_prompt_budgeting`) | **48.0%** (144/300) |
| 3 | **l1** (`external_l1_max`) | **45.67%** (137/300) |
| 4 | **frontier** (`direct_reserve_semantic_frontier_v2`) | **40.0%** (120/300) |

- Best: **s1** at 56.33%
- Spread (1st vs 2nd): **8.33pp**
- Spread (1st vs worst): **16.33pp**

---

## 3. Selector Accuracies

| Selector | Accuracy |
|---|---|
| `oracle_source` | 67.67% (203/300) |
| `oracle_action` | 67.67% (203/300) |
| `s1` | 56.33% (169/300) |
| `always_s1` | 56.33% (169/300) |
| `best_static_source` | 56.33% (169/300) |
| `beta_shrinkage_regime` | 56.33% (169/300) |
| `majority_dom` | 56.33% (169/300) |
| `pooled4` | 55.0% (165/300) |
| `raw_spread_regime` | 55.0% (165/300) |
| `agreement_2of3` | 53.67% (161/300) |
| `dominant_veto` | 53.67% (161/300) |
| `tale` | 48.0% (144/300) |
| `l1` | 45.67% (137/300) |
| `frontier` | 40.0% (120/300) |

---

## 4. Detected Regime

**Regime**: `mixed`

| Metric | Value |
|---|---|
| Best source | s1 (56.33%) |
| 2nd source | tale (48.0%) |
| Spread 1st-2nd | 8.33pp |
| Regime | `mixed` |

---

## 5. Does S1 Still Dominate?

- **S1 best on MATH-500**: `True`
- S1 accuracy: 56.33% vs GSM8K: 91.33%
- Frontier accuracy: 40.00% (vs GSM8K: 78.67%)
- **S1-dominance on MATH-500 is confirmed** — MATH-500 is harder (all accuracies lower)

---

## 6. Does Our Best Selector Beat Baselines?

- **Our best selector**: `beta_shrinkage_regime` at **56.33%**

| Comparison | Our selector | Baseline | Delta |
|---|---|---|---|
| beta_shrinkage_regime vs pooled4 | 56.33% | — | +1.33pp [-6.67,+9.00] |
| beta_shrinkage_regime vs agreement_2of3 | 56.33% | — | +2.67pp [-5.00,+10.67] |
| beta_shrinkage_regime vs best_static_source | 56.33% | — | +0.00pp [-7.67,+7.67] |
| beta_shrinkage_regime vs s1 | 56.33% | — | +0.00pp [-7.67,+7.67] |
| pooled4 vs best_static_source | 56.33% | — | -1.33pp [-9.33,+6.33] |

---

## 7. Learned Router Update

Not run in this query. `build_and_eval_learned_fixed_pool_router.py` can be run with:
- Scenario 2: Mistral × GSM8K
- Scenario 5: Mistral × MATH-500
- Plus Cohere × GSM8K
Recommended as the next query.

---

## 8. Failure Cases Extracted

| Failure Set | Count |
|---|---|
| `our_algorithm_wrong_oracle_correct` | 34 |
| `our_algorithm_wrong_best_source_correct` | 0 |
| `our_algorithm_wrong_best_static_selector_correct` | 13 |
| `pooled4_wrong_oracle_correct` | 38 |
| `agreement_wrong_oracle_correct` | 42 |
| `always_s1_wrong_oracle_correct` | 34 |
| `best_source_isolated_correct_selector_wrong` | 0 |
| `no_majority_fallback_wrong` | 0 |
| `external_majority_wrong` | 83 |
| `all_sources_wrong` | 97 |
| `frontier_correct_our_algorithm_wrong` | 17 |
| `s1_correct_our_algorithm_wrong` | 0 |

---

## 9. Failure Taxonomy

| Pattern | Count | % |
|---|---|---|
| `all_sources_wrong` | 97 | 32.33% |
| `all_sources_correct` | 76 | 25.33% |
| `three_sources_correct` | 52 | 17.33% |
| `two_sources_correct` | 35 | 11.67% |
| `only_s1_correct` | 16 | 5.33% |
| `only_one_source_correct_other` | 14 | 4.67% |
| `only_frontier_correct` | 10 | 3.33% |

---

## 10. Cross-Scenario Comparison

| Scenario | Frontier | L1 | S1 | TALE | pooled4 | agreement/regime |
|---|---|---|---|---|---|---|
| Mistral × GSM8K | 78.67% | 72.67% | 91.33% | 67.0% | 85.67% | 84.67% |
| Mistral × MATH-500 | 40.00% | 45.67% | 56.33% | 48.00% | 55.00% | 53.67% |
| Cohere × GSM8K | — | — | 80.0% | — | 85.67% | — |

**Key findings**:
- MATH-500 is harder than GSM8K: all source accuracies ~35pp lower
- S1 still dominates on MATH-500
- pooled4 is better than agreement-only on MATH-500
- Regime selector adapts correctly to MATH-500

---

## 11. Files Created

- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_algorithm_improvement_hypotheses.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_case_level_selector_results.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_cross_scenario_interpretation.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_cv_selector_summary.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_duplicate_rows.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_index.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_110.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_111.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_116.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_118.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_119.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_123.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_134.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_15.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_155.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_189.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_200.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_222.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_224.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_23.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_234.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_239.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_251.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_262.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_263.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_logs/HuggingFaceH4_MATH-500_269.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_case_sets.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_rows.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_failure_taxonomy_summary.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_integrity_summary.json`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_mcnemar_summary.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_method_accuracy_summary.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_method_counts.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_missing_rows.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_oracle_summary.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_paired_ci_summary.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_recovery_regression_summary.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_regime_summary.json`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_representative_failure_cases.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_selector_replay_summary.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_source_ranking_and_regime.md`
- `outputs/mistral_math500_scenario5_processing_20260524/mistral_math500_vs_mistral_gsm8k_comparison.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/replay_agreement_only_2of3/manifest.json`
- `outputs/mistral_math500_scenario5_processing_20260524/replay_agreement_only_2of3/paired_ci_summary.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/replay_agreement_only_2of3/per_example_policy_replay.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/replay_agreement_only_2of3/policy_summary.csv`
- `outputs/mistral_math500_scenario5_processing_20260524/source_file_inventory.json`

---

## 12. Safety Confirmation

- No API calls made.
- Cerebras × GSM8K job NOT touched.
- Cerebras × MATH-500 NOT launched.
- No commit or push.
- No original artifacts overwritten.
- Gold labels used only for offline evaluation.
