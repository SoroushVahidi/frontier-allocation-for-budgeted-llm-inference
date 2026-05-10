# Non-overlap discovery3 live report

- Ran our method live on 30 non-overlap casebook cases (matched-50 excluded).
- Non-overlap exclusion confirmed against selected_50case_core4_baseline_cases.csv.
- Accuracy: 23/30.
- Discovery3: gold_absent=5, present_not_selected=2, parse_failure=0, runtime_failure=0.
- Main families: {'state_update': 14, 'unknown': 13, 'ratio_setup': 2, 'final_target_mismatch': 1}.
- Pattern repeat check: gold-absent and selection failures remain dominant, consistent with prior matched-50 findings.
- More data needed: no for initial pattern discovery; yes for broad generalization.
- Recommended next direction: design candidate-diversity + selection-policy patch and run focused 15-case confirmation pilot
- Caveats: baseline fields are reused from casebook snapshots, not freshly rerun in this stage.
