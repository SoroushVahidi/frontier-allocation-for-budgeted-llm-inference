# Manuscript support index (2026-04-13)

This note indexes the manuscript-support notes currently stored in `docs/` so later paper writing can find the most relevant internal references quickly.

## 1. Core framing and project direction

### `docs/theory_backbones_2026-04-13.md`
Main theory-framing note.

Use this for:
- core problem statement
- main classical backbones
- current theorem target
- overall paper-shape implications

### `docs/project_direction_neurips_2026-04-13.md`
Project-direction constraint note.

Use this for:
- contribution-focused filtering
- why breadth without contribution is not the goal
- priority order for future work

## 2. Learned-scorer lessons

### `docs/learned_scorer_lessons_2026-04-13.md`
Main empirical-interpretation note for v1 and v2 learned scorers.

Use this for:
- why static branch promise was too weak
- why continuation-style targets are better aligned
- current bottleneck in local target quality

## 3. Metareasoning / value-of-computation notes

### `docs/metareasoning_voc_foundations_2026-04-13.md`
Main conceptual note on metareasoning and VOC.

Use this for:
- interpreting branch scoring as value of computation
- linking classical AI theory to adaptive branch allocation
- explaining why controller decisions are metareasoning decisions

### `docs/metareasoning_source_verification_2026-04-13.md`
Citation-discipline note for classical metareasoning sources.

Use this for:
- safest citation role of Russell & Wefald, Horvitz, and bounded-optimality sources
- what is formally proved vs conceptual only
- overclaims to avoid in manuscript writing

## 4. Fixed-budget BAI note

### `docs/bai_source_verification_2026-04-13.md`
Citation-discipline note for classical best-arm identification sources.

Use this for:
- fixed-budget vs fixed-confidence distinction
- safest classical BAI citations
- lower-bound and gap-dependent complexity inspiration
- overclaims to avoid

## 5. Adaptive submodularity note

### `docs/adaptive_submodularity_source_verification_2026-04-13.md`
Citation-discipline note for adaptive submodularity.

Use this for:
- adaptive greedy guarantees under structural assumptions
- why adaptive submodularity is currently a secondary supporting lens
- safe conditional manuscript wording

## 6. Knapsack note

### `docs/knapsack_source_verification_2026-04-13.md`
Citation-discipline note for MCKP/MKP/MMKP.

Use this for:
- offline shadow-problem interpretation
- exact offline baseline inspiration
- hardness context for static allocation
- distinction between MCKP, MKP, and MMKP

## 7. Current best manuscript assembly path

If writing starts soon, a reasonable order of use is:

1. `theory_backbones_2026-04-13.md`
2. `project_direction_neurips_2026-04-13.md`
3. `learned_scorer_lessons_2026-04-13.md`
4. `metareasoning_voc_foundations_2026-04-13.md`
5. citation-discipline notes (`metareasoning`, `bai`, `adaptive_submodularity`, `knapsack`)

## 8. Status

This index should be updated whenever new manuscript-support notes are added, so the internal theory/citation record remains organized rather than fragmented.