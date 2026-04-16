# Project master plan (canonical)

## Project identity

This repository is the canonical home for the current NeurIPS-oriented project on:
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
4. and the main obstacle is not raw scale but **decision-aligned supervision quality**.

## What the repo already has

The repository already provides:
- a runnable frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation paths,
- local-gate / stop-vs-act experimentation machinery,
- canonical branch-learning corpus construction and matched evaluation paths,
- dataset and baseline integration readiness tooling,
- conservative external process-supervision ingestion,
- provenance-aware outputs and documentation.

These are meaningful assets. The repository is already a strong research platform.

## What is still missing

The current gap is **not** that the project lacks ideas or code. The main missing piece is a supervision and evaluation picture that fully matches the real decision:

> **Which active branch should receive the next unit of compute under the remaining budget?**

This appears as:
- proxy-label mismatch,
- noisy branch-comparison targets,
- incomplete opportunity-cost awareness,
- weak held-out support on exact-promoted and related hard slices,
- broad-vs-aligned external supervision that still does not separate clearly,
- inconsistent controller-level wins over strong internal anchors.

## Canonical paper story

The strongest current paper story is:

**fixed-budget cross-controller frontier allocation for LLM reasoning, where the core methodological problem is learning how to rank active branches and allocate the next unit of compute under uncertainty, limited budget, and imperfect supervision.**

A local stop-vs-act gate can still be useful as an implementation simplification, but it should not be treated as the full conceptual center of the paper.

## Main methodological layers

### Layer 1: framing
- Fixed-budget adaptive test-time compute allocation.
- Cross-controller frontier allocation rather than only binary revise-routing.
- Compute as a scarce resource to be allocated where marginal utility is highest.

### Layer 2: mechanism
- Anti-collapse controller design.
- Branch-priority / next-step allocation over active branches.
- Pairwise and pointwise branch scoring as strong active learned lines.
- Optional local continuation gate as a simplification, not the main conceptual primitive.

### Layer 3: evidence
- Canonical processed corpora and matched branch-learning passes.
- Hard-slice diagnostics: near-tie, adjacent-rank, small-margin, exact-promoted.
- Oracle frontier headroom and matched controller-level comparisons.
- Real-model and external-supervision evidence interpreted honestly and conservatively.

## What we have learned so far

1. The new framing is real and distinct from the old binary revise-routing manuscript.
2. Anti-collapse design matters.
3. Target construction and comparator semantics often matter more than model-class swaps.
4. Hard-case representation and hard-slice evaluation matter materially.
5. External process supervision can be integrated and made non-degenerate, but transfer to the true branch-allocation decision is not automatic.
6. Scaling up before supervision and evaluation quality improve is unlikely to be the most efficient next move.

## Current best evidence picture

- Internal supervision is substantially stronger than earlier in the repo’s history.
- Canonical corpora and matched learning passes are now mature enough for a careful paper-facing story.
- PRM800K-assisted methods can show small stable gains over the internal anchor in rebuilt corpus families.
- However, broad vs aligned PRM usage still does not separate clearly, and exact-promoted evidence is still too thin to overinterpret.

## What we should do next

### Near-term
- strengthen branch-comparison and next-step allocation target design,
- improve held-out evidence on low-budget, exact-promoted, and comparator-fragile slices,
- keep the same matched method family long enough to understand where broad vs aligned external supervision truly differs,
- sharpen manuscript-safe claims and evaluation protocols.

### Mid-term
- broaden hard-slice support further,
- improve transfer alignment from external process supervision to internal branch comparison,
- expand real-model evidence on high-value hard states,
- tighten controller-level robustness across seeds / budgets / datasets.

### Later
- only after evidence quality improves, scale to heavier runs,
- revisit Math-Shepherd or other external supervision families,
- broaden benchmark coverage,
- test richer action spaces and stronger learned allocators.

## Explicit non-goals for now

- Do not market the repo as if a final universal winning controller already exists.
- Do not let heavy scaling substitute for supervision/evaluation quality work.
- Do not collapse the paper story back into the old “when to revise” binary-routing manuscript.
- Do not overclaim that external process supervision already solves the problem.
- Do not move to new external datasets merely because they are available.

## Safe high-level claim

The safest current top-line statement is:

**This repository already supports a serious paper on fixed-budget adaptive test-time compute allocation, but the strongest honest contribution is still the framing, evaluation lens, and diagnosis of decision-aligned branch-allocation supervision rather than a final universally dominant controller.**

## Recommended collaborator reading order

1. `README.md`
2. `docs/PROJECT_MASTER_PLAN.md`
3. `docs/CURRENT_PROJECT_STATUS.md`
4. `docs/CURRENT_BOTTLENECKS.md`
5. `docs/CURRENT_SAFE_CLAIMS.md`
6. `docs/PAPER_POSITIONING_NOTE.md`
7. `docs/EXPERIMENT_STATUS.md`
8. `docs/REPO_MAP.md`
