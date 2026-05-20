# RelationReady seed pool v0

Purpose
- Extract a small, clean pool of positive candidate rows that are safe to use as parents for synthetic corruption.
- Keep seed extraction separate from corruption generation so filtering rules stay explicit and auditable.

Input expectation
- Candidate-level rows with a formula surface, such as `candidate_formula`, `solution_formula`, `formula_text`, or `equation`.
- Positive RelationReady label fields such as `relation_ready_label`, `accept`, or `is_positive`.
- A split field such as `split` or `suggested_split`.

Selection rules
- Keep only positive rows.
- Drop prompt/gold inconsistent rows.
- Keep only allowed splits (default: train/val/test).
- Allow explicit case-id exclusions for held-out slices or any other quarantined set.
- Keep only rows with an actual formula string.

Output
- `seed_rows.jsonl`
- `seed_rows.csv`
- `seed_summary.json`
- `seed_report.md`

How it is used
- The corruption pool runner consumes these seed rows and generates synthetic negatives from them.

Limitations of v0
- No semantic execution or learned ranking.
- No automatic discovery of held-out slices beyond explicit exclusions and split filtering.
- Intended as a deterministic scaffold, not a final curation policy.
