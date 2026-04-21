# Hundred-case hard early coverage: depth-2 vs depth-3 (20260421T010733Z)

## Depth-3 rule

Same mechanism as depth-2, but each root family must reach max(expandable depth) >= 3 before another root family that is still below 3 may be ignored for cross-family expansion priority. Within each pending family, branch choice still follows the normal scored ordering (not fixed BFS).

Same-level ordering inside the eligible pending families is still determined by the existing ``scored`` priorities and anti-collapse stack; the hard rule only **filters which root families are eligible** when cross-family imbalance would violate the minimum depth quota.

- **Controller parameter:** ``hard_early_root_coverage_forced_min_depth=3``
- **Code:** ``GlobalDiversityAggregationController._hard_early_root_coverage_forced_diagnostic`` / ``_apply_hard_early_root_coverage_forced_override`` inserted after the width-depth guard and before metalevel.

## RNG alignment

Uses ``fresh_our`` for baseline / depth-2 / depth-3 and ``fresh_best`` for ``reasoning_beam2``, matching the hundred-case builder.

## Outputs

- ``outputs/hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421T010733Z``

## Aggregate (100 cases)

| Metric | Baseline | Depth-2 | Depth-3 |
|--------|----------|---------|---------|
| absent_from_tree | 78 | 20 | 15 |
| present_not_selected | 22 | 10 | 10 |
| repeated_same_family_present | 97 | 86 | 83 |
| gold_in_tree | 22 | 80 | 85 |
| mean actions | 11.48 | 9.73 | 9.54 |
| mean expansions | 10.84 | 9.14 | 8.93 |

### vs baseline (correctness)

- Depth-2: improved **70**, worsened **0**, unchanged still wrong **30**
- Depth-3: improved **75**, worsened **0**, unchanged still wrong **25**

### Depth-3 vs depth-2 (strict correctness)

- Depth-3 correct & depth-2 wrong: **22**
- Depth-2 correct & depth-3 wrong: **17**
- Impossible-under-budget release: depth-2 **17**, depth-3 **34**
- Depth-3 budget-heavy incomplete coverage heuristic: **17**

## Dataset-wise (improved / worsened / unchanged still wrong vs baseline)

- `HuggingFaceH4/MATH-500` — depth2: {'improved': 18, 'worsened': 0, 'unchanged_still_wrong': 9}, depth3: {'improved': 19, 'worsened': 0, 'unchanged_still_wrong': 8}
- `HuggingFaceH4/aime_2024` — depth2: {'improved': 11, 'worsened': 0, 'unchanged_still_wrong': 8}, depth3: {'improved': 14, 'worsened': 0, 'unchanged_still_wrong': 5}
- `olympiadbench` — depth2: {'improved': 21, 'worsened': 0, 'unchanged_still_wrong': 6}, depth3: {'improved': 23, 'worsened': 0, 'unchanged_still_wrong': 4}
- `openai/gsm8k` — depth2: {'improved': 20, 'worsened': 0, 'unchanged_still_wrong': 7}, depth3: {'improved': 19, 'worsened': 0, 'unchanged_still_wrong': 8}

## Depth-3 vs baseline: improved cases

- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_33`: absent_from_tree → correct (actions 16 → 16)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_24`: absent_from_tree → correct (actions 12 → 12)
- `olympiadbench__Hothan_OlympiadBench_28`: absent_from_tree → correct (actions 16 → 16)
- `openai__gsm8k__openai_gsm8k_10`: absent_from_tree → correct (actions 12 → 12)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_21`: absent_from_tree → correct (actions 10 → 9)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_27`: absent_from_tree → correct (actions 16 → 12)
- `olympiadbench__Hothan_OlympiadBench_85`: absent_from_tree → output_or_extraction_mismatch (actions 16 → 2)
- `openai__gsm8k__openai_gsm8k_37`: absent_from_tree → correct (actions 16 → 16)
- `openai__gsm8k__openai_gsm8k_95`: absent_from_tree → correct (actions 3 → 16)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_32`: absent_from_tree → correct (actions 5 → 16)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_17`: absent_from_tree → correct (actions 14 → 14)
- `olympiadbench__Hothan_OlympiadBench_76`: absent_from_tree → correct (actions 2 → 16)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_19`: absent_from_tree → correct (actions 4 → 10)
- `olympiadbench__Hothan_OlympiadBench_81`: absent_from_tree → correct (actions 3 → 7)
- `openai__gsm8k__openai_gsm8k_47`: present_not_selected → correct (actions 16 → 16)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_30`: absent_from_tree → correct (actions 14 → 14)
- `olympiadbench__Hothan_OlympiadBench_22`: absent_from_tree → correct (actions 7 → 5)
- `openai__gsm8k__openai_gsm8k_46`: absent_from_tree → correct (actions 7 → 7)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_21`: absent_from_tree → correct (actions 16 → 8)
- `olympiadbench__Hothan_OlympiadBench_4`: present_not_selected → correct (actions 10 → 10)
- `openai__gsm8k__openai_gsm8k_51`: absent_from_tree → correct (actions 14 → 2)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_20`: absent_from_tree → correct (actions 16 → 2)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_23`: absent_from_tree → correct (actions 2 → 2)
- `olympiadbench__Hothan_OlympiadBench_20`: absent_from_tree → correct (actions 10 → 2)
- `openai__gsm8k__openai_gsm8k_66`: present_not_selected → correct (actions 16 → 9)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_53`: absent_from_tree → correct (actions 14 → 14)
- `olympiadbench__Hothan_OlympiadBench_61`: absent_from_tree → correct (actions 10 → 10)
- `openai__gsm8k__openai_gsm8k_89`: absent_from_tree → correct (actions 7 → 14)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_69`: absent_from_tree → output_or_extraction_mismatch (actions 14 → 5)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_14`: absent_from_tree → correct (actions 14 → 14)
- `openai__gsm8k__openai_gsm8k_31`: absent_from_tree → correct (actions 16 → 6)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_60`: absent_from_tree → correct (actions 12 → 11)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_11`: absent_from_tree → correct (actions 14 → 9)
- `olympiadbench__Hothan_OlympiadBench_89`: absent_from_tree → correct (actions 16 → 16)
- `openai__gsm8k__openai_gsm8k_59`: absent_from_tree → correct (actions 9 → 2)
- _…and 40 more._

## Depth-3 vs baseline: worsened cases

_None._

## Depth-3 vs depth-2 (strict): depth-3 wins

- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_24` (actions d2→d3: 12 → 12)
- `olympiadbench__Hothan_OlympiadBench_28` (actions d2→d3: 16 → 16)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_27` (actions d2→d3: 6 → 12)
- `olympiadbench__Hothan_OlympiadBench_22` (actions d2→d3: 8 → 5)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_21` (actions d2→d3: 16 → 8)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_20` (actions d2→d3: 16 → 2)
- `olympiadbench__Hothan_OlympiadBench_20` (actions d2→d3: 9 → 2)
- `openai__gsm8k__openai_gsm8k_31` (actions d2→d3: 4 → 6)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_60` (actions d2→d3: 2 → 11)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_25` (actions d2→d3: 10 → 10)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_55` (actions d2→d3: 12 → 2)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_22` (actions d2→d3: 12 → 5)
- `olympiadbench__Hothan_OlympiadBench_21` (actions d2→d3: 4 → 16)
- `openai__gsm8k__openai_gsm8k_49` (actions d2→d3: 14 → 14)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_18` (actions d2→d3: 2 → 5)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_0` (actions d2→d3: 14 → 8)
- `olympiadbench__Hothan_OlympiadBench_23` (actions d2→d3: 2 → 16)
- `openai__gsm8k__openai_gsm8k_4` (actions d2→d3: 14 → 14)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_89` (actions d2→d3: 10 → 7)
- `olympiadbench__Hothan_OlympiadBench_36` (actions d2→d3: 2 → 11)
- `openai__gsm8k__openai_gsm8k_85` (actions d2→d3: 6 → 4)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_16` (actions d2→d3: 13 → 14)

