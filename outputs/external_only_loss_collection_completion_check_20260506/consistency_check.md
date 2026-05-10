# Consistency Check

- Run directory: `outputs/external_only_loss_collection_pal_vs_l1_20260506T040238Z`
- Completed: **No**

## Required Files
- Missing 17/17 required files.
- Present files in run directory are preflight-only (`allowed_example_ids.jsonl`, `fresh_candidate_preflight.json`).

## Verifications
- Methods check from available artifact: PASS
- Pair completion counts: NOT VERIFIABLE (missing `paired_casebook.csv` / `collection_summary.json`)
- Outcome counts (external_correct_pal_wrong, etc.): NOT VERIFIABLE
- External-only casebook row equality check: NOT VERIFIABLE
- Failed/skipped calls check: NOT VERIFIABLE (missing `failed_or_skipped_calls.jsonl`)
- Call cap <= 1500: NOT VERIFIABLE (missing `call_usage_summary.json`)
- Metric consistency warnings: NOT VERIFIABLE

## Conclusion
This run family instance did not complete the collection outputs needed for loss analysis.
