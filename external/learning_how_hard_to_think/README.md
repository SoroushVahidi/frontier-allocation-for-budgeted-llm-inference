# Learning How Hard to Think external baseline note

## Canonical paper identity

- **Title:** *Learning How Hard to Think: Input-Adaptive Allocation of LM Computation*
- **Canonical paper URL:** https://openreview.net/forum?id=6qUUgw9bAZ
- **Primary source-of-truth for this integration:** OpenReview page above.

## Current status in this repository

- **Official-paper record:** `learning_how_hard_to_think` (`discuss_only`)
- **Runnable adapter lane:** `learning_how_hard_to_think_mode_a` (`adapter_based`)
- **Control equivalence:** `adjacent`

## Official code verification status (conservative)

As of this integration pass (2026-04-22), we did **not** verify a clearly attributable official public repository directly from the OpenReview page.

Therefore this repository does **not** claim official reproduction.

## Implemented comparator

A paper-inspired adaptive best-of-k style comparator with explicit sanity bundle:

- `learning_how_hard_to_think_mode_a`
- `uniform_matched_compute`
- `fixed_k_matched_compute`
- `easy_to_hard_ordering`
- `hard_to_easy_ordering`

All policies run under the same in-repo substrate and the same matched budget accounting contract.

Runner and config:

- `scripts/run_learning_how_hard_to_think_mode_a.py`
- `configs/learning_how_hard_to_think_mode_a_v1.json`

Output family:

- `outputs/learning_how_hard_to_think_mode_a/<run_id>/`

## Claim boundary

Manuscript-safe wording:

> We include a paper-inspired matched-substrate MODE A adapter for *Learning How Hard to Think* that preserves input-adaptive compute allocation and adaptive best-of-k-style behavior under fixed budget, but does not claim official code-level reproduction.
