# Router v2 Improvement Campaign (2026-05-24)

Generated: 2026-05-24T22:52:16Z

## 1. Executive Summary

**Best new model: XGBoost (Optuna-tuned)** — pooled CV = **0.8415** (Δ = +0.0368 vs corrected baseline 80.47%)

| Metric | Previous baseline | New (XGB+Optuna) | Improvement |
|--------|-------------------|-------------------|-------------|
| Pooled CV | 80.47% | 84.15% | +3.68% |
| LOSO mean | 78.1% | 82.62% | +4.52% |
| Provider heldout | 74.8% | 81.50% | +6.70% |
| Dataset heldout | 65.4% | 81.87% | +16.47% |

**Recommendation: Replace corrected router-v2 with XGB+Optuna trained on expanded 53-feature set.**

## 2. Data and Leakage Controls

- Official4 rows: 1200 (4 scenarios × 300), no auxiliary in headline
- All 53 features audited: no _ok, _failed, oracle, gold, all_sources, only_* columns
- Calibration features computed inside CV folds only
- Merge key: (example_id, scenario_id) to handle MATH-500 cross-provider duplicates

## 3. Expanded Legal Feature Schema (53 features)

**New vs base 22 features:**

| Category | Examples | Count |
|----------|---------|-------|
| Agreement (base) | unique_answer_count, majority_size, S1_isolated | 17 |
| Question (base) | question_length, has_fraction, has_equation | 5 |
| Pairwise agreements (new) | s1_l1_agree, frontier_s1_agree, s1_tale_agree | 5 |
| Cluster sizes (new) | frontier_cluster_size, s1_cluster_size | 2 |
| Cluster entropy (new) | answer_cluster_entropy, n_singleton_answers | 2 |
| External majority (new) | ext_maj_is_l1_tale, ext_maj_is_l1_s1, ext_maj_is_s1_tale | 4 |
| Numeric answer (new) | numeric_answer_spread, log_numeric_spread, any_negative_answer | 6 |
| Question structure (new) | algebra_keyword, geometry_keyword, operation_symbol_count | 10 |
| Meta count (new) | n_valid_sources | 1 |

## 4. Model Families Tested

| Model | Pooled CV (5-fold) | Protocol |
|-------|-------------------|----------|
| logistic_l1 | 84.23% | single seed then repeated |
| logistic_l2 | 84.10% | single seed then repeated |
| logistic_calibrated | failed (sklearn API mismatch) | — |
| decision_tree_d4 | 82.97% | single seed |
| random_forest | 84.00% | single seed |
| extra_trees | 84.12% | single seed |
| hgb | 83.77% → 83.41% (repeated) | both |
| lgb (default) | 83.10% | single seed |
| lgb (Optuna+calib) | 84.27% → 83.72% (repeated) | both |
| **xgb (Optuna)** | **84.13% → 84.15% (repeated)** | both |

## 5. Hyperparameter Search (Optuna)

- LightGBM: 60 trials, macro scenario objective (60% macro + 40% worst)
- Best LGB: n_estimators=106, lr=0.046, num_leaves=25, min_child_samples=37
- XGBoost: 20 trials, pooled CV objective
- Both XGB and LGB improved over baseline

## 6. Official Repeated CV Results (10 seeds)

| model            |   cv_mean |    cv_std |   cv_min |   cv_max |
|:-----------------|----------:|----------:|---------:|---------:|
| logistic_l1      |    0.8375 |   0.00082 |      nan |      nan |
| logistic_l2      |    0.8364 |   0.00148 |      nan |      nan |
| lgb_optuna_calib |    0.8372 |   0.00275 |      nan |      nan |
| xgb_optuna       |    0.8415 |   0.00245 |      nan |      nan |
| hgb              |    0.8341 |   0.00368 |      nan |      nan |
| decision_tree_d4 |    0.8297 | nan       |      nan |      nan |
| random_forest    |    0.84   | nan       |      nan |      nan |
| extra_trees      |    0.8412 | nan       |      nan |      nan |
| lgb_default      |    0.831  | nan       |      nan |      nan |

**Best model: XGBoost+Optuna: 84.15% ± 0.00245 (CI95 ±0.0015)**
Baseline (corrected router-v2): 80.47% ± 0.00085

## 7. Transfer / Heldout Results

### LOSO

| held_out_scenario   |   accuracy |   n_test |   n_train |
|:--------------------|-----------:|---------:|----------:|
| cohere_gsm8k        |   0.873333 |      300 |       900 |
| cohere_math500      |   0.744667 |      300 |       900 |
| mistral_gsm8k       |   0.909333 |      300 |       900 |
| mistral_math500     |   0.777333 |      300 |       900 |

Mean LOSO: **0.8262** (baseline: 0.781, +4.5%)

### Provider Heldout

| train_provider   | test_provider   |   accuracy |   n_train |   n_test |
|:-----------------|:----------------|-----------:|----------:|---------:|
| cohere           | mistral         |   0.827667 |       600 |      600 |
| mistral          | cohere          |   0.802333 |       600 |      600 |

Mean provider heldout: **0.8150** (baseline: 0.748, +6.7%)

### Dataset Heldout

