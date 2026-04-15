# Current references supplement (2026-04-16)

## Purpose

This note refreshes the project-side literature interpretation after the latest stop-vs-act bounded passes.

It focuses on what the literature implies **now**, given that several plausible target variants have already been tried in the repo and did not replace the current default.

This is a working guidance note, not a formal bibliography.

---

## Literature themes that still matter most

### 1. Metareasoning / value of computation
These papers still provide the core conceptual frame:
- extra reasoning is an action,
- that action has value,
- and it should be chosen only when its expected gain exceeds its opportunity cost.

Current repo-side implication:
- keep framing the project around whether the next unit of compute is worth spending **here**.

### 2. Process rewards / verifiers / progress-aware signals
These lines remain useful because they support intermediate-state signals rather than final correctness alone.

Current repo-side implication:
- use them as ingredients or features,
- but do not treat them as the final answer to local target construction.

### 3. Uncertainty-aware stopping / escalation / abstention
These papers still support the binary stop-vs-act framing and the use of uncertainty as a real control signal.

Current repo-side implication:
- binary stop-vs-act remains the right controller family for now,
- but uncertainty handling alone has already proven insufficient as the main fix.

### 4. Active feature acquisition / value-of-information acquisition
This remains one of the closest analogies to the stop-vs-act label problem, because it asks whether the next acquisition is worth taking under a budget.

Current repo-side implication:
- local marginal value and cost-sensitive acquisition remain strong conceptual guides,
- especially for opportunity-cost-aware STOP semantics.

### 5. Difference rewards / local credit assignment / local counterfactual contribution
These papers remain highly relevant because they emphasize contribution over a baseline rather than raw eventual reward.

Current repo-side implication:
- the comparator should still reflect incremental contribution relative to a meaningful baseline,
- not just branch-local eventual usefulness.

### 6. Horizon-conditioned / finite-horizon local targets
These papers supported the small-horizon experiments and still matter because one-step local signals can be too myopic.

Current repo-side implication:
- horizon still matters,
- but bounded repo evidence suggests that a small horizon alone does not fix the problem if STOP semantics are still weak.

### 7. Paired comparison / matched-rollout / action-gap estimation
This literature became more important after later bounded experiments.

Current repo-side implication:
- paired ACT-vs-STOP gaps are the right object to think about,
- but paired randomness alone did not solve the repo-side problem.

### 8. Opportunity-cost / preserve-budget / reallocation-aware baselines
This is now the most important new literature theme for the current phase.

Current repo-side implication:
- STOP should mean preserve compute for later use under the downstream policy,
- not merely branch-local inactivity or a weak local fallback proxy.

---

## What bounded repo evidence has now ruled out as a main fix

The literature helped motivate many ideas. The repository has now tested several of them in bounded form.

The following are useful but not yet strong enough to treat as the main fix:
- threshold / gray-band tuning by itself,
- simple uncertainty-band handling,
- one-step here-vs-best-other counterfactual target,
- small-horizon ACT-vs-STOP target by itself,
- repeated averaging / estimator stabilization by itself,
- matched randomness by itself,
- one-step policy-coupled STOP reallocation by itself.

These are not failures of the overall direction. They are evidence that the remaining bottleneck is more specific.

---

## Current strongest literature-backed interpretation

The best current interpretation is:

- stop-vs-act remains the right near-term controller framing,
- the local comparison should still be action-conditional and opportunity-cost-aware,
- but the real unresolved issue is now the future meaning of STOP,
- especially how preserved compute should be reallocated by the downstream policy over a bounded horizon.

In concise form:

**the comparator is still too branch-local or too shallow on the STOP side.**

---

## Most relevant reference buckets for the next paper phase

For future writing and positioning, the reference buckets that matter most now are:

1. **Metareasoning / value of computation**
2. **Adaptive test-time compute allocation / budgeted inference**
3. **Process reward models / verifier-guided reasoning**
4. **Uncertainty-aware stopping / escalation / abstention**
5. **Active feature acquisition / value-of-information acquisition**
6. **Difference rewards / local credit assignment**
7. **Paired comparison / matched-rollout action-gap estimation**
8. **Opportunity-cost / preserve-budget / reallocation-aware baselines**
9. **Finite-horizon / horizon-conditioned local values**

---

## Current practical literature takeaway for the repo

The current literature-backed message for the repo is:

- the project no longer mainly needs another controller family,
- and it no longer mainly needs another threshold tweak,
- it needs a better local ACT-vs-STOP comparison in which STOP more faithfully represents preserved compute being reused by the downstream allocator.

---

## Safe wording for current notes and paper planning

Prefer to say:
- the stop-vs-act line is informed by metareasoning, uncertainty-aware control, local credit assignment, acquisition/value-of-information, paired action-gap estimation, and reallocation-aware baselines,
- but bounded evidence remains conservative,
- and the current default setup remains the best bounded baseline until a stronger opportunity-cost-aware STOP comparator wins.
