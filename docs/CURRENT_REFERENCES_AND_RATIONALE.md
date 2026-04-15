# Current references and method rationale (canonical supporting note)

## Purpose

This note records the most relevant literature conclusions for the current project direction so they are available inside the repository and do not depend on external chat history.

Use this note as:
- a compact literature-backed rationale for the current method direction,
- a reminder of what nearby papers do and do **not** already solve,
- and a guide for what should be implemented next.

This note is **supporting** rather than primary. For current project interpretation, start with:
- `docs/CURRENT_PROJECT_STATUS.md`
- `docs/CURRENT_BOTTLENECKS.md`
- `docs/STOP_VS_ACT_DIRECTION.md`
- `docs/NEXT_LIGHTWEIGHT_STEPS.md`
- `docs/PAPER_POSITIONING_NOTE.md`

---

## Current project interpretation

The current project is best framed around the question:

> **Is the next unit of compute worth spending here?**

This is more precise than:
- generic branch ranking,
- generic controller scoring,
- or static branch quality prediction.

The ideal target is closer to the **expected marginal utility of the next compute action** under a fixed remaining budget.

However, for the current phase, the best first implementation is likely **not** a continuous marginal-value regressor. Under current proxy supervision, a **budget-conditioned binary stop-vs-act controller** is expected to be more stable, more auditable, and less brittle.

---

## Main literature-backed conclusions

### 1. Value-of-computation is the right conceptual lens
Relevant metareasoning and adaptive test-time compute papers motivate modeling the value of further computation rather than only final-answer quality. The project should therefore focus on whether an additional action is worth its cost, not merely whether a branch looks promising in isolation.

Practical implication:
- Prefer action-conditional allocation decisions over generic scalar branch scores when possible.

### 2. Process rewards and verifier signals are useful but not sufficient by themselves
Process reward models, verifier-guided reasoning, and progress-oriented supervision provide stronger intermediate signals than final correctness alone. But these signals still do not automatically equal the true marginal value of spending one more unit of compute on a branch.

Practical implication:
- Keep process/verifier features and branch-scoring signals, but treat them as components of an allocation decision, not the final target itself.

### 3. Current bottleneck is target mismatch more than model capacity
Nearby literature and current repo evidence both suggest that supervision quality and target alignment matter more than immediately scaling to heavier models. Continuous or fine-grained targets become especially noisy when labels are proxy-derived.

Practical implication:
- Improve supervision target design first.
- Do not treat larger models or broader sweeps as the first remedy.

### 4. Binary decisions are often more stable than noisy continuous scores
Several nearby papers and evaluation-oriented findings suggest that binary or thresholded decisions (stop/continue, act/escalate, route/don’t route) are usually more stable under uncertainty and label noise than directly regressing a continuous value target.

Practical implication:
- The first serious next controller should likely be a **binary stop-vs-act controller**.
- Use uncertainty both in the controller input and in training-data selection/reweighting.

### 5. Uncertainty should be used twice
The strongest nearby patterns use uncertainty in two roles:
1. **as a policy signal** to decide whether cheap reasoning is trustworthy enough,
2. **as a data-quality signal** to filter or downweight ambiguous training examples.

Practical implication:
- Treat uncertainty-aware training as part of the canonical next implementation direction.

### 6. Cheap approximate marginal labels are the right next step
The literature most useful for immediate progress supports approximate targets such as:
- stop vs one-more-action,
- +1 action delta labels,
- short-horizon small-k rollout deltas,
- bounded local oracle comparisons,
- explicit uncertain/ambiguous labels for near-zero estimated gain.

Practical implication:
- Before generating much more data, first define a clean lightweight label-construction protocol.

---

## Recommended current method direction

### Canonical near-term controller
A good first controller for the next phase is:

- **budget-conditioned**,
- **binary**,
- **stop-vs-act**,
- using uncertainty as both:
  - an inference-time feature,
  - and a training-time filtering or reweighting signal.

### Why this is preferred right now
Because current labels are approximate and noisy, a binary controller is currently preferable to a raw continuous marginal-value regressor for the first implementation.

This does **not** mean continuous value models are unimportant. It means they should likely come **after** label construction and calibration improve.

---

## Relationship to current branch-scorer line

Pairwise BT branch scoring remains important and should be preserved.

Current interpretation:
- it is one of the strongest active learned directions,
- it is a useful baseline and companion line,
- it may later become part of a hybrid controller,
- but it should not currently be documented as the settled final controller.

The current repo should therefore treat pairwise BT as:
- strong active branch,
- strong learned baseline,
- promising but not final.

---

## What should be done before HPC returns

Prioritize:
1. define binary stop-vs-act labels,
2. add uncertainty-aware filtering/reweighting,
3. test cheap approximate marginal labels,
4. run bounded matched comparisons versus strong heuristics and BT baseline,
5. update claims only after those bounded results are stable.

Do **not** prioritize yet:
- large-scale label generation,
- broad benchmark expansion,
- heavy neural models,
- overclaiming from exploratory wins.

---

## What should wait until HPC returns

After the lightweight phase shows better signal quality:
- larger-scale approximate marginal-label generation,
- larger robustness sweeps,
- more real-model runs,
- only then heavier models if they still look necessary,
- larger rollout/oracle-assisted label generation if the lightweight labels are still too weak.

---

## Closest reference themes to keep in mind

These are the most relevant theme buckets for the current project:

1. **Metareasoning / value of computation**
   - supports the conceptual framing of compute as an action with value.

2. **Adaptive test-time compute allocation / budgeted inference**
   - supports fixed-budget allocation framing and matched-cost evaluation.

3. **Process reward models / process verifiers / verifier-guided search**
   - supports intermediate-state and progress-aware signals.

4. **Uncertainty-aware stopping / escalation / routing**
   - supports binary stop-vs-act style decisions.

5. **Noisy supervision / ambiguity-aware preference learning**
   - supports filtering, reweighting, and cautious use of proxy labels.

---

## Suggested paper-side interpretation

The likely strongest paper story is:

**fixed-budget branch/controller allocation with supervision-target design as the central unresolved issue, and a budget-conditioned binary stop-vs-act controller as the most promising near-term controller design.**

This keeps the paper honest while still making a clear scientific contribution.

---

## Caution

Do not overstate the current state as:
- final,
- robustly solved,
- or already supported by broad real-model evidence.

The honest current position is:
- strong framing,
- strong infrastructure,
- promising learned directions,
- but supervision-target quality remains the main unresolved issue.
