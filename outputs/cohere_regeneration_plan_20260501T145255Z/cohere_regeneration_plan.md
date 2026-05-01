# Bounded Cohere Regeneration Plan (REGEN50)

- Casebook: `outputs/selector_evidence_package_20260501T014547Z/present_not_selected_casebook.jsonl`
- Max cases: **50** (hard cap)
- Dataset/seed/budget: `openai/gsm8k`, seed `11`, budget `4`
- Method to regenerate: `direct_reserve_semantic_frontier_v2` only
- External method behavior: `external_l1_max` will **not** be rerun; existing labels from casebook are reused only for evaluation metadata.

## Planned bounded command
```bash
python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp <REGEN_TIMESTAMP> \
  --providers cohere \
  --datasets openai/gsm8k \
  --budgets 4 \
  --seeds 11 \
  --methods direct_reserve_semantic_frontier_v2 \
  --target-scored-per-slice 50 \
  --max-examples 50 \
  --allowed-example-ids-file outputs/selector_evidence_package_20260501T014547Z/present_not_selected_casebook.jsonl \
  --output-root outputs
```

## Dry-run/call-plan output
Dry-run command run with `--dry-run-call-plan` and same filter file. Output captured in `dry_run_output.txt` in this folder.

Expected Cohere call count: bounded by **<=50 cases** for the single DR-v2 slice. (Exact retries may slightly vary; failures/retries are tracked in per-example records.)

## Output root
- Regenerated raw source root: `outputs/cohere_real_model_cost_normalized_validation_<REGEN_TIMESTAMP>_COHERE_SELECTOR_EVIDENCE_REGEN50/`

## Expected artifacts
- `per_example_records.jsonl` (required by recovery)
- aggregate summaries from runner (`per_budget_summary.csv`, `aggregate_summary.csv`, etc.)
- optional trace artifacts if emitted by runner settings

## Safety / retention
- No unrelated datasets, seeds, budgets, or methods.
- Hard filter by casebook IDs and max-cases.
- No API keys printed; no secrets/log caches committed.
- Do not commit `.env*`, cache files, raw secret-bearing logs, or compressed blobs.
