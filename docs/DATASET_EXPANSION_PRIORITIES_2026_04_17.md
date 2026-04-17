# Dataset expansion priorities (2026-04-17)

## Purpose

This note records the current dataset-expansion recommendation for the repository.

The goal is not to maximize benchmark count. The goal is to add datasets that most directly help the current bottleneck:
- hard ambiguous branch decisions,
- near-tie cases,
- and stronger empirical breadth beyond the current math-heavy core.

## Current repository core

The current repository already has substantial work around:
- GSM8K,
- MATH-500,
- AMO-Bench,
- and related current evaluation/integration infrastructure.

These remain important, but they do not by themselves give enough diversity in ambiguity type for the final paper.

## Current recommendation

The current recommendation is:

> **improve current data quality first, then add a small number of carefully chosen new datasets that introduce genuinely different ambiguity regimes.**

This means:
- do not broaden immediately into many new datasets,
- and do not add more datasets that are only minor arithmetic variants unless there is a specific reason.

## Highest-priority additions

### 1. DROP
Why it matters:
- paragraph-grounded numerical reasoning,
- evidence selection ambiguity,
- reference resolution plus discrete operations,
- moves the empirical story beyond pure short-form math reasoning.

Recommended use:
- evaluation first,
- training second.

### 2. MuSR
Why it matters:
- long-lived ambiguity among plausible interpretations,
- useful stress test for hard branch-comparison and near-tie allocation behavior,
- meaningfully different from arithmetic-heavy reasoning sets.

Recommended use:
- evaluation first,
- possibly targeted training later.

## Second-priority additions

### 3. BIG-Bench Hard
Why it matters:
- broader logical and symbolic variety,
- reduces risk that the paper looks too math-specific,
- supports a stronger cross-domain reasoning story.

Recommended use:
- evaluation first.

### 4. AQuA
Why it matters:
- multiple-choice structure can support cleaner supervision than free-form generation,
- useful for branch-comparison supervision design,
- easy to integrate compared with heavier bespoke datasets.

Recommended use:
- both training and evaluation.

## Lower-priority near-term additions

Potentially useful later, but not the first additions:
- CommonsenseQA,
- StrategyQA,
- SVAMP,
- CHAMP,
- GSM-Hard,
- AsDiv.

These are not bad datasets, but they are currently lower value than the top four for the repository’s immediate bottleneck.

## Practical rule

When choosing the next dataset to integrate, ask:
1. does it add a new kind of ambiguity,
2. does it help hard branch-allocation decisions,
3. does it improve the paper’s empirical breadth,
4. and can it be integrated cleanly without derailing the current data-quality work?

If the answer is mostly no, it is probably not the right next dataset.

## Current staged plan

### Phase 1
- improve current data quality,
- then add **DROP** and **MuSR**.

### Phase 2
- add **BIG-Bench Hard** and **AQuA**.

### Phase 3
- reconsider broader additions after seeing whether the top four materially improve the empirical story.

## Neighbor docs

- `docs/CURRENT_BOTTLENECKS.md`
- `docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`
- `docs/ASSET_AUDIT_AND_WORKING_SET_2026_04_17.md`
- `docs/OUTPUTS_INTERPRETATION_GUIDE.md`
