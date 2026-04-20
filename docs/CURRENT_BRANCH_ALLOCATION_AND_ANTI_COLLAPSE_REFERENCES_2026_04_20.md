# Current branch-allocation and anti-collapse references (2026-04-20)

## Purpose

This note is the current focused reference memo for the repo's **fixed-budget branch-allocation / anti-collapse** direction.

It answers a narrower question than the broader references notes:

> **Which references are now most useful for understanding when to keep expanding a current branch family versus when to redirect compute to alternative answer groups under a fixed budget?**

This is not a formal bibliography.
It is a curated repository-facing guidance note for:
- current paper positioning,
- controller design,
- and honest comparison / adjacency boundaries.

## Why this note now exists

Recent repository diagnosis and bounded experiments have made the current bottleneck more specific:
- the correct answer still enters our tree too rarely on many hard failures,
- repeated same-family expansion remains common,
- and a smaller but important slice consists of correct answers already present in the tree but not selected.

That means the most useful recent references are no longer just general adaptive-inference papers.
They are the papers that help answer:

> **how should a fixed-budget tree-search controller decide when to deepen a current family, when to widen into alternatives, and how to avoid premature collapse without blindly forcing diversity?**

## Current highest-priority direct-neighbor references

### 1. BG-MCTS
**Current relevance:** highest direct-neighbor priority.

**Why:**
- It is the clearest recent fixed-budget tree-search reference for the current project direction.
- It aligns directly with the repo's core question because it conditions search behavior on the remaining budget.
- It is especially useful for the current branch-family anti-collapse story because it connects deepen-vs-widen decisions to fixed-budget control.

**What idea it gives the repo:**
- budget-conditioned tree-search policy,
- widening/deepening under remaining budget,
- and uncertainty/disagreement-aware expansion logic rather than a blind fixed search pattern.

**How to use in writing:**
- foreground as one of the closest modern method neighbors,
- especially when explaining that our project is about fixed-budget step-level allocation, not only query-level routing.

**Current repo-side translation:**
- family-level continuation should depend on both recent gain and remaining budget,
- with family widening preserved when uncertainty/disagreement remains meaningful.

### 2. Budget-Aware Value Tree Search (BAVT)
**Current relevance:** highest direct-neighbor priority.

**Why:**
- It is one of the closest references for the repo's new low-marginal-gain / residual-progress direction.
- It is useful because it emphasizes residual value / relative progress rather than only absolute score.

**What idea it gives the repo:**
- recent progress matters more than static branch quality alone,
- and remaining budget should be allocated according to expected residual value.

**How to use in writing:**
- foreground as a near-direct tree-search/value-allocation neighbor,
- especially when motivating marginal-gain-aware family cooldown or residual-progress-aware allocation.

**Current repo-side translation:**
- branch-family control should react to stalled recent improvement,
- but should preserve a floor for a genuinely strong incumbent family.

### 3. Adaptive Branching MCTS (AB-MCTS)
**Current relevance:** very high.

**Why:**
- It is a strong close neighbor for the widen-vs-deepen decision under inference-time constraints.
- It helps justify that the current project is not merely scoring nodes; it is controlling search shape.

**What idea it gives the repo:**
- whether to deepen or branch should itself be an adaptive decision.

**How to use in writing:**
- use as a close tree-search control neighbor,
- especially for explaining that family-level anti-collapse is not equivalent to generic diverse decoding.

**Current repo-side translation:**
- use family-level evidence to decide whether a family deserves another child or whether budget should shift to alternatives.

## Current highest-priority conceptual support references

### 4. When More Thinking Hurts
**Current relevance:** very high.

**Why:**
- It gives strong support for the repo's current diminishing-returns intuition.
- It is especially useful now that the repo is experimenting with low-marginal-gain cooldown control.

**What idea it gives the repo:**
- extra test-time compute can have flat or negative marginal value,
- so more compute is not automatically better.

**How to use in writing:**
- use as an empirical motivation source,
- not as a claim that it already solves the branch-family control problem.

### 5. ToolTree
**Current relevance:** high.

**Why:**
- It is useful for the current repo because it supports the idea that pruning / redirection decisions should use more than one signal stage.
- It is especially relevant for the repo's soft-cooldown-plus-override logic.

