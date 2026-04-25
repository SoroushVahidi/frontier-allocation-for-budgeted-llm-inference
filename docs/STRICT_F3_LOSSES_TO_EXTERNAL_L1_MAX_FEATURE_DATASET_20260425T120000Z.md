# STRICT_F3 losses-to-external_l1_max feature dataset (20260425T120000Z)

## Scope
- Provider: cohere
- Model: command-r-plus-08-2024
- Dataset: openai/gsm8k
- Seeds: 11, 23
- Budgets: 4, 6, 8
- Comparison: strict_f3 vs external_l1_max

## Answers to required questions
1. strict_f3-loss-to-external_l1_max cases found: **9**.
2. 100 cases reached: **False**.
   - Why not: Only artifact-available matched Cohere GSM8K scored pairs were used (stage1-min slice), yielding fewer than 100 strict_f3-loss cases; no synthetic rows added.
3. Distribution summaries are in `feature_summary.csv` and include budget, operation type, step estimate, failure tags, and gold-in-tree split.
4. Dominant failure patterns (top rows) are in `top_failure_patterns.csv`; dominant failure tag: `unknown`.
5. Loss drivers are decomposed via `strict_f3_failure_tag` and budget/op distributions; budget/depth and unknown failures are explicitly separated in summary artifacts.
6. Concrete controller improvements are listed in `candidate_controller_rules.md`.

## Outputs
- `outputs/strict_f3_loses_to_external_l1_max_feature_dataset_20260425T120000Z/`
- `docs/STRICT_F3_LOSSES_TO_EXTERNAL_L1_MAX_FEATURE_DATASET_20260425T120000Z.md`
