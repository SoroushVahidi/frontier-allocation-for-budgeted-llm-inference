# Current references supplement (2026-04-15)

## Purpose

This note captures the most relevant literature conclusions from the recent project-analysis conversations that are not yet fully reflected in the older repository notes.

It is not a formal bibliography. It is a working project-side reference note explaining which literature themes matter most for the current phase and what they imply for the repo.

---

## Main literature themes now relevant

### 1. Metareasoning / value of computation
These papers support the central project framing:
- computation itself is an action,
- that action has value,
- and the controller should decide whether additional reasoning is worth its cost.

Project takeaway:
- keep framing the project around **whether the next unit of compute is worth spending here**.

### 2. Process rewards / process verifiers / verifier-guided reasoning
These papers support using intermediate-state and progress-aware signals rather than only final correctness.

Project takeaway:
- process/verifier signals are useful ingredients,
- but they should not automatically be treated as the true local target.

### 3. Uncertainty-aware stopping / escalation / routing
Nearby papers on stop/continue, act/escalate, and defer/not-defer decisions support:
- binary controller framing,
- calibration awareness,
- and using uncertainty as a real policy signal.

Project takeaway:
- binary stop-vs-act remains well motivated,
- and uncertainty should remain part of the controller design.

### 4. Reject-option / learning-to-defer / abstention-style supervision
These lines are useful because they suggest:
- explicit gray zones,
- asymmetric treatment of mistakes,
- and cautious handling of ambiguous labels.

Project takeaway:
- this supported several of our label-design and uncertainty-handling ideas,
- but bounded repo evidence later showed that threshold/gray-zone tuning alone was not enough.

### 5. Active feature acquisition / value-of-information acquisition
This literature is especially relevant because it supervises **whether the next acquisition is worth taking now**, often under a budget.

Project takeaway:
- this is one of the closest analogies to stop-vs-act label construction,
- especially for building local state-conditional utility targets rather than relying on terminal success labels.

### 6. Difference rewards / local credit assignment / local counterfactual contribution
These papers are important because they replace raw shared or terminal reward labels with local counterfactual contribution signals.

Project takeaway:
- they strongly support the idea that local stop-vs-act supervision should ideally reflect contribution over a baseline,
- not just raw eventual usefulness.

### 7. Horizon-conditioned / finite-horizon local value targets
These papers support using small-horizon local values instead of extremely myopic one-step gains.

Project takeaway:
- this motivated the small-horizon ACT-vs-STOP pass.
- bounded repo evidence so far suggests that this idea is conceptually sound but still too noisy in the current implementation to replace the default.

---

## What our bounded repo evidence changed

The literature helped motivate several ideas. The repo now has bounded evidence about which of those ideas were useful and which were not enough.

### Supported by both literature and current repo evidence
- binary stop-vs-act is still the right near-term controller framing,
- local target quality matters more than heavier models right now,
- uncertainty should be handled carefully and asymmetrically,
- local counterfactual thinking is relevant,
- target design matters more than raw classifier complexity.

### Motivated by literature but not yet validated strongly enough in this repo
- threshold/gray-band style label tuning as a main fix,
- one-step here-vs-best-other counterfactual target as a replacement default,
- small-horizon ACT-vs-STOP target as a replacement default.

### Current strongest repo-side conclusion
The next phase should focus on:
- target stabilization,
- variance reduction,
- and more reliable local target estimation,
not just another high-level target swap.

---

## Reference buckets to keep in mind for future paper writing

For the current paper direction, the most useful reference buckets are:

1. **Metareasoning / value of computation**
2. **Adaptive test-time compute allocation / budgeted inference**
3. **Process reward models / verifiers / progress-aware scoring**
4. **Uncertainty-aware stopping / escalation / abstention**
5. **Reject-option / learning-to-defer**
6. **Active feature acquisition / value-of-information acquisition**
7. **Difference rewards / local credit assignment**
8. **Finite-horizon / horizon-conditioned local values**

---

## Current literature-backed interpretation of the stop-vs-act line

A good concise interpretation is:

- binary stop-vs-act remains the right controller framing,
- but the local target still appears too noisy,
- and the next technical move should likely improve target reliability rather than introducing another loosely validated target family.

---

## Practical implication for the repo

When rewriting notes or future paper text, prefer to say:
- the stop-vs-act line is informed by metareasoning, uncertainty-aware control, acquisition/value-of-information, and local credit-assignment ideas,
- but bounded repo evidence still supports a conservative stance,
- with the current default setup retained as the best bounded baseline until stronger replacement evidence appears.
