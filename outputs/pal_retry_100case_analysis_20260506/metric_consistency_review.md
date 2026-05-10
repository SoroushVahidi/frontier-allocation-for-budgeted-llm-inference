# Metric consistency review

- failed_or_skipped_calls.jsonl empty: **True**
- metric_consistency_audit external consistent rate: **1.000**
- metric_consistency_audit PAL consistent rate: **1.000**
- candidate_strong => exec_ok violations: **2**
- selected-case disjointness against prior exclusions: **True** (intersection=0)

## gold_in_tree / Discovery3 note
- paired_casebook `pal_corrected_gold_in_tree` count: **7**
- raw PAL records `gold_in_tree` count: **91**
- paired_casebook `pal_discovery3` count: **2**
- Assessment: low corrected_gold_in_tree and discovery3 are primarily definition/threshold effects in current summary fields, not evidence of a computation bug.
- Specifically, corrected_gold_in_tree tracks a strict "corrected-when-wrong" subset, not raw gold-in-tree prevalence.
