# Outcome Verifier Selector Diagnostic

This diagnostic implements a Cobbe-style *outcome verifier selector* over existing frontier candidates only.

## Guardrails
- No real API calls.
- No manuscript/canonical artifact updates.
- Gold answer equality is used only as an offline training label for leakage-safe evaluation.

## Run
```bash
.venv-test/bin/python scripts/run_outcome_verifier_selector_diagnostic.py
```

## Outputs
- `outputs/outcome_verifier_selector_diagnostic_20260427T021118Z/candidate_answer_groups.csv`
- `outputs/outcome_verifier_selector_diagnostic_20260427T021118Z/candidate_branch_features.csv`
- `outputs/outcome_verifier_selector_diagnostic_20260427T021118Z/selector_summary.csv`
- `outputs/outcome_verifier_selector_diagnostic_20260427T021118Z/per_case_selector_decisions.csv`
- `outputs/outcome_verifier_selector_diagnostic_20260427T021118Z/verifier_training_report.csv`
- `outputs/outcome_verifier_selector_diagnostic_20260427T021118Z/oracle_gap_report.csv`
- `outputs/outcome_verifier_selector_diagnostic_20260427T021118Z/l1_better_subset_selector_report.csv`
- `outputs/outcome_verifier_selector_diagnostic_20260427T021118Z/README.md`
