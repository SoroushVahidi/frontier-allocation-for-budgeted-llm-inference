# Current references supplement (2026-04-16)

## Purpose

This note refreshes the project-side literature interpretation for the current paper direction.

It is not a formal bibliography. It is a **working guidance note** for:
- how to think about the literature,
- which reference buckets matter most,
- which outside baselines are most important,
- and how to position the paper honestly.

## Current reference-phase update

The repository is no longer in a broad nearby-controller search phase.

It is now in a **target-definition phase**.

That means the most important references are no longer just the ones that suggest another tweak.
They are the ones that help answer:

> **what target/oracle definition should govern hard close-branch decisions under a fixed compute budget?**

## Highest-priority literature themes

### 1. Metareasoning / value of computation
This remains the core conceptual frame.

Repo-side implication:
- extra reasoning is an action,
- that action has value and cost,
- and the paper should stay centered on whether the next unit of compute is worth spending **here**.

### 2. Adaptive test-time compute allocation / budgeted inference
This remains the main neighboring AI framing.

Repo-side implication:
- the paper should clearly belong to the adaptive-inference / budgeted-allocation family,
- but should remain honest about the project’s more specific frontier-control question.

### 3. Fixed-budget best-arm identification / small-gap allocation
This has become one of the most important paper-level framing buckets.

Repo-side implication:
- the hard disagreement slice is increasingly best understood as a small-gap branch-allocation problem,
- not only as another controller-stack problem.

### 4. Process rewards / verifiers / progress-aware signals
These remain useful because they support intermediate-state signals, not only final correctness.

Repo-side implication:
- use them as ingredients, features, and neighboring baselines,
- especially for completion-aware or semantic branch-quality signals,
- but do not mistake them for the full answer to the repo’s target-definition problem.

### 5. Uncertainty-aware stopping / escalation / abstention
This remains directly relevant to the stop-vs-act helper framing.

Repo-side implication:
- uncertainty is still important,
- but uncertainty handling alone is not the final fix.

### 6. Paired comparison / matched-rollout ACT-vs-STOP estimation
This still matters because the object we ultimately want is a local action-gap estimate, not just a branch score.

Repo-side implication:
- paired ACT-vs-STOP thinking remains useful,
- but the repo now needs a stronger incumbent/commit notion than earlier weak STOP comparators provided.

### 7. Selective pairwise judging with calibrated abstention
This remains important for hard close-branch control.

Repo-side implication:
- selective intervention on fragile comparisons is still correct,
- but the repo should now think about it together with target/oracle definition, not as an isolated controller trick.

## Current strongest literature-backed interpretation

The best current interpretation is:

- continuation value remains a strong core object,
- process/verifier/completion-aware signals are useful as bounded correction ingredients,
- and hard near-tie cases should be handled as a selective disagreement slice rather than as proof that the core continuation-value framing is broadly wrong.

In concise form:

**the current project should keep continuation value as the core target/oracle and study bounded completion-aware correction in small-gap disagreement states.**

## Outside-paper buckets currently most useful

### Controller-side references
These are most useful for the current hard-case target-definition question:
- metareasoning / value of computation,
- selective pairwise judging with abstention,
- learning to defer to one or multiple experts,
- conformal / risk-controlled abstention,
- confidence-calibrated acceptance/defer rules.

### Paper-framing references
These are most useful for the paper’s core technical identity:
- fixed-budget best-arm identification,
- structured fixed-budget bandits,
- active pairwise selection under budget,
- gap-sensitive allocation and elimination,
- adaptive test-time compute allocation.

### Ingredient references
These are useful but should not be oversold as the whole answer:
- process reward models,
- verifier-guided search,
- state-level process verification,
- search-policy papers,
- frontier-family controller references.

## External baseline priority for this repo

### Most important direct / near-direct budget-control baselines
1. **s1** — strongest practical direct/near-direct baseline for explicit budget forcing.
2. **TALE** — strongest adjacent published per-instance budget-allocation baseline.
3. **L1** — strong controllable-reasoning-length baseline for matched budget comparison.

### Important adjacent adaptive-allocation baselines
4. **BEST-Route** — strong general adaptive-compute routing baseline.
5. **When To Solve, When To Verify** — important solve-vs-verify budget tradeoff neighbor.
6. **Cascade routing** — important routing/cascading neighbor.
7. **MoB** — important best-of-N style selection neighbor.
8. **ReST-MCTS*** — important process-reward-guided tree-search neighbor.

## Positioning rule for writing

When writing the paper, distinguish clearly between:
- **core conceptual references**,
- **direct / near-direct budget-control baselines**,
- **adjacent adaptive-allocation baselines**,
- and **ingredient references**.

This matters because not all neighboring papers operate in the same action space or at the same level of control.

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
- more routing variants without stronger target-definition content,
- or more nearby controller sweeps without semantic disagreement analysis.

These remain useful components, but not yet the whole answer.

## Practical literature takeaway for the repo

The project no longer mainly needs:
- another loosely related controller family,
- another threshold tweak,
- or scale for its own sake.

It needs:
- a frozen target/oracle definition for hard disagreement states,
- a bounded correction rule that is justified only where continuation value and visible semantic completion diverge,
- and literature usage that clearly separates core foundations, direct baselines, adjacent baselines, and ingredients.

## Safe wording for paper planning

Prefer to say:
- the project is informed by metareasoning, adaptive test-time compute allocation, uncertainty-aware control, local credit assignment, paired action-gap estimation, selective pairwise judging, process/verifier signals, and fixed-budget best-arm identification;
- continuation value remains the strongest current core object;
- completion-aware evidence is useful as a bounded correction ingredient in hard disagreement states;
- and the current unresolved issue is target/oracle definition for hard close-branch decisions rather than infrastructure.

## External baseline integration update (2026-04-16)

- The most important direct/near-direct baselines (s1, TALE, L1) are maintained with explicit MODE A runnable vs MODE B partial boundaries in executable scripts/configs.
- BEST-Route, when_solve_when_verify, cascade routing, MoB, ReST-MCTS, and OpenR now have strict runnable-adjacent import protocols with explicit adjacent-only claim boundaries.
- Reviewer-facing completeness state is centralized in `docs/external_baseline_completeness_report.md` with machine-readable exports under `outputs/external_baseline_completeness_summary.{json,csv}`.
- `compute_optimal_tts` remains blocked / uncertain for direct manuscript-facing baseline use until paper↔repo provenance is verified.

## Cross-link to the central audit

For the current curated relevance map of the reference base, see:
- `docs/REFERENCES_AUDIT_AND_CURATION_2026_04_18.md`


## Required baseline-family lock for current phase (added 2026-04-18)

The following families are mandatory in repository-facing baseline framing for this paper phase:

- **Direct essential family:** *Q*: Improving Multi-step Reasoning for LLMs with Deliberative Planning (currently discuss-only / not-yet-integrated).
- **Adjacent essential family:** *Let's Verify Step by Step* (completion-aware PRM/verifier; adjacent, non-equivalent control space).
- **Adjacent essential family:** *Rational Metareasoning for Large Language Models* (stop-vs-continue adaptive compute framing; adjacent).
- **Adjacent optional-unless-scope-broadens:** *Efficient Contextual LLM Cascades through Budget-Constrained Policy Learning* (routing/cascade family).
- **Ingredient-adjacent boundary essential framing:** *Best Arm Identification: A Unified Approach to Fixed Budget and Fixed Confidence* (small-gap near-tie allocation lens).

This lock should be used alongside the canonical project center: fixed-budget next-step branch allocation with continuation-value core plus bounded completion-aware correction in disagreement slices.
