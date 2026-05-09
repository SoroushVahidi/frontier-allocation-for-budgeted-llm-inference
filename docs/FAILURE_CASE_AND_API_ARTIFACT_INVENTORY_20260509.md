# Failure-case and API artifact inventory (2026-05-09)

This inventory groups migration-critical artifacts by scientific use. Status values are from the local audit and may change after staging. Sizes are approximate `du -sh` values.

## External-only losses

| Artifact group | Path | Status | Size | Raw vs curated | Why it matters | Action | Producer / consumer |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| PAL+retry vs best external selected failures | `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/` | untracked | `63M` | mixed; raw JSONL plus curated reports | 247-ID 4-way collection; 34 preferred PAL-wrong/external-correct rows; 45 selected failure corpus | Archive full bundle; commit selected summaries/casebooks | Produced by `scripts/collect_pal_failure_vs_externals.py`; consumed by `scripts/replay_track_b_commitment_gate.py`, `scripts/materialize_track_b_ab_pilot_bundle.py`, schema/validator scripts |
| PAL-vs-L1 external-only loss collection, completed | `outputs/external_only_loss_collection_pal_vs_l1_completed_20260506T125123Z/` | untracked | `49M` | raw-heavy plus casebooks | External-only losses before newer 4-way bundle; preserves paid PAL/L1 rows | Archive full bundle; optionally summarize | Produced by PAL/L1 collection scripts; consumed by loss/casebook analysis |
| PAL-vs-L1 external-only loss collection round 2 | `outputs/external_only_loss_collection_pal_vs_l1_round2_20260506T130225Z/` | untracked | `47M` | raw-heavy plus casebooks | Additional external-only loss coverage | Archive full bundle | Produced by PAL/L1 collection scripts |
| PAL-vs-L1 external-only loss collection round 3 | `outputs/external_only_loss_collection_pal_vs_l1_round3_20260506T151731Z/` | untracked | `35M` | raw-heavy plus casebooks | Additional external-only loss coverage | Archive full bundle | Produced by PAL/L1 collection scripts |
| Earlier trace-complete external-loss retry | `outputs/trace_complete_external_losses_retry_20260430T204900Z/` | mixed / likely tracked subset | `72M` | raw-heavy | Earlier external-loss traces and selector-evidence material | Archive full bundle; keep curated tracked subset | Produced by trace collection runner; consumed by selector evidence/recovery scripts |

## PAL / PAL+retry failures

| Artifact group | Path | Status | Size | Raw vs curated | Why it matters | Action | Producer / consumer |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| 300-case PAL+retry curated analysis | `outputs/pal_retry_300case_analysis_20260506/` | tracked | `44K` | curated | Claim-safe paired stats: PAL+retry `252/300` vs L1 `244/300`; not decisive | Keep tracked | Produced by offline analysis; consumed by docs and claims |
| 300-case PAL+retry raw run | `outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/` | untracked | `91M` | raw-heavy | Paid API rows backing the 300-case headline | Archive outside Git; commit only selected summaries if needed | Produced by `scripts/materialize_cohere_paired_pal_external_bundle.py` and validation runner |
| Baseline rematerialized 300-case bundle | `outputs/cohere_paired_pal_retry_vs_external_l1_300case_BASELINE_REMAT_20260506/` | untracked | `127M` | raw-heavy | Consistency/rematerialization backing for 300-case comparison | Archive outside Git | Same family as above |
| Poolfix 300-case bundle | `outputs/cohere_paired_pal_retry_vs_external_l1_300case_poolfix_20260506/` | untracked | `127M` | raw-heavy | Poolfix diagnostic for PAL execution pool behavior | Archive outside Git; summarize if referenced | Produced by poolfix/materialization scripts |
| PAL+retry 100-case raw bundle | `outputs/cohere_paired_pal_retry_vs_external_l1_100case_20260506T185133Z/` | untracked | `31M` | raw-heavy | Earlier 100-case comparison; superseded but useful provenance | Archive if storage allows | Same family |
| PAL empty-code retry smoke/followup | `outputs/cohere_pal_empty_code_retry_smoke_5case_20260506T173309Z/`, `outputs/cohere_pal_empty_code_retry_followup_15case_20260506T175516Z/` | untracked | `908K`, `2.0M` | mixed | Shows retry behavior for empty-code PAL cases | Archive or summarize | PAL retry scripts |

## PAL execution-error failures

