# s1: Simple test-time scaling (external published baseline)

- Paper (arXiv): https://arxiv.org/abs/2501.19393
- Paper (ACL Anthology EMNLP 2025): https://aclanthology.org/2025.emnlp-main.1025/
- Official code: https://github.com/simplescaling/s1
- License (upstream repo): Apache-2.0

## Integration status in this repository

- Integration mode: `adapter_partial`
- Scope implemented: inference-time **budget forcing** behavior (stop/continue control)
- In-repo method id: `external_s1_budget_forcing`
- Policy: no vendored upstream code; provenance links only

## What is and is not reproduced

Implemented here:
- A conservative adapter for the s1 inference control loop (ignore early end-of-thinking and force continuation using a short wait cue).

Not reproduced here:
- Full s1 training/data pipeline.
- Exact tokenizer/serving stack parity (e.g., vLLM stop-token mechanics from upstream scripts).
- Paper-level benchmark replication claims.

## Local runner hooks

- `python scripts/run_light_anchor_vs_s1_comparison.py`
- `python scripts/run_light_external_style_baseline_comparison.py`

See also:
- `docs/s1_baseline_integration_note_2026_04_15.md`
