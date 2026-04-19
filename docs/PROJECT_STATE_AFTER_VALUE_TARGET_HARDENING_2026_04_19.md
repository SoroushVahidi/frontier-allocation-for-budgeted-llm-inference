# Project state after value-target hardening (2026-04-19)

## Purpose

This note gives one compact, repository-facing answer to the following questions:
- what is the repository about now,
- what has already been done,
- what changed in the recent April 19 learner-side passes,
- what the main bottlenecks are now,
- and what remains before the project is in stronger paper-ready shape.

This file is intended to help collaborators quickly understand the current project state without reconstructing it from many scattered notes.

## Project identity now

The repository is currently about:

> **fixed-budget adaptive test-time compute allocation for LLM reasoning, centered on which active branch should receive the next unit of compute and when the system should continue versus commit.**

This repository is **not** currently the old binary revise-routing story.

## Current top-level method picture

The current strongest repository-backed main line is:

> **broad diversity-aware branch allocation with answer-support aggregation**

This remains the main serious family because repository evidence now supports the following bounded interpretation:
- earlier local target/oracle refinements were useful diagnostics,
- but they were not the final broad method answer,
- a broader diversity/aggregation family was the first branch-allocation family to behave like a serious broad competitor,
- stricter simulator confirmation held up for that family,
- and bounded real-model confirmation kept it alive as plausible but still underconfirmed.

## What has already been done

### Broad family / main line
The repository already has:
- diversity-aware controller implementations,
- answer-support aggregation mechanisms,
- duplicate-aware and semantic-overlap-aware variations,
- comparative mistake audits versus the strongest broad baseline,
- and bounded real-model confirmation paths.

### Learner-side / target-design line
The repository also now has a much stronger learner-side target stack than before.
Recent passes implemented:
- `Q_commit` and per-branch `Q_expand` target fields,
- explicit continuation-minus-commit advantages,
- regret / gap metadata,
- ambiguity buckets for near-ties,
- exact / approximate provenance fields,
- and a lightweight target-stabilization layer using paired rollouts, repeated estimation, and reliability summaries.

This means the repository no longer depends only on brittle hard local winner labels for the learner-side branch-allocation path.

## What changed in the April 19 learner-side hardening passes

The key recent change is that the repo now supports a cleaner metareasoning-style learner-side formulation:
- compare **expand branch j** versus **commit now**,
- represent this with continuation-minus-commit targets,
- and treat ambiguity and reliability more explicitly during training and evaluation.

Bounded evidence from the April 19 value-aware target comparison supports the following directional conclusions:
- expand-vs-commit behavior improved materially in the matched bounded run,
- mean regret improved materially,
- near-tie pairwise behavior improved directionally,
- and ambiguity-aware value-based supervision looks better than the older brittle winner-label setup.

This should still be treated as **bounded directional evidence**, not as final broad closure.

## What the repository now understands more clearly

The project now has a cleaner split between two levels of difficulty.

### 1. Learner-side supervision problem
This was previously a major bottleneck.
It is now **partially reduced** because the repo has:
- better target semantics,
- better ambiguity handling,
- and better target-stability instrumentation.

The remaining learner-side issue is no longer mainly “the labels are obviously wrong.”
It is now more narrowly:
- exact-heavy confirmation,
- target variance / reliability,
- and calibration of ambiguity handling on larger matched state sets.

### 2. Repo-wide main method problem
This is still the bigger bottleneck.
Even with better learner-side targets, the repo is still mainly limited by:
- reliable useful diversity realization,
- ranking / aggregation quality after diversity exists,
- and stronger real-model confirmation.

In simple words:
- the repository is now better at thinking about **whether to continue versus commit**,
- but it is still not fully good enough at **making useful diversity appear reliably and then using it correctly under realistic noise**.

## What has worked so far

### Clear progress
- fixed-budget branch allocation is now the right project framing,
- the repo has one leading serious main family rather than many equally plausible stories,
- learner-side value-aware targets are stronger than brittle winner labels,
- and the repo has better observability, provenance, and status-note discipline than before.

### Useful but not fully sufficient ideas
- anti-collapse / minimum exploration ideas,
- diversity bonuses,
- semantic-overlap-aware scoring,
- duplicate-aware aggregation,
- completion-aware local corrections,
- and bounded defer / ambiguity logic.

These were directionally useful, but not enough alone to close the problem.

## What remains unresolved

### Main repository bottleneck
The main unresolved bottleneck is still best described as:

> **reliable useful diversity realization plus stronger post-diversity scoring / aggregation under real-model noise.**

### Main learner-side residual
The main learner-side residual is now:

> **stabilizing and validating the continuation-minus-commit target regime on larger, more exact-heavy matched state sets.**

## What should happen next

### Highest-value next work
1. Keep the broad diversity/aggregation family as the main line.
2. Keep the value-aware continuation-minus-commit target regime as the current serious learner-side direction.
3. Run larger exact-heavy validation for the learner-side regime.
4. Use those results to decide whether the stabilized value-aware regime should become the learner-side default.
5. Then test whether that learner-side improvement transfers into the broader diversity/aggregation family.

### What should not be the default next move
- opening a new unrelated controller family,
- another broad simulator-only campaign without realism follow-up,
- pretending the learner-side bottleneck is fully solved already,
- or broad paper-level claims that exceed current real-model evidence.

## Best concise state summary

A safe current summary is:

> The repository now has a clear leading broad method family and a stronger learner-side supervision stack than before. The learner-side target problem has been materially improved but not fully closed. The main repo-wide challenge remains making useful diversity reliably materialize, using it correctly once it exists, and confirming the current family more strongly under real-model evaluation.