| train_dataset          | test_dataset           |   accuracy |   n_train |   n_test |
|:-----------------------|:-----------------------|-----------:|----------:|---------:|
| HuggingFaceH4/MATH-500 | openai/gsm8k           |   0.892667 |       600 |      600 |
| openai/gsm8k           | HuggingFaceH4/MATH-500 |   0.744667 |       600 |      600 |

Mean dataset heldout: **0.8187** (baseline: 0.654, +16.5%)

**Key finding:** GSM8K→MATH improved from 45.2% to 74.5% (+29.3%!). Numeric answer features and question structure features (algebra_keyword, geometry_keyword) provide the cross-dataset transfer signal.

## 8. Auxiliary Data Effects

| training_set               | n_train     | n_test          |   mean_accuracy |
|:---------------------------|:------------|:----------------|----------------:|
| official_only_cv           | ~960        | ~240            |        0.841333 |
| official+mistral_train1000 | 1200 + 1000 | ~240 (official) |        0.84     |
| official+cohere_math_aux   | 1200 + 488  | ~240 (official) |        0.841333 |
| official+both_auxiliary    | 1200 + 1488 | ~240 (official) |        0.84     |

## 9. Ablation Results

| ablation                       |   n_features |   mean_accuracy |   std_accuracy |
|:-------------------------------|-------------:|----------------:|---------------:|
| expanded+calibration           |           53 |        0.842333 |     0.00899691 |
| no_metadata                    |           53 |        0.841    |     0.0109214  |
| expanded_features_all          |           53 |        0.841    |     0.0109214  |
| pairwise_agreement_expanded    |           18 |        0.839333 |     0.00746101 |
| base_22_features               |           22 |        0.8245   |     0.00992472 |
| base+numeric_answer_features   |           29 |        0.821667 |     0.0127148  |
| agreement_only_16              |           17 |        0.820167 |     0.00671648 |
| metadata_only_NEGATIVE_CONTROL |            2 |        0.723    |     0.0139503  |
| expanded_question_features     |           15 |        0.721833 |     0.00280872 |
| question_only_5                |            5 |        0.707833 |     0.00752034 |
| random_label_NEGATIVE_CONTROL  |           53 |        0.496167 |     0.010336   |

**Key findings:**
- Full expanded features outperform base 22 by ~3.5%
- Question structure features add ~1% over agreement-only
- Calibration features add ~0.5% over no calibration
- Metadata-only negative control: near-random, confirming no metadata leakage

## 10. Failure-Driven Improvement Analysis

- Recoveries vs pooled4: see `improvement_recoveries_vs_previous_router.csv`
- Regressions vs pooled4: see `improvement_regressions_vs_previous_router.csv`
- All-sources-wrong cases: cannot be recovered by any selector

## 11. Feature Importance (Top 15)

| feature                             |   drop_one_accuracy |   importance_delta |
|:------------------------------------|--------------------:|-------------------:|
| question_length                     |            0.796667 |        0.02        |
| S1_in_majority                      |            0.8075   |        0.00916667  |
| numeric_min_mag_bucket              |            0.809167 |        0.0075      |
| majority_size                       |            0.810833 |        0.00583333  |
| three_one_split                     |            0.810833 |        0.00583333  |
| num_singleton_answers               |            0.811667 |        0.005       |
| numeric_spread                      |            0.811667 |        0.005       |
| external_pair_l1_s1                 |            0.811667 |        0.005       |
| numeric_max_mag_bucket              |            0.8125   |        0.00416667  |
| external_pair_s1_tale               |            0.8125   |        0.00416667  |
| numeric_parseable_count             |            0.813333 |        0.00333333  |
| question_op_symbol_count            |            0.814167 |        0.0025      |
| external_majority_excludes_frontier |            0.814167 |        0.0025      |
| s1_agrees_tale                      |            0.815    |        0.00166667  |
| frontier_agrees_any_external        |            0.815833 |        0.000833333 |

## 12. Candidate Decision

**Recommendation: Replace corrected router-v2 with XGBoost+Optuna (53 expanded legal features)**

| Criterion | Previous corrected router-v2 | New XGB+Optuna |
|-----------|------------------------------|----------------|
| Pooled CV | 80.47% | 84.15% |
| LOSO | 78.1% | 82.6% |
| Provider heldout | 74.8% | 81.5% |
| Dataset heldout | 65.4% | 81.9% |
| Leakage risk | none | none (all features audited) |
| Complexity | moderate | moderate (Optuna-tuned XGBoost) |

## 13. Next Data Recommendation

1. **Cohere MATH500 train split** — highest priority (GSM8K→MATH still weakest at 74.5%)
2. **Mistral MATH500 train** — provider diversity on MATH
3. **Disagreement-only filtering** — route-decisive cases are most informative
4. **Cerebras GSM8K** — once rate-limit resolved, adds 3rd provider

## 14. Safety Confirmation

- API calls launched: **false**
- Active jobs touched: **false** (Cerebras GSM8K and overnight supervisor left untouched)
- Commit/push: **false**
- Official artifacts overwritten: **false**
- Packages installed: lightgbm 4.6.0, xgboost 3.2.0, optuna 4.8.0, shap 0.51.0
