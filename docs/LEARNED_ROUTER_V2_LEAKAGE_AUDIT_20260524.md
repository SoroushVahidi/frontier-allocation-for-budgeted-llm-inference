# Learned Router v2: Forensic Leakage Audit Report

**Audit Date:** 2026-05-24 17:06 UTC  
**Status:** ❌ **INVALID - CRITICAL LEAKAGE DETECTED**

---

## Executive Summary

**CRITICAL FINDING:** The reported learned_router_v2 results (93.67% pooled CV) are **INVALID due to oracle/gold leakage**. The model was trained with four columns that directly encode whether actions are correct, using gold answer comparisons:

- `all_sources_correct` - all four sources give correct answer
- `all_sources_wrong` - all four sources give wrong answers  
- `only_L1_correct` - only L1 gives correct answer
- `only_S1_correct` - only S1 gives correct answer

When these leaky columns are removed and replaced with runtime-legal features only:

| Metric | Leaky | No-Leakage | Delta |
|--------|-------|-----------|-------|
| **Pooled CV** | 93.67% | 83.94% | **-9.73pp** |
| **Within-scenario** | 91.76% | 86.04% | **-5.72pp** |
| **LOSO** | 88.88% | 76.38% | **-12.50pp** |
| **Provider heldout** | 84.17% | 73.39% | **-10.78pp** |
| **Dataset heldout** | 88.75% | 68.17% | **-20.58pp** |

**Conclusion:** The 93.67% result is **NOT VALID**. The model was learning oracle patterns, not predictive features.

---

## 1. Feature-Column Audit

### Declared Features in Schema (41 total)

The `feature_schema_full.json` claimed to use:
```
L1_TALE_agree, S1_in_majority, S1_isolated, all_different, all_four_agree,
all_sources_correct, all_sources_wrong, external_majority_excludes_S1,
external_majority_excludes_frontier, external_majority_exists,
external_majority_size, frontier_in_majority, frontier_isolated,
has_equation, has_equation_feat, has_fraction, has_fraction_feat,
has_majority, majority_size, majority_size_feat, no_majority_flag,
only_L1_correct, only_S1_correct, question_has_equation_flag,
question_length, question_length_bucket, question_number_count,
strict_majority_exists, three_one_split, three_one_split_feat,
two_two_split, two_two_split_feat, ...
```

### Leaky Columns Identified

✓ **CONFIRMED LEAKAGE:** The following oracle/gold columns ARE in the schema:

| Column | Meaning | Leakage Type |
|--------|---------|--------------|
| `all_sources_correct` | All 4 sources correct (vs gold) | Oracle correctness |
| `all_sources_wrong` | All 4 sources wrong (vs gold) | Oracle correctness |
| `only_L1_correct` | Only L1 correct (vs gold) | Source-specific oracle |
| `only_S1_correct` | Only S1 correct (vs gold) | Source-specific oracle |

These columns are derived from comparing candidate answers to gold answers and directly encode whether actions are correct.

### Leaky Columns in Source Data

The source data (rg_eb_official4_case_table.csv) contains 35 leaky columns:
- 4 source correctness columns (`frontier_ok`, `L1_ok`, `S1_ok`, `TALE_ok`)
- 4 source failure indicators (`frontier_failed`, `L1_failed`, `S1_failed`, `TALE_failed`)
- 9 action correctness labels (`pooled4_ok`, `agreement_only_ok`, etc.)
- 4 oracle labels (`only_frontier_correct`, `only_L1_correct`, etc.) ⚠️
- Plus decision columns and answer columns

**ALL 4 CRITICAL ORACLE LABELS MADE IT INTO THE FEATURE SCHEMA.**

---

## 2. Correctness/Gold/Oracle Leakage Audit

### What These Columns Encode

```python
all_sources_correct[i] = 1 if (frontier_ok[i] AND L1_ok[i] AND S1_ok[i] AND TALE_ok[i]) else 0
all_sources_wrong[i] = 1 if (NOT frontier_ok[i] AND NOT L1_ok[i] AND NOT S1_ok[i] AND NOT TALE_ok[i]) else 0
only_L1_correct[i] = 1 if (L1_ok[i] AND NOT frontier_ok[i] AND NOT S1_ok[i] AND NOT TALE_ok[i]) else 0
only_S1_correct[i] = 1 if (S1_ok[i] AND NOT frontier_ok[i] AND NOT L1_ok[i] AND NOT TALE_ok[i]) else 0
```

where `frontier_ok = (frontier_ans == gold)` etc.

These directly encode which actions/sources are correct by comparing to gold.

### How the Model Exploited This

The model learned patterns like:
- "If `all_sources_correct == 1`, any action is correct" 
- "If `only_L1_correct == 1`, choose L1"
- "If `all_sources_wrong == 1`, guess any action"

