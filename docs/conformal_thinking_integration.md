# Conformal Thinking integration (MODE A adapter)

## Scope and status

This repository integrates *Conformal Thinking: Risk Control for Reasoning on a Compute Budget* as a conservative **paper-inspired MODE A adapter comparator**.

- Primary source (arXiv page): https://arxiv.org/abs/2602.03814
- Primary source (arXiv PDF): https://arxiv.org/pdf/2602.03814.pdf
- Official-paper record id: `conformal_thinking` (`discuss_only`)
- Runnable comparator id: `conformal_thinking_mode_a` (`adapter_based`)
- Control equivalence: `adjacent`

## Official code verification result

No clearly verified official public code repository was confirmed directly from the primary arXiv sources above during this integration pass.

Therefore this integration is **not** an official reproduction claim.

## What is implemented

Runner:

- `scripts/run_conformal_thinking_mode_a.py`

Config:

- `configs/conformal_thinking_mode_a_v1.json`

Implemented control variable:

- per-query stop time under a fixed maximum compute budget (`max_steps_per_query`).

Stopping policies included:

1. `full_budget_baseline`
2. `fixed_budget_truncation_baseline`
3. `naive_upper_threshold_stopping`
4. `conformal_thinking_mode_a_upper`
5. `conformal_thinking_mode_a_dual`

Calibration behavior:

- validation/evaluation split is explicit.
- threshold calibration supports naive empirical tuning and finite-sample corrected tuning (`plus_one` style).
- upper-threshold calibration controls wrong-early-exit risk estimate.
- dual-threshold mode additionally calibrates a low-progress lower-threshold false-negative risk estimate.

## Faithfulness vs approximation

Faithful core ideas retained:

- risk-controlled early-exit framing,
- upper-threshold confidence-style stopping,
- optional dual-threshold logic with lower-threshold low-progress stopping,
- validation-based threshold calibration with finite-sample correction.

Approximate pieces:

- confidence/progress signals are repository-local proxies,
- trajectory dynamics are matched-substrate simulation,
- no official probes/EAT/model-specific pipeline from the paper is claimed.

## Why this is adjacent (not direct)

This adapter controls query-level early stopping under a capped trajectory budget and does not implement branch-level next-step frontier allocation over competing branches. Claims must stay in the `adapter_based` / `adjacent` lane.

## Output contract

Output family:

- `outputs/conformal_thinking_mode_a/<run_id>/`

Required outputs:

- `status.json`
- `comparison_summary.csv`
- `per_seed_summary.csv`
- `per_example_results.jsonl`
- `calibration_summary.json`
- `diagnostic_summary.json`
- `diagnostic_report.md`
- `manifest.json`
- `config_snapshot.json`
- `command_snapshot.txt`

## Run command

```bash
python scripts/run_conformal_thinking_mode_a.py \
  --config configs/conformal_thinking_mode_a_v1.json
```

## Paper-facing usage guardrail

Only surface this baseline as a paper-inspired matched-substrate comparator with explicit caveats. Do not label as official reproduction or branch-level control-equivalent.
