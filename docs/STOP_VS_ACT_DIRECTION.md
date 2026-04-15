# Local gating vs branch-priority allocation

## Clarification

For the current project, the main conceptual object is **branch-priority / next-step allocation over active branches**.

The main question is:

> **Which active branch should receive the next unit of compute?**

A local stop-vs-act question can still be used, but only as a **local approximation** or **continuation gate** inside a richer branch-allocation process.

## Better decomposition

A cleaner allocator has two layers:

1. **Branch-priority / candidate-selection layer**
   - Compare active branches.
   - Maintain their scores or priorities.
   - Choose the highest-priority candidate for the next budget step.

2. **Optional local continuation gate**
   - Ask whether the selected candidate really deserves the next unit of compute.
   - If not, redirect or preserve that budget according to the downstream allocation rule.

In this view, a local gate is not the whole algorithm. It is only a layer on top of branch comparison / ranking.

## Why a local gate was considered useful

Compared with a first-pass continuous marginal-value regressor or full multi-action allocator:

1. A binary local gate can be easier to train.
2. Its targets may be more stable than fully continuous marginal-value targets.
3. It can be used as a bounded approximation while the richer ranking/allocation policy is still under development.

But this convenience should not be mistaken for the full conceptual formulation of the project.

## Role of pairwise BT branch scoring

Pairwise BT branch scoring remains central and useful:
- as a strong baseline,
- as an active branch of work,
- and as one of the cleanest current ways to represent branch comparison.

This fits the project better conceptually than treating a standalone local gate as the whole allocator.

## Recommended implementation interpretation

A clean near-term implementation can look like this:

- keep active branches in a priority structure,
- score or rank them,
- pop the highest-priority branch,
- expand / verify / update it,
- recompute its score,
- push it back if still alive.

A local gate may still be inserted after candidate selection, but only as a local decision aid.

## Recommended language for the paper and docs

Prefer terms like:
- branch-priority allocation,
- next-step branch allocation,
- continue-here vs reallocate-elsewhere,
- candidate selection plus continuation gate,
- budget allocation over active branches.

## File-role note

This file keeps the historical `STOP_VS_ACT_DIRECTION.md` path for continuity, but the current repo interpretation is broader: branch ranking / next-step allocation is the main conceptual center.