This explains why the model achieves ~91% accuracy using **only these 4 leaky columns**:

```
Leaky-only CV accuracy: 0.9128 (vs reported 0.9367)
```

The model didn't learn to make decisions from legal features; it memorized correctness patterns.

---

## 3. Split/Preprocessing Audit

### Train/Test Split Safety

The script used `StratifiedKFold` with `shuffle=True`, which is good. However:
- All 4 leaky columns are **oracle labels computed before the split**
- These labels are **identical for all folds** (not recomputed inside folds)
- The split only affects which rows see which labels in training/testing
- But the labels themselves encode ground truth, causing universal leakage

### Preprocessing Leakage

**Acknowledged:** Scaler was fit inside CV folds (good practice). But this doesn't matter when the features themselves are oracle labels.

---

## 4. Oracle Ceiling Analysis

### Oracle Accuracy vs Learned Router

For the same evaluation set:

| Evaluation | Oracle Action | Leaky Router | Correct Action |
|-----------|-----------------|--------------|-----------------|
| Pooled CV | Can't exceed 100% | 93.67% | ✓ Router ≤ oracle |
| LOSO | Varies by scenario | 88.88% | ? |

When router accuracy is so close to oracle ceiling (93.67% on 1200 examples across 4 scenarios), it's suspicious. The presence of oracle columns explains this.

---

## 5. Corrected No-Leakage Results

### Feature Set Used in Corrected Model

**23 runtime-legal features:**
```
L1_TALE_agree, S1_in_majority, S1_isolated, all_different, all_four_agree,
external_majority_excludes_S1, external_majority_excludes_frontier,
external_majority_exists, external_majority_size, frontier_in_majority,
frontier_isolated, has_equation, has_fraction, has_majority, majority_size,
no_majority_flag, question_has_equation_flag, question_length,
question_number_count, strict_majority_exists, three_one_split,
two_two_split, unique_answer_count
```

**Excluded 43 leaky/oracle columns:**
- All `_ok`, `_failed`, `_ans`, `_decision` columns
- All oracle labels (`all_sources_correct`, `only_*_correct`, etc.)
- Gold answer and reference columns
- Provider/dataset metadata (for provider-free variant)

### Corrected Results

**Pooled Stratified 5-Fold CV:**
- **Accuracy: 83.94% ± 0.89%**
- Much more in line with baselines (beta/C1d ~65%, agreement_only ~63%)
- Model performs meaningfully better than baselines (+19-21pp), but not suspiciously so

**Within-Scenario CV:**
- Mean: 86.04% (vs 91.76% leaky)
- More reasonable per-scenario variation

**Transfer/Heldout:**
- LOSO: 76.38% (vs 88.88% leaky) - **-12.5pp degradation**
- Provider: 73.39% (vs 84.17% leaky) - **-10.8pp degradation**
- Dataset: 68.17% (vs 88.75% leaky) - **-20.6pp degradation**

**Interpretation:** 
- Significant transfer degradation on dataset/provider heldout suggests the model learned some provider/dataset-specific patterns
- But this is expected with limited data (300 examples per scenario)
- Results are now credible

---

## 6. Leakage Stress Tests

### Test A: Leaky Columns Alone

**Just the 4 leaky columns, no other features:**
```
Pooled CV accuracy: 0.9128 (91.28%)
```

**vs reported full model: 0.9367 (93.67%)**

Conclusion: Leaky columns alone account for ~98% of reported performance. The remaining 37 "legal" features contributed minimal additional accuracy.

### Test B: Legal Features Only (No Leaky Columns)

**Just 23 legal features, no oracle labels:**
```
Pooled CV accuracy: 0.8394 (83.94%)
```

Conclusion: Without leakage, realistic accuracy is 83.94%.

---

## 7. Root Cause Analysis

### How Leakage Entered

1. **RG-EB source data** (`rg_eb_official4_case_table.csv`) includes oracle/gold-derived columns for analysis
2. **Router v2 feature engineering** in `get_numeric_features()` selected ALL numeric columns by type, with insufficient filtering
3. **No explicit exclusion list** for oracle columns - the script only tried to avoid a few obvious patterns
4. **Feature schema not validated** before training - schema includes leaky columns without review

### Why It Wasn't Caught

- Leaky column names are plausible ("all_sources_correct" looks like a business metric)
- The reported accuracy (93.67%) seemed reasonable without a baseline for comparison
- No oracle ceiling check before accepting results
- No systematic feature whitelist review

---

## 8. Final Validity Decision

### Original (Leaky) Results

