# BEST-Route (Microsoft Research)

- **Repository:** https://github.com/microsoft/best-route-llm
- **Paper / project page:**
  - arXiv: https://arxiv.org/abs/2506.22716
  - Microsoft Research: https://www.microsoft.com/en-us/research/publication/best-route-adaptive-llm-routing-with-test-time-optimal-compute/
- **License (upstream repo):** MIT (`LICENSE.md` in upstream repository; verify pinned commit during any clone-based reproduction).
- **Import status in this repo:** **`RUNNABLE_ADJACENT` via verified import protocol only**.

## Why this is adjacent (not direct) here

This repository evaluates frontier/action-style adaptive allocation methods. Upstream BEST-Route uses a different workflow shape:

1. mixed multi-source prompt dataset construction,
2. per-model multi-sample response-bank generation,
3. reward-model scoring over response banks,
4. router training over cost-quality targets,
5. policy evaluation under routing + best-of-n choices.

Because upstream control arms are model+best-of-n variants (bo1..boN), this is not treated as direct control-space equivalence with this repo's native action substrate.

## What is now unblocked

A strict import-validation protocol now exists in this repo:

- validator: `scripts/verify_best_route_import.py`
- canonical integration note: `docs/best_route_integration.md`
- status artifacts:
  - `outputs/external_baseline_completeness/best_route_status.json`
  - `outputs/external_baseline_completeness/best_route_status.md`

## Non-overclaim boundary

Safe:

- reviewer-auditable adjacent import comparisons after validation.

Not safe:

- claiming full in-repo BEST-Route reproduction,
- claiming apples-to-apples direct comparability with frontier/action-native controllers.
