# TALE baseline integration (fair, reviewer-defensible)

This document defines a conservative TALE integration for the current NeurIPS-oriented fixed-budget compute-allocation project.

## Upstream method summary (audited)

From the official TALE paper/repo:
- TALE includes an inference-time budget-allocation line (e.g., TALE-EP) where a per-problem token budget is estimated and injected into the reasoning prompt.
- The repo includes budget-search and estimator-oriented scripts (`search_budget.py`, `TALE-EP.py`) plus a separate TALE-PT training path (`TALE-PT.py`).
- Therefore, inference-time prompt budgeting and post-training are distinct and must be reported separately.

## Mode split in this repository

## MODE A (primary): `prompt_budgeting_inference_only`

- Fully runnable in this repository.
- Implements a faithful TALE-style adapter:
  - per-instance token budget estimation,
  - prompt-level budget injection,
  - budget-constrained generation behavior in our local controller environment.
- Does **not** include TALE-PT post-training.

Runner:
- `python scripts/run_tale_baseline.py --config configs/tale_prompt_budgeting_v1.json`

## MODE B (secondary): `official_full_adapter`

- Partial adapter/reporting path.
- Supports importing externally-produced official/full TALE results for side-by-side reporting.
- If official artifacts are unavailable, run is recorded as `blocked` (no overclaim).

Runner:
- `python scripts/run_tale_baseline.py --config configs/tale_official_adapter_v1.json`

## What is faithful vs adapted

Faithful to TALE core idea:
- Per-instance budget assignment.
- Prompt-level token budget instruction.
- Budget-aware quality/cost reporting.

Adapted to this repository:
- Our canonical execution substrate is frontier/action-based controller evaluation.
- TALE token budgets are mapped to this substrate via explicit token↔action conversion metadata.
- The estimator in MODE A is a lightweight in-repo estimator (`char_length_linear`) rather than TALE's full external stack.

## Fairness protocol

Primary comparison:
- `adaptive_min_expand_1` (our anchor) vs `external_tale_prompt_budgeting` (TALE-style adapter).

Budget matching:
- Report fixed-grid comparisons and **matched average compute** comparisons.
- Matching uses average generated-token estimates (plus action-budget metadata).

Required caveat:
- TALE is a strong adjacent published baseline but not the same decision granularity as stop-vs-act frontier control.

## Metrics emitted

At minimum:
- accuracy / exact match,
- average generated tokens,
- predicted budget and budget adherence/violation rates,
- budget exhaustion,
- frontier summaries (Pareto cost-quality).

## Artifacts emitted per run

Under `outputs/tale_baseline/<run_id>/`:
- `manifest.json`
- `summary.csv`
- `summary_per_seed.csv`
- `per_example.jsonl`
- `note.md`
- `fairness_report.md`
- `comparison_to_ours.csv`
- `frontier_summary.csv`
- `official_mode_import.csv`

## Non-claims

- No claim that TALE-PT is fully reproduced in-repo.
- No claim of exact control-space equivalence between TALE prompt budgeting and frontier stop-vs-act policies.
- No claim of exact paper-number reproduction without full official assets.

## Upstream references

- Paper page: https://aclanthology.org/2025.findings-acl.1274/
- PDF: https://aclanthology.org/2025.findings-acl.1274.pdf
- arXiv: https://arxiv.org/abs/2412.18547
- Official code: https://github.com/GeniusHTX/TALE
