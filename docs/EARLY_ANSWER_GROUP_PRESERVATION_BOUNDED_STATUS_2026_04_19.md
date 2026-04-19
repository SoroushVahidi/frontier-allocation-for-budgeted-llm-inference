# Early answer-group preservation bounded status (2026-04-19)

## Hypothesis tested
Correct answer-groups are often lost at the first meaningful split; preserving one plausible alternative early should reduce dominant failure patterns better than another late-threshold tweak.

## Implemented mechanism (materially different from threshold-only rescue)
- Early useful-diversity protection: force at most a small number of early steps to expand a **plausible challenger answer-group** when support collapse appears early.
- Early target-variable check: each candidate branch receives a target-alignment score (likely aligned vs likely intermediate/mistargeted); preservation only applies to alternatives that pass this screen.
- Early divergence instrumentation: metadata now includes first/second split survival of gold answer-group, first/last presence, disappearance step, and an explicit early-divergence failure category.

## Bounded comparison setup
- Methods:
  - baseline broad: `broad_diversity_aggregation_strong_v1`
  - local reference: `self_consistency_3`
  - new early-preservation variant: `broad_diversity_aggregation_strong_v1_early_answer_group_preservation_v1`
- Datasets: openai/gsm8k, HuggingFaceH4/MATH-500, HuggingFaceH4/aime_2024
- Seeds: [11, 23]
- Budgets: [6, 8]
- Subset size per dataset/seed: 20

## Key bounded metrics
- Mean accuracy:
  - baseline broad: 0.6250
  - reference: 0.5042
  - early-preservation: 0.6792
  - delta (early-preservation - baseline broad): +0.0542
- Wrong commit timing count:
  - baseline broad: 0
  - early-preservation: 0
- Gold answer-group survival:
  - after first split: baseline 0.6250 -> early-preservation 0.6583 (delta +0.0333)
  - after second split: baseline 0.6208 -> early-preservation 0.6417 (delta +0.0208)
- Failure category counts (baseline -> early-preservation):
  - not generated: 75 -> 65
  - generated but underweighted: 0 -> 0
  - collapsed early: 0 -> 0
  - committed away from later: 15 -> 12
- Improved / harmed / unchanged vs baseline broad: 66 / 53 / 121

## Conservative assessment
- This run **does** support the core hypothesis directionally: early answer-group survival improved and final accuracy also improved.
- Harms are still substantial, so this should be treated as **active but not yet stable**.
- It is materially different from the demoted threshold-only line and qualifies for continued bounded promotion work.

## Exact next recommendation
Run one constrained follow-up focused on reducing harmed cases while preserving survival gains:
1. tighten early-preservation selectivity by dataset slice,
2. cap preservation intervention on strong incumbent slices,
3. audit harmed cases where baseline was already correct,
4. re-run the same bounded matrix before any wider claim.
