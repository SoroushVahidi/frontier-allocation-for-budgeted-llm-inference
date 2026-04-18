# Research ideas and next steps (2026-04-18)

## Purpose

This note records:
- the strongest current research ideas,
- which ideas are already partly or fully pressure-tested,
- what kind of next work is still worth doing,
- and the recommended ordering of that work.

This note is intended to reduce repeated rediscovery of nearby weak ideas.

## Current diagnosis to start from

The current best repository-backed diagnosis is now:
- many nearby target/control refinements have already been pressure-tested,
- fresh observability-enabled runs now support semantic failure diagnosis,
- bounded answer recovery now permits contested-case adjudication,
- and the current main unresolved question is the **target/oracle definition** for hard close-branch states.

Any new idea should be judged against that diagnosis first.

## Ideas that are already pressure-tested enough to not be default next steps

These ideas are informative evidence, but they should not be the default next move without a new reason:
- discounted multistep targets as a broad replacement family,
- compute-response curve prediction as a broad successor claim,
- rank-instability supervision as a broad successor claim,
- instability-to-decision coupling as a broad successor claim,
- broad scalar-target tweaks that do not materially change the target-definition question,
- generic defer-policy sweeps,
- and broad nearby controller sweeps without new semantic disagreement evidence.

## Highest-priority work now

### 1. Target/oracle definition consolidation
Core idea:
- settle the repository’s current hybrid stance rather than broadening method search.

Why it is now highest priority:
- fresh bounded studies support continuation value as a strong core object,
- but also support bounded completion-aware correction in disagreement slices.

Main risk:
- continuing to experiment broadly before freezing the target may create more artifacts without increasing clarity.

### 2. Semantic disagreement adjudication
Core idea:
- use fresh observability-enabled casebooks plus answer recovery to determine when semantic branch quality and continuation value genuinely diverge.

Why it is important:
- this is now the most direct evidence source for whether the hybrid stance is really justified.

Main risk:
- if done loosely, semantic examples can be overread from a tiny bounded slice.

### 3. Data expansion for ambiguity diversity
Core idea:
- add only a small number of datasets with genuinely different ambiguity regimes.

Why it is important:
- the current math-heavy core is strong, but does not yet give enough ambiguity diversity for the final paper story.

Current recommended additions:
- DROP,
- MuSR,
- then BIG-Bench Hard and AQuA if needed.

Main risk:
- broadening too fast may weaken data discipline rather than strengthen the bottleneck-focused story.

## Strongest bounded idea still worth keeping alive

### 4. Bounded hybrid-oracle / completion-aware target validation
Core idea:
- keep continuation value as the default target/oracle,
- and validate bounded completion-aware correction only in disagreement slices, especially near-ties.

Why it is still alive:
- this is now the closest method-design idea to the repository’s actual evidence.

Main risk:
- if overgeneralized, it may become another broad replacement-family claim that the current evidence does not support.

## Medium-priority ideas

### 5. Better incumbent / commit-quality signals
Core idea:
- improve the current notion of commit quality / current branch quality without collapsing back into ad hoc scalar tweaking.

Why it is plausible:
- the current bottleneck is partly about what it means for a branch to be good enough to stop on now.

Main risk:
- it can easily become another nearby score tweak if not tied to the target-definition question.

### 6. Broader answer-level adjudication infrastructure
Core idea:
- improve final-answer recovery and normalization beyond the current bounded contested slice.

Why it is useful:
- this makes future semantic/oracle comparisons more trustworthy.

Main risk:
- infrastructure work can expand without changing the substantive target-definition question unless kept bounded.

## Lower-priority ideas for now

Potentially useful later, but not current defaults:
- another nearby scalar target family,
- another generic fallback policy,
- another uncertainty-only calibration sweep,
- mixture-of-experts branch scorers before a clearer regime story exists,
- broad new controller families not directly tied to the current disagreement question.

## Practical next-step order

### Recommended order if we want repository clarity first
1. freeze the target/oracle definition memo,
2. adjudicate the fresh semantic disagreement cases,
3. complete the bounded data expansion pass,
4. rerun the most relevant bounded comparison under the stabilized target/data story,
5. only then consider another method-family change.

### Recommended order if we want one bounded implementation follow-up later
1. targeted hybrid-oracle validation under better data coverage,
2. broader answer-level adjudication,
3. only then any new scorer/control experiment.

## What to avoid repeating now

Avoid defaulting to:
- another threshold-only tweak,
- another confidence calibration pass with unchanged target semantics,
- another small reweighting of the same supervision family,
- another broad nearby controller sweep,
- or another generic fallback variant with no new target-definition or semantic-adjudication content.

These may still be useful later, but they are not currently the highest-leverage moves.

## Recommended current answer

If only one next repository question is chosen right now, it should be:

> **exactly how should the repo define the hybrid target/oracle for hard close-branch disagreement states?**

If only one next data move is chosen right now, it should be:
- **integrate DROP and MuSR cleanly**, then reassess whether broader expansion is still needed.

## Conservative conclusion

The repository now has enough evidence that the next strong ideas should focus on:
- target/oracle consolidation,
- semantic disagreement adjudication,
- and ambiguity-diverse data,

rather than merely reweighting examples or shifting thresholds around another nearby method family.
