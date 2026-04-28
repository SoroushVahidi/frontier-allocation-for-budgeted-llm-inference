# Dry selection: expanded-loss-pool (20260428T143500Z)

Offline selection only (no Cohere API). Output directory: `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z_DRY/`.

## Command

```bash
python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp 20260428T143500Z_DRY \
  --mode cohere \
  --dry-run-selection \
  --selection-profile expanded-loss-pool \
  --max-cases 30 \
  --allow-large-run \
  --allow-duplicate-example-fallback \
  --methods external_l1_max,strict_f3,direct_reserve_semantic_frontier_v1,semantic_minimum_maturation_plus_direct_reserve_v1 \
  --budgets 4,6,8 \
  --dataset-name openai/gsm8k \
  --loss-jsonl outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/loss_cases_absent_from_tree.jsonl
```

## Summary (from stdout)

| Metric | Value |
|--------|------:|
| candidates_inspected | 189 |
| rejected_empty_question_or_gold | 163 |
| eligible_after_filters | 26 |
| unique example_ids in eligible pool | 16 |
| **selected_rows** | **30** |
| **unique example_ids selected** | **16** |
| n_fallback_duplicate_or_cycle_rows | 14 |
| max_cases_requested | 30 |

**Verdict:** `n_picked = 30` (≥ 20) — **proceed** to live Wulver run with the same parameters (without `--dry-run-selection`).

**Pool limit:** With the current single `loss_cases_absent_from_tree.jsonl` (GSM8K, l1 external), only **16** unique `example_id`s have the full **internal-wrong / external-correct** pattern with question+gold. The selection **duplicated** **14** case slots (different `seed`/`budget` source rows or cycling) to reach 30 rows. `cohort_slot` in `per_case_results` will disambiguate paired analysis.