## Depth-3 vs depth-2 (strict): depth-2 wins

- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_62` (actions d2→d3: 4 → 10)
- `olympiadbench__Hothan_OlympiadBench_90` (actions d2→d3: 13 → 16)
- `openai__gsm8k__openai_gsm8k_42` (actions d2→d3: 14 → 10)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_20` (actions d2→d3: 16 → 16)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_12` (actions d2→d3: 5 → 9)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_26` (actions d2→d3: 11 → 16)
- `olympiadbench__Hothan_OlympiadBench_44` (actions d2→d3: 14 → 2)
- `openai__gsm8k__openai_gsm8k_53` (actions d2→d3: 16 → 2)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_5` (actions d2→d3: 14 → 14)
- `olympiadbench__Hothan_OlympiadBench_32` (actions d2→d3: 14 → 13)
- `openai__gsm8k__openai_gsm8k_55` (actions d2→d3: 11 → 14)
- `openai__gsm8k__openai_gsm8k_33` (actions d2→d3: 7 → 10)
- `olympiadbench__Hothan_OlympiadBench_25` (actions d2→d3: 14 → 14)
- `openai__gsm8k__openai_gsm8k_71` (actions d2→d3: 2 → 7)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_6` (actions d2→d3: 2 → 2)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_79` (actions d2→d3: 14 → 10)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_91` (actions d2→d3: 9 → 2)

## Depth-3 budget-heavy incomplete coverage heuristic

- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_28`: actions d2→d3 5 → 8, completed_fully=False
- `olympiadbench__Hothan_OlympiadBench_90`: actions d2→d3 13 → 16, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_32`: actions d2→d3 14 → 16, completed_fully=False
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_17`: actions d2→d3 11 → 14, completed_fully=False
- `olympiadbench__Hothan_OlympiadBench_76`: actions d2→d3 14 → 16, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_30`: actions d2→d3 2 → 14, completed_fully=False
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_14`: actions d2→d3 9 → 14, completed_fully=False
- `olympiadbench__Hothan_OlympiadBench_89`: actions d2→d3 11 → 16, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_46`: actions d2→d3 2 → 16, completed_fully=False
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_29`: actions d2→d3 11 → 14, completed_fully=False
- `olympiadbench__Hothan_OlympiadBench_59`: actions d2→d3 2 → 14, completed_fully=False
- `olympiadbench__Hothan_OlympiadBench_21`: actions d2→d3 4 → 16, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_59`: actions d2→d3 10 → 12, completed_fully=False
- `openai__gsm8k__openai_gsm8k_55`: actions d2→d3 11 → 14, completed_fully=False
- `openai__gsm8k__openai_gsm8k_33`: actions d2→d3 7 → 10, completed_fully=False
- `olympiadbench__Hothan_OlympiadBench_23`: actions d2→d3 2 → 16, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_80`: actions d2→d3 2 → 16, completed_fully=False

## Cost / rigidity tradeoff

Depth-3 further tightens the early cross-family constraint, so **`release_impossible_under_budget` rises** (34 vs 17 for depth-2 on this slice) and fewer runs complete the forced phase fully (65 vs 81). Mean actions/expansions still stay **below baseline** and slightly below depth-2 here, but the higher release rate is the main mechanical risk if budgets are tight.

## Conclusion (auto-generated)

**Depth-3 is mixed but slightly favorable vs depth-2** — strict head-to-head wins vs depth-2 outweigh losses, and absent-from-tree does not regress vs the depth-2 intervention.
