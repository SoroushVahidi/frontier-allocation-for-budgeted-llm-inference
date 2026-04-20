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

It is now in a **branch-family stabilization and target-definition phase**.

That means the most important references are no longer just the ones that suggest another tweak.
They are the ones that help answer:

> **what target/oracle definition and branch-family control rule should govern hard close-branch decisions under a fixed compute budget?**

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
This remains one of the most important paper-level framing buckets.

Repo-side implication:
- the hard disagreement slice is increasingly best understood as a small-gap branch-allocation problem,
- not only as another controller-stack problem.

### 4. Budget-aware tree search / widen-vs-deepen control
This is now a top-priority method-neighbor bucket.

Repo-side implication:
- current branch-family anti-collapse control should be positioned against recent fixed-budget tree-search references,
- especially the papers that make widen-vs-deepen or residual-progress decisions under a hard budget.

### 5. Residual progress / low-marginal-gain allocation
This is now a top-priority design bucket.

Repo-side implication:
- recent bounded repo experiments now justify treating low-marginal-gain family control as a real promoted refinement direction,
- so references that emphasize recent progress, residual value, or diminishing returns now matter more than before.

### 6. Process rewards / verifiers / progress-aware signals
These remain useful because they support intermediate-state signals, not only final correctness.

Repo-side implication:
- use them as ingredients, features, and neighboring baselines,
- especially for completion-aware or semantic branch-quality signals,
- but do not mistake them for the full answer to the repo’s branch-family control problem.

### 7. Uncertainty-aware stopping / escalation / abstention
This remains directly relevant to the stop-vs-act helper framing.

Repo-side implication:
- uncertainty is still important,
- but uncertainty handling alone is not the final fix.

### 8. Answer-group-aware preservation and semantic anti-collapse
This has become more important than generic diversity bonuses.

Repo-side implication:
- the current paper should increasingly emphasize preserving and maturing distinct answer groups,
- not just adding a broad diversity encouragement term.

## Current strongest literature-backed interpretation

The best current interpretation is:

- continuation value remains a strong core object,
- process/verifier/completion-aware signals are useful as bounded correction ingredients,
- hard near-tie cases should be handled as a selective disagreement slice rather than as proof that the core continuation-value framing is broadly wrong,
- and the closest newer method neighbors are now budget-aware tree-search papers that decide when to deepen, when to widen, and how to react to stalled recent progress under fixed budget.

In concise form:

**the current project should keep continuation value as the core target/oracle, position itself inside fixed-budget branch-family allocation, and study bounded anti-collapse control plus low-marginal-gain correction inside hard disagreement states.**

## Most useful newer direct-neighbor references for the current phase

These are now among the most important newer references for the repo’s branch-family anti-collapse direction:
- **BG-MCTS** — closest current fixed-budget tree-search neighbor for budget-conditioned widen-vs-deepen control.
- **Budget-Aware Value Tree Search (BAVT)** — closest residual-progress / recent-gain neighbor for low-marginal-gain family control.
- **Adaptive Branching MCTS (AB-MCTS)** — useful close neighbor for deciding when to deepen the current path versus open alternatives.
- **When More Thinking Hurts** — strongest empirical support for diminishing-return and stagnation-aware control.
- **ToolTree** — useful support for staged or feedback-aware pruning / redirection.
- **semantic-similarity-based ToT pruning references** — useful for answer-group-aware anti-collapse rather than generic diversity forcing.
- **confidence-dynamics stopping references** — useful for rolling-window or trend-based cooldown logic.

For the current focused memo on these references, use:
- `docs/CURRENT_BRANCH_ALLOCATION_AND_ANTI_COLLAPSE_REFERENCES_2026_04_20.md`

## Outside-paper buckets currently most useful

### Controller-side references
These are most useful for the current hard-case target-definition and anti-collapse question:
- metareasoning / value of computation,
- selective pairwise judging with abstention,
- learning to defer to one or multiple experts,
- conformal / risk-controlled abstention,
- confidence-calibrated acceptance/defer rules,
- budget-aware tree search,
- residual-progress allocation,
- and controlled widen-vs-deepen logic.

### Paper-framing references
These are most useful for the paper’s core technical identity:
- fixed-budget best-arm identification,
- structured fixed-budget bandits,
- active pairwise selection under budget,
- gap-sensitive allocation and elimination,
- adaptive test-time compute allocation,
- and budget-aware tree-search control.

