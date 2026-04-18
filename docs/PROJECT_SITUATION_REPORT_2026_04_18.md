# Project situation report (2026-04-18)

## Purpose

This note is the shortest repository-facing answer to the following questions:

1. What has already been built and validated?
2. What changed most recently?
3. What currently looks promising?
4. What has already been pressure-tested and should not be casually repeated?
5. What are the most likely next steps?

This is a synthesis note, not a single-experiment report.

## Canonical project identity

The repository is currently about:
- fixed-budget adaptive test-time compute allocation for LLM reasoning,
- branch/frontier allocation under budget,
- deciding which active branch should receive the next unit of compute,
- and learning better supervisory targets and control signals for that decision.

This repository is **not** currently centered on the old binary revise-routing framing.

## Short current answer

The shortest honest reading of the repo right now is:

- many recent bounded fixes around the same one-step/local target family were negative or mixed,
- the first current line with a genuinely positive signal is the **multi-step branch-utility target** line,
- that line survived a bounded follow-up validation pass better than nearby ideas,
- but the evidence is still **promising, not yet trustworthy**,
- and the dominant remaining failure pattern currently looks like **overvaluing delayed payoff relative to immediate next-step value/outside-option strength**.

## What is already strong in the repository

The repository already has strong infrastructure for:
- branch/frontier allocation experiments,
- target-regime construction and rebuilds,
- strict validation and matched comparisons,
- hard-slice diagnostics,
- artifact-backed reports and safe-claim discipline,
- failure-case extraction and natural-language casebook generation,
- and repo-facing organization around canonical vs exploratory vs historical materials.

## Recent major updates now recorded in the repo

Recent bounded work has now added and validated all of the following:

### Branch-value + uncertainty line
- canonical regime rebuild and strict replay support,
- support-size robustness analysis,
- derived compare/defer validation,
- and related selective/uncertainty diagnostics.

### Nearby hard-case supervision / control variants that were pressure-tested
- conditional near-tie extra-information expansion,
- probabilistic branch-value allocation,
- opportunity-intensity-weighted upstream supervision,
- statewise supervision-object reformulation,
- allocation-regret target reformulation.

### Current leading target-fidelity line
- bounded multi-step branch-utility target experiment,
- follow-up validation with k1 / k2 / k3 style horizon checks,
- disagreement and support diagnostics,
- failure-case extraction for the current leading multistep method,
- natural-language casebook for the dominant current failure group.

### Repository organization / navigation
- improved top-level README guidance,
- canonical reading-path notes,
- compact diagnostic reading path,
- and additional repo-facing dashboard/ledger/continuation docs.

## What recent negative results now mean

The repo has already pressure-tested many tempting nearby ideas.

The strongest current interpretation is:

> the repository was likely near the limit of what it could extract from the same one-step/local target family via small chooser tweaks, weighting changes, or supervision-format changes.

This does **not** mean representation is irrelevant.
It means the recent failures were informative and narrowed the diagnosis.

## What currently looks most promising

The best current direction is:

> **multi-step target fidelity for branch allocation**

Why this direction now leads:
- it is the first recent line to show a meaningful positive signal,
- it survived a bounded validation pass better than nearby ideas,
- and it fits the current diagnostic story that one-step/local targets are too weak for the hardest close-branch states.

## What the current leading failure pattern is

The current natural-language casebook identifies the dominant interpretable failure group as:

> **delayed_payoff_overvaluation_with_outside_option_miss**

In plain language:
- the method can overvalue branches with future-looking multistep uplift,
- while the oracle-best branch is better for the next immediate compute unit and has a better outside-option gap.

This is the most important current diagnosis for target-design work.

## What is currently not solved

The repository still does not have:
- a robust universally winning learned allocator,
- a clearly trustworthy hard-case solution for close ambiguous branches,
- strong enough support to make a final paper-level claim about the current multistep line,
- or a final target/control design that is clearly stable across conditions.

## What should not be overclaimed right now

Do not overclaim:
- that the multistep line is already solved,
- that the current leading method is broadly robust,
- that close-branch discrimination is fully fixed,
- or that the remaining gap is only calibration or only lack of features.

The safer current claim is:

> the repo has narrowed the diagnosis substantially, and the multi-step target line is the current best lead, but more validation and failure-focused analysis are still needed.

## What we are currently doing

The repository’s current live work should be read as:
- validating and interpreting the multistep target line,
- extracting and understanding the dominant current mistakes,
- improving repo-facing summaries and navigation,
- and choosing the next experiment based on the dominant failure pattern rather than broad random search.

## Most likely next steps

### High-priority next steps
1. Validate whether discounted or otherwise horizon-aware multistep targets reduce delayed-payoff overvaluation without collapsing back to one-step behavior.
2. Continue failure-case diagnosis with richer natural-language reconstruction where possible.
3. Compare one-step vs multistep vs discounted-multistep disagreement on the dominant failure group.
4. Test stronger target-object changes rather than another scalar-score tweak around the same local signal.

### Stronger next research ideas if bounded scalar-target tweaks stall
1. compute-response curve prediction,
2. rank-instability supervision,
3. explicit information-gathering actions under the same fixed budget,
4. distributional branch utility,
5. latent-regime / mixture-of-experts scoring.

## Recommended reading path after this note

Read next:
1. `CURRENT_LEADING_DIRECTION_2026_04_17.md`
2. `DIAGNOSTIC_READING_PATH_2026_04_18.md`
3. `NATURAL_LANGUAGE_FAILURE_CASEBOOK_DOMINANT_GROUP_2026_04_18.md`
4. `CONTINUATION_PLAN_2026_04_18.md`
5. `RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md`
6. `WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md`

## Conservative conclusion

The repository is no longer best described as “trying many ideas and failing.”

A better summary is:

> many nearby ideas around the same local target family were already pressure-tested and ruled weak, the diagnosis is now narrower, and the current best lead is multi-step target fidelity plus failure-pattern-aware next-step experiments.
