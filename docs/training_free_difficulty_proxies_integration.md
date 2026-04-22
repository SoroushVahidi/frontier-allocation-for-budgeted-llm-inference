# Integration: Adaptive Test-Time Compute Allocation via Training-Free Difficulty Proxies (MODE A adapter)

## Baseline scope

This repository adds a conservative, paper-inspired adapter baseline for:

- OpenReview: https://openreview.net/forum?id=ztGHhyicWs
- PDF: https://openreview.net/pdf?id=ztGHhyicWs

Two-lane split:

1. `adaptive_test_time_compute_allocation_training_free_proxies` (official-paper record, discuss-only)
2. `training_free_difficulty_proxies_mode_a` (runnable adapter lane)

## Official code verification

No clearly attributable official public code repository was verified from the OpenReview page/PDF during this pass.

Therefore this integration is **not** an official reproduction claim.

## Implemented algorithmic core (matched-substrate approximation)

The runnable lane preserves the paper’s central DIPA-style structure:

- global test-set budget over a batch,
- one pull = one additional generation attempt for one unsolved instance,
- initialize `M_i` from a cheap input proxy,
- update unsolved selected instance with generation-based proxy (MGL-style failed-generation length),
- choose next instance by policy:
  - DIPA-style: `P_i ∝ 1 / M_i^lambda` among active unsolved instances,
  - and matched reference policies.
- remove instance immediately on success.

## Required sanity bundle

Implemented policies under shared accounting/substrate:

- `uniform`
- `fixed_round_robin`
- `easy_to_hard_mgl`
- `hard_to_easy_mgl`
- `dipa_mgl`

## Why this is adjacent, not direct

This lane is query/sample-level allocation over problem instances, while the repository’s canonical method focuses on branch-level next-step frontier allocation under budget. Therefore control equivalence remains `adjacent`.

## Artifacts

Output family:

- `outputs/training_free_difficulty_proxies_mode_a/<run_id>/`

Key files:

- `status.json`
- `comparison_summary.csv`
- `per_seed_summary.csv`
- `per_attempt_trace.jsonl`
- `diagnostic_summary.json`
- `diagnostic_report.md`
- `manifest.json`

## Run command

```bash
python scripts/run_training_free_difficulty_proxies_mode_a.py \
  --config configs/training_free_difficulty_proxies_mode_a_v1.json
```

## Safe claim boundary

- `adapter_based`
- `control_equivalence: adjacent`
- query-level global-budget comparator, not branch-level equivalent
- paper-inspired matched-substrate adapter, not official reproduction
