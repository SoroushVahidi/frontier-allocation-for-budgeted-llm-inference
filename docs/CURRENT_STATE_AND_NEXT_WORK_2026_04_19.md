# Current state and next work (2026-04-19)

## Purpose

This note gives one compact repository-facing answer to:
- what the project is about now,
- what has already been done,
- what the strongest current line is,
- what was recently improved,
- what still remains,
- and what the next highest-value work should be if the goal is to beat prior methods with a stronger NeurIPS-level pair of method and evidence.

## Project identity now

The repository is currently about:

> **fixed-budget adaptive test-time compute allocation for LLM reasoning, centered on which active branch should receive the next unit of compute and when the system should continue versus commit.**

This repository is **not** the older binary revise-routing story.

## Current strongest broad method line

The current main serious family remains:

> **broad diversity-aware branch allocation with answer-support aggregation**

This remains the main line because repository evidence already supports the following bounded interpretation:
- earlier local target/oracle refinements were useful diagnostics,
- but they were not the final broad answer,
- the broad diversity/aggregation family was the first branch-allocation family to behave like a serious broad competitor,
- stricter simulator confirmation held up for that family,
- and bounded real-model confirmation kept it plausible, though still underconfirmed.

## What has already been done

### Main-family / controller side
The repository already has:
- diversity-aware controllers,
- answer-support aggregation,
- duplicate-aware and semantic-overlap-aware refinements,
- observability and failure-case capture,
- comparative mistake audits against the strongest broad baseline,
- and bounded real-model confirmation paths.

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

### Dataset layer expansion
Recent dataset work has also expanded the repository's evaluation surface.
Current practical status is:
- AIME 2025: added,
- HMMT: added,
- BRUMO: added,
- MMLU-Pro: added,
- LiveCodeBench: partially added at the dataset layer,
- HLE: still requires explicit confirmation of final repo integration status before it should be treated as available in the canonical summary.

This improves the repository's ability to test transfer and broader evaluation coverage, but dataset registration should still be distinguished from full experiment readiness.

## What the recent work changed

### 1. The learner-side supervision bottleneck is narrower now
The repo is now much better positioned on the learner-side problem than before.
Bounded evidence already suggests:
- stronger expand-vs-commit behavior,
- lower regret,
- and better near-tie handling under the newer value-aware target regime.

That does **not** mean the learner-side problem is fully solved.
It means the learner-side residual is now more specific:
- exact-heavy confirmation,
- target variance / reliability,
- and ambiguity calibration on larger matched state sets.

### 2. The repo-wide main bottleneck is now clearer
The dominant repo-wide issue is no longer “invent another target family.”
It is still best described as:

> **reliable useful diversity realization plus stronger post-diversity scoring / aggregation under realistic noise, followed by stronger real-model confirmation.**

In simple words:
- the project is now better at deciding **whether to continue versus commit**,
- but it is still not fully good enough at **making useful diversity appear reliably and then selecting correctly once it exists**.

### 3. The next paper-strengthening step is not broad method search
The repo no longer looks like it needs another unrelated controller family by default.
It looks like it needs:
- stronger validation,
- better diagnosis of what the new bottleneck actually is after the recent improvements,
- and stronger evidence that the current best line can beat earlier methods consistently.

## What is still unresolved

### Main repository bottleneck
The current main unresolved bottleneck is still:

> **reliable useful diversity realization plus stronger post-diversity scoring / aggregation under real-model noise.**

### Main learner-side residual
The main learner-side residual is now:

> **stabilizing and validating the continuation-minus-commit regime on larger, more exact-heavy matched state sets.**

### Evaluation-surface residual
The main dataset/evaluation residual is now:
- making sure newly added datasets are not only registered but genuinely usable in experiments,
- especially distinguishing exact-answer math additions from broader or code-execution-heavy additions such as LiveCodeBench.

## What has worked but not fully closed the problem

The following ideas were directionally useful but not sufficient alone:
- anti-collapse / minimum exploration ideas,
- diversity bonuses,
- semantic-overlap-aware scoring,
- duplicate-aware aggregation,
- local completion-aware correction,
- and bounded ambiguity / defer logic.

These helped shape the current strongest family, but they did not yet close the broad failure gap by themselves.

## What the next needed works should be

If the goal is to beat previous methods and strengthen the project for NeurIPS, the next work should be prioritized in this order.

### 1. Refresh the failure taxonomy after the recent improvements
Run a new comparative mistake audit / dominant-failure regrouping using the current best post-April-19 line.

Reason:
- the old dominant group was `insufficient_diversity_realized`,
- but after learner-side hardening and diversity-related refinements, the dominant bottleneck may have shifted,
- and the repo should not keep optimizing for an outdated failure diagnosis.

Core question:
> is insufficient diversity still the dominant residual, or has the main problem shifted to bad diversity, post-diversity ranking, aggregation concentration, or commit timing?

### 2. Run stronger exact-heavy validation for the learner-side regime
Use a larger matched exact-heavy slice to determine whether the stabilized value-aware continuation-minus-commit regime should become the learner-side default.

Reason:
- current evidence is directional and promising,
- but still bounded.

### 3. Test transfer of learner-side gains into the broad main family
If the newer learner-side regime really helps, the next important question is whether it improves the broad diversity/aggregation family rather than only improving an isolated learner-side subproblem.

Core question:
> does the better target / metareasoning layer actually help the repo's main serious family beat strong prior methods more often?

### 4. Separate dataset registration from experiment readiness
For the newly expanded datasets, clarify which ones are actually experiment-ready now.

Immediate practical emphasis:
- exact-answer math additions first,
- broader or code-execution-heavy additions second,
- honest readiness notes for partial integrations such as LiveCodeBench.

### 5. Strengthen real-model confirmation once the refreshed bottleneck is known
The repo still needs larger but controlled real-model confirmation before broad-best claims become paper-strong.

This should happen after:
- the dominant current bottleneck is refreshed,
- and the current strongest candidate is better stabilized.

## What should not be the default next move

Do **not** default to:
- another unrelated controller family,
- another broad simulator-only campaign without realism follow-up,
- pretending the learner-side problem is fully solved already,
- or broad paper-level claims that exceed the current real-model evidence.

## Best concise summary

A safe current summary is:

> The repository now has a clear broad main line, a stronger learner-side target stack, and a broader dataset surface than before. The learner-side problem has improved materially but is not fully closed. The main remaining challenge is still making useful diversity materialize reliably and using it correctly under realistic noise. The next highest-value work is to refresh the dominant failure taxonomy after the recent improvements, validate the new learner-side regime on larger exact-heavy slices, and then test whether those gains transfer into the broad main family strongly enough to beat prior methods more consistently.
