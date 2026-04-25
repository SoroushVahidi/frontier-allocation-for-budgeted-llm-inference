# Reasoning diversity bonus diagnostic report

- Label: diagnostic/probe
- Slice: ten_case
- Cases evaluated: 0 method-case rows

## Answers
1. Improvement on 10 deep-dive: see `repair_cases.csv`.
2. Absent-from-tree reduction: compare `absent_from_tree_rate` in `summary.csv`.
3. Present-not-selected reduction: compare `present_not_selected_rate` in `summary.csv`.
4. Actual reasoning diversity: compare operation/role/signature and collapse metrics in `summary.csv`.
5. Most helpful component: inspect `per_decision_reasoning_diversity.jsonl`.
6. Hurt cases: see `hurt_cases.csv`.
7. Missing text reliability limits: see `missing_fields_report.csv`.
8. Candidate status: keep diagnostic/probe unless stable gains are observed across slices.