### Ingredient references
These are useful but should not be oversold as the whole answer:
- process reward models,
- verifier-guided search,
- state-level process verification,
- search-policy papers,
- frontier-family controller references,
- semantic deduplication / pruning,
- and confidence-dynamics stopping.

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

### Important newer branch-search neighbors for related-work positioning
These are not necessarily current runnable repo baselines, but they are increasingly important for honest paper positioning:
- BG-MCTS,
- BAVT,
- AB-MCTS,
- ToolTree,
- semantic anti-redundancy / dynamic pruning references,
- and confidence-dynamics stopping references.

## Positioning rule for writing

When writing the paper, distinguish clearly between:
- **core conceptual references**,
- **closest branch-allocation / tree-search neighbors**,
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
- more nearby controller sweeps without semantic disagreement analysis,
- or generic diversity bonuses without answer-group structure.

These remain useful components, but not yet the whole answer.

## Practical literature takeaway for the repo

The project no longer mainly needs:
- another loosely related controller family,
- another threshold tweak,
- or scale for its own sake.

It needs:
- a frozen target/oracle definition for hard disagreement states,
- a bounded correction rule that is justified only where continuation value and visible semantic completion diverge,
- a branch-family anti-collapse controller that reacts to stalled recent progress without suppressing genuinely strong incumbents too early,
- and literature usage that clearly separates core foundations, closest branch-allocation neighbors, direct baselines, adjacent baselines, and ingredients.

## Safe wording for paper planning

Prefer to say:
- the project is informed by metareasoning, adaptive test-time compute allocation, uncertainty-aware control, local credit assignment, paired action-gap estimation, selective pairwise judging, process/verifier signals, fixed-budget best-arm identification, and budget-aware tree search;
- continuation value remains the strongest current core object;
- completion-aware evidence is useful as a bounded correction ingredient in hard disagreement states;
- branch-family anti-collapse control under fixed budget is now one of the clearest method-level refinements in the repo;
- and the current unresolved issue is target/oracle definition plus early tree-shape control for hard close-branch decisions rather than infrastructure.

## External baseline integration update (2026-04-16)

- The most important direct/near-direct baselines (s1, TALE, L1) are maintained with explicit MODE A runnable vs MODE B partial boundaries in executable scripts/configs.
- BEST-Route, when_solve_when_verify, cascade routing, MoB, ReST-MCTS, and OpenR now have strict runnable-adjacent import protocols with explicit adjacent-only claim boundaries.
- Reviewer-facing completeness state is centralized in `docs/external_baseline_completeness_report.md` with machine-readable exports under `outputs/external_baseline_completeness_summary.{json,csv}`.
- `compute_optimal_tts` remains blocked / uncertain for direct manuscript-facing baseline use until paper↔repo provenance is verified.

## Cross-link to the central audit

For the current curated relevance map of the reference base, see:
- `docs/REFERENCES_AUDIT_AND_CURATION_2026_04_18.md`

For the current focused branch-family anti-collapse memo, see:
- `docs/CURRENT_BRANCH_ALLOCATION_AND_ANTI_COLLAPSE_REFERENCES_2026_04_20.md`

## Required baseline-family lock for current phase (added 2026-04-18)

The following families are mandatory in repository-facing baseline framing for this paper phase:

- **Direct essential family:** *Q*: Improving Multi-step Reasoning for LLMs with Deliberative Planning (currently discuss-only / not-yet-integrated).
- **Adjacent essential family:** *Let's Verify Step by Step* (completion-aware PRM/verifier; adjacent, non-equivalent control space).
- **Adjacent essential family:** *Rational Metareasoning for Large Language Models* (stop-vs-continue adaptive compute framing; adjacent).
- **Adjacent optional-unless-scope-broadens:** *Efficient Contextual LLM Cascades through Budget-Constrained Policy Learning* (routing/cascade family).
- **Ingredient-adjacent boundary essential framing:** *Best Arm Identification: A Unified Approach to Fixed Budget and Fixed Confidence* (small-gap near-tie allocation lens).

This lock should be used alongside the canonical project center: fixed-budget next-step branch allocation with continuation-value core plus bounded completion-aware correction in disagreement slices.
