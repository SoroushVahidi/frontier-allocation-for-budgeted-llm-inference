# Current references supplement (2026-04-16)

## Purpose

This note refreshes the project-side literature interpretation for the current paper direction.

It is not a formal bibliography. It is a **working guidance note** for:
- how to think about the literature,
- which reference buckets matter most,
- which outside baselines are most important,
- and how to position the paper honestly.

## Highest-priority literature themes

### 1. Metareasoning / value of computation
This remains the core conceptual frame:
- extra reasoning is an action,
- that action has value,
- and it should be chosen only when its expected gain exceeds its opportunity cost.

Repo-side implication:
- keep the paper centered on whether the next unit of compute is worth spending **here**.

### 2. Adaptive test-time compute allocation / budgeted inference
This is the main neighboring AI framing.

Repo-side implication:
- the paper should clearly belong to the adaptive-inference / budgeted-allocation family,
- but should remain honest about the project’s more specific frontier-control question.

### 3. Process rewards / verifiers / progress-aware signals
These remain useful because they support intermediate-state signals, not only final correctness.

Repo-side implication:
- use them as ingredients, features, and neighboring baselines,
- but do not mistake them for the full solution to local controller supervision.

### 4. Uncertainty-aware stopping / escalation / abstention
This remains directly relevant to the stop-vs-act framing.

Repo-side implication:
- uncertainty is still important,
- but uncertainty handling alone is not the final fix.

### 5. Active acquisition / value-of-information / local credit assignment
These are important because they are among the closest conceptual analogies to deciding whether the next action is worth its cost.

Repo-side implication:
- local contribution and opportunity cost matter more than raw eventual usefulness.

### 6. Paired comparison / matched-rollout ACT-vs-STOP estimation
This matters because the object we ultimately want is a local action-gap estimate, not just a branch score.

Repo-side implication:
- paired ACT-vs-STOP thinking is still correct,
- but the STOP comparator remains too weak if preserved budget is not modeled realistically.

## Current strongest literature-backed interpretation

The best current interpretation is:

- stop-vs-act remains the right near-term controller family,
- the controller target should be action-conditional and opportunity-cost-aware,
- and the biggest remaining issue is still the meaning of STOP,
- especially how preserved compute should be reallocated by the downstream policy.

In concise form:

**the current comparator is still too shallow on the STOP side.**

## External baseline priority for this repo

### Most important direct / near-direct budget-control baselines
1. **s1** — strongest published practical baseline for explicit stop / continue style control.
2. **TALE** — strongest published per-instance budget-allocation baseline.
3. **L1** — highly relevant methodological baseline for hard or controlled token budgets, even if not yet venue-published in the same way.

### Important adjacent adaptive-allocation baselines
4. **BEST-Route** — strong published general adaptive-compute routing baseline.
5. **Learning How Hard to Think** — conceptually very relevant predecessor for adaptive compute allocation across inputs / procedures.

## Positioning rule for writing

When writing the paper, distinguish clearly between:
- **direct budget-control baselines**, and
- **adjacent adaptive-allocation baselines**.

This is important because not all neighboring papers operate in the same action space or at the same level of control.

## What bounded repo evidence has ruled out as a full solution by itself

Useful but not yet sufficient as the main fix:
- threshold tuning alone,
- uncertainty-band handling alone,
- one-step local counterfactual targets alone,
- short-horizon ACT-vs-STOP targets alone,
- stabilization / repeated averaging alone,
- paired randomness alone,
- weak policy-coupled STOP reallocation alone.

These remain useful components, but not yet the whole answer.

## Practical literature takeaway for the repo

The project no longer mainly needs:
- another loosely related controller family,
- another threshold tweak,
- or scale for its own sake.

It needs a better local ACT-vs-STOP comparator in which STOP faithfully represents preserved compute being reused later by the downstream allocator.

## Safe wording for paper planning

Prefer to say:
- the project is informed by metareasoning, adaptive test-time compute allocation, uncertainty-aware control, local credit assignment, paired action-gap estimation, and opportunity-cost-aware control;
- stop-vs-act is the strongest near-term controller family;
- and the current unresolved issue is supervision-target fidelity rather than infrastructure.
