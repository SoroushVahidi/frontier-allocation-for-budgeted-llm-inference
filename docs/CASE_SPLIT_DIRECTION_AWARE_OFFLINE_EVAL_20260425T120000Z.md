# CASE_SPLIT_DIRECTION_AWARE_OFFLINE_EVAL_20260425T120000Z

## Setup
- Output directory: `outputs/case_split_direction_aware_offline_eval_20260425T120000Z/`.
- Datasets: openai/gsm8k, HuggingFaceH4/MATH-500, HuggingFaceH4/aime_2024.
- Budgets: 4, 6, 8.
- Seeds: 11, 23, 37, 41, 53.

## Answers to required questions
1. Overall improvement over strict_f3: delta = -0.0133.
2. Improvement on detected counting/case-split subset: delta = -0.0061.
3. Absent-from-tree reduction: delta = +0.0145 (negative is better).
4. Non-case-split harm check: delta = -0.0238.
5. Versus strict_gate1_cap_k6 / strict_f3_anti_collapse_weak_v1: deltas = +0.0042, -0.0121.
6. Versus external_l1_max on matched offline budget: delta = +0.1067.
7. Manuscript candidacy threshold check (>=1pp): appendix_or_exploratory.
8. Failure interpretation: see `failure_decomposition.csv` and `pairwise_comparisons.csv` for where gains/losses concentrate.
