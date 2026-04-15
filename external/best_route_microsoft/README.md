# BEST-Route (Microsoft Research)

- **Repository:** https://github.com/microsoft/best-route-llm
- **Paper / project page:**
  - arXiv: https://arxiv.org/abs/2506.22716
  - Microsoft Research: https://www.microsoft.com/en-us/research/publication/best-route-adaptive-llm-routing-with-test-time-optimal-compute/
- **License (upstream repo):** MIT (`LICENSE.md` in upstream repository; verify pinned commit during any clone-based reproduction).
- **Import status in this repo:** **Blocked for runnable-comparison claims** (documentation-only record, no vendored code).

## Why this is currently blocked here (conservative)

This repository currently evaluates frontier/action-style adaptive allocation methods. BEST-Route upstream currently expects a different workflow shape:

1. mixed multi-source prompt dataset construction,
2. per-model multi-sample response-bank generation,
3. reward-model scoring over response banks,
4. router training over cost-quality targets,
5. policy evaluation under routing + best-of-n choices.

A fair adapter from BEST-Route to this repo's substrate is **not** yet implemented. Therefore this baseline is currently **non-runnable in this repo** and must not be presented as completed empirical comparison.

## What would be required for fair later integration

- Shared prompt set that is also valid for this repo's internal methods.
- Shared candidate model family list and API/accounting assumptions.
- Common cost model (prompt + completion + sampling multiplicity) aligned with current frontier accounting.
- Common quality scoring interface (reward-model or equivalent) applied consistently across methods.
- Explicit protocol doc that separates "direct" versus "adjacent" control-space comparisons.

Until these are implemented, BEST-Route remains an explicit **blocked** baseline in `configs/external_baselines_registry.json` and `docs/external_baseline_completeness_report.md`.
