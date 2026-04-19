# Current state and next work (2026-04-19)

## Purpose

This note gives one compact repository-facing answer to:
- what the project is about now,
- what has already been done,
- what the strongest current line is,
- what changed in the most recent method passes,
- what the main bottleneck is now,
- and what the next highest-value work should be if the goal is to beat prior methods with a strong NeurIPS-level pair of method and evidence.

## Important update (demotion)

The incumbent-challenger metalevel ICC refinement line has been **demoted to diagnostic-branch status** after bounded selector, commit-side, and final near-tie single-point passes. It is **not** the promoted main method at this time. See:

- `docs/ICC_METALEVEL_DIAGNOSTIC_BRANCH_DEMOTION_2026_04_19.md`
- `outputs/data_consolidation_20260418/icc_diagnostic_branch_demotion_summary_20260419.json`

## Project identity now

The repository is currently about:

> **fixed-budget adaptive test-time compute allocation for LLM reasoning, centered on which active branch should receive the next unit of compute and when the system should continue versus commit.**

This repository is **not** the older binary revise-routing story.

## Current strongest broad method line

The current main serious family remains:

> **broad diversity-aware branch allocation with answer-support aggregation**

But the strongest tested refinement inside that broad line was no longer mainly diversity-pushing. Historically, the repository pointed toward:

> **answer-group-level incumbent-vs-challenger commit control, especially with dependence-aware support, inside the broad diversity-aware family.**

This is no longer the active promoted optimization line; it remains diagnostically useful because repository evidence showed:
- earlier local target/oracle refinements were useful diagnostics but not the final broad answer,
- a broad diversity/aggregation family became the first serious broad competitor,
- refreshed failure analysis showed the dominant bottleneck shifted away from insufficient diversity,
- and bounded incumbent-vs-challenger commit control was the first recent method line to improve the new dominant bottleneck directly.

## What has already been done

### Main-family / controller side
The repository already has:
- diversity-aware controllers,
- answer-support aggregation,
- duplicate-aware and semantic-overlap-aware refinements,
- observability and failure-case capture,
- comparative mistake audits against the strongest broad baseline,
- bounded real-model confirmation paths,
- and bounded incumbent-vs-challenger commit-controller variants (now retained as diagnostic artifacts).

### Learner-side / target-design side
Recent passes materially strengthened the learner-side branch-allocation supervision stack.
The repository now includes:
- `Q_commit`,
- per-branch `Q_expand`,
- continuation-minus-commit advantages,
- regret / gap metadata,
- ambiguity buckets,
- exact / approximate provenance fields,
- and lightweight target-stabilization signals such as repeated estimation and reliability summaries.

This means the learner-side path is no longer only a brittle hard-label setup.

### Dataset layer and readiness surface
Recent dataset work broadened the repository’s evaluation surface and improved readiness discipline.
Current practical status is:
- AIME 2025: experiment-ready,
- HMMT: experiment-ready,
- BRUMO: experiment-ready,
- MMLU-Pro: partially ready,
- LiveCodeBench: partially ready,
- HLE: partially added / partially experiment-ready through safe text-first and auto-gradable slices,
- and dataset bundles / readiness reports now distinguish registry integration from actual experiment usability.

This improves the repository’s ability to test transfer and broader coverage while staying honest about what can really be run today.

## What the recent work changed

### 1. The learner-side supervision bottleneck is no longer the main story
The repo is now much better positioned on the learner-side problem than before.
Bounded evidence already showed:
- stronger expand-vs-commit behavior,
- lower regret,
- and better near-tie handling under the newer value-aware target regime.

That does **not** mean the learner-side problem is fully solved.
But it is no longer the main repository bottleneck.

### 2. The dominant failure taxonomy has changed
A refreshed comparative failure re-audit showed that:
- `wrong_commit_timing` became the dominant failure group,
- `insufficient_diversity_realized` is no longer dominant,
- and aggregation instability, while still relevant, is not the top residual in the refreshed grouped ranking.

So the project is no longer mainly bottlenecked by “not enough diversity.”
It is now mainly bottlenecked by:

> **bad continue-versus-commit decisions and unstable final answer selection among answer groups already present in the frontier.**

