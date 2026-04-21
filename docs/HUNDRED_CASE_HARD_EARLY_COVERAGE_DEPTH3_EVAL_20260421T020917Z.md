# Hundred-case hard early coverage: depth-2 vs depth-3 (20260421T020917Z)

## Depth-3 rule

Same mechanism as depth-2, but each root family must reach max(expandable depth) >= 3 before another root family that is still below 3 may be ignored for cross-family expansion priority. Within each pending family, branch choice still follows the normal scored ordering (not fixed BFS).

Same-level ordering inside the eligible pending families is still determined by the existing ``scored`` priorities and anti-collapse stack; the hard rule only **filters which root families are eligible** when cross-family imbalance would violate the minimum depth quota.

- **Controller parameter:** ``hard_early_root_coverage_forced_min_depth=3``
- **Code:** ``GlobalDiversityAggregationController._hard_early_root_coverage_forced_diagnostic`` / ``_apply_hard_early_root_coverage_forced_override`` inserted after the width-depth guard and before metalevel.

## RNG alignment

Uses ``fresh_our`` for baseline / depth-2 / depth-3 and ``fresh_best`` for ``reasoning_beam2``, matching the hundred-case builder.

## Outputs

- ``outputs/hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421T020917Z``

## Aggregate (100 cases)

| Metric | Baseline | Depth-2 | Depth-3 |
|--------|----------|---------|---------|
| absent_from_tree | 78 | 24 | 21 |
| present_not_selected | 22 | 13 | 13 |
| repeated_same_family_present | 97 | 86 | 83 |
| gold_in_tree | 22 | 76 | 79 |
| mean actions | 11.48 | 10.03 | 9.49 |
| mean expansions | 10.84 | 9.51 | 8.93 |

### vs baseline (correctness)

- Depth-2: improved **63**, worsened **0**, unchanged still wrong **37**
- Depth-3: improved **66**, worsened **0**, unchanged still wrong **34**

### Depth-3 vs depth-2 (strict correctness)

- Depth-3 correct & depth-2 wrong: **25**
- Depth-2 correct & depth-3 wrong: **22**
- Impossible-under-budget release: depth-2 **10**, depth-3 **13**
- Depth-3 budget-heavy incomplete coverage heuristic: **17**

## Dataset-wise (improved / worsened / unchanged still wrong vs baseline)

- `HuggingFaceH4/MATH-500` — depth2: improved 16, worsened 0, unchanged still wrong 11; depth3: improved 17, worsened 0, unchanged still wrong 10
- `HuggingFaceH4/aime_2024` — depth2: improved 10, worsened 0, unchanged still wrong 9; depth3: improved 9, worsened 0, unchanged still wrong 10
- `olympiadbench` — depth2: improved 20, worsened 0, unchanged still wrong 7; depth3: improved 21, worsened 0, unchanged still wrong 6
- `openai/gsm8k` — depth2: improved 17, worsened 0, unchanged still wrong 10; depth3: improved 19, worsened 0, unchanged still wrong 8

## Depth-3 vs baseline: improved cases

- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_33`: absent_from_tree → correct (actions 16 → 9)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_24`: absent_from_tree → correct (actions 12 → 12)
- `olympiadbench__Hothan_OlympiadBench_28`: absent_from_tree → correct (actions 16 → 16)
- `openai__gsm8k__openai_gsm8k_10`: absent_from_tree → correct (actions 12 → 12)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_21`: absent_from_tree → correct (actions 10 → 10)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_27`: absent_from_tree → correct (actions 16 → 14)
- `olympiadbench__Hothan_OlympiadBench_85`: absent_from_tree → output_or_extraction_mismatch (actions 16 → 2)
- `openai__gsm8k__openai_gsm8k_37`: absent_from_tree → correct (actions 16 → 16)
- `olympiadbench__Hothan_OlympiadBench_90`: present_not_selected → correct (actions 16 → 16)
- `openai__gsm8k__openai_gsm8k_95`: absent_from_tree → correct (actions 3 → 16)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_32`: absent_from_tree → correct (actions 5 → 16)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_17`: absent_from_tree → correct (actions 14 → 6)
- `olympiadbench__Hothan_OlympiadBench_76`: absent_from_tree → correct (actions 2 → 10)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_19`: absent_from_tree → correct (actions 4 → 10)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_20`: absent_from_tree → correct (actions 16 → 9)
- `olympiadbench__Hothan_OlympiadBench_81`: absent_from_tree → correct (actions 3 → 7)
- `openai__gsm8k__openai_gsm8k_47`: present_not_selected → correct (actions 16 → 16)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_30`: absent_from_tree → correct (actions 14 → 14)
- `olympiadbench__Hothan_OlympiadBench_22`: absent_from_tree → correct (actions 7 → 8)
- `openai__gsm8k__openai_gsm8k_46`: absent_from_tree → correct (actions 7 → 7)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_21`: absent_from_tree → correct (actions 16 → 7)
- `olympiadbench__Hothan_OlympiadBench_4`: present_not_selected → correct (actions 10 → 10)
- `openai__gsm8k__openai_gsm8k_51`: absent_from_tree → correct (actions 14 → 2)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_20`: absent_from_tree → correct (actions 16 → 2)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_23`: absent_from_tree → correct (actions 2 → 2)
- `olympiadbench__Hothan_OlympiadBench_20`: absent_from_tree → correct (actions 10 → 2)
- `openai__gsm8k__openai_gsm8k_66`: present_not_selected → correct (actions 16 → 9)
- `olympiadbench__Hothan_OlympiadBench_61`: absent_from_tree → correct (actions 10 → 7)
- `openai__gsm8k__openai_gsm8k_89`: absent_from_tree → correct (actions 7 → 14)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_69`: absent_from_tree → output_or_extraction_mismatch (actions 14 → 14)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_14`: absent_from_tree → correct (actions 14 → 14)
- `openai__gsm8k__openai_gsm8k_31`: absent_from_tree → correct (actions 16 → 6)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_60`: absent_from_tree → correct (actions 12 → 4)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_11`: absent_from_tree → correct (actions 14 → 9)
- `olympiadbench__Hothan_OlympiadBench_89`: absent_from_tree → correct (actions 16 → 16)
- _…and 31 more._

## Depth-3 vs baseline: worsened cases

_None._

## Depth-3 vs depth-2 (strict): depth-3 wins

- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_24` (actions d2→d3: 12 → 12)
- `olympiadbench__Hothan_OlympiadBench_28` (actions d2→d3: 16 → 16)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_21` (actions d2→d3: 10 → 10)
- `openai__gsm8k__openai_gsm8k_95` (actions d2→d3: 16 → 16)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_17` (actions d2→d3: 14 → 6)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_19` (actions d2→d3: 10 → 10)
- `openai__gsm8k__openai_gsm8k_46` (actions d2→d3: 7 → 7)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_21` (actions d2→d3: 16 → 7)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_20` (actions d2→d3: 16 → 2)
- `olympiadbench__Hothan_OlympiadBench_61` (actions d2→d3: 10 → 7)
- `openai__gsm8k__openai_gsm8k_89` (actions d2→d3: 11 → 14)
- `openai__gsm8k__openai_gsm8k_31` (actions d2→d3: 4 → 6)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_60` (actions d2→d3: 2 → 4)
- `olympiadbench__Hothan_OlympiadBench_89` (actions d2→d3: 16 → 16)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_46` (actions d2→d3: 2 → 16)
- `olympiadbench__Hothan_OlympiadBench_21` (actions d2→d3: 4 → 16)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_70` (actions d2→d3: 16 → 16)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_90` (actions d2→d3: 8 → 8)
- `olympiadbench__Hothan_OlympiadBench_23` (actions d2→d3: 2 → 16)
- `olympiadbench__Hothan_OlympiadBench_56` (actions d2→d3: 12 → 9)
- `openai__gsm8k__openai_gsm8k_4` (actions d2→d3: 10 → 14)
- `olympiadbench__Hothan_OlympiadBench_36` (actions d2→d3: 2 → 14)
- `openai__gsm8k__openai_gsm8k_85` (actions d2→d3: 6 → 4)
- `openai__gsm8k__openai_gsm8k_62` (actions d2→d3: 14 → 2)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_16` (actions d2→d3: 9 → 11)

## Depth-3 vs depth-2 (strict): depth-2 wins

- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_62` (actions d2→d3: 4 → 12)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_12` (actions d2→d3: 14 → 8)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_53` (actions d2→d3: 10 → 14)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_26` (actions d2→d3: 10 → 13)
- `olympiadbench__Hothan_OlympiadBench_44` (actions d2→d3: 14 → 2)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_29` (actions d2→d3: 14 → 14)
- `olympiadbench__Hothan_OlympiadBench_59` (actions d2→d3: 2 → 13)
- `openai__gsm8k__openai_gsm8k_19` (actions d2→d3: 12 → 12)
- `openai__gsm8k__openai_gsm8k_53` (actions d2→d3: 16 → 2)
- `olympiadbench__Hothan_OlympiadBench_32` (actions d2→d3: 14 → 13)
- `olympiadbench__Hothan_OlympiadBench_39` (actions d2→d3: 16 → 16)
- `openai__gsm8k__openai_gsm8k_33` (actions d2→d3: 7 → 10)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_6` (actions d2→d3: 4 → 10)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_50` (actions d2→d3: 4 → 10)
- `olympiadbench__Hothan_OlympiadBench_25` (actions d2→d3: 14 → 14)
- `openai__gsm8k__openai_gsm8k_71` (actions d2→d3: 2 → 7)
- `openai__gsm8k__openai_gsm8k_6` (actions d2→d3: 14 → 14)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_6` (actions d2→d3: 2 → 2)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_79` (actions d2→d3: 14 → 10)
- `olympiadbench__Hothan_OlympiadBench_74` (actions d2→d3: 6 → 6)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_80` (actions d2→d3: 2 → 16)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_91` (actions d2→d3: 9 → 2)

## Depth-3 budget-heavy incomplete coverage heuristic

- `openai__gsm8k__openai_gsm8k_10`: actions d2→d3 2 → 12, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_62`: actions d2→d3 4 → 12, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_30`: actions d2→d3 2 → 14, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_53`: actions d2→d3 10 → 14, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_69`: actions d2→d3 11 → 14, completed_fully=False
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_14`: actions d2→d3 9 → 14, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_46`: actions d2→d3 2 → 16, completed_fully=False
- `olympiadbench__Hothan_OlympiadBench_21`: actions d2→d3 4 → 16, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_44`: actions d2→d3 9 → 16, completed_fully=False
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_0`: actions d2→d3 12 → 14, completed_fully=False
- `openai__gsm8k__openai_gsm8k_33`: actions d2→d3 7 → 10, completed_fully=False
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_6`: actions d2→d3 4 → 10, completed_fully=False
- `olympiadbench__Hothan_OlympiadBench_23`: actions d2→d3 2 → 16, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_50`: actions d2→d3 4 → 10, completed_fully=False
- `openai__gsm8k__openai_gsm8k_29`: actions d2→d3 4 → 10, completed_fully=False
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_80`: actions d2→d3 2 → 16, completed_fully=False
- `olympiadbench__Hothan_OlympiadBench_36`: actions d2→d3 2 → 14, completed_fully=False

## Conclusion (auto-generated)

**Depth-3 modestly improves on depth-2 here** — vs baseline, depth-3 fixes at least as many cases as depth-2 and further reduces `absent_from_tree`; strict depth-3 vs depth-2 correctness favors depth-3. Tradeoff: more `release_impossible_under_budget` events when the quota is tight, so monitor real budgets carefully.
