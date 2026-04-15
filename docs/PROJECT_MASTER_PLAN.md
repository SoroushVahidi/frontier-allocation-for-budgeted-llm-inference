# Project master plan (canonical)

## Project identity

This repository is the canonical home for the **new NeurIPS-oriented project** on:
- fixed-budget adaptive test-time compute allocation for LLM reasoning,
- cross-controller frontier allocation,
- budget-conditioned stop-vs-act control,
- oracle frontier headroom and anti-collapse controller design.

The central project question is:

> **Is the next unit of compute worth spending here?**

This question should guide the method design, evaluation design, safe claims, and paper writing.

## Final paper goal

The long-run paper goal is **not** merely to show that additional reasoning can help. That is already well known.

The real goal is to show that:
1. test-time compute should be treated as a scarce budgeted resource,
2. that resource can be allocated more effectively than uniform spending,
3. the most useful near-term controller is a budget-conditioned stop-vs-act decision rule,
4. and the main obstacle is not infrastructure but **supervision-target quality**.

## What the repo already has

The repository already provides:
- a runnable frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation paths,
- stop-vs-act dataset / model / evaluation machinery,
- dataset and baseline integration readiness tooling,
- oracle-label pilot infrastructure,
- provenance-aware outputs and documentation.

These are meaningful assets. The repository is already a strong research platform.

## What is still missing

The current gap is **not** that the project lacks ideas or code. The main missing piece is a stable, action-conditional supervision signal that teaches the controller whether compute should be spent now or preserved for later.

This appears as:
- proxy-label mismatch,
- noisy or shallow ACT-vs-STOP comparators,
- unstable controller calibration across budgets / seeds / datasets,
- inconsistent controller-level wins over strong heuristics.

## Canonical paper story

The strongest current paper story is:

**fixed-budget cross-controller frontier allocation for LLM reasoning, with budget-conditioned stop-vs-act control as the leading near-term method direction, and supervision-target design as the central unresolved methodological issue.**

This paper story is stronger and more honest than pretending the project already has a universally winning learned allocator.

## Main methodological layers

### Layer 1: framing
- Fixed-budget adaptive test-time compute allocation.
- Cross-controller frontier allocation rather than only binary revise-routing.
- Compute as a scarce resource to be allocated where marginal utility is highest.

### Layer 2: mechanism
- Anti-collapse controller design.
- Budget-conditioned stop-vs-act control.
- Pairwise BT branch scoring as a strong active baseline / companion line.

### Layer 3: evaluation lens
- Oracle frontier headroom.
- Matched controller-level comparisons.
- Budget-aware frontier summaries.
- Real-model evidence where feasible, with simulator evidence interpreted honestly as process-proxy evidence.

## What we have learned so far

1. The new framing is real and distinct from the old binary revise-routing manuscript.
2. Anti-collapse design matters.
3. Pairwise BT remains one of the strongest active learned directions.
4. Stop-vs-act is the clearest near-term controller family.
5. Several bounded target variants helped, but none has yet fully solved the comparator problem.
6. Scaling up before target quality improves is unlikely to be the most efficient next move.

## What we should do next

### Near-term
- strengthen ACT-vs-STOP target design,
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
- test richer action spaces and stronger learned controllers.

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
