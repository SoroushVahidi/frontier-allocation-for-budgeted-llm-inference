# Expanded failure bank collection report

- Collected rows: 50 (selected=50), using existing artifacts only.
- Call budget used: 0 / 250 (all records reused).
- Our wrong: 11; our wrong while best core4 right: 2; both wrong: 9.
- Discovery3 counts: gold_absent=9, present_not_selected=2, parse_failure=0.
- Most common families: {'state_update': 15, 'unknown': 20, 'ratio_setup': 10, 'final_target_mismatch': 4, 'percent_base': 1}.
- Most common proposed fixes: {'none': 39, 'selection policy + final-target verifier': 2, 'expand candidate diversity / decomposition': 9}.
- More data needed: yes for non-overlap cases; current bank is deep on matched-50 but not broader distribution.
- Recommended next step: run_our_method_on_new_nonoverlap_casebook_subset_with_discovery3_logging
- Caveats: no new live calls in this stage; production-equivalent runtime still not represented in live matched evidence.
