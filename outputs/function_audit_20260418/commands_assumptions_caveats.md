# Function audit commands, assumptions, and caveats (2026-04-18)

## Commands run

- `pwd; rg --files -g 'AGENTS.md'`
- `find .. -name AGENTS.md -print`
- `sed -n '1,220p' README.md`
- `sed -n '1,260p' docs/CANONICAL_START_HERE.md`
- `sed -n '1,260p' docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`
- `sed -n '1,260p' docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
- `sed -n '1,260p' docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`
- `sed -n '1,260p' docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`
- `sed -n '1,260p' docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md`
- `sed -n '1,260p' docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md`
- `sed -n '1,260p' docs/ORACLE_MISMATCH_STUDY_2026_04_18.md`
- `sed -n '1,260p' docs/FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md`
- `sed -n '1,260p' docs/FULL_METHOD_COMPARISON_STATUS_2026_04_18.md`
- `sed -n '1,280p' scripts/build_bruteforce_target_regimes.py`
- `sed -n '1,320p' scripts/run_oracle_mismatch_study.py`
- `sed -n '1,300p' scripts/run_completion_aware_decision_experiment.py`
- `sed -n '1,260p' scripts/run_multistep_branch_utility_target_experiment.py`
- `sed -n '1,280p' scripts/run_compute_response_curve_experiment.py`
- `sed -n '1,280p' scripts/run_rank_instability_experiment.py`
- `sed -n '1,280p' scripts/run_instability_decision_coupling_experiment.py`
- `rg -n "strategy|multistep_branch_utility_target|discounted_multistep|compute_response_curve_target|rank_instability_target|penalized_marginal_defer|opportunity_intensity_weighted|allocation_regret_target|soft_pair_target|outside|defer|tie" scripts/build_bruteforce_target_regimes.py`

## Assumptions used in this pass

1. Canonical status is determined by explicit 2026-04-18 docs and repeated summary language, not by raw function existence alone.
2. Exploratory function families are preserved and documented, not removed.
3. Completion-aware and instability-aware mechanisms are treated as bounded/local policy layers unless broader replacement evidence appears.
4. The repository is in a target-definition consolidation phase, so consistency and explicitness are prioritized over adding new method families.

## Caveats

- This is a canonicalization/documentation pass; it does not claim new metric improvements.
- Some older scripts still contain alternative formulations for provenance and should not be interpreted as default canonical paths.
- Numeric thresholds and coefficients in exploratory policies remain tunable and are not frozen here as universal constants.
