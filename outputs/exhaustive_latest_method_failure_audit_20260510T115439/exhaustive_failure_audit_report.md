# Exhaustive Latest-Method Failure Audit Report — 2026-05-10

## SECTION 1 — Paths and archives searched
- `/home/soroush/frontier-allocation-for-budgeted-llm-inference`
- `/home/soroush/research-next-wt`
- `/home/soroush/diverse-root-clean`
- `/home/soroush/pal-pilot-clean`
- `/home/soroush/migration_artifacts_20260509/` (Extracted archives: `pal_vs_production_and_track_b.tgz`, `pal_retry_vs_external_core_artifacts.tgz`, `external_baseline_and_selector_diagnostics.tgz`)
- `/tmp/migration_audit/`

Total potential failure-bearing files inspected: **6,065**

## SECTION 2 — Total latest-method failures found
- **Total unique failures (case_id + method)**: 1,127
- **Unique case_ids**: ~900+

## SECTION 3 — FULL/PARTIAL/ID_ONLY counts
For the latest method variants:
- **FULL**: 215
- **PARTIAL**: 467
- **ID_ONLY**: 445

## SECTION 4 — Additional FULL cases beyond main
- **FULL cases in main/handoff**: 53
- **Additional FULL cases found locally**: 162
- **Total unique FULL case_ids**: 174

Top sources of additional FULL cases:
1. `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/per_example_records.jsonl` (58 cases)
2. `outputs/cohere_paired_pal_retry_vs_external_l1_300case_poolfix_20260506/pal_results.csv` (48 cases)
3. `outputs/external_only_loss_collection_pal_vs_l1_completed_20260506T125123Z/pal_results.csv` (20 cases)
4. `outputs/external_only_loss_collection_pal_vs_l1_round3_20260506T151731Z/pal_results.csv` (18 cases)

## SECTION 5 — Why other Cohere samples were excluded
- **ID-only**: 445 cases were excluded from FULL because they lacked problem text or gold/selected answers in the artifact.
- **Older methods**: Hundreds of FULL failures were identified for methods like `strict_f3` or `strict_gate1_cap_k6` which are not the current "latest/best" method.
- **Successes**: Many recent Cohere runs (e.g. `discovery3_candidate_diversity`) had high accuracy, so most rows were not failures.
- **Missing Selected Answer**: Some casebooks (e.g. `cumulative_pal_vs_prod_casebook.csv`) had rows where the latest method failed but didn't produce a parseable answer (e.g. API error or empty response), making them PARTIAL rather than FULL.

## SECTION 6 — Output directory
`outputs/exhaustive_latest_method_failure_audit_20260510T115439/`

## SECTION 7 — Final answer: is 28 really the current FULL latest-method count?
**No.** The previous count of 28 was restricted to a small subset of curated artifacts. The exhaustive audit confirms that we have **174 unique FULL failure case_ids** (215 total FULL records) for the latest method variants across all local worktrees and archives. This is more than enough for meaningful pattern mining.
