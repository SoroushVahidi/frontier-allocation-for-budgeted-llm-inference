# Comparison across paired GSM8K runs

| Run | Cases | External | PAL / PAL+retry | Gap (pp) | Notes |
|---|---:|---:|---:|---:|---|
| No-retry paired (prior) | 100 | 75% | PAL 80% | +5.0 | Earlier slice; cohort differs |
| PAL+retry fresh (prior) | 100 | 85% | PAL+retry 84% | -1.0 | Different sample IDs; headline external higher |
| **PAL+retry (this)** | **300** | **81.33%** | **84.00%** | **+2.67** | **Preferred single headline estimate** |

Interpretation:
- Absolute accuracies drift across cohorts (`external_l1_max` swung between **75%** and **85%** on two 100-case draws), illustrating **sample variance** on modest `n`.
- The **300-case** run pairs both methods on the **same contiguous fresh ID band** (`openai_gsm8k_772`–`1071`) with zero overlap to earlier selected IDs; treat it as the **strongest current paired estimate**.
