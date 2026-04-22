# Adaptive Test-Time Compute Allocation via Training-Free Difficulty Proxies

## Canonical paper identity

- **Title:** *Adaptive Test-Time Compute Allocation via Training-Free Difficulty Proxies*
- **OpenReview page:** https://openreview.net/forum?id=ztGHhyicWs
- **OpenReview PDF:** https://openreview.net/pdf?id=ztGHhyicWs

## Status in this repository

- **Official-paper record baseline id:** `adaptive_test_time_compute_allocation_training_free_proxies`
- **Runnable adapter lane id:** `training_free_difficulty_proxies_mode_a`
- **Classification:** `adapter_based`
- **Control equivalence:** `adjacent`
- **Allocation level:** query/sample-level global budget allocation (not branch-level frontier-equivalent)

## Official code verification

As of this integration pass (2026-04-22), we did **not** verify a clearly attributable official public code repository from the OpenReview page/PDF.

Therefore this repository does **not** claim official reproduction.

## Implemented MODE A adapter

Runner:

- `scripts/run_training_free_difficulty_proxies_mode_a.py`

Config:

- `configs/training_free_difficulty_proxies_mode_a_v1.json`

Output family:

- `outputs/training_free_difficulty_proxies_mode_a/<run_id>/`

Sanity bundle policies:

- `uniform`
- `fixed_round_robin`
- `easy_to_hard_mgl`
- `hard_to_easy_mgl`
- `dipa_mgl`

## Claim boundary

Use manuscript-safe wording such as:

> We include a paper-inspired matched-substrate adapter implementing a query-level global-budget DIPA-style allocation policy with training-free proxies. This lane is not an official reproduction and is adjacent rather than branch-level control-equivalent.
