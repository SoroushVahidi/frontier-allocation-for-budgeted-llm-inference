# Current state and next work (2026-04-19)

## Purpose

This note gives one compact repository-facing answer to:
- what the project is about now,
- what has already been done,
- what the strongest current line is,
- what changed in the most recent method passes,
- what the main bottleneck is now,
- and what the next highest-value work should be if the goal is to beat prior methods with a strong NeurIPS-level pair of method and evidence.

## Project identity now

The repository is currently about:

> **fixed-budget adaptive test-time compute allocation for LLM reasoning, centered on which active branch should receive the next unit of compute and when the system should continue versus commit.**

This repository is **not** the older binary revise-routing story.

## Current strongest serious method line

The current promoted integrated line is now:

> **broad diversity-aware branch allocation with answer-support aggregation, strengthened by anti-collapse answer-group-aware allocation, soft repeat-expansion control, and a deterministic output-layer repair stage.**

This is the main serious line at present.

Older lines such as ICC remain useful diagnostic provenance, but they are not the promoted main path.

## What has already been done

### Main-family / controller side
The repository already has:
- diversity-aware controllers,
- answer-support aggregation,
- anti-collapse and repeat-expansion refinements,
- observability and failure-case capture,
- comparative mistake audits against strong baselines,
- bounded real-model confirmation paths,
- exact old-vs-current comparison artifacts,
- fresh current-loss-set builders,
- and a deterministic post-tree output repair layer.

### Comparison / artifact side
Recent work materially strengthened the repository’s evidence stack.
The repo now includes:
- broad comparison bundles with reuse-aware evaluation,
- exact 20-case adversarial bundles,
- old-vs-current discovered-tree comparison bundles,
- fresh current-failure sets for the tuned and full integrated methods,
- and targeted repair bundles for output-layer mismatch.

This means the current repo can now separate:
- broad ranking questions,
- fresh exact-loss questions,
- and targeted failure-repair questions.

### Dataset layer and readiness surface
Current practical broad comparison surface is matched on:
- `openai/gsm8k`
- `HuggingFaceH4/MATH-500`
- `HuggingFaceH4/aime_2024`
with fixed budgets and seeds in the latest comparison bundle.

This is a cleaner and more honest stable exact-answer surface than several older partial-integration discussions.

## What the recent work changed

### 1. The method story is now integrated
The repo is no longer best summarized as only:
- diversity control,
- or only output-layer repair,
- or only learner-side target design.

It is now better summarized as an integrated method stack with:
- tree-growth control,
- answer-group-aware allocation,
- repeat-expansion control,
- and deterministic final-answer repair when needed.

### 2. The competitive picture is sharper now
The latest broad current comparison bundle says:
- the latest integrated full method is **not** #1 overall,
- the strongest matched-bundle leader is still a strong repeat-fine broad-family variant,
- and the strongest direct adversary on the fresh current-loss surface is `reasoning_beam2`.

So the repo is now much clearer about what “best method” means on different evaluation surfaces.

### 3. The dominant residual has shifted again
A targeted 16-case subset showed that output-layer mismatch could fully explain a specific remaining slice once the correct answer was already in the tree.

But the fresh exact current full-method failure set against the best direct adversary shows the broader remaining problem is now more upstream:

> **too many failures still come from the correct answer being absent from our tree, with repeated same-family expansion still appearing in most current-loss cases.**

So the repo is no longer mainly bottlenecked by output-layer mismatch.
That is now a preserved repair stage, not the main broad problem.

## What is still unresolved

### Main repository bottleneck
The main unresolved bottleneck is now best described as:

> **under fixed budget, the controller still over-concentrates on one branch family too often and does not yet get the correct answer into the tree reliably enough against the strongest current competitor.**

In simple words:
- the repo is much better at diagnosis than before,
- but it still needs better early tree-shape control.

### Main secondary residual
A secondary residual still exists:
- when the right answer is already in the tree, some cases still need better final selection or local answer consolidation.

But this is not the first thing to fix on the broad current competitive surface.

## What has worked but not fully closed the problem

The following ideas were directionally useful but not sufficient alone:
- anti-collapse / minimum exploration ideas,
- diversity bonuses,
- semantic-overlap-aware scoring,
- duplicate-aware aggregation,
- local completion-aware correction,
- repeat-expansion penalties,
- output-layer repair in targeted subsets,
- and a diversity-needed predictor / gate.

These ideas helped the project diagnose and reduce earlier residuals, but they did not close the broad current competitive gap by themselves.

## What the next needed works should be

If the goal is to beat current methods and strengthen the project for NeurIPS, the next work should now be prioritized in this order.

### 1. Target the absent-from-tree failure slice
Use the fresh exact current full-method failure set to determine:
- which absent-from-tree cases are most representative,
- how repeated same-family expansion appears in those cases,
- and what minimal method change is best justified by the exact tree evidence.

Core question:
> how do we get the correct answer into the tree more often without damaging the cases where we already have it?

### 2. Tighten same-family control without pushing blind diversity
The current evidence suggests that generic diversity pressure is not the right fix by itself.

Core question:
> can a bounded, answer-group-aware anti-monopolization refinement reduce absent-from-tree failures without harming the present-but-not-selected slice?

### 3. Re-run broad matched comparison after the targeted repair
After the next targeted repair, the important step is to re-run the current full comparison bundle.

Core question:
> does the latest integrated line move closer to or past the current matched-bundle leader?

### 4. Keep the output-layer repair stage, but do not over-prioritize it
The targeted repair result is important and should remain part of the integrated method.

But the broad next-method work should not be centered on output-layer repair first.

### 5. Strengthen independent validation once the next upstream repair is in place
The repository still needs fresh independent confirmation before broad-best claims become paper-strong.

This should happen after:
- the absent-from-tree slice is better addressed,
- and the broad matched comparison is rerun.

## What should not be the default next move

Do **not** default to:
- another unrelated controller family,
- another broad generic diversity-first campaign,
- pretending the latest integrated line is already best overall,
- or broad paper-level claims that exceed the latest current comparison bundle.

## Best concise summary

A safe current summary is:

> The repository now has a clear integrated promoted line, a much stronger exact-failure and comparison stack, and a cleaner distinction between tree-generation and output-layer failures. The latest integrated full method is promising but not yet best overall. The dominant current bottleneck is still upstream: repeated same-family expansion and absent-from-tree failures on the strongest current loss slices.
