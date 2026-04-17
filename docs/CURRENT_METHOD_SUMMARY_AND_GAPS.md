# Current method summary and gaps

## Purpose

This note is a compact, continuation-oriented summary of what the current method actually is, what has worked, and where the main gaps remain.

It is intended for:
- future implementation passes,
- paper writing,
- collaborator onboarding,
- and preventing repeated exploration of already-tested weak directions.

## Current strongest method picture

The strongest current method picture is:

- **problem framing**: fixed-budget cross-controller frontier allocation / next-step branch allocation,
- **default learned object**: pairwise branch comparison,
- **default strong representation**: hard-case feature set `v2`,
- **hard-case handling**: tie-aware post-hoc deferral,
- **fallback path**: specialized pointwise expert on deferred ambiguous cases.

In short:

> **pairwise default + tie-aware post-hoc deferral + specialist pointwise fallback**

is the strongest currently supported controller family in the repository.

## What has worked

### 1. The frontier-allocation framing is stronger than the old binary revise-routing story
The repository now has a clearer and more honest identity around fixed-budget allocation over active branches.

### 2. Hard-case feature representation mattered a lot
The richer `v2` representation materially improved hard slices for the pairwise logistic path under fixed supervision.

### 3. Hard-case ambiguity is real, not just noise in aggregate metrics
Near-tie and adjacent-rank slices repeatedly behave differently from ordinary comparisons, and multiple bounded passes now support treating them as a first-class challenge.

### 4. Specialized pointwise fallback is promising
A specialized pointwise fallback can preserve or improve the strongest near-tie signal relative to ordinary forced-binary baselines.

### 5. Cleaner controller accounting helped
Strict-coupled and later tie-aware post-hoc deferral variants improved controller cleanliness, reduced spillover, and gave more honest unresolved/deferred accounting even when they did not increase headline forced accuracy.

## What has not worked well enough

### 1. Model-class changes alone
GBDT / stronger tabular rankers did not become clear universal winners.

### 2. Exact hard-region promotion alone
Targeted exact relabeling improved localization/instrumentation more than end metrics on the hardest slices.

### 3. Pure formulation changes alone
Ternary / abstention / fallback variations did not by themselves solve forced near-tie behavior.

### 4. Deferred-state-only specialist training
Training the specialist only on deferred train states did not improve deferred-subset quality and hurt overall forced/top-1 versus the stronger tie-aware baseline.

### 5. Broad hard-pair replacement
Recent bounded hard-case adjudication/relabeling passes, including a bounded Cohere pass, did not provide a clean win under the tested replacement policies.

## Current best interpretation of the bottleneck

The bottleneck is no longer best described as “we need another controller family” or “we need another model class.”

The best current interpretation is:

> **the main remaining weakness is supervision / confidence design for ambiguous hard cases, together with the need for a more principled selective pairwise decision rule.**

This includes:
- noisy low-margin supervision,
- ambiguous near-tie labels,
- heuristic deferral triggers,
- and specialist-expert training that is still not principled enough on the deferred subset.

## What should currently be treated as the strongest scaffold

If implementing the next method pass, keep fixed unless there is strong new evidence:
- pairwise comparator as the default path,
- `v2` feature representation,
- tie-aware post-hoc deferral as the cleaner ambiguity-handling scaffold,
- specialist pointwise expert as the fallback path.

## What should currently be treated as unstable / not yet settled

- exact best training regime for the specialist expert,
- final uncertainty / confidence score for calibrated deferral,
- final paper-level comparison against strongest external baselines,
- final best-arm-identification-style allocation algorithmic story.

## Recommended immediate next step

The best current next step is:

> **upgrade the hard-pair supervision pipeline before broadening again into more controller complexity.**

Concretely, this means building a more principled hard-pair cleanup path:
- suspicious-pair ranking,
- selective cleanup,
- reliability-aware weighting,
- and only then more targeted exact review or multi-judge aggregation if needed.

That direction is now more urgent than another generic controller-family expansion.
