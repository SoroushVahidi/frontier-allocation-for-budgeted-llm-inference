# Next Paper Summary, References, and Goals

## Why this file exists

This repository already supports the manuscript:

**When to Revise: Cost-Aware Adaptive Routing for LLM Reasoning**

That manuscript is centered on **query-level binary adaptive routing** between a cheap reasoning route and a revise-based route under a budget.

The next manuscript must be **materially different** in its main problem, main method, and main experimental story.

This file summarizes our current understanding of:
- what the existing manuscript already covers
- what the new paper should be about
- which literature matters most
- what the immediate research goals are

---

## 1. Scope of the current manuscript

The current manuscript is centered on:

- query-level inference control
- binary cheap-vs-revise routing
- selective escalation / deciding when to revise
- fixed vs adaptive vs oracle comparisons
- v5 / v6 / v7 style adaptive routing policies
- matched manuscript regimes
- regime-dependent routing headroom
- answer-error signals vs generic warning signals

This means the next paper should **not** be framed as:
- a stronger learned router for the same binary setup
- an improved v5 / v6 / v7 paper
- the same four-regime routing paper with stronger classifiers
- another manuscript whose main question is still “when to revise”

---

## 2. New paper direction

The new paper should be centered on:

**budgeted frontier allocation across heterogeneous reasoning/controller families**

Short version:
- old paper: **When should we revise?**
- new paper: **Where should the next unit of compute go?**

Recommended framing:
- frontier allocation under a fixed budget
- heterogeneous controller / reasoning families
- oracle frontier headroom
- controller-design choices that affect realized budget use
- anti-collapse controller design
- later, if feasible: one more genuinely different modality (code/tool or retrieval)

Recommended honest terminology:
- **cross-controller frontier allocation**
- with heterogeneous reasoning/controller strategies

Avoid overclaiming “cross-strategy” unless the frontier includes genuinely different modalities beyond closely related controller/search variants.

---

## 3. Current best scientific claim

The strongest current claim for the new paper is:

**Under a fixed inference budget, cross-controller frontier allocation has measurable headroom beyond static controller choice, and controller-design choices such as anti-collapse constraints materially affect realized budget use and reasoning performance.**

This is different from the old binary revise-routing paper because:
- it is not a binary gate
- it is not query-level cheap-vs-revise escalation
- it studies heterogeneous frontier allocation under budget
- it emphasizes allocation behavior and controller design

---

## 4. Key mechanism-level finding so far

A central controller-design finding already emerging from the repo work is:

**Premature verify/prune can cause under-allocation collapse.**

Observed pattern:
- if verify/prune is allowed before any meaningful expansion, adaptive controllers may under-spend budget
- enforcing minimum exploration before prune/verify can restore sensible budget use
- this can materially improve realized performance in real API-backed runs

This should be treated as:
- a main ablation
- a controller-design principle
- one of the strongest mechanism-level findings in the new paper

Do not make the entire paper only about this one knob; instead use it as one important design result inside the broader frontier-allocation paper.

---

## 5. Literature summary

### Closest existing lines
The main nearby research areas are:

1. **Binary cheap-vs-revise / selective escalation**
   - already covered by the current manuscript
   - not the target for the new paper

2. **Query-level multi-strategy routing**
   - e.g., Route-to-Reason
   - usually picks one strategy per query
   - different from frontier allocation across multiple controller families

3. **Branch-level / tree-search control**
   - e.g., AB-MCTS, DUCHESS
   - controls width/depth/pruning inside one search framework
   - different from heterogeneous frontier allocation across families

4. **Budgeted metacontrollers**
   - e.g., CoT2-Meta
   - rich multi-action control within a tree-centric framework
   - close in spirit, but still not the same as heterogeneous controller-family frontier allocation

### Main novelty lesson
We should **not** claim novelty for:
- generic branch-level allocation
- generic metacontrol
- generic budget-aware reasoning
- generic multi-strategy routing

We should instead emphasize:
- heterogeneous frontier allocation
- oracle frontier headroom
- anti-collapse controller design
- how controller design changes realized budget use, not only final accuracy

---

## 6. Current repo-grounded controller families

Current families already used or scaffolded in the repo include:

- `reasoning_greedy`
- `self_consistency_3`
- `reasoning_beam2`
- adaptive controller variants such as:
  - `adaptive_min_expand_0`
  - `adaptive_min_expand_1`
  - `adaptive_min_expand_2`

These support a first paper version centered on **cross-controller frontier allocation**.

A stronger later version should add at least one more genuinely different modality if supported cleanly:
- code/tool reasoning
- retrieval-assisted reasoning
- other truly distinct reasoning family

---

## 7. Minimal publishable version vs stronger version

### Minimal publishable version
- cross-controller frontier allocation
- oracle frontier headroom
- anti-collapse controller ablation
- real runs on at least one meaningful dataset
- multiple budgets
- larger-than-smoke subsets

### Stronger version
- everything above, plus:
- at least one more genuinely different modality
- cross-dataset evidence
- stronger oracle-gap evidence
- more robust controller-allocation analysis

---

## 8. Immediate research goals

The next practical goals are:

1. Produce a real manuscript-style frontier table with:
   - multiple budgets
   - larger subset sizes
   - oracle frontier upper bound
   - selected-controller frequencies
   - realized accuracy / cost / action usage

2. Strengthen the anti-collapse result with:
   - larger slices
   - more than one budget
   - more than one controller family
   - ideally more than one dataset

3. Keep repo organization honest:
   - old manuscript assets remain clearly separate
   - new-paper artifacts use names involving:
     - frontier
     - controller
     - allocation
     - anti_collapse
     - oracle_gap

4. If feasible, add one more genuinely distinct modality to the frontier.

---

## 9. What to avoid

Avoid drifting back into:
- binary revise-routing framing
- “better router for the old paper”
- “same paper with stronger classifiers”
- “generic branch allocation is novel”
- calling the frontier strongly heterogeneous if it only contains closely related controller/search variants

---

## 10. Working title directions

Good current title directions include:

- **Budgeted Frontier Allocation for Heterogeneous LLM Reasoning Controllers**
- **Headroom and Anti-Collapse Design in Budgeted Frontier Allocation for LLM Reasoning**
- **Cross-Controller Frontier Allocation for Budgeted LLM Reasoning**

---

## 11. Bottom line

The new paper should be a **distinct paper** centered on:

**budgeted frontier allocation across heterogeneous reasoning/controller families, with oracle headroom and anti-collapse controller design**

The repo is no longer only a binary adaptive-routing repo; it now also supports a real emerging second direction. The immediate task is to turn that second direction into clean, larger, manuscript-quality evidence.