| Claim | Validity |
|-------|----------|
| Pooled CV: 93.67% | ❌ **INVALID** |
| Within-scenario: 91.76% | ❌ **INVALID** |
| LOSO: 88.88% | ❌ **INVALID** |
| Provider heldout: 84.17% | ❌ **INVALID** |
| Dataset heldout: 88.75% | ❌ **INVALID** |

**Reason:** Model trained with oracle/gold labels as features.

### Corrected (No-Leakage) Results

| Metric | Valid Accuracy | vs Baselines |
|--------|-----------------|--------------|
| Pooled CV | **83.94%** | +19-21pp vs beta/C1d/RGEB (~65%) |
| Provider heldout | **73.39%** | -10.6pp vs leaky version |
| Dataset heldout | **68.17%** | -20.6pp vs leaky version |

**Reason:** Model trained with runtime-legal features only, no oracle leakage.

**Conclusion:** Corrected results show meaningful but modest improvement over baselines. Performance degrades significantly on cross-domain held-outs, suggesting the model relies on some dataset-specific patterns.

---

## 9. Recommendations

### Immediate Actions

1. ❌ **Do NOT promote original learned_router_v2 results** (93.67% is invalid)
2. ✅ **Use corrected no-leakage results** (83.94% pooled CV) if proceeding
3. ✅ **Add leakage audit to standard test suite**

### Process Improvements

1. **Feature whitelist:** Maintain explicit whitelist of runtime-legal features per domain
2. **Oracle ceiling check:** Before accepting high results, compute oracle action/source accuracy on same rows
3. **Feature name audit:** Scan feature names for oracle patterns before training
4. **Leakage tests:** Include "leaky columns only" stress test as part of validation

### Next Steps

1. If 83.94% (corrected) is acceptable, prepare manuscript with corrected results and leakage discussion
2. Consider auxiliary data or feature engineering to improve dataset/provider transfer
3. Retrain with corrected features in high-confidence setting for final results

---

## 10. Safety Confirmation

- ✓ Audit completed offline only
- ✓ No API calls made
- ✓ No active Cerebras jobs touched
- ✓ Original artifacts preserved (no deletions)
- ✓ No commits/pushes made
- ✓ Corrected scripts created for reproducibility

---

## 11. Files Created

**Audit Outputs:**
- `outputs/learned_router_v2_leakage_audit_20260524/feature_audit_inventory.json`
- `outputs/learned_router_v2_leakage_audit_20260524/feature_usage_audit.json`
- `outputs/learned_router_v2_leakage_audit_20260524/no_leakage_*.csv` (5 evaluation tables)
- `outputs/learned_router_v2_leakage_audit_20260524/corrected_training_*.log`
- `outputs/learned_router_v2_leakage_audit_20260524/features_no_leakage.json`

**Corrected Script:**
- `scripts/train_learned_router_v2_no_leakage.py`

**This Report:**
- `docs/LEARNED_ROUTER_V2_LEAKAGE_AUDIT_20260524.md`

---

## Appendix: Leaky vs Clean Feature Comparison

### Full Leaky Feature Schema (41 features)
```json
[
  "L1_TALE_agree", "S1_in_majority", "S1_isolated", "all_different", "all_four_agree",
  "all_sources_correct",           ⚠️ ORACLE LABEL
  "all_sources_wrong",             ⚠️ ORACLE LABEL
  "external_majority_excludes_S1", "external_majority_excludes_frontier",
  "external_majority_exists", "external_majority_size", "frontier_in_majority",
  "frontier_isolated", "has_equation", "has_equation_feat", "has_fraction",
  "has_fraction_feat", "has_majority", "majority_size", "majority_size_feat",
  "no_majority_flag",
  "only_L1_correct",               ⚠️ ORACLE LABEL
  "only_S1_correct",               ⚠️ ORACLE LABEL
  "question_has_equation_flag", "question_length", "question_length_bucket",
  "question_number_count", "strict_majority_exists", "three_one_split",
  "three_one_split_feat", "two_two_split", "two_two_split_feat",
  ... (more duplicates with _feat suffix)
]
```

### Clean Feature Schema (23 features)
```json
[
  "L1_TALE_agree", "S1_in_majority", "S1_isolated", "all_different", "all_four_agree",
  "external_majority_excludes_S1", "external_majority_excludes_frontier",
  "external_majority_exists", "external_majority_size", "frontier_in_majority",
  "frontier_isolated", "has_equation", "has_fraction", "has_majority",
  "majority_size", "no_majority_flag", "question_has_equation_flag",
  "question_length", "question_number_count", "strict_majority_exists",
  "three_one_split", "two_two_split", "unique_answer_count"
]
```

---

**Audit Status: COMPLETE ✓**  
**Result Validity: ❌ INVALID (LEAKAGE DETECTED)**  
**Corrected Result: ✅ 83.94% (VALID, NO LEAKAGE)**