### 3. The leading method line changed accordingly
The repository then tested answer-group-level incumbent-vs-challenger commit control.
A stronger matched validation pass showed:
- dependence-aware incumbent-vs-challenger commit control improved over the base controller on accuracy,
- reduced wrong-commit timing substantially,
- and outperformed the raw-support version on both accuracy and wrong-commit reduction.

This did not survive later bounded refinement checks as a promoted line; it is now a demoted diagnostic branch pending a materially different hypothesis.

## What is still unresolved

### Main repository bottleneck
The current main unresolved bottleneck is now best described as:

> **wrong commit timing at the answer-group level: deciding whether the incumbent is already safe to commit to, whether a challenger still deserves compute, and how to avoid harmful late-stage instability.**

In simple words:
- the project is better than before at surfacing alternatives,
- but still not good enough at knowing when the current best answer is already strong enough and stable enough to stop with.

### Main method residual inside ICC
The new leading line is promising but not final.
The main remaining ICC-side questions are now:
- which wrong-commit subtypes remain most stubborn,
- when dependence discounting helps vs over-discounts useful corroboration,
- what harms remain in improved-vs-harmed case analysis,
- and whether minimal refinements can reduce those harms without losing the current gains.

### Evaluation-surface residual
The main dataset/evaluation residual is now:
- keeping experiment-readiness honest for partial integrations,
- especially for LiveCodeBench and the broader multimodal portions of HLE,
- while using the exact-answer-ready bundle as the primary stable comparison surface.

## What has worked but not fully closed the problem

The following ideas were directionally useful but not sufficient alone:
- anti-collapse / minimum exploration ideas,
- diversity bonuses,
- semantic-overlap-aware scoring,
- duplicate-aware aggregation,
- local completion-aware correction,
- bounded ambiguity / defer logic,
- and a diversity-needed predictor / gate.

These ideas helped the project diagnose and reduce earlier residuals, but they did not close the new dominant bottleneck by themselves.

## What the next needed works should be

If the goal is to beat previous methods and strengthen the project for NeurIPS, the next work should now be prioritized in this order.

### 1. Refine the incumbent-vs-challenger commit controller by subtype
Use the existing wrong-commit subtype structure to determine:
- which subtype ICC already fixes best,
- which subtype remains dominant,
- and which minimal refinement is best justified by the harmed-case analysis.

Core question:
> which remaining wrong-commit subtype is now the main residual inside the best current method line?

### 2. Tighten dependence-aware support rather than replacing ICC
The current evidence suggests dependence-aware support is better than raw support, but the remaining question is when it over-discounts useful corroboration.

Core question:
> can a bounded refinement preserve the current wrong-commit gains while reducing harmed cases?

### 3. Run broader but still controlled confirmation for ICC
After subtype-driven refinement, the next important step is to run broader stable confirmation:
- larger exact-answer matched validation,
- then wider stable bundles where appropriate,
- then stronger real-model confirmation.

Core question:
> does dependence-aware ICC remain the strongest line when tested more broadly and more carefully?

### 4. Keep dataset-readiness discipline
Continue to distinguish:
- experiment-ready exact-answer expansions,
- partially ready breadth/control datasets,
- and code / multimodal datasets that still require more evaluation machinery.

### 5. Strengthen real-model confirmation once ICC is stabilized further
The repository still needs larger but controlled real-model confirmation before broad-best claims become paper-strong.

This should happen after:
- the main wrong-commit subtype is better understood,
- and the leading ICC line is refined and stabilized.

## What should not be the default next move

Do **not** default to:
- another unrelated controller family,
- another broad diversity-first campaign,
- broad simulator-only experimentation without realism follow-up,
- pretending the method is final already,
- or broad paper-level claims that exceed the current real-model evidence.

## Best concise summary

A safe current summary is:

> The repository now has a clear leading broad family, a stronger learner-side target stack, a broader and cleaner dataset surface, and a sharper current bottleneck than before. The dominant problem is no longer mainly insufficient diversity; it is wrong commit timing at the answer-group level. Dependence-aware incumbent-vs-challenger commit control is now the strongest serious next method line, and the highest-value next work is to refine it by wrong-commit subtype, reduce its harmed cases, and then confirm it more broadly.
