# Trace recovery report

- Merged JSONL files: **2**

  - `/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/outputs/cohere_real_model_cost_normalized_validation_20260502T210610Z_DISCOVERY/per_example_records.jsonl`
  - `/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/outputs/trace_complete_external_losses_retry_20260430T204900Z/cohere_real_model_cost_normalized_validation_20260430T204900Z/per_example_records.jsonl`

- Gold-absent focus cases: **66**
- Rows with internal trace: **66**
- Rows with external trace (matched key): **62**

External traces require the same `(dataset, example_id, seed, budget)` as the discovery JSONL.
If external rows are missing, path-gap proxies that depend on external depth/action count stay blank.
