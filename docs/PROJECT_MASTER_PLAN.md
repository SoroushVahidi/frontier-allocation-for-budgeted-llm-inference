# Project master plan (canonical)

## Project identity

This repository is the canonical home for the **new NeurIPS-oriented project** on:
- fixed-budget adaptive test-time compute allocation for LLM reasoning,
- cross-controller frontier allocation,
- branch-priority / next-step allocation over active branches,
- oracle frontier headroom and anti-collapse controller design.

The central project question is:

> **Which active branch should receive the next unit of compute?**

Equivalent local phrasing:

> **Is the next unit of compute worth spending here, relative to other active branches?**

This question should guide the method design, evaluation design, safe claims, and paper writing.

## Final paper goal

The long-run paper goal is **not** merely to show that additional reasoning can help. That is already well known.

The real goal is to show that:
1. test-time compute should be treated as a scarce budgeted resource,
2. that resource can be allocated more effectively than uniform spending,
3. the most useful near-term learned object is a branch-priority / next-step allocation policy,
4. and the main obstacle is not infrastructure but **supervision-target quality**.

## What the repo already has

The repository already provides:
- a runnable frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation paths,
- local-gate / stop-vs-act experimentation machinery,
- dataset and baseline integration readiness tooling,
- oracle-label pilot infrastructure,
- provenance-aware outputs and documentation.

These are meaningful assets. The repository is already a strong research platform.

## What is still missing

The current gap is **not** that the project lacks ideas or code. The main missing piece is a stable supervision signal that teaches the allocator which branch should receive the next unit of compute.

This appears as:
- proxy-label mismatch,
- noisy branch-comparison targets,
- shallow local comparator definitions,
- unstable calibration across budgets / seeds / datasets,
- inconsistent controller-level wins over strong heuristics.

## Canonical paper story

The strongest current paper story is:

**fixed-budget cross-controller frontier allocation for LLM reasoning, where the core methodological problem is learning how to rank active branches and allocate the next unit of compute under uncertainty and limited budget.**

A local stop-vs-act gate can still be useful as an implementation simplification, but it should not be treated as the full conceptual center of the paper.

## Main methodological layers

### Layer 1: framing
- Fixed-budget adaptive test-time compute allocation.
- Cross-controller frontier allocation rather than only binary revise-routing.
- Compute as a scarce resource to be allocated where marginal utility is highest.

### Layer 2: mechanism
- Anti-collapse controller design.
- Branch-priority / next-step allocation over active branches.
- Pairwise BT branch scoring as a strong active baseline / companion line.
- Optional local continuation gate as a simplification, not the main conceptual primitive.

### Layer 3: evaluation lens
- Oracle frontier headroom.
- Matched controller-level comparisons.
- Budget-aware frontier summaries.
- Real-model evidence where feasible, with simulator evidence interpreted honestly as process-proxy evidence.

## What we have learned so far

1. The new framing is real and distinct from the old binary revise-routing manuscript.
2. Anti-collapse design matters.
3. Pairwise BT remains one of the strongest active learned directions.
4. The cleanest conceptual center is branch ranking / next-step allocation over active branches.
5. A standalone stop-vs-act story is useful only as a local approximation, not as the full allocation formulation.
6. Scaling up before target quality improves is unlikely to be the most efficient next move.

## What we should do next

### Near-term
- strengthen branch-comparison and next-step allocation target design,
- improve uncertainty-aware filtering / reweighting,
- run matched bounded comparisons against strong heuristics and BT baseline,
- integrate the most important external paper baselines fairly,
- sharpen manuscript-safe claims and evaluation protocols.

### Mid-term
- expand oracle-label pilot runs,
- test selective distillation paths,
- broaden real-model evidence,
- tighten controller-level robustness across seeds / budgets / datasets.

### Later
- only after target quality improves, scale to heavier runs,
- broaden benchmark coverage,
- test richer action spaces and stronger learned allocators.

## Explicit non-goals for now

- Do not market the repo as if a final universal winning controller already exists.
- Do not let heavy scaling substitute for target-quality work.
- Do not collapse the paper story back into the old “when to revise” binary-routing manuscript.
- Do not overclaim exact comparability to external methods where the action space differs.

## Safe high-level claim

The safest current top-line statement is:

**This repository already supports a serious paper on fixed-budget adaptive test-time compute allocation, but the strongest honest contribution is currently the framing, evaluation lens, and supervision-target diagnosis rather than a final universally dominant controller.**

## Recommended collaborator reading order

1. `README.md`
2. `docs/PROJECT_MASTER_PLAN.md`
3. `docs/CURRENT_PROJECT_STATUS.md`
4. `docs/CURRENT_BOTTLENECKS.md`
5. `docs/CURRENT_SAFE_CLAIMS.md`
6. `docs/STOP_VS_ACT_DIRECTION.md`
7. `docs/NEXT_LIGHTWEIGHT_STEPS.md`
8. `docs/LATER_HEAVIER_STEPS.md`
9. `docs/PAPER_POSITIONING_NOTE.md`
10. `docs/REPO_MAP.md`