**What idea it gives the repo:**
- use a soft first-stage control signal and allow stronger action only after richer evidence arrives.

**Current repo-side translation:**
- soft cooldown before hard exclusion,
- and a strong-incumbent or post-expansion override path.

### 6. Semantic Similarity Based Dynamic Pruning for Tree-of-Thought
**Current relevance:** high.

**Why:**
- It helps the repo's current answer-group-aware anti-collapse story.
- It is useful because the current failure surface often involves budget being spent on semantically redundant branches.

**What idea it gives the repo:**
- semantic redundancy and structural redundancy should not be treated as unrelated.

**Current repo-side translation:**
- answer-group-aware family control should preserve genuinely distinct alternatives while demoting semantically repetitive families.

## Important safeguard / control-shaping references

### 7. Dynamic Early Exit in Reasoning Models
**Current relevance:** medium-high.

**Why:**
- It is useful for the repo's current question of how to avoid blocking a strong incumbent too early.
- It supports using trends, not one-shot scores, for stopping-like decisions.

### 8. Confidence-Dynamics Early Stopping for Large Reasoning Models
**Current relevance:** medium-high.

**Why:**
- It provides a useful trend-based stopping analogy for family cooldown.
- It supports rolling-window logic rather than one-step hard triggers.

### 9. Rollout Roulette
**Current relevance:** medium-high.

**Why:**
- It is a useful nearby idea for preserving diversity without flatly keeping all trajectories equally alive.
- It supports probabilistic demotion rather than immediate deletion.

### 10. BudgetThinker / budget-guidance style methods
**Current relevance:** medium.

**Why:**
- These are not direct branch-family search baselines,
- but they are useful analogs for soft budget conditioning rather than hard caps.

## Current best disciplined split for these references

### Core conceptual foundations
- metareasoning / value of computation,
- adaptive test-time compute allocation,
- fixed-budget small-gap / best-arm framing.

### Closest branch-allocation / anti-collapse method neighbors
- BG-MCTS,
- BAVT,
- AB-MCTS.

### Strong empirical motivation / control-shaping support
- When More Thinking Hurts,
- Dynamic Early Exit,
- Confidence-Dynamics stopping references.

### Search/pruning ingredient references
- ToolTree,
- semantic similarity pruning for ToT,
- Rollout Roulette,
- verifier/process-guided search references.

### Adjacent but not direct control-space equivalents
- routing/cascade methods,
- query-level budget prompting/guidance,
- best-of-N and majority-style test-time scaling families.

## Current writing rule

When discussing the repo's newest promoted branch-family direction, do **not** compress all of these references into one flat related-work paragraph.

Instead separate clearly:
1. **core foundations**,
2. **closest branch-allocation / tree-search neighbors**,
3. **control-shaping support references**,
4. **ingredient references**,
5. **adjacent but non-equivalent adaptive-compute baselines**.

## Current paper-facing takeaway

The safest current paper-facing interpretation is:

- the project remains grounded by metareasoning, adaptive test-time compute allocation, and fixed-budget ambiguity-aware allocation,
- but the closest current method neighbors are now budget-aware tree-search papers that make widen-vs-deepen or residual-progress decisions under a fixed budget,
- and the current repository contribution should be framed as **branch-family anti-collapse control** rather than generic diversity forcing.

## Practical repo takeaway

For the repo's current promoted line, the most relevant new literature-backed design ideas are:
- budget-conditioned family continuation,
- residual-progress-aware family scoring,
- widen-vs-deepen control under remaining budget,
- soft cooldown instead of default hard blocking,
- protected-incumbent logic,
- and answer-group-aware preservation of distinct alternatives.

## Recommended immediate usage rule

If a new reference is being added to the repo for this branch-allocation phase, explicitly record:
- whether it is a **closest branch-allocation neighbor**,
- whether it is a **control-shaping support** reference,
- whether it is only an **ingredient** reference,
- and whether it is **adjacent but not control-space-equivalent**.

That prevents new anti-collapse references from being mixed indiscriminately with routing-only or query-level adaptive-compute papers.
