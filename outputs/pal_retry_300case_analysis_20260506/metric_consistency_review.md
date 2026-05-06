# Metric consistency review (300-case materialization)

- failed/skipped_calls empty: **True** (`0` non-empty lines).
- Materialization consistency JSON: `{'paired_rows_match_summary': True, 'pair_outcomes_match_summary': True, 'failed_count_matches_file': True, 'call_cap_respected': True, 'selected_disjoint_from_prior_used_ids': True, 'selected_overlap_count_with_prior': 0}`
- `metric_consistency_audit` external canonical agreement rate: **1.000**
- PAL canonical agreement rate: **1.000**
- **`pal_candidate_strong` ⇒ `pal_exec_ok`** violations in paired_casebook: **12**

## Field-definition caveats
- `paired_casebook.csv` **`retry_enabled`** column is **incorrectly all-zero** despite retries running (`pal_empty_code_retry_*` fields in raw JSON resolve this); **do not trust that CSV column**, use raw `pal_execution` or derived `statistical_summary.json`.
- **`pal_corrected_gold_in_tree`** describes a conditioned diagnostic (approximately: incorrect final but gold reachable somewhere in the surfaced tree/trace), distinct from unconditional **gold containment** narratives.
- **Exact ⇒ gold-in-tree implication** is directional only after defining how `gold_absent` is computed for this pipeline; violating rows would contradict materialization QA but were not enumerated here.

## Internal retry metric consistency
- Raw-derived retry-enabled count (**300**) is consistent with method configuration (PAL runs with retry policy available). 
- Retry ran (**16**) aligns with nonzero `pal_empty_code_retry_ran` in PAL metadata.
