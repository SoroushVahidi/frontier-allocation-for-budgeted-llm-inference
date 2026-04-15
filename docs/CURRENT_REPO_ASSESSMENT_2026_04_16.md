# Current repository assessment (2026-04-16)

## Purpose

This note is the current repository-wide assessment after the latest stop-vs-act follow-up passes.

It is meant to answer, in one place:
- what the repository currently is,
- what is strong,
- what has actually been implemented,
- what has already been tried,
- what the current bottleneck is,
- what should remain canonical,
- and what the next phase should be.

Use this note as the best single current-status summary for the project.

---

## Repository identity

This repository is for the **current NeurIPS-oriented project** on:
- fixed-budget adaptive test-time compute allocation for LLM reasoning,
- cross-controller frontier allocation,
- branch/controller decisions under a global compute budget,
- oracle frontier headroom,
- anti-collapse controller design,
- and supervision-target design for allocation decisions.

The central project question remains:

> **Is the next unit of compute worth spending here?**

That question is still the right one.

---

## Current overall assessment

The repository is currently best understood as:
- a **strong research platform**,
- with a **good problem framing**,
- and **active-development-level method maturity**.

### Strong parts of the repository
- Frontier/controller infrastructure is in place.
- Anti-collapse design and related audits are in place.
- Branch-scorer experimentation is substantial.
- Dataset and baseline readiness work is strong.
- The stop-vs-act line is now implemented and reproducibly testable.
- The repo keeps useful provenance and bounded experiment history.

### Not solved yet
- No robust learned-controller winner over the strongest heuristic baseline.
- No sufficiently stable local supervision target for stop-vs-act decisions.
- No broad enough real-model evidence for strong paper claims.
- No settled replacement for the current default stop-vs-act setup.

---

## What has actually been implemented

### Earlier established work
- Frontier/controller allocation scaffold.
- Comparative frontier audits.
- Pairwise BT and related branch-scorer lines.
- Reliability-aware and warm-start branch-scorer experiments.
- Baseline/data readiness tooling.

### Implemented stop-vs-act line
The stop-vs-act controller is no longer a proposal. It is implemented and has already gone through multiple bounded passes.

Implemented pieces include:
- stop-vs-act dataset construction,
- stop-vs-act train/eval path,
- end-to-end stop-vs-act wrapper,
- bounded robustness sweep,
- diagnosis + targeted revision,
- label-refinement pass,
- one-step counterfactual target pass,
- small-horizon ACT-vs-STOP target pass,
- target-stabilization / repeated-averaging pass,
- matched-comparator pass,
- policy-coupled STOP-baseline pass.

This is now a substantial experimental branch, not a sketch.

---

## What has been learned

### High-confidence conclusions
1. The overall project framing is strong and still worth pursuing.
2. The stop-vs-act controller framing remains the best near-term controller framing.
3. The line is implemented enough that future work should be empirical refinement, not conceptual setup.
4. The current bottleneck is not infrastructure and not mainly model class.

### Mixed but informative conclusions
1. Initial stop-vs-act feasibility was promising.
2. Robustness versus the uncertainty-only baseline is generally better than robustness versus the strongest heuristic baseline.
3. A targeted uncertainty-handling revision helped on a small grid but did not solve the method.

### Negative but valuable conclusions
1. Simple threshold / uncertainty-band tuning did not fix the problem.
2. One-step here-vs-best-other counterfactual target did not replace the default.
3. Small-horizon ACT-vs-STOP target did not replace the default.
4. Repeated local averaging improved stability metrics but not controller outcomes.
5. Matched-RNG ACT-vs-STOP comparison did not replace the default.
6. One-step policy-coupled STOP reallocation also did not replace the default.

These are useful negative results because they narrow the real source of error.

---

## Current main bottleneck

The current main bottleneck is:

**local supervision target quality, especially the decision-relevance and stability of the local ACT-vs-STOP comparison.**

This now looks more specific than earlier generic “label noise” language.

The problem appears to involve:
- noisy local target estimation,
- unstable bounded rollout comparisons,
- imperfect ACT-vs-STOP comparator construction,
- and especially imperfect STOP semantics.

The latest evidence suggests:
- matched randomness alone is not enough,
- simple stabilization alone is not enough,
- and one-step policy-coupled STOP is still too shallow.

So the current deeper issue is likely:

**how to define ACT versus a genuinely policy-coupled, opportunity-cost-aware STOP baseline under a bounded future horizon.**

---

## What should remain canonical now

### Canonical
- The overall fixed-budget frontier-allocation framing.
- The stop-vs-act line as the main near-term controller direction.
- The current default stop-vs-act setup as the anchor baseline inside that line.
- The bounded small-grid evaluation style for this phase.
- Conservative interpretation and promotion rules.

### Exploratory but important
- Counterfactual target variants.
- Matched-comparator variants.
- Policy-coupled STOP variants.
- Additional branch-scorer variants.

### Historical / provenance only
- Older binary revise-routing manuscript artifacts.
- Older note snapshots that do not reflect the current stop-vs-act phase.

---

## What we are doing now

The project is currently in this phase:

**bounded refinement of the stop-vs-act supervision target, with the current default setup as anchor and comparator-design quality as the main unresolved issue.**

That means we are currently doing:
- bounded stop-vs-act target refinement,
- bounded comparator refinement,
- bounded diagnosis of why reasonable target variants are not replacing the default,
- repo-side consolidation of notes and safe claims.

That also means we are **not** currently centered on:
- heavier models,
- broad benchmark scaling,
- or searching for more existing external labeled data as the main fix.

---

## What we should do next

### Most likely next method step
The next step should likely be:

**a slightly longer-horizon, policy-coupled reallocation-aware STOP baseline**, still bounded and lightweight.

Reason:
- one-step policy-coupled STOP looks too shallow,
- matched randomness alone was not enough,
- and the remaining likely mismatch is the future meaning of preserved compute.

### Practical next-phase goals
- make STOP mean “release this compute unit back to the downstream allocator under the same policy context,”
- keep comparisons tightly matched,
- keep the current default as anchor,
- continue using small matched grids,
- only promote changes if they improve both margins and win/loss behavior.

### What should *not* be the next move
- not broad scaling,
- not heavier controller models,
- not more threshold-only tuning,
- not replacing the default with a new variant on weak evidence,
- not treating more external data as the main immediate fix.

---

## Safe current wording

Safe to say:
- the repository has a strong framing and strong experimental infrastructure,
- stop-vs-act is implemented and important,
- the current default stop-vs-act setup remains the best bounded baseline within that line,
- the strongest current bottleneck is local comparator/target quality,
- several bounded negative results have narrowed the next target-design question.

Not safe to say:
- the method is already robustly better than the best heuristic baseline,
- a counterfactual or policy-coupled target already solved the problem,
- the remaining fix is just scale or more external data,
- the current stop-vs-act line is finished.

---

## Bottom line

The repository is in good research shape.

Its strongest current state is:
- strong framing,
- strong infrastructure,
- strong provenance,
- implemented stop-vs-act line,
- and increasingly precise diagnosis of what is still wrong.

The main unresolved issue is no longer whether the repo can study the problem. It is:

**how to build a local ACT-vs-STOP target whose STOP side really reflects the downstream opportunity cost of preserving compute.**
