# Research upgrade note (2026-04-17)

## Purpose

This note records the most useful current outside research takeaways for improving both:
- the **method**, and
- the **paper framing**.

It is a working guidance note, not a bibliography.

## Highest-value current research takeaway

The strongest current outside-research lesson is:

> **the controller should become a principled selective pairwise judge, and the overall paper should be framed as fixed-budget best-arm identification over branches.**

These are related but distinct upgrades.

## 1. Controller upgrade direction

### Selective pairwise judging
The current tie-aware post-hoc deferral controller is cleaner than earlier heuristic routing, but it still relies on a structured heuristic threshold stack.

The most promising upgrade is to move toward:
- a **calibrated selective pairwise judge**,
- with a more principled uncertainty score,
- and a validation-calibrated accept/defer decision.

### Why this matters
This would strengthen:
- the method itself,
- the interpretation of hard near-ties,
- and the credibility of accepted-set vs deferred-set claims.

### Practical repo implication
The next strong method pass should likely improve:
- confidence / uncertainty estimation for pairwise comparison,
- acceptance/defer calibration,
- and accepted-set risk / coverage reporting.

It should **not** start by redesigning the whole controller family again.

## 2. Paper-framing upgrade direction

### Fixed-budget best-arm identification over branches
The strongest current paper-framing upgrade is to present branch allocation as:
- a fixed-budget allocation problem,
- where active branches are candidate arms,
- and budget should be concentrated on unresolved competitors.

### Why this matters
This makes the work look:
- less like a collection of controller patches,
- and more like a principled allocation / identification problem.

### Practical repo implication
The paper should increasingly emphasize:
- gap-sensitive allocation,
- ambiguity concentrated in small-gap branch sets,
- and structured branch features as a path beyond independent arm treatment.

## 3. What this does **not** mean

It does **not** mean:
- immediately writing a theorem-first paper,
- discarding the current empirical scaffold,
- or stopping current controller work.

It means the current scaffold should be interpreted as an instantiation inside a stronger conceptual frame.

## 4. Best immediate use in the repository

The best immediate use is:

1. keep the current tie-aware post-hoc deferral scaffold stable,
2. improve it toward selective pairwise judging,
3. update notes and paper-positioning language to reflect fixed-budget identification more explicitly,
4. and keep external baseline comparisons conservative and clearly labeled.

## 5. Current recommendation

If choosing between many possible next passes, prefer work that makes one of these stronger:
- selective pairwise confidence/defer control,
- accepted-set risk / coverage reporting,
- structured fixed-budget branch-allocation framing,
- or external comparisons that support the more principled story.

Do not prioritize:
- another generic weak variant,
- another broad sweep without sharper method meaning,
- or more complexity that does not improve the paper’s conceptual center.
