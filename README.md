# adaptive-reasoning-budget-allocation

Repository for the **current NeurIPS-oriented project** on **fixed-budget adaptive test-time compute allocation for LLM reasoning**.

## Project identity (canonical)

This repository is now organized around one primary research question:

> **Is the next unit of compute worth spending here?**

Concretely, the project focuses on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- branch/controller allocation under a global compute budget,
- oracle frontier headroom,
- anti-collapse controller design,
- supervision target design for allocation decisions.

## Current interpretation (important)

This repo is best interpreted as:
- a **strong research platform** with solid infrastructure and framing,
- with **active-development-level method maturity**.

What is strong now:
- infrastructure and experiment scaffolding,
- frontier/controller framing,
- dataset and baseline integration readiness,
- careful diagnostics and provenance notes.

What is not solved yet:
- robust learned allocation signal,
- supervision target quality / calibration,
- robust controller-level wins over strongest heuristics,
- broad real-model evidence.

## Main bottleneck (canonical)

The main bottleneck is **supervision target quality** and **proxy-label mismatch**.

It is **not** primarily:
- missing infrastructure,
- or lack of heavier models.

## Current best next method direction

The recommended near-term controller direction is:

- a **lightweight, budget-conditioned, binary stop-vs-act controller**
- for branch/controller allocation,
- with uncertainty used both:
  - as controller input features,
  - and as training-example filtering/reweighting signal.

Rationale: binary targets are currently expected to be more stable under noisy proxy supervision than a first-pass continuous marginal-value regressor.

## Canonical path (read in this order)

1. [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md)
2. [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
3. [`docs/STOP_VS_ACT_DIRECTION.md`](docs/STOP_VS_ACT_DIRECTION.md)
4. [`docs/NEXT_LIGHTWEIGHT_STEPS.md`](docs/NEXT_LIGHTWEIGHT_STEPS.md)
5. [`docs/EXPERIMENT_STATUS.md`](docs/EXPERIMENT_STATUS.md)
6. [`docs/REPO_MAP.md`](docs/REPO_MAP.md)
7. [`scripts/README.md`](scripts/README.md)

## Canonical vs exploratory vs historical

- **Canonical now**: docs listed in “Canonical path” and corresponding frontier/allocation scripts.
- **Exploratory**: branch-scorer variants (reliability-aware, warm-start, tie-aware variants) and targeted audits.
- **Historical**: old manuscript/binary revise-routing materials and dated memo snapshots.

See [`docs/REPO_MAP.md`](docs/REPO_MAP.md) and [`docs/README.md`](docs/README.md) for exact labels.
