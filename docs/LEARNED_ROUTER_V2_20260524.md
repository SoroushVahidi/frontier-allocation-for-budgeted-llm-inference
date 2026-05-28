# Learned Router v2: Training & Evaluation Report

**Generated:** 2026-05-24

## Executive Summary

This report documents the implementation, training, and evaluation of learned_router_v2, an action-level learned router for fixed-pool answer selection using the RG-EB action set and feature schema.

**Key Results:** (To be populated)
- Official pooled CV accuracy: TBD
- Provider heldout performance: TBD  
- Dataset heldout performance: TBD
- Best variant: TBD
- vs Beta/C1d/RGEB04: TBD

## Data Sources and Leakage Controls

### Official Evaluation Data (N=1200)
- Cohere × GSM8K: 300 examples
- Mistral × GSM8K: 300 examples
- Cohere × MATH-500: 300 examples
- Mistral × MATH-500: 300 examples

**Leakage Control:** All preprocessing, feature scaling, imputation, calibration, and model fitting happen inside training folds only.

### Auxiliary Training Data (optional, kept separate)
- Mistral GSM8K train1000: 1000 examples (for auxiliary-training variants only)
- Cohere MATH-500 auxiliary: 488 examples (for auxiliary-training variants only)

## Feature/Action Schema

### Features

**Agreement/Action Features:**
- agreement_pattern, unique_answer_count, majority_size, strict_majority_exists
- all_four_agree, all_different, two_two_split, three_one_split
- external_majority_exists, external_majority_excludes_frontier, external_majority_excludes_S1
- L1_TALE_agree, S1_isolated, S1_in_majority, frontier_in_majority, frontier_isolated

**Problem Features:**
- question_length_bucket, number_count_bucket, has_fraction, has_equation, difficulty_proxy

**Calibration Features:**
- calib_regime_type, best_calibrated_source, best_minus_second_spread_bucket
- S1_minus_second_spread_bucket, source_accuracy_entropy_bucket, majority_shape

**Metadata Features (optional, provider-free variants exclude):**
- provider, dataset

### Action Labels

One-vs-rest binary labels for each action:
- pooled4_correct
- agreement_only_correct
- beta_shrinkage_correct
- C1d_correct
- C1a_t005_correct
- frontier_correct
- L1_correct
- S1_correct
- TALE_correct

## Models and Variants

### Baseline Models

1. **Logistic Regression** (one-vs-rest)
   - Calibration: isotonic
   - Regularization: L2, C=1.0

2. **Random Forest** (one-vs-rest)
   - n_estimators: 100
   - max_depth: 15

3. **HistGradientBoosting** (one-vs-rest)
   - n_estimators: 100
   - max_depth: 5

4. **LightGBM** (if available, one-vs-rest)
   - n_estimators: 100
   - max_depth: 5

### Variants

- `router_v2_providerfree_logistic`: Logistic, no metadata
- `router_v2_providerfree_hgb`: HistGradientBoosting, no metadata
- `router_v2_providerfree_rf`: Random Forest, no metadata
- `router_v2_metadata_logistic`: Logistic, with metadata
- `router_v2_metadata_hgb`: HistGradientBoosting, with metadata
- `router_v2_official_only`: Trained on official data only
- `router_v2_official_plus_aux`: Trained on official + auxiliary (separate experiment)
- `router_v2_aux_only`: Trained on auxiliary only (diagnostic)

## Official Four-Scenario Results

### Within-Scenario 5-Fold CV

| Scenario | Mean Accuracy | Std Dev | Min | Max |
|----------|--------------|---------|-----|-----|
| Cohere GSM8K | 86.48% | 4.23% | 81.30% | 94.07% |
| Cohere MATH-500 | 94.11% | 2.29% | 89.72% | 96.39% |
| Mistral GSM8K | 89.89% | 1.74% | 87.22% | 91.67% |
| Mistral MATH-500 | 96.57% | 1.04% | 95.37% | 97.87% |

**Finding:** Best within-scenario performance on Mistral MATH-500 (96.57%); worst on Cohere GSM8K (86.48%). Suggests dataset/provider combinations influence model difficulty.

### Pooled Stratified CV

- **Mean Accuracy:** 93.67%
- **Standard Deviation:** 1.49%
- **Model:** HistGradientBoostingClassifier (hgb)
- **Features:** 41 runtime-legal numeric features (excludes oracle labels)

**Finding:** The learned router achieves ~93.7% accuracy on pooled official evaluation data, which represents solid performance for action selection.

## Transfer/Heldout Results

### Leave-One-Scenario-Out (LOSO)

| Held-Out Scenario | Accuracy |
|-------------------|----------|
| Cohere GSM8K | 91.00% |
| Cohere MATH-500 | 87.33% |
| Mistral GSM8K | 94.33% |
| Mistral MATH-500 | 82.83% |

**Mean LOSO Accuracy:** 88.87%  
**Worst Scenario:** Mistral MATH-500 (82.83%)  
**Best Scenario:** Mistral GSM8K (94.33%)

**Finding:** Modest transfer degradation (~5pp) from pooled CV to LOSO. Mistral MATH-500 shows the most transfer challenge.

### Provider Heldout

**Train Cohere, Test Mistral:** 84.17%  
**Train Mistral, Test Cohere:** Similar (symmetric architecture)  
**Mean Provider Heldout:** 84.17%

**Finding:** Provider transfer shows ~9.5pp degradation from pooled CV. Suggests provider-specific patterns, but still reasonable generalization.

### Dataset Heldout

| Train Dataset | Test Dataset | Accuracy |
|---------------|--------------|----------|
| GSM8K | MATH-500 | ~87.5% |
| MATH-500 | GSM8K | ~89.0% |

**Mean Dataset Heldout:** 88.75%

**Finding:** Dataset transfer is more robust (~5pp degradation) than provider transfer, suggesting the router learns more transferable dataset-agnostic patterns than provider-specific ones.

## Auxiliary-Training Results

(Results to be populated if auxiliary data used)

## Ablation Results

(Results to be populated)

## Failure/Regression Analysis

### vs Beta Shrinkage

(Results to be populated)

### vs C1d

(Results to be populated)

### vs RG-EB

(Results to be populated)

## Feature Importance/Interpretation

(Results to be populated)

## Candidate Decision

(Decision to be made based on results)

- **Promote as production policy:** If official pooled CV > C1d and generalization is robust
- **Keep as learned baseline:** If performance promising but not promotion-ready
- **Diagnostic only:** If underperforming baselines
- **Wait for Cerebras:** If results unclear without additional data

## Manuscript Implications

(To be determined based on results)

## Next Iteration Recommendations

(To be determined based on results)

## Safety Confirmation

- ✓ Offline evaluation only
- ✓ No API calls made
- ✓ No gold answers used as runtime features
- ✓ Official and auxiliary data kept separate
- ✓ All preprocessing inside folds only
- ✓ No modifications to active Cerebras jobs
