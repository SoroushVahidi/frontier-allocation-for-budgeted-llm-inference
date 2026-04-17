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

### 7. Selective pairwise judging with calibrated abstention
This is now one of the most important new literature buckets for the current controller state.

Repo-side implication:
- the next strong controller upgrade is likely not another heuristic fallback variant,
- but a more principled selective pairwise judge with an explicit accept/defer calibration rule.

### 8. Fixed-budget best-arm identification and structured bandits
This is now one of the most important literature buckets for the paper-level framing.

Repo-side implication:
- the paper can increasingly be positioned as a fixed-budget identification/allocation problem over active branches,
- rather than only as a controller stack or a stop-vs-act story.

## Current strongest literature-backed interpretation

The best current interpretation is:

- pairwise branch comparison remains the strongest default comparator family,
- hard near-tie cases should increasingly be handled through **selective pairwise control** rather than only heuristic hard-case routing,
- and the full paper should increasingly be framed as **fixed-budget branch identification / allocation** with ambiguity concentrated in small-gap branch sets.

In concise form:

**the current controller should move toward selective pairwise judging, and the paper should move toward structured fixed-budget best-arm identification.**

## Outside-paper buckets currently most useful

### Controller-side papers
These are most useful for improving the current hard-case controller:
- selective pairwise judging with abstention,
- learning to defer to one or multiple experts,
- conformal / risk-controlled abstention,
- confidence-calibrated acceptance/defer rules.

### Paper-framing papers
These are most useful for improving the paper’s core technical identity:
- fixed-budget best-arm identification,
- structured fixed-budget bandits,
- active pairwise selection under budget,
- gap-sensitive allocation and elimination.

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
- weak policy-coupled STOP reallocation alone,
- narrower specialist-subset training alone,
- or more routing variants without a more principled selective pairwise accept/defer rule.

These remain useful components, but not yet the whole answer.

## Practical literature takeaway for the repo

The project no longer mainly needs:
- another loosely related controller family,
- another threshold tweak,
- or scale for its own sake.

It needs:
- a better selective pairwise controller for ambiguous branch decisions,
- a more principled confidence/defer rule,
- and a paper framing that makes branch allocation look like a principled fixed-budget identification problem.

## Safe wording for paper planning

Prefer to say:
- the project is informed by metareasoning, adaptive test-time compute allocation, uncertainty-aware control, local credit assignment, paired action-gap estimation, selective pairwise judging, and fixed-budget best-arm identification;
- pairwise comparison plus selective deferral is the strongest current controller family;
- and the current unresolved issue is supervision-target fidelity and accepted/deferred-set control rather than infrastructure.

## External baseline integration update (2026-04-16)

- The most important direct/near-direct baselines (s1, TALE, L1) are now maintained with explicit MODE A runnable vs MODE B partial boundaries in executable scripts/configs.
- BEST-Route has been inspected and now has a strict runnable-adjacent import protocol with explicit adjacent-only claim boundaries (still no direct reproduction claim).
- Reviewer-facing completeness state is centralized in `docs/external_baseline_completeness_report.md` with machine-readable exports under `outputs/external_baseline_completeness_summary.{json,csv}`.
- compute_optimal_tts now has an explicit blocked/protocol integration package with paper↔repo provenance uncertainty made explicit.
