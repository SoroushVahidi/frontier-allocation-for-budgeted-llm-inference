# Previous pilot reinterpretation

The diagnostic CSV cohort for the 66-case slice **does not coincide** with "gold absent everywhere" under a single definition:

- Loader used `discovery_failure_gold_absent OR gold_present_in_candidate_groups==0 OR gold_present_in_tree==0`, which admits cases that are absent in tree but present in pooled candidates (or inconsistent path-gap-derived groups vs post-hoc `selector_candidate_pool` on baseline JSONL).
- Baseline headline counts (gold in DR-v2 `selector_candidate_pool` / reconstructed pool) therefore can be **much higher** than a strict "never appeared in baseline discovery artifact" cohort.

Use **Slice 2 strict baseline-absent** (this script emits `strict_baseline_gold_absent_case_list.csv`) as the equitable discovery-centric evaluation set.
