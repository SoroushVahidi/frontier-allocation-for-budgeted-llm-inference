# Direct-Reserve v2 small-run selection debug (20260428T_DR_V2_THRESH_SMALL)

## Conclusion (root cause)
The 0-slot result was a **data availability/path issue**, not a Cohere/API issue and not a selection-filter regression.

- The expanded-loss-pool selector reads loss rows from `--loss-jsonl` (default points to `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/loss_cases_absent_from_tree.jsonl`).
- In this environment, that JSONL file is missing, so the merged loss pool is empty (`candidates_inspected=0`), which forces `selected_rows=0`.

## Evidence inspected
- Small run manifest: `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_THRESH_SMALL/manifest.json` shows all pool counters at zero.
- Small run expansion audit: `.../case_pool_expansion_audit.csv` shows `candidates_inspected=0`.
- Earlier reference docs (`20260428T143500Z`) show nonzero historical counts from the intended loss pool:
  - candidates inspected: 189
  - eligible after filters: 26
  - unique example IDs: 16
  - selected rows: 30 (with fallback duplicates enabled)

## Loss JSONL existence check
- Checked path:
  `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/loss_cases_absent_from_tree.jsonl`
- Result: **missing** in current workspace.

## Offline dry-selection reproduction (no Cohere calls)
Used explicit `--loss-jsonl` with the missing path to verify behavior.

### max-cases=8
- candidates_inspected: 0
- eligible_after_filters: 0
- unique_example_ids_in_eligible_pool: 0
- selected_rows: 0

### max-cases=30
- candidates_inspected: 0
- eligible_after_filters: 0
- unique_example_ids_in_eligible_pool: 0
- selected_rows: 0

Because candidates are zero, no rejection filter is responsible; there are simply no input rows loaded.

## Was explicit --loss-jsonl a fix?
No. Passing `--loss-jsonl` explicitly does not help if the referenced file does not exist locally.

## Corrected command for next small Cohere run
Use an explicit, **existing** loss JSONL path (and verify it before running):

```bash
test -f outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/loss_cases_absent_from_tree.jsonl && \
python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp 20260428T_DR_V2_THRESH_SMALL_RERUN \
  --mode cohere \
  --run-live-cohere \
  --selection-profile expanded-loss-pool \
  --max-cases 8 \
  --allow-duplicate-example-fallback \
  --methods external_l1_max,strict_f3,direct_reserve_semantic_frontier_v1,direct_reserve_semantic_frontier_v2_thresholded_ordered \
  --budgets 4,6,8 \
  --emit-full-traces \
  --dataset-name openai/gsm8k \
  --loss-jsonl outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/loss_cases_absent_from_tree.jsonl
```

If that file is not present, regenerate/copy the loss JSONL first; otherwise selection will remain zero.

## Manuscript impact
None. This is an operational input-path/data-availability issue for a diagnostic run, not a methodological result.
