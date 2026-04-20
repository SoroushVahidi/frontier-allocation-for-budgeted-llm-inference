# Current project status (canonical)

## Scope

This is the canonical status note for the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- branch-priority / next-step allocation over active branches,
- answer-support aggregation,
- and controlled final-answer surfacing under exact-answer evaluation.

## Core project goal

Learn and evaluate policies that decide **which active branch should receive the next unit of compute**, while respecting a fixed budget, avoiding allocation collapse, and surfacing the right final answer from the explored frontier.

## Final paper goal

The final paper should show that:
1. budgeted test-time compute allocation is a meaningful and distinct problem,
2. a clean frontier / controller framing is more honest than a vague “more reasoning helps” story,
3. branch ranking / next-step allocation is the right conceptual center,
4. early tree shape matters materially under budget,
5. and the remaining challenges can be decomposed into tree-generation failures and output-layer failures rather than treated as one undifferentiated error class.

## Current promoted method picture

The current promoted line is:

> **broad diversity-aware branch allocation with answer-support aggregation, strengthened by anti-collapse answer-group-aware allocation, soft repeat-expansion control, and a deterministic output-layer repair stage.**

This is still the same broad family. It is not a separate controller family.

## What has been built

The repo already contains:
- a runnable frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- answer-support aggregation infrastructure,
- observability-aware tree and branch capture,
- dataset and baseline integration/readiness tooling,
- provenance-aware output and reporting patterns,
- exact failure-case bundles and discovered-tree reconstructions,
- broad comparison-bundle infrastructure with reuse-aware evaluation,
- and a deterministic post-tree output repair module.

## What has been learned

1. The new project framing is sound and distinct from the old binary revise-routing track.
2. Anti-collapse controller design matters for realized budget use and frontier behavior.
3. Repeat-expansion control is meaningful, but not sufficient alone.
4. Output-layer mismatch can be a major residual on targeted subsets where the correct answer is already in the tree.
5. However, on the latest broad comparison surface, the strongest remaining failures are again mostly upstream tree-generation failures rather than output-layer mismatch alone.
6. The latest integrated full method is stronger and cleaner than earlier variants, but it is **not** yet the best overall method on the latest matched broad bundle.
7. Different comparison surfaces expose different leading competitors, so the repo must distinguish:
   - broad matched ranking leader,
   - and strongest direct adversary on fresh exact-loss surfaces.

## Current broad competitive picture

The current matched full comparison bundle places:
- `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1` at **#1** overall,
- and the latest integrated full method at **#3**.

The latest exact current-loss-set builder found the strongest direct adversary on that fresh surface to be:
- `reasoning_beam2`.

So the repository is now in a stronger and more measurable state, but not yet in “best overall method” territory.

## Main unresolved issue

The current main unresolved issue is now best described as:

> **under fixed budget, the controller still tends to over-expand one early-favored branch family and does not yet reliably get the correct answer into the tree often enough against the strongest current competitor.**

A more precise split is:
- some failures are **correct answer absent from our tree**,
- some are **correct answer present but not selected**,
- and a targeted subset was previously shown to be **output-layer mismatch** rather than missing-tree generation.

## Current methodological interpretation

The project should currently be interpreted as:

> **a strong platform and paper direction whose main open problem is still next-step branch allocation and tree-shape control under budget, with output-layer correctness now treated as a separate, auditable stage rather than an invisible side effect.**

## Current best next implementation direction

- Keep branch-priority / next-step allocation as the canonical conceptual center.
- Keep the broad diversity / aggregation family as the main serious family.
- Preserve the integrated promoted line.
- Prioritize repairs on the strongest current failure slices, especially where the correct answer is absent from our tree.
- Use exact current-loss sets and current full comparison bundles together, rather than relying on only one artifact family.
- Strengthen broad comparison evidence before stronger paper claims.

## Practical implication

The repo is ready for serious paper planning, collaborator onboarding, and targeted next-method work. The next phase should focus on reducing absent-from-tree failures, improving branch-family control on hard slices, and validating the latest integrated line against the current broad leader and strongest direct adversary.

## Historical note

Many older status sections in the repository document valuable earlier phases:
- learner-side target design,
- pairwise ambiguity control,
- near-tie routing,
- and diagnostic branches such as ICC.

These remain useful for provenance, but they are no longer the shortest canonical explanation of the repository’s current center.

## Best concise summary

A safe current summary is:

> The repository now has a clear integrated promoted line, a much stronger exact-failure and comparison stack, and a cleaner distinction between tree-generation and output-layer failures. The latest integrated method is promising but not yet best overall; the main remaining bottleneck is still getting the correct answer into the tree reliably enough under fixed budget against the strongest current competitors.
