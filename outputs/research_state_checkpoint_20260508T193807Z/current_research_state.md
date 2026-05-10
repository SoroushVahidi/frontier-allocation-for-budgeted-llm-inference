# Current research state checkpoint

## Repo snapshot
- branch: `research-next-frontier-iteration-2`
- head: `5549682`
- ahead_behind_vs_origin_branch: `0	0`
- modified_tracked_files: 19
- untracked_files: 339
- staged_entries: 0

## Latest key artifacts
- `main_table_core4_baselines_50case_checkpoint_*` -> `outputs/main_table_core4_baselines_50case_checkpoint_20260508T174557Z`
- `core4_50case_parsing_rescore_audit_*` -> `outputs/core4_50case_parsing_rescore_audit_20260508T181119Z`
- `fair_core4_paired_comparison_report_*` -> `outputs/fair_core4_paired_comparison_report_20260508T181853Z`
- `expanded_failure_bank_collection_*` -> `outputs/expanded_failure_bank_collection_20260508T185435Z`
- `nonoverlap_our_method_discovery3_live_*` -> `outputs/nonoverlap_our_method_discovery3_live_20260508T185859Z`
- `discovery3_candidate_diversity_selection_v1_design_*` -> `outputs/discovery3_candidate_diversity_selection_v1_design_20260508T190601Z`
- `discovery3_candidate_diversity_selection_v1_live_pilot_*` -> `outputs/discovery3_candidate_diversity_selection_v1_live_pilot_20260508T191122Z`
- `discovery3_candidate_diversity_selection_v1_parsefix_5case_live_*` -> `outputs/discovery3_candidate_diversity_selection_v1_parsefix_5case_live_20260508T193024Z`
- `discovery3_parsefix_parser_fallback_audit_*` -> `outputs/discovery3_parsefix_parser_fallback_audit_20260508T193503Z`
- `production_equivalence_stage3_50_dry_run_*` -> `outputs/production_equivalence_stage3_50_dry_run_zzzz_latest`

## A. Current best matched-50 comparison
- our patch-focused method: 39/50
- L1 fair: 31/50
- SC4 fair: 33/50
- S1 faithful: 32/50
- TALE-EP faithful: 34/50
- best_core4 oracle: 38/50
- paired vs best_core4: our_only=3, best_core4_only=2, both_correct=36, both_wrong=9

## B. Fair baseline status
- core4 operationally stable on 50 cases
- parsing failures remain unresolved
- SC6/PAL implemented/smoke-tested but not included in matched-50 comparison

## C. Failure-bank status
- expanded matched-50 bank: gold_absent_discovery=9, present_not_selected=2
- non-overlap 30-case bank: our correct 23/30, gold_absent=5, present_not_selected=2
- main repeated bottleneck: candidate discovery, then selection

## D. Discovery3 patch status
- design/dry-run successful
- live 15-case failed: 0/15 exact, 15 parsing failures
- parsefix 5-case failed: 0/5 exact, 3 parsing failures
- conservative parser fallback recovered 0
- recommendation: do not integrate; archive as negative result

## E. Production-equivalence status
- dry-run bridge exists
- live production-equivalent runtime still not complete
- blocking issue remains controller-level integration
