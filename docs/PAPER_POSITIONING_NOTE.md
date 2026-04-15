# Paper positioning note (canonical interpretation)

## Strongest current paper story

The strongest current paper direction is:

**fixed-budget cross-controller frontier allocation for LLM reasoning, where the central methodological question is how to rank active branches and allocate the next unit of compute under uncertainty and limited budget.**

## What this means in practice

The paper should not be framed as:
- “we already found the universally best controller,”
- or “more reasoning helps,”
- or “a small variant of the old revise-routing manuscript.”

It also should not be framed as if a standalone local stop-vs-act gate fully defines the problem.

Instead, the paper should be framed as:
- a distinct budgeted inference problem,
- with a clear frontier/controller lens,
- a branch-ranking / next-step allocation view,
- an honest evaluation lens centered on oracle headroom and matched comparisons,
- and a diagnosis that target quality is currently the main blocker to stronger learned control.

## Recommended positioning elements

1. **Problem:** fixed-budget adaptive test-time compute allocation for LLM reasoning.
2. **Mechanism:** cross-controller frontier allocation with anti-collapse design.
3. **Conceptual center:** branch-priority / next-step allocation over active branches.
4. **Evaluation lens:** oracle frontier headroom + matched controller-level comparisons + budget-aware frontier summaries.
5. **Main unresolved issue:** supervision-target quality and proxy-label mismatch.
6. **Honest contribution type:** framing, evaluation design, and allocation-target diagnosis, with emerging but not yet final method evidence.

## Best contribution framing

A strong introduction should make clear that the contribution is not merely a stronger search heuristic. The contribution is the combination of:
- a cleaner resource-allocation framing,
- a more interpretable next-step branch-allocation question,
- explicit anti-collapse / frontier considerations,
- and a clearer diagnosis of why learned branch allocation is hard.

## Baseline framing guidance

The paper should compare against:
- strong in-repo heuristic and learned baselines,
- the strongest directly relevant external budget-control baselines,
- and a few adjacent adaptive-allocation baselines when they support the broader claim.

But the paper must distinguish:
- **direct budget-control baselines**, and
- **adjacent adaptive-allocation baselines**.

That distinction will make the empirical story more reviewer-proof.

## Claims discipline for writing

- Emphasize platform strength and methodological honesty.
- Treat pairwise BT as a strong active line / baseline, not the settled endpoint.
- Treat a local stop-vs-act gate as an implementation approximation, not the full conceptual center.
- Present heavier models and larger scaling as later-stage tools after target quality improves.
- Avoid implying that current partial external-baseline integration already settles the empirical picture.

## Best current headline

A strong safe headline for the paper direction is:

**effective test-time compute allocation depends on deciding which active branch deserves the next unit of compute, not merely on allowing more reasoning steps overall.**
