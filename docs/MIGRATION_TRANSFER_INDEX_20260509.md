# Migration transfer index (2026-05-09)

Purpose: preserve scientifically important local work before migrating away from this machine. This is a transfer checklist, not a claim-promotion document. Do not infer broad superiority over `external_l1_max` from any single artifact below.

## Current repository state

- Branch: `research-next-frontier-iteration-2`
- Local branch state at audit time: ahead of `origin/research-next-frontier-iteration-2` by 1 commit.
- Uncommitted tracked fixes:
  - `scripts/build_external_baseline_loss_casebook.py`
  - `tests/test_external_baseline_loss_casebook.py`
- Untracked paths: about `4,726`, mostly under `outputs/`.
- Local identity checked earlier: OS user `soroush`; GitHub CLI account `SoroushVahidi`.

## Latest active method

Active internal engineering line:

```text
direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal
```

Shorthand: PAL+retry / guarded PAL.

Track B, structural commit, adaptive router, and `production_equiv_v1` variants are experimental follow-on lines unless a later promotion document says otherwise. Production-equivalent work is currently best treated as diagnostic/runtime-integration evidence, not as the active headline method.

## Latest external-baseline comparison result

Primary PAL+retry vs `external_l1_max` evidence:

- Curated tracked summary: `outputs/pal_retry_300case_analysis_20260506/`
- Raw/API-expensive source bundle: `outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/`
- PAL+retry: `252/300`
- `external_l1_max`: `244/300`
- Paired gap: `+8` cases, about `+2.67 pp`
- McNemar-style p-value: about `0.322`
- Bootstrap 95% paired-difference CI: includes zero
- Safe interpretation: directionally positive / competitive, but not statistically decisive.

Latest matched-50 external-suite result:

- Local untracked summary: `outputs/external_full_suite_matched50_comparison_20260508T222631Z/` (`24K`)
- `production_equiv_v1`: `36/50`
- `external_l1_max_fair_v1`: `31/50`
- `external_self_consistency_4_fair_v1`: `33/50`
- `external_self_consistency_6_fair_v1`: `36/50`
- `external_pal_pot_fair_v1`: `40/50`
- `external_s1_budget_forcing_faithful_v1`: `32/50`
- `external_tale_ep_prompt_budgeting_faithful_v1`: `34/50`
- Safe interpretation: production-equivalent beats several fair baselines, ties SC6, and trails PAL/PoT fair on that slice.

## Current external baseline list

Use these current fair/adapted baseline IDs for May 2026 external-suite references:

- `external_l1_max_fair_v1`
- `external_self_consistency_4_fair_v1`
- `external_self_consistency_6_fair_v1`
- `external_pal_pot_fair_v1`
- `external_s1_budget_forcing_faithful_v1`
- `external_tale_ep_prompt_budgeting_faithful_v1`
- Derived analysis-only comparators: `best_individual_external`, `best_full_external_oracle`, `best_core4_oracle`

Older docs may still mention `external_l1_max`, `external_tale_prompt_budgeting`, `external_s1_budget_forcing`, and `external_l1_exact`. Treat those as historical or compatibility names unless the manifest for a specific run uses them.

## Git-suitable artifacts to preserve

These are small enough for Git after review:

| Path | Status | Size | Why preserve | Action |
| --- | --- | ---: | --- | --- |
| `outputs/pal_retry_300case_analysis_20260506/` | tracked | `44K` | Curated 300-case PAL+retry vs L1 statistics and claim-safe summary | Keep tracked |
| `outputs/external_full_suite_matched50_comparison_20260508T222631Z/` | untracked | `24K` | Latest matched-50 fair external-suite comparison and claim correction | Commit after review |
| `outputs/gold_absent_external_success_schema_mining_20260507/` | untracked | `56K` | Schema/failure-mode mining feeding target-staged PAL retry | Commit or vendor minimal CSV under `data/` |
| Selected files from `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/` | untracked | part of `63M` | 247-ID failure collection, 45-case selected corpus, Track-B replay summaries | Commit only reports/summaries/selected CSVs |
| Selected files from `outputs/cohere_track_b_ab_pilot_30case_20260507T204409Z/` | untracked | part of `7.2M` | Track-B A/B result plus causal audit showing non-causal override caveat | Commit report/audit/summary only |
| `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/` summaries | untracked | part of `14M` | PAL-vs-production disagreement collection; first loop exhausted eligible cases | Commit summary/report/memo/casebook after review |
| `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/` summaries | untracked | part of `28M` | Relaxed PAL-vs-production collection; cumulative useful cases count | Commit summary/report/memo/casebook after review |

## Raw/API-expensive artifacts to archive outside Git

Archive these before migration. They contain paid API generations, per-example records, raw results, logs, or failure traces.

