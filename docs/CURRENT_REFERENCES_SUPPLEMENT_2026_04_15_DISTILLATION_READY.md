# Current references supplement (distillation-ready phase)

## Purpose

This note updates the project-side literature interpretation for the current phase after:
- many bounded lightweight stop-vs-act target variants,
- the transition to oracle-label pilot readiness,
- and the addition of selective-distillation and student-training scaffolding.

It focuses on what the literature means **now**, given the repository’s current state.

---

## Most relevant literature themes now

### 1. Metareasoning / value of computation
These papers remain the core conceptual foundation:
- compute is an action,
- it has value,
- and it should only be spent when its expected gain exceeds its opportunity cost.

Current repo implication:
- the project framing remains correct,
- but better labels and better selective trust are now needed to teach that decision faithfully.

### 2. Active feature acquisition / value-of-information acquisition
These remain among the closest analogies because they ask whether the next acquisition is worth paying for under a budget.

Current repo implication:
- the stop-vs-act controller should ultimately learn from labels that reflect marginal action value under a budget,
- not just eventual branch quality.

### 3. Difference rewards / local credit assignment / action-gap supervision
This literature still strongly supports supervision based on incremental contribution over a baseline rather than raw terminal success.

Current repo implication:
- paired ACT-vs-STOP oracle action-gap labels remain the most justified teacher signal for the next phase.

### 4. Paired comparison / matched action-gap estimation
This theme became more important during the bounded stop-vs-act phase.

Current repo implication:
- action-gap supervision is still the right object,
- but bounded lightweight local approximations were not faithful enough.

### 5. Opportunity-cost / preserve-budget / reallocation-aware baselines
These papers remain especially important because they sharpen what STOP should mean.

Current repo implication:
- STOP should represent preserved compute being available to future downstream allocation,
- not merely local inactivity.

### 6. Active imitation learning / selective state sampling / expensive-label allocation
This is central because the pilot labels will be generated only for a selected subset of states.

Current repo implication:
- the pilot should choose states that are on-distribution, non-redundant, and decision-critical,
- not just high-uncertainty by themselves.

### 7. Oracle-label trust / audited acceptance / selective filtering
This is now a major theme for the repo.

Current repo implication:
- expensive labels should not be trusted uniformly,
- pre-distillation acceptance gates should depend on margin, audit evidence, and slice-wise quality,
- and filtered trust is now part of the method, not an afterthought.

### 8. Selective distillation / trusted-slice student learning
This is now the newest major theme.

Current repo implication:
- accepted labels should receive strong supervision,
- borderline labels should likely receive weaker / softer / uncertainty-aware supervision,
- rejected labels should be dropped,
- and student evaluation should test whether filtering preserved decision quality rather than just cleaning the dataset.

---

## What bounded repo evidence and new scaffolding now imply

The literature motivated many bounded experiments. The repository now has evidence that several reasonable lightweight fixes were not enough to replace the current default.

That means the current literature-backed interpretation is now:

- the stop-vs-act controller family still looks right,
- lightweight local target construction likely had insufficient label fidelity,
- the oracle-label pilot is the correct next empirical move,
- and selective distillation should not collapse all trusted labels into one uniform hard-label dataset.

This is the important current phase interpretation.

---

## Current strongest literature-backed project interpretation

A concise interpretation now is:

- use the current default stop-vs-act setup as the anchor baseline,
- move from lightweight local target engineering to higher-fidelity oracle-style supervision,
- generate paired ACT-vs-STOP oracle action-gap labels on a carefully selected pilot state set,
- apply selective acceptance/filtering before distillation,
- and train students under accepted-only and accepted+borderline conditions rather than assuming one uniform label bucket.

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
8. **Oracle-label trust / audited acceptance / selective filtering**
9. **Selective distillation / abstention-aware or soft-target student training**
10. **Matched-condition evaluation of filtered vs unfiltered supervision**

---

## Practical implication for the repo

When updating notes or planning the paper, the strongest current message is:

- the repo already tested many reasonable lightweight target variants,
- those bounded negative results justified a phase transition,
- the current serious next step is a real oracle-label pilot with explicit quality gates,
- and the current serious next step after that is selective distillation and matched-condition student evaluation.

That is the cleanest current interpretation of the project.
