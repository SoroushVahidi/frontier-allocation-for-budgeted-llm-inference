# Next phase: target stabilization and variance reduction

## Why this note exists

The repo has already completed several bounded stop-vs-act refinements:
- uncertainty-handling revision,
- label-refinement pass,
- one-step counterfactual target pass,
- small-horizon ACT-vs-STOP target pass.

The most important current conclusion is that the next step should focus on **stabilizing the target**, not inventing another superficially different label rule without addressing variance.

---

## Current diagnosis

The stop-vs-act line appears limited by:
- noisy local target estimation,
- unstable bounded rollout deltas,
- and insufficiently stable local value summaries.

This is deeper than:
- threshold tuning,
- uncertainty-band tuning,
- or one more simple target-family swap.

---

## Main objective

Improve the **stability and reliability** of the current stop-vs-act supervision target while keeping the pipeline lightweight and bounded.

---

## Priority sequence

### 1. Stabilize the current default target
Focus first on variance reduction for the current default target family.

Examples:
- matched ACT/STOP rollout pairing,
- repeated local target estimation with averaging,
- reduced randomness mismatch between compared local futures,
- target reliability scores for weighting.

### 2. Improve the bounded value summary, not only the threshold
If the horizon-end or local utility summary is too noisy, try a slightly more stable bounded summary before inventing another new target family.

Examples:
- smoother bounded horizon utility summaries,
- more stable aggregation over local candidate outcomes,
- less brittle dependence on a single end snapshot.

### 3. Keep comparisons matched and small
Use:
- 2–3 seeds,
- 2 budgets,
- current default as anchor,
- heuristic baseline as external reference.

### 4. Update claims only if stability improves
A small positive run is not enough. Promote changes only if:
- mean margins improve,
- win/loss counts improve,
- and the result is less noisy than prior passes.

---

## Explicit non-goals for this phase

Do **not** prioritize:
- broad scaling,
- heavier models,
- broad dataset expansion,
- another simple threshold-only refinement,
- replacing the default target path without stronger bounded evidence.

---

## Suggested concrete bounded experiment types

### A. Paired-rollout variance reduction
- Use tighter paired ACT/STOP local rollouts.
- Keep nuisance randomness aligned as much as possible.
- Train on paired-difference estimates rather than loosely matched local deltas.

### B. Multi-sample target averaging
- Estimate the same local target several times cheaply.
- Use the mean as the training target and the variance as a reliability feature/weight.

### C. Reliability-aware training weights
- Retain current default labels but add weights derived from local target stability.
- Do not collapse this into generic uncertainty suppression; keep it explicitly tied to target reliability.

### D. Slightly richer bounded value summary
- Use a more stable bounded utility estimate if current end-of-horizon utility is too brittle.

---

## Promotion rule

Only promote a refinement if it clearly improves on the current default in bounded matched evidence.

Otherwise:
- keep the default,
- keep the result as informative provenance,
- and continue treating stop-vs-act as promising but mixed.

---

## Bottom line

The next important work is:

**make the current stop-vs-act target more stable**

not:
- a new grand reframing,
- a broad scale-up,
- or another small threshold-only tweak.
