# Current Experiment Status (2026-05-24)

Timestamp basis: non-invasive checks run during this hygiene pass on 2026-05-24 (UTC).  
Safety rule: no job was attached, restarted, killed, or modified.

## Live/Repair Run Status

## Cohere targeted no-majority fallback rerun

- Original run wrote frontier-only rows and completed (`47/188` rows in original artifact).
- Missing-method repair (`cohere_missing_methods_repair_20260524T003751Z`) is complete and ready for merge.
- Repair completion evidence:
  - `per_example_records.jsonl`: `141` rows
  - `completion_summary.json`: `target_rows=141`, `scored_rows=141`, `missing_rows=0`, `duplicate_rows=0`
  - Method coverage in repair: `47` each for `external_l1_max`, `external_s1_budget_forcing`, `external_tale_prompt_budgeting`

## Mistral full-300 regime-selector validation

- Original run wrote frontier-only rows and completed (`300/1200` rows in original artifact).
- Missing-method repair (`mistral_missing_methods_repair_20260524T003751Z`) is complete on disk.
- Repair completion evidence:
  - `per_example_records.jsonl`: `901` rows total (one duplicate key row)
  - `completion_summary.json`: `target_rows=900`, `scored_rows=900`, `missing_rows=0`, `duplicate_rows=1`
  - Method coverage observed in per-example rows: `external_l1_max=301`, `external_s1_budget_forcing=300`, `external_tale_prompt_budgeting=300`
- Last heartbeat events reach attempted/scored `300/300` for `external_tale_prompt_budgeting`.

## Cerebras frozen agreement-only 2-of-3 validation

- Process remains active and untouched:
  - wrapper PID: `2195504`
  - python PID: `2195513`
- Current record count snapshot: `247` rows in `per_example_records.jsonl`.
- Latest heartbeat entry still at the first method (`direct_reserve_semantic_frontier_v2`), with long per-example latency and no external-method rows yet.
- Operational interpretation: running very slowly / likely stalled progression; keep non-invasive monitoring only unless a separate intervention task is requested.

## What Must Happen Before Interpreting Repaired Cohere/Mistral Results

- Merge original frontier-only rows with corresponding missing-method repair rows.
- Run integrity checks:
  - expected row counts,
  - method completeness (all 4 methods),
  - duplicate-key handling (especially Mistral duplicate row).
- Replay selectors on merged complete artifacts.
- Only then interpret policy outcomes from those reruns.

## Warning

Do not interpret incomplete first-method-only artifacts as full policy evidence. They are structurally incomplete until merged with repairs and validated.

## Pointers

- `docs/REPAIR_INCOMPLETE_COHERE_MISTRAL_RUNS_20260524.md`
- `docs/REPAIR_JOBS_STATUS_20260524.md`
- `docs/ACTIVE_VALIDATION_JOBS_STATUS_20260523.md`
- `docs/CEREBRAS_HEALTH_STATUS_20260523.md`
- `docs/COHERE_TARGETED_NO_MAJORITY_FALLBACK_RERUN_20260523.md`
- `docs/MISTRAL_FULL300_REGIME_SELECTOR_VALIDATION_20260523.md`
