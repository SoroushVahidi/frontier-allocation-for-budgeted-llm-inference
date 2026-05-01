# Candidate fix recommendations

- Most absent-from-tree losses are: **trace_unavailable**.
- Correct reasoning region entered rate: **0.000**.
- Promising-branch-abandoned proxy count: **0** (near-miss absent-final).
- Early-commit proxy count: **0**.
- Concentration by budget/seed/dataset/problem type: see `by_budget_summary.csv`, `by_seed_summary.csv`, `by_dataset_summary.csv`, `by_problem_type_summary.csv`.
- Cost inefficiency check: see `cost_latency_summary.csv` (`internal_more_costly_rate`).
- Most justified controller change:
- Prefer delayed commit with additional continuation when prefix coverage is medium/high but final answer is absent.

## Top 3 recommended fixes
- Prefer delayed commit with additional continuation when prefix coverage is medium/high but final answer is absent.
- Add direct-path fallback when immediate misses dominate and correct region is not entered.
- Tune anti-collapse/continuation scoring to keep promising branches alive in near-miss absent-final cases.
