# Cohere collection plan

- Exact Cohere validation command to run:
  `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp <RUN_STAMP> --providers cohere --datasets openai/gsm8k --budgets 4 --seeds 11 --methods direct_reserve_semantic_frontier_v2,external_l1_max --target-scored-per-slice 100 --max-examples 100 --save-branch-traces --emit-trace-audit`
- Number of examples (explicit cap): 100 paired examples maximum (same dataset/seed/budget slice).
- Methods compared: `direct_reserve_semantic_frontier_v2` vs `external_l1_max`.
- Dataset/split: `openai/gsm8k` pilot slice via existing loader (seed=11, budget=4).
- Seed/budget: seed `11`, budget `4`.
- Expected Cohere calls: bounded by this command cap; exact call count is runtime-dependent by branch expansion path and method behavior. Hard example cap prevents uncapped runs.
- Expected outputs: timestamped `outputs/cohere_real_model_cost_normalized_validation_<RUN_STAMP>/` including `per_example_records.jsonl`, summaries, and trace artifacts.
- Candidate/tree metadata preservation: enabled via `--save-branch-traces`; DR-v2 metadata retained in per-example records and traces for downstream selector evidence extraction.
- Secret handling: no API key values will be logged or committed; only readiness state/outcomes are recorded.
- Dry-run-like precheck used: `--validate-methods-only` (no API calls) to verify runnable method IDs.
