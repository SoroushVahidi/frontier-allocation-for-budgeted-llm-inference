# Learning How Hard to Think integration (MODE A adapter)

## Scope and status

This repository integrates **Learning How Hard to Think: Input-Adaptive Allocation of LM Computation** as a conservative **MODE A adapter-based comparator**.

- Paper page (primary source): https://openreview.net/forum?id=6qUUgw9bAZ
- Official-paper record id: `learning_how_hard_to_think` (`discuss_only`)
- Runnable comparator id: `learning_how_hard_to_think_mode_a` (`adapter_based`)
- Control equivalence: `adjacent`

## Official code verification result

- During this pass, no clearly attributable official public repository was verified directly from the OpenReview paper page.
- Therefore this integration is **not** an official reproduction claim.

## What is implemented

Runner:

- `scripts/run_learning_how_hard_to_think_mode_a.py`

Config:

- `configs/learning_how_hard_to_think_mode_a_v1.json`

Implemented control variable:

- per-example candidate count `k` (best-of-k style) under fixed/matched total action budget.

Budget unit:

- primary budget is `actions_per_example`.
- runner converts actions to candidate slots by `candidate_action_cap`, then allocates slots according to policy.

Sanity-check policy bundle (same substrate, matched budget accounting):

1. `learning_how_hard_to_think_mode_a`
2. `uniform_matched_compute`
3. `fixed_k_matched_compute`
4. `easy_to_hard_ordering`
5. `hard_to_easy_ordering`

## Faithfulness vs approximation

Faithful core idea retained:

- input-adaptive compute allocation,
- adaptive best-of-k style allocation,
- fixed/matched test-time budget.

Approximate pieces:

- hardness signal is heuristic and repository-local,
- generation/scoring substrate is in-repo simulator/API interface,
- no paper-specific official training/checkpoints are reproduced.

## Why this is adjacent (not direct)

Even with adaptive best-of-k allocation, this adapter does not implement the paper’s full official artifact stack and remains a matched-substrate approximation. Therefore claims must stay in the `adapter_based` / `adjacent` lane.

## Output contract

Output family:

- `outputs/learning_how_hard_to_think_mode_a/<run_id>/`

Required outputs:

- `status.json`
- `comparison_summary.csv`
- `per_seed_summary.csv`
- `per_example_results.jsonl`
- `diagnostic_summary.json`
- `diagnostic_report.md`
- `manifest.json`
- `config_snapshot.json`
- `command_snapshot.txt`

## Run command

```bash
python scripts/run_learning_how_hard_to_think_mode_a.py \
  --config configs/learning_how_hard_to_think_mode_a_v1.json
```

## Paper-facing usage guardrail

Only surface this baseline in paper-facing tables when diagnostics are included and caveats are explicitly shown as "paper-inspired matched-substrate comparator (not official reproduction)".
