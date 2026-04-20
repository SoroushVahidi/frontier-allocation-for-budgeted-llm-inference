# L1 baseline integration (fair, reviewer-defensible split)

This document defines a conservative L1 integration for the current NeurIPS-oriented fixed-budget compute-allocation project.

## Upstream method summary (audited)

From the official L1 paper/project/repository:
- L1 uses **Length Controlled Policy Optimization (LCPO)**, an RL training method to control reasoning length through prompt conditioning.
- Two operational variants are emphasized:
  - **L1-Exact / LCPO-Exact**: condition on exact target reasoning length.
  - **L1-Max / LCPO-Max**: condition on maximum allowable reasoning length.
- Official scripts include separate replication/evaluation paths (`eval_inference_exact.sh`, `eval_inference_max.sh`) and RL training scripts (`run_l1_exact.sh`, `run_l1_max.sh`).

## Mode split in this repository

## MODE A (primary): `inference_only_adapter`

- Fully runnable in this repository.
- Implements an L1-style adapter with both Exact and Max length-conditioning prompts:
  - `external_l1_exact`
  - `external_l1_max`
- Uses the same evaluation stack as our method for matched-budget comparison.
- Does **not** claim to reproduce L1 RL training.

Runner:
- `python scripts/run_l1_baseline.py --config configs/l1_inference_adapter_v1.json`

## MODE B (secondary): `official_full_adapter`

- Partial adapter/reporting path.
- Supports importing externally produced official/full L1 results for side-by-side reporting.
- If official assets are unavailable, run is marked `blocked` in `manifest.json`.

Runner:
- `python scripts/run_l1_baseline.py --config configs/l1_official_full_adapter_v1.json`

Import contract (MODE B):
- `python scripts/verify_l1_mode_b_import.py --results-path <path> --expected-dataset <ds> --expected-budgets <comma-separated ints>`

## What is faithful vs adapted

Faithful to L1 core idea:
- Explicit length conditioning in prompt.
- Separate Exact vs Max variants.
- Budget-adherence and quality reporting under controlled budgets.

Adapted to this repository:
- Our core evaluation substrate is frontier/action-based stop-vs-act allocation.
- MODE A maps L1 token budgets onto this substrate using explicit token↔action conversion metadata.
- MODE A is inference-only and therefore does not replicate RL optimization dynamics of official L1 training.

## Fairness protocol

Primary comparison:
- `adaptive_min_expand_1` (our anchor) vs `external_l1_exact` and `external_l1_max`.

Budget matching:
- Report action-budget and token-equivalent columns.
- Report average generated tokens and budget error/violation rates.
- Present matched-average-budget comparisons where possible.

Required caveat:
- L1 is a strong direct budget-control baseline, but not identical to frontier stop-vs-act control granularity.

## Metrics emitted

At minimum:
- accuracy / exact match,
- average generated tokens,
- average token-budget error,
- budget adherence/violation rates,
- budget exhaustion,
- cost-quality frontier summaries.

## Artifacts emitted per run

Under `outputs/l1_baseline/<run_id>/`:
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

- No claim that full L1 RL training is reproduced in this repository.
- No claim of exact control-space equivalence with frontier stop-vs-act.
- No claim that MODE B is complete unless official/full outputs are supplied.

## Upstream references

- Project page: https://cmu-l3.github.io/l1/
- Official code: https://github.com/cmu-l3/l1
- arXiv abstract: https://arxiv.org/abs/2503.04697
- arXiv PDF: https://arxiv.org/pdf/2503.04697.pdf
