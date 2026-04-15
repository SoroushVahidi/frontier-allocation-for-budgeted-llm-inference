# s1: Simple test-time scaling (external published baseline)

- Paper (arXiv): https://arxiv.org/abs/2501.19393
- Paper (ACL Anthology EMNLP 2025): https://aclanthology.org/2025.emnlp-main.1025/
- Official code: https://github.com/simplescaling/s1
- License (upstream repo): Apache-2.0

## Integration status in this repository

- Integration mode: `MODE_A_COMPLETE_MODE_B_PARTIAL`
- Scope implemented:
  - MODE A inference-time **budget forcing** behavior under matched in-repo settings.
  - MODE B official/full reporting adapter path (import-based; not full in-repo training reproduction).
- In-repo method id: `external_s1_budget_forcing`
- Policy: no vendored upstream code; provenance links only.

## What is and is not reproduced

Implemented here:
- A conservative adapter for s1 inference control (ignore early end-of-thinking and force continuation using a short wait cue).
- Explicit fairness split between inference-only (primary) and full/official-with-post-training (secondary).

Not reproduced here automatically:
- Full s1/s1.1 post-training/data pipeline in this repository.
- Exact tokenizer/serving stack parity for upstream vLLM internals.
- Paper-level benchmark replication claims.

## Local runner hooks

- `python scripts/run_s1_budget_forcing_baseline.py --config configs/s1_budget_forcing_inference_only_v1.json`
- `python scripts/run_s1_budget_forcing_baseline.py --config configs/s1_full_or_official_adapter_v1.json`
- `python scripts/run_s1_baseline_comparison_bundle.py --run-dirs <run_dir_1,run_dir_2,...>`

See also:
- `docs/s1_baseline_integration.md`
