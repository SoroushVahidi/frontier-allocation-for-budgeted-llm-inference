# Current project status (canonical)

## Scope

This is the canonical status note for the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- branch-priority / next-step allocation over active branches.

## Core project goal

Learn and evaluate policies that decide **which active branch should receive the next unit of compute**, while respecting a fixed budget and avoiding allocation collapse.

## Final paper goal

The final paper should show that:
1. budgeted test-time compute allocation is a meaningful and distinct problem,
2. a clean frontier / controller framing is more honest than a vague “more reasoning helps” story,
3. branch ranking / next-step allocation is the right conceptual center,
4. and the main methodological challenge is decision-aligned supervision quality rather than raw scale alone.

## What has been built

The repo now contains:
- a runnable frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation stack,
- canonical branch-learning corpus construction and audit paths,
- matched internal learning passes and bounded intervention passes,
- dataset and baseline integration/readiness tooling,
- conservative external-supervision ingestion for PRM800K / Math-Shepherd / APPS,
- provenance-aware output and reporting patterns.

## What has been learned

1. The new project framing is sound and distinct from the old binary revise-routing track.
2. Anti-collapse controller design matters for realized budget use and frontier behavior.
3. Target quality and comparator semantics matter more than model-class swap alone.
4. Representation quality and hard-slice handling matter, especially on near-tie and adjacent-rank slices.
5. External process supervision can now be integrated and made non-degenerate, but transfer to the real branch-allocation decision is not automatic.
6. Larger scale alone is unlikely to fix the current weaknesses without better targets and better evaluation support on the hardest slices.

## Main unresolved issue

The main unresolved issue is now best described as **decision-aligned supervision quality for budget-aware branch comparison**, including:
- proxy-label mismatch,
- noisy branch-comparison targets,
- imperfect opportunity-cost modeling,
- uneven robustness across budgets / seeds / datasets,
- weak held-out support on exact-promoted and related hard slices,
- incomplete transfer alignment from external process supervision to internal branch-allocation decisions.

## Current methodological interpretation

The project should currently be interpreted as:

> **a strong platform and paper direction whose main open problem is learning how to compare active branches and allocate the next unit of compute well under imperfect supervision and limited budget.**

## Current best next implementation direction

- Keep branch-priority / next-step allocation as the canonical conceptual center.
- Use pairwise and pointwise branch scoring as the main learned objects.
- Treat stop-vs-act only as a helper mechanism, not the full algorithm.
- Continue matched comparisons on canonical corpora with explicit hard-slice diagnostics.
- Improve evidence quality on exact-promoted and related hard slices before broadening to additional external-supervision families.

## Practical implication

The repo is already ready for serious paper planning, collaborator onboarding, and conservative manuscript drafting. The next phase should focus on sharpening the branch-comparison signal and strengthening hard-slice evidence, not on simply adding more scale or more architectures.

## Internal supervision and corpus status

- A real medium-scale GSM8K-backed brute-force/near-brute-force label run was completed and showed high but imperfect exact-vs-approx agreement on overlapping tiny states.
- A broader multi-dataset label campaign across GSM8K, MATH-500, and AMO-Bench materially expanded supervision volume and improved the branch-learning evidence base.
- A canonical processed branch-learning corpus path now exists, with manifest-backed row files, schema, provenance, and slice summaries.
- A canonical matched learning runner now supports anchor, intervention, and external-supervision comparisons on canonical corpora.

Conservative interpretation: the internal data bottleneck is **materially improved but not closed**.

## Hard-case / ambiguity status

- Hard-region exact-supervision tooling now exists, but bounded runs did not clearly solve near-tie or adjacent-rank behavior.
- Hard-case richer features improved some bounded pairwise results, showing that representation quality is part of the bottleneck.
- Ternary / abstention / calibration / near-tie routing passes improved diagnostics and sometimes operating behavior, but did not close the hardest-slice reliability gap.

Conservative interpretation: hard-slice ambiguity is now better instrumented than before, but still unresolved.

## External supervision status

- PRM800K and Math-Shepherd are integrated conservatively as candidate-first external process-supervision sources.
- APPS is registry-integrated as a verifier-backed coding dataset, but remains environment-caveated.
- PRM800K ingestion was repaired from an initially degenerate mapping to a non-degenerate external prior.
- Repaired PRM800K-assisted methods now show stable small gains over the internal anchor in rebuilt corpus families, but broad and aligned PRM variants remain empirically tied in the main matched evidence so far.
- Comparator-boundary PRM use is diagnostically useful and can produce real pair flips, but has not clearly surpassed the broad/aligned PRM variants on the current evidence.

Conservative interpretation: external process supervision is now **technically real and somewhat promising**, but the main unresolved question is still transfer alignment plus evaluation-slice quality, not whether ingestion is possible.

## Current evidence-backed picture

- Internal supervision, canonical corpora, and matched learning infrastructure are now strong enough for a careful paper story.
- The strongest current positive result is that small PRM800K-assisted gains over the internal anchor appear stable in rebuilt corpus families.
- The strongest current limitation is that broad vs aligned PRM usage still does not separate clearly, and exact-promoted evaluation support remains weak.

## Bottom-line project status

The repository should currently be presented as:

> **a mature experimental platform with credible internal and external supervision pathways, where the key remaining research challenge is decision-aligned branch comparison on the hardest budget-sensitive slices rather than basic infrastructure or data access.**
