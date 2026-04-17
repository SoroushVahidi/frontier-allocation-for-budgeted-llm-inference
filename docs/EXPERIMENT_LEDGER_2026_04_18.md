# Experiment ledger (2026-04-18)

## Purpose

This note is a compact ledger of the most important experiment families in the current repository.

It is not a full replacement for the detailed method-status notes. Instead, it records:
- what experiment families exist,
- what they were trying to test,
- whether they look successful, mixed, or currently unsuccessful,
- and how they should be interpreted going forward.

## Reading rule

Use this ledger to orient yourself quickly.
Use the linked detailed notes for artifact paths, commands, and exact caveats.

## Legend

- **Strong / useful**: clearly worth keeping in the current project scaffold
- **Mixed / bounded**: informative and useful, but not settled as a default winner
- **Weak / not the right fix**: important negative result or not strong enough to justify default use

---

## 1. Frontier-allocation framing

### Goal
Shift from the old binary revise-routing story to fixed-budget next-step branch allocation.

### Status
**Strong / useful**

### Why
This is now the clearest and strongest repository identity.

### Interpretation
Keep as canonical.

---

## 2. Anti-collapse controller design

### Goal
Prevent pathological budget allocation collapse and improve realized spend behavior.

### Status
**Strong / useful**

### Why
Repeated repo notes indicate anti-collapse design matters materially.

### Interpretation
Keep as a core evaluation and method layer.

---

## 3. Pairwise BT / pairwise branch comparison line

### Goal
Use pairwise comparison as the main learned object for branch allocation.

### Status
**Strong / useful**

### Why
Still one of the strongest active learned directions and a meaningful anchor baseline.

### Interpretation
Keep as a strong baseline/default learned object, but not necessarily the final supervision semantics.

---

## 4. Stronger tabular model classes (GBDT etc.)

### Goal
See whether stronger model class alone solves branch-allocation weakness.

### Status
**Mixed / bounded**

### Why
Model-class changes alone did not yield a robust universal winner.

### Interpretation
Useful baseline family, not the primary next move.

---

## 5. Brute-force / near-brute-force label generation

### Goal
Generate higher-fidelity supervision for branch allocation.

### Status
**Strong / useful**

### Why
Materially reduced the data bottleneck and made stronger audits possible.

### Interpretation
Keep and continue, but do not assume label quantity alone solves the main bottleneck.

---

## 6. Exact-vs-approx audits and target-fidelity regimes

### Goal
Understand how supervision quality and regime design affect learning.

### Status
**Strong / useful**

### Why
These passes sharpened understanding of the true bottleneck and showed regime design matters a lot.

### Interpretation
Canonical diagnostic layer.

---

## 7. Hard-region exact promotion

### Goal
Spend exact supervision on mined difficult branch comparisons.

### Status
**Mixed / bounded**

### Why
Improved localization and instrumentation more than end metrics.

### Interpretation
Useful for targeted high-value relabeling, not a full solution.

---

## 8. Hard-case feature representation improvements

### Goal
Make the model better on near-tie and adjacent-rank slices through stronger features.

### Status
**Strong / useful**

### Why
Richer features materially improved hard slices for the pairwise logistic path.

### Interpretation
Keep richer hard-case representation in the current strong scaffold.

---

## 9. Ternary / selective-abstention formulations

### Goal
Handle ambiguity more honestly than forced binary labels.

### Status
**Mixed / bounded**

### Why
Ternary/abstention clearly revealed a real coverage-accuracy tradeoff, but did not close the hardest-slice gap.

### Interpretation
Important evidence that ambiguity is real, but not a finished solution.

---

## 10. Ambiguity calibration + fallback

### Goal
Improve accepted-accuracy / coverage behavior and ambiguous-case resolution quality.

### Status
**Mixed / bounded**

### Why
Improved operating behavior in some settings, but did not clearly solve near-tie forced behavior.

### Interpretation
Useful control layer, not the core bottleneck fix.

---

## 11. Dedicated near-tie routing policies

### Goal
Route hard near-tie cases differently from ordinary comparisons.

### Status
**Mixed / bounded**

### Why
Meaningful improvements in some policies, but gains are policy-dependent and not fully robust.

### Interpretation
Useful hard-case lever, but still not the final answer.

---

## 12. Near-tie specialized pointwise fallback

### Goal
Use a specialized pointwise expert to resolve deferred or hard near-tie cases.

### Status
**Promising but mixed**

### Why
Specialized pointwise fallback retained some of the strongest near-tie signal, but remains brittle and not fully solved.

### Interpretation
Keep in the current strongest scaffold, but do not overclaim closure.

---

## 13. Tie-aware post-hoc deferral

### Goal
Add cleaner unresolved/deferred accounting without degrading strong existing hard-slice behavior too much.

### Status
**Strong / useful**

### Why
Improved controller cleanliness and more honest ambiguity handling.

### Interpretation
Current strongest ambiguity-handling scaffold.

---

## 14. Deferred-only specialist training

### Goal
Train a specialist only on deferred cases to improve deferred-subset quality.

### Status
**Weak / not the right fix**

### Why
Did not improve deferred-subset quality enough and hurt forced/top-1 behavior.

### Interpretation
Do not treat as the main next direction.

---

## 15. Learned two-stage deferral

### Goal
Move from post-hoc deferral to a more principled learned defer family.

### Status
**Promising but mixed**

### Why
Interesting controller family, but current bounded runs remain mixed and do not yet beat the strongest tie-aware post-hoc scaffold.

### Interpretation
Keep as an active but non-default line.

---

## 16. Penalized marginal left/right/defer targets

### Goal
Make targets more opportunity-cost-aware under a budget.

### Status
**Promising but not closed**

### Why
Important semantic improvement, especially after fixing branch-specific cost so lambda matters, but defer / tau calibration remains unresolved.

### Interpretation
High-value target-design direction, still under active refinement.

---

## 17. Cohere bounded passes

### Goal
Test whether external adjudication or listwise reranking can improve hard ambiguous-case handling or provide useful comparisons.

### Status
**Mixed / bounded**

### Why
Useful for understanding limits and adjacent baselines, but not a clean default fix for the bottleneck.

### Interpretation
Adjunct comparison line, not canonical bottleneck solution.

---

## 18. Value-target / selective marginal-allocation direction

### Goal
Move from brittle pairwise winner labels toward branch-level value plus defer-aware derived decisions.

### Status
**Research-backed and promising, not yet empirically closed**

### Why
Recent research-takeaway notes suggest this is the strongest next target-design direction.

### Interpretation
One of the best next bounded implementation directions.

---

## Current strongest scaffold overall

The strongest current scaffold is still:

> **pairwise default + tie-aware post-hoc deferral + specialist pointwise fallback**

But the most promising next target-design direction is:

> **budget-conditioned branch-level value or penalized marginal continuation value with explicit defer / unresolved handling.**

## Overall project lesson

The repo’s main problem is not lack of experiments. The repo already has many useful method families.

The central lesson is:

> **the current bottleneck is target semantics and selective ambiguity handling, not generic capacity or infrastructure.**
