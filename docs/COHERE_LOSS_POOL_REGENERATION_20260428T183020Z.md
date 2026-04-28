# Cohere loss-pool regeneration report (20260428T183020Z)

## Status
Regeneration succeeded locally **without Cohere calls** and **without Slurm**.

## Command run

```bash
python scripts/build_cohere_absent_from_tree_loss_diagnostics.py
```

## Regenerated output directory

`outputs/cohere_absent_from_tree_loss_diagnostics_20260428T183020Z`

## Core regenerated file

`outputs/cohere_absent_from_tree_loss_diagnostics_20260428T183020Z/loss_cases_absent_from_tree.jsonl`

## Counts
- line count (`wc -l`): **189**
- rows with non-empty `question` and non-empty `gold_answer`: **26**
- unique `example_id` (all 189 rows): **84**
- eligible rows for expanded-loss-pool GSM8K selector (`question/gold + iw/ec + allowed methods/baselines`): **26**
- unique `example_id` in eligible subset: **16**

These match the earlier known expanded-pool dry-selection behavior (189 candidates, 26 eligible, 16 unique eligible IDs).

## Dry-selection recheck (no Cohere)

### max-cases=8
```bash
python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp 20260428T_DR_V2_THRESH_SELECTION_RECHECK \
  --mode cohere \
  --dry-run-selection \
  --selection-profile expanded-loss-pool \
  --max-cases 8 \
  --allow-duplicate-example-fallback \
  --methods external_l1_max,strict_f3,direct_reserve_semantic_frontier_v1,direct_reserve_semantic_frontier_v2_thresholded_ordered \
  --budgets 4,6,8 \
  --dataset-name openai/gsm8k \
  --loss-jsonl outputs/cohere_absent_from_tree_loss_diagnostics_20260428T183020Z/loss_cases_absent_from_tree.jsonl
```
Result: `selected_rows=8`, `unique_example_ids_selected=8`.

### max-cases=30 (sanity compare to prior run)
Result: `candidates_inspected=189`, `eligible_after_filters=26`, `unique_example_ids_in_eligible_pool=16`, `selected_rows=30`, `n_fallback_duplicate_or_cycle_rows=14`.

## Exact next small live-v2 command (updated path)

```bash
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
  --loss-jsonl outputs/cohere_absent_from_tree_loss_diagnostics_20260428T183020Z/loss_cases_absent_from_tree.jsonl
```

No manuscript impact; this restores missing local selection input only.
