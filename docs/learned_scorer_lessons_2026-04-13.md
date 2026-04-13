# Learned scorer lessons note (2026-04-13)

This note records the main lessons from the first learned branch-scoring experiments so they can later be used in manuscript writing, positioning, and experimental interpretation.

## 1. Why this note matters

The learned-scorer experiments are not only implementation steps. They have already clarified what the project's **real local learning problem** is. Preserving these lessons now is important because they are likely to become part of the paper's core argument.

## 2. High-level lesson

The project has shifted from:

> **Can an adaptive controller act at all?**

to:

> **What local target should a branch scorer learn in order to support good fixed-budget allocation decisions?**

This shift is important. It means the central bottleneck is no longer infrastructure or controller mechanics alone. The main difficulty is the design of the local branch-scoring target.

## 3. v1 lesson: static branch-promise prediction is too weak

The first lightweight learned scorer used a proxy closer to static branch promise. This was a reasonable first step, but it did not beat the strongest hand-designed ranking rule in pilot comparison.

Main interpretation:
- a branch can look promising in a static sense while still being a poor place to spend the **next** unit of compute
- the controller does not only need a notion of branch quality
- it needs a notion of **marginal value of additional computation**

Therefore, v1 should be interpreted as an informative negative result:
- learning alone is not enough if the local supervision target is misaligned with the allocation objective
- a learned scorer trained on the wrong local target can lose to a strong heuristic ranking rule

## 4. v2 lesson: continuation-style targets are closer to the right object

The second learned scorer moved toward a continuation-value style target. Even though the target remains approximate, this direction is conceptually much closer to the real local decision problem.

Main interpretation:
- the relevant local question is not simply "is this branch good?"
- the relevant local question is closer to "what is the value of giving this branch one more unit of compute?"
- continuation-style or progress-style targets are more naturally aligned with fixed-budget adaptive allocation than static promise targets

This lesson should remain central in manuscript framing.

## 5. Current best project interpretation

The learned scorer should not be positioned as a generic verifier or static branch classifier. The strongest current interpretation is:

> The learned branch scorer is an estimator of **marginal continuation value** or **marginal value of computation** for a partial reasoning branch.

This aligns better with:
- fixed-budget branch allocation
- metareasoning / value-of-computation ideas
- process-progress style supervision
- local-to-global theorem targets based on misranking or continuation-value estimation error

## 6. Current empirical bottleneck

The main remaining bottleneck is now the gap between:
- **approximate continuation labels from logged traces**, and
- the **true counterfactual marginal value** of one extra compute unit on a branch

In other words, the learned-scorer problem has improved, but it is still not yet using the fully correct local supervision signal.

## 7. Practical implication for future experiments

The next experimental improvements should prioritize:
1. better continuation-value target construction
2. stronger out-of-sample controller-level evaluation
3. clearer decision-point ranking metrics

The next improvements should **not** prioritize:
- large model complexity jumps before target quality improves
- broad benchmark scaling before the local target is better aligned
- overclaiming causal correctness from approximate continuation labels

## 8. Likely manuscript use

These lessons are likely to support several manuscript points later:

### 8.1 Motivation point
Naive local branch quality is not the right object for budgeted adaptive reasoning.

### 8.2 Method point
The local learner should estimate continuation-style branch value, not only static branch promise.

### 8.3 Theory point
A natural theorem target is to relate **local marginal-value misranking** to **global allocation regret**.

### 8.4 Experimental point
The empirical progression from v1 to v2 is evidence that target alignment matters, not only model class.

## 9. Working manuscript sentence

A useful working sentence is:

> Early learned-scorer experiments suggest that the main challenge is not merely learning whether a partial branch appears promising, but learning the marginal continuation value of spending additional compute on that branch under a fixed global budget.

## 10. Status

At the current stage, the safest and strongest interpretation is:
- v1 provided an informative negative result about target misalignment
- v2 moved the project closer to the right local learning problem
- the next major step is to reduce the gap between approximate continuation labels and true counterfactual marginal compute value