| Artifact group | Path | Status | Size | Raw vs curated | Why it matters | Action | Producer / consumer |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| External-baseline loss casebook builder fix | `scripts/build_external_baseline_loss_casebook.py`, `tests/test_external_baseline_loss_casebook.py` | modified tracked | n/a | code/test | Real script now emits `pal_error_type` and `pal_error_message`; test calls real script | Commit before migration | Test command: `pytest tests/test_external_baseline_loss_casebook.py -v` |
| PAL error rows in raw bundles | `failed_or_skipped_calls.jsonl`, `pal_results.jsonl`, `per_example_records.jsonl` under PAL/L1 raw bundles | untracked | included above | raw-heavy | Preserves execution failures/timeouts needed for diagnosis | Archive outside Git | Consumed by `scripts/build_external_baseline_loss_casebook.py` |

## Production-vs-PAL failures

| Artifact group | Path | Status | Size | Raw vs curated | Why it matters | Action | Producer / consumer |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| Initial PAL-vs-production casebook live | `outputs/pal_vs_production_equiv_casebook_live_20260508T223635Z/` | untracked | `5.1M` | mixed | Initial PAL/production disagreement collection | Archive; commit report/summary if used | Produced by `scripts/run_pal_vs_production_equiv_casebook_live.py` |
| Multi-batch PAL-vs-production live loop | `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/` | untracked | `14M` | mixed | 135 screened, 75 followup, 3 PAL-only useful cases; shows more data needed | Archive full; commit summary/memo/casebook after review | Produced by `scripts/run_pal_vs_production_multibatch_casebook_live.py` |
| Relaxed multi-batch PAL-vs-production live loop | `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/` | untracked | `28M` | mixed | Cumulative 225 followups, 9 PAL-only useful selector cases; latest source for PAL-hybrid data | Archive full; commit summary/memo/casebook after review | Produced by `scripts/run_pal_vs_production_multibatch_relaxed_live.py` |
| Matched-50 full external suite | `outputs/external_full_suite_matched50_comparison_20260508T222631Z/` | untracked | `24K` | curated | Shows production-equivalent does not beat PAL/PoT fair; important claim-safety correction | Commit after review | Produced by matched external suite comparison scripts |

## Track-B replay failures

| Artifact group | Path | Status | Size | Raw vs curated | Why it matters | Action | Producer / consumer |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| Track-B A/B pilot | `outputs/cohere_track_b_ab_pilot_30case_20260507T204409Z/` | untracked | `7.2M` | mixed | 30-case pilot: Track B `22/30` vs baseline `20/30`, but causal audit says helpful overrides were zero | Archive full; commit `report.md`, `pilot_causal_audit.md`, summaries | Produced by Track-B pilot materialization/validation scripts |
| Offline Track-B replay inside failure collection | `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/track_b_gate_offline_replay_*` | untracked | included in `63M` | curated CSV/JSON/MD | Replay targets and guardrails for present-not-selected cases | Commit selected replay summaries/targets after review | Produced/consumed by `scripts/replay_track_b_commitment_gate.py` |

## Gold-absent / discovery failures

| Artifact group | Path | Status | Size | Raw vs curated | Why it matters | Action | Producer / consumer |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| Gold-absent schema mining | `outputs/gold_absent_external_success_schema_mining_20260507/` | untracked | `56K` | curated | 21 inspected cases, 11 primary external-correct; identifies `multi_step_chain`, target/units/state errors | Commit or vendor minimal CSV under `data/` | Produced by `scripts/mine_gold_absent_external_schema.py`; consumed by target-staged PAL pilot |
| Structural validator eval | `outputs/gsm8k_structural_validator_eval_20260507/` | untracked | `2.2M` | mixed | Shows static structural score is not a good Track-B ranker; useful negative telemetry | Commit small summaries only; archive full if desired | Produced by `scripts/evaluate_gsm8k_structural_validator.py`, `scripts/pal_code_static_audit.py` |
| Tracked failure corpus | `outputs/failure_case_corpus_20260507/` | tracked | `1.7M` | curated | 48-case structured failure corpus and taxonomy seeds | Keep tracked | Produced by `scripts/build_failure_case_corpus.py` |
| PAL discovery deficit atlas | `outputs/offline_pal_discovery_deficit_atlas_20260506/` | tracked | `24K` | curated | Offline discovery failure archetypes | Keep tracked | Produced by `scripts/offline_pal_discovery_deficit_atlas.py` |
| PAL path coverage counterfactual | `outputs/offline_pal_path_coverage_counterfactual_20260506/` | tracked | `20K` | curated | Path-coverage diagnostic | Keep tracked | Produced by `scripts/offline_pal_path_coverage_counterfactual.py` |

