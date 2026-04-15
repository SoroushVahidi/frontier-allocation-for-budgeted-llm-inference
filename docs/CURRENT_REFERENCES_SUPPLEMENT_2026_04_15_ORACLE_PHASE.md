# Current references supplement (oracle-phase)

## Purpose

This note updates the project-side literature interpretation for the current oracle-label transition phase.

It focuses on what the literature means **after** the repository has already tried many bounded lightweight stop-vs-act target variants and has moved into oracle-label pilot readiness.

---

## Most relevant literature themes now

### 1. Metareasoning / value of computation
These papers remain the core conceptual foundation:
- compute is an action,
- it has value,
- and it should only be spent when its expected gain exceeds its opportunity cost.

Current repo implication:
- the project framing remains correct,
- but better local labels are now needed to teach that decision faithfully.

### 2. Active feature acquisition / value-of-information acquisition
These remain among the closest analogies because they ask whether the next acquisition is worth paying for under a budget.

Current repo implication:
- the stop-vs-act controller should ultimately learn from labels that reflect marginal action value under a budget,
- not just eventual branch quality.

### 3. Difference rewards / local credit assignment / action-gap supervision
This literature still strongly supports supervision based on incremental contribution over a baseline rather than raw terminal success.

Current repo implication:
- paired ACT-vs-STOP oracle action-gap labels are now the most justified teacher signal for the next phase.

### 4. Paired comparison / matched action-gap estimation
This theme became more important in the bounded stop-vs-act phase.

Current repo implication:
- action-gap supervision is still the right object,
- but bounded lightweight local approximations were not faithful enough.

### 5. Opportunity-cost / preserve-budget / reallocation-aware baselines
These papers remain especially important because they sharpen what STOP should mean.

Current repo implication:
- STOP should represent preserved compute being available to future downstream allocation,
- not merely local inactivity.

### 6. Active imitation learning / selective state sampling / expensive-label allocation
This is now a central theme because the repo is preparing a pilot in which expensive oracle labels will be generated only for a selected subset of states.

Current repo implication:
- the pilot should choose states that are on-distribution, non-redundant, and decision-critical,
- not just high-uncertainty by themselves.

### 7. Contrastive reasoning supervision / sibling comparisons
Reasoning-specific work suggests that local supervision is strongest when nearby alternatives create meaningful comparisons.

Current repo implication:
- pilot states with close sibling alternatives or near decision flips are especially valuable for oracle-labeling.

---

## What bounded repo evidence has now changed

The literature motivated many bounded experiments. The repository now has evidence that several reasonable lightweight fixes were not enough to replace the current default.

That means the current literature-backed interpretation is now:

- the stop-vs-act controller family still looks right,
- but lightweight local target construction likely has insufficient label fidelity,
- so the next serious step is higher-fidelity offline oracle-style supervision.

This is the important phase transition.

---

## Current strongest literature-backed project interpretation

A good concise interpretation now is:

- use the current default stop-vs-act setup as the anchor baseline,
- move from lightweight local target engineering to label-fidelity engineering,
- generate paired ACT-vs-STOP oracle action-gap labels on a selected pilot state set,
- and only then judge whether the stop-vs-act line can substantially improve through stronger supervision.

---

## Most relevant reference buckets for the next paper phase

For future writing and project positioning, the main buckets now are:

1. **Metareasoning / value of computation**
2. **Adaptive test-time compute allocation / budgeted inference**
3. **Active feature acquisition / value-of-information acquisition**
4. **Difference rewards / local credit assignment / action-gap supervision**
5. **Paired comparison / matched action-gap estimation**
6. **Opportunity-cost / preserve-budget / reallocation-aware baselines**
7. **Active imitation learning / selective state sampling**
8. **Contrastive reasoning supervision / sibling comparisons**

---

## Practical implication for the repo

When updating notes or planning the paper, the strongest current message is:

- the repo already tested many reasonable lightweight target variants,
- those bounded negative results justified a phase transition,
- and the current serious next step is an oracle-label pilot with carefully selected states and explicit quality gates.

That is the cleanest current interpretation of the project.
