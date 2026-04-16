# Allocation, not stop, is the conceptual center

This note records a clarified interpretation that emerged from recent project discussion.

## Main point

The repository should not be interpreted primarily as solving a literal global **stop-vs-act** problem.

The more faithful conceptual center is:

> repeatedly choose which active branch should receive the next unit of compute.

## Why this matters

A stop-vs-act framing can be useful as a local approximation, but it can easily distort the true scientific question.

The actual controller loop is closer to:
1. score active frontier actions,
2. identify the highest-value candidate,
3. allocate the next unit of budget there.

So the central learned object is not “should we stop?” in isolation. It is:
- a branch ranking,
- a branch-vs-branch comparison,
- or a branch-vs-outside-option comparison.

## When a stop view is still useful

A stop decision is still meaningful when modeled as one of the following:
- a **null action** among frontier actions,
- a **local continuation gate** on a candidate branch,
- or a shorthand for “this branch is not the best use of the next unit.”

Under this view:
- **ACT** means the branch deserves the next compute unit.
- **STOP** means the branch does not beat the outside option.

The outside option could be:
- another active branch,
- another controller family,
- verifier use,
- or true termination.

## Recommended mathematical interpretation

The most faithful target is comparative marginal utility under remaining budget `B`.

A ranking-style view:
- choose `b* = argmax_b Δ(b | B)`

A binary helper view for a single branch `b`:
- ACT if `Δ(b | B)` beats the outside option,
- STOP otherwise.

## Writing recommendation

Prefer phrases such as:
- next-step branch allocation,
- frontier allocation,
- branch-priority selection,
- marginal value of the next compute unit,
- opportunity-cost-aware selection.

Avoid making the paper sound like it is fundamentally about global stop-vs-act unless that is truly the algorithmic center.

## Practical consequence for this repo

- Pairwise and pointwise branch-scoring lines are conceptually central.
- Local stop-vs-act datasets or gates are helper mechanisms.
- Evaluation should emphasize whether the controller spends the next unit on the right frontier action, not only whether it stops or continues in a local sense.