## Selector-recoverable cases

| Artifact group | Path | Status | Size | Raw vs curated | Why it matters | Action | Producer / consumer |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| Fully scored selector on 88 external losses | `outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/` | likely tracked/curated subset | `264K` | curated | 88-loss selector rerun with zero missing verifier scores; 22 selector-recoverable vs 66 gold-absent | Preserve/commit curated files if not already | Produced by full selector pipeline |
| L1 defeat selector Wulver result | `outputs/l1_defeat_selector_wulver_20260430T182316Z/` | likely tracked subset | `104K` | curated + some JSONL | Selector evidence on L1 defeat cases | Preserve tracked subset; archive raw if needed | Selector evidence scripts |
| Unified selector evidence | `outputs/unified_selector_evidence_20260501T145906Z/` | likely tracked/curated subset | `416K` | mixed | Unified candidate trace evidence for selector development | Commit curated summary; archive JSONL if needed | `scripts/build_unified_selector_evidence.py` |
| Offline selector sensitivity replay | `outputs/offline_selector_sensitivity_replay_20260507/` | tracked | `20K` | curated | Feature attribution and sensitivity for selector behavior | Keep tracked | `scripts/offline_selector_sensitivity_replay.py` |

## Cached verifier / CMV / self-consistency artifacts

| Artifact group | Path | Status | Size | Raw vs curated | Why it matters | Action | Producer / consumer |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| Outcome verifier selector final/partial folders | `outputs/outcome_verifier_answer_group_selector_*`, `outputs/outcome_verifier_selector_margin_sweep_*` | mixed | small-to-medium | mixed | Cached verifier selector evidence and margin sweeps | Preserve curated summaries; archive caches if present | `scripts/run_outcome_verifier_answer_group_selector.py`, `scripts/run_outcome_verifier_selector_margin_sweep.py` |
| Self-consistency selector recovery | `outputs/self_consistency_majority_selector_recovery_20260501T201910Z/` | mixed | small | curated | Literature selector baseline over fixed candidate pools | Commit summary if referenced | `scripts/run_self_consistency_majority_selector.py` |
| Self-consistency vs selected selector paired | `outputs/self_consistency_vs_selected_selector_paired_20260501T201949Z/` | mixed | small | curated | Same-pilot selector comparison artifact | Commit summary if referenced | selector comparison scripts |
| Self-verification / CMV call plan and scores | `outputs/self_verification_cmv_call_plan_20260501T210232Z/`, `outputs/self_verification_cmv_scores_20260501T210232Z/` | mixed | small | mixed | CMV baseline cost and score evidence | Archive scores; commit concise summary if needed | `scripts/compare_self_verification_selectors.py` |

## Statistical summaries and casebooks

| Artifact group | Path | Status | Size | Raw vs curated | Why it matters | Action | Producer / consumer |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| 300-case statistical summary | `outputs/pal_retry_300case_analysis_20260506/statistical_summary.json`, `paired_statistical_tests.md` | tracked | included in `44K` | curated | Claim-safe uncertainty | Keep tracked | Offline stats scripts |
| Matched-50 external suite summary | `outputs/external_full_suite_matched50_comparison_20260508T222631Z/external_full_suite_summary.json` | untracked | included in `24K` | curated | Latest fair external suite and claim correction | Commit after review | External suite scripts |
| External baseline loss casebook outputs | `external_l1_loss_casebook.csv`, `.jsonl`, generated docs | generated | variable | mixed | Loss taxonomy including PAL execution-error fields | Commit generated summaries only when curated | `scripts/build_external_baseline_loss_casebook.py` |
| Failure pattern mining | `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/failure_pattern_mining_report.md` | untracked | small inside `63M` | curated | Shows 23/34 preferred failures are present-not-selected and 11/34 gold-absent | Commit after review | failure mining scripts |

## Exclude / regenerate

- `_tmp_*` directories
- repeated dry-run folders superseded by live reports
- `__pycache__/`
- raw logs and progress heartbeat files
- cache JSONL unless needed to avoid API reruns
- duplicated timestamped generated docs unless collapsed into a canonical summary

## Minimum preservation checklist

1. Commit this inventory and `docs/MIGRATION_TRANSFER_INDEX_20260509.md`.
2. Commit the casebook script/test fix.
3. Commit or archive `outputs/external_full_suite_matched50_comparison_20260508T222631Z/`.
4. Archive the raw/API-heavy bundles listed above before migration.
5. Do not bulk-add `outputs/`.
