# Current project status (canonical)

## Scope

This is the canonical status note for the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- branch-priority / next-step allocation over active branches.

## Core project goal

Learn and evaluate policies that decide **which active branch should receive the next unit of compute**, while respecting a fixed budget and avoiding allocation collapse.

## Final paper goal

The final paper should show that:
1. budgeted test-time compute allocation is a meaningful and distinct problem,
2. a clean frontier / controller framing is more honest than a vague “more reasoning helps” story,
3. branch ranking / next-step allocation is the right conceptual center,
4. and the main methodological challenge is supervision-target quality.

## What has been built

The repo already contains:
- a runnable frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation stack,
- local-gate / stop-vs-act dataset / train / eval machinery,
- dataset and baseline integration/readiness tooling,
- oracle-label pilot infrastructure,
- provenance-aware output and reporting patterns.

## What has been learned

1. The new project framing is sound and distinct from the old binary revise-routing track.
2. Anti-collapse controller design matters for realized budget use and frontier behavior.
3. Pairwise BT remains one of the strongest active learned directions.
4. The clean conceptual center is branch ranking / next-step allocation over active branches.
5. A local stop-vs-act formulation is useful only as a bounded approximation or continuation gate.
6. Larger scale alone is unlikely to fix the current weaknesses without better targets.

## Main unresolved issue

The main unresolved issue is **supervision target quality** for branch allocation:
- proxy-label mismatch,
- noisy branch-comparison targets,
- imperfect opportunity-cost modeling,
- uneven controller robustness across budgets / seeds / datasets.

## Current methodological interpretation

The project should currently be interpreted as:

> **a strong platform and paper direction whose main open problem is learning how to compare active branches and allocate the next unit of compute well.**

## Current best next implementation direction

- Keep branch-priority / next-step allocation as the canonical conceptual center.
- Use pairwise or pointwise branch scoring as the main learned object.
- Treat any local stop-vs-act gate as a helper mechanism, not the full algorithm.
- Continue matched bounded comparisons versus strong heuristics and BT baseline.
- Integrate the most important external paper baselines carefully and fairly.

## Practical implication

The repo is already ready for serious paper planning, collaborator onboarding, and baseline integration work. The next phase should focus on sharpening the branch-comparison signal and tightening the evaluation story, not on simply adding more scale.


## External baseline completeness status (2026-04-16 pass)

- s1 / TALE / L1: integrated with runnable MODE A and partial MODE B adapters with explicit blocker state reporting.
- BEST-Route: explicit blocked integration record (fair-adapter protocol not yet implemented).
- Completeness artifact: `docs/external_baseline_completeness_report.md` plus machine-readable `outputs/external_baseline_completeness_summary.{json,csv}`.
- Runnability artifact: `outputs/external_baseline_runnability/<run_id>/verification_summary.json`.

- compute_optimal_tts: moved from vague link-only to explicit blocked/protocol status with machine-readable artifacts and provenance checks.