| Path | Status | Size | Why archive |
| --- | --- | ---: | --- |
| `outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/` | untracked | `91M` | Canonical raw backing bundle for 300-case PAL+retry vs L1 |
| `outputs/cohere_paired_pal_retry_vs_external_l1_300case_BASELINE_REMAT_20260506/` | untracked | `127M` | Baseline rematerialization / consistency backing bundle |
| `outputs/cohere_paired_pal_retry_vs_external_l1_300case_poolfix_20260506/` | untracked | `127M` | Poolfix comparison bundle |
| `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/` | untracked | `63M` | 247-ID 4-way result rows and selected failure corpus |
| `outputs/trace_complete_external_losses_retry_20260430T204900Z/` | mixed / likely tracked subset | `72M` | Earlier external-loss traces and selector-evidence raw records |
| `outputs/external_only_loss_collection_pal_vs_l1_completed_20260506T125123Z/` | untracked | `49M` | External-only PAL-vs-L1 loss collection |
| `outputs/external_only_loss_collection_pal_vs_l1_round2_20260506T130225Z/` | untracked | `47M` | External-only PAL-vs-L1 round 2 collection |
| `outputs/external_only_loss_collection_pal_vs_l1_round3_20260506T151731Z/` | untracked | `35M` | External-only PAL-vs-L1 round 3 collection |
| `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/` | untracked | `14M` | Raw PAL screen and production followup rows |
| `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/` | untracked | `28M` | Raw relaxed loop rows and cumulative casebook |
| `outputs/cohere_track_b_ab_pilot_30case_20260507T204409Z/` | untracked | `7.2M` | Raw 30-case Track-B A/B per-example records |

Raw files to keep out of Git unless explicitly reviewed: `per_example_records.jsonl`, `pal_results.jsonl`, `external_l1_results.jsonl`, `all_results.jsonl`, `progress_heartbeat.jsonl`, `failed_or_skipped_calls.jsonl`, `raw/failures.jsonl`, `live_run.log`, runner stdout/stderr logs, and cache JSONL files.

## Local-only clutter

Generally exclude from Git:

- `_tmp_*` output folders
- repeated dry-run folders that have superseding reports
- `__pycache__/`
- old timestamped `docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_*.md` files unless collapsed into one curated summary
- `local_patches/` unless a patch is intentionally preserved
- raw logs, caches, and heartbeat JSONL

## Code and tests to transfer

Must be reviewed and pushed if this line should survive migration:

- `scripts/build_external_baseline_loss_casebook.py`
- `tests/test_external_baseline_loss_casebook.py`
- `experiments/gsm8k_structural_validate.py`
- `scripts/evaluate_gsm8k_structural_validator.py`
- `scripts/track_a_discovery_diagnostics.py`
- `scripts/pal_code_static_audit.py`
- `scripts/mine_gold_absent_external_schema.py`
- `experiments/target_staged_pal_pilot_dry_run.py`
- `experiments/target_staged_pal_pilot_manifest.py`
- `experiments/target_staged_pal_pilot_runner.py`
- `experiments/target_staged_pal_prompt.py`
- `manifests/target_staged_pal_retry_primary_11_20260507.json`
- `prompts/target_staged_pal_retry/`
- matching tests under `tests/test_gsm8k_structural_*` and `tests/test_target_staged_pal_*`

## Exact next commands

Archive outside Git first:

```bash
mkdir -p ../migration_artifacts_20260509
tar -czf ../migration_artifacts_20260509/api_expensive_outputs_20260509.tgz \
  outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z \
  outputs/cohere_paired_pal_retry_vs_external_l1_300case_BASELINE_REMAT_20260506 \
  outputs/cohere_paired_pal_retry_vs_external_l1_300case_poolfix_20260506 \
  outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z \
  outputs/trace_complete_external_losses_retry_20260430T204900Z \
  outputs/external_only_loss_collection_pal_vs_l1_completed_20260506T125123Z \
  outputs/external_only_loss_collection_pal_vs_l1_round2_20260506T130225Z \
  outputs/external_only_loss_collection_pal_vs_l1_round3_20260506T151731Z \
  outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z \
  outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z \
  outputs/cohere_track_b_ab_pilot_30case_20260507T204409Z
```

Then review/stage in small commits:

```bash
git status -sb
git add docs/MIGRATION_TRANSFER_INDEX_20260509.md docs/FAILURE_CASE_AND_API_ARTIFACT_INVENTORY_20260509.md
git add README.md START_HERE_CURRENT.md docs/CURRENT_EXTERNAL_BASELINE_GAP.md
git add scripts/build_external_baseline_loss_casebook.py tests/test_external_baseline_loss_casebook.py
git add outputs/external_full_suite_matched50_comparison_20260508T222631Z
git add outputs/gold_absent_external_success_schema_mining_20260507
git diff --cached --stat
```

Do not bulk-add `outputs/`.
