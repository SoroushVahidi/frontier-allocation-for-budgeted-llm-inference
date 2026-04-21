# Hundred-case hard early root depth-2 coverage evaluation (20260421T005344Z)

## Rule (experimental)

Root families are the two initial branches (div_0 / div_1) tracked via branch_family_ids. While any root family has a non-done, non-pruned head with max(depth) < 2, the allocator must not expand a branch whose family already satisfies max(depth)>=2 among its expandable heads; it redirects to the neediest pending family (lowest max expandable depth, then score). If remaining actions are strictly less than the sum of per-family lower bounds (2 - max_depth) over pending families, forcing releases for the rest of the run (impossible-under-budget fallback). If hard_early_coverage_min_remaining_actions_to_release > 0, forcing also releases when remaining actions are at or below that threshold (disabled in these specs: value 0).

## Relation to `adaptive_min_expand`

The legacy `adaptive_min_expand` path (see `scripts/run_pilot_gsm8k.py`) enforces a minimum number of expansions before pruning on a different axis than global family coverage. It does not guarantee balanced shallow depth across the two root families before concentration. The new rule is intentionally stronger and global: it blocks continuing on an already depth-2-covered root family while another root family still has expandable heads below depth 2.

- **Insertion point:** experiments/controllers.py: GlobalDiversityAggregationController.run(), immediately after the width_depth_allocation_guard block and before incumbent/challenger metalevel.
- **Baseline method:** `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1`
- **New method:** `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1__deterministic_output_layer_repair_v1`
- **Beam reference:** `reasoning_beam2`

## Outputs

- Directory: `outputs/hundred_hard_early_root_depth2_coverage_eval_20260421T005344Z`
- `eval_manifest.json` — config + rule text
- `per_case_comparison.json` — per-case machine-readable comparison
- `aggregate_summary.json` — headline aggregates
- `comparison_table.csv` — flattened table

## Aggregate comparison (baseline vs new)

| Metric | Baseline | New |
|--------|----------|-----|
| absent_from_tree | 78 | 20 |
| present_not_selected | 22 | 10 |
| repeated_same_family_present | 97 | 86 |
| gold_in_tree | 22 | 80 |
| mean expansions | 10.84 | 9.14 |
| mean actions | 11.48 | 9.73 |

## Outcomes vs baseline (correctness)

- Improved: **70**
- Worsened: **0**
- Unchanged still wrong: **30**
- Unchanged correct: **0**

## Dataset-wise outcomes (improved / worsened / unchanged still wrong)

- `HuggingFaceH4/MATH-500`: improved **18**, worsened **0**, unchanged still wrong **9**
- `HuggingFaceH4/aime_2024`: improved **11**, worsened **0**, unchanged still wrong **8**
- `olympiadbench`: improved **21**, worsened **0**, unchanged still wrong **6**
- `openai/gsm8k`: improved **20**, worsened **0**, unchanged still wrong **7**

## Forced-coverage diagnostics

- Completed fully (no budget release): **81 / 100**
- Released due to impossible lower bound: **17 / 100**
- Cases where absent tree → present tree (new): **61**

## Improved cases

- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_33`: absent_from_tree → correct (actions 16 → 16)
- `openai__gsm8k__openai_gsm8k_10`: absent_from_tree → correct (actions 12 → 2)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_21`: absent_from_tree → correct (actions 10 → 10)
- `olympiadbench__Hothan_OlympiadBench_85`: absent_from_tree → output_or_extraction_mismatch (actions 16 → 11)
- `openai__gsm8k__openai_gsm8k_37`: absent_from_tree → correct (actions 16 → 16)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_62`: absent_from_tree → correct (actions 12 → 4)
- `olympiadbench__Hothan_OlympiadBench_90`: present_not_selected → correct (actions 16 → 13)
- `openai__gsm8k__openai_gsm8k_95`: absent_from_tree → correct (actions 3 → 9)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_32`: absent_from_tree → correct (actions 5 → 14)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_17`: absent_from_tree → correct (actions 14 → 11)
- `olympiadbench__Hothan_OlympiadBench_76`: absent_from_tree → correct (actions 2 → 14)
- `openai__gsm8k__openai_gsm8k_42`: present_not_selected → correct (actions 5 → 14)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_19`: absent_from_tree → correct (actions 4 → 10)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_20`: absent_from_tree → correct (actions 16 → 16)
- `olympiadbench__Hothan_OlympiadBench_81`: absent_from_tree → correct (actions 3 → 16)
- `openai__gsm8k__openai_gsm8k_47`: present_not_selected → correct (actions 16 → 6)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_30`: absent_from_tree → correct (actions 14 → 2)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_12`: absent_from_tree → correct (actions 4 → 5)
- `openai__gsm8k__openai_gsm8k_46`: absent_from_tree → correct (actions 7 → 7)
- `olympiadbench__Hothan_OlympiadBench_4`: present_not_selected → correct (actions 10 → 10)
- `openai__gsm8k__openai_gsm8k_51`: absent_from_tree → correct (actions 14 → 11)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_23`: absent_from_tree → correct (actions 2 → 2)
- `openai__gsm8k__openai_gsm8k_66`: present_not_selected → correct (actions 16 → 9)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_53`: absent_from_tree → correct (actions 14 → 14)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_26`: absent_from_tree → correct (actions 16 → 11)
- `olympiadbench__Hothan_OlympiadBench_61`: absent_from_tree → correct (actions 10 → 10)
- `openai__gsm8k__openai_gsm8k_89`: absent_from_tree → correct (actions 7 → 11)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_69`: absent_from_tree → output_or_extraction_mismatch (actions 14 → 11)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_14`: absent_from_tree → correct (actions 14 → 9)
- `olympiadbench__Hothan_OlympiadBench_44`: absent_from_tree → correct (actions 7 → 14)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_11`: absent_from_tree → correct (actions 14 → 5)
- `olympiadbench__Hothan_OlympiadBench_89`: absent_from_tree → correct (actions 16 → 11)
- `openai__gsm8k__openai_gsm8k_59`: absent_from_tree → correct (actions 9 → 4)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_29`: absent_from_tree → correct (actions 14 → 11)
- `olympiadbench__Hothan_OlympiadBench_59`: absent_from_tree → correct (actions 14 → 2)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_39`: absent_from_tree → correct (actions 12 → 12)
- `olympiadbench__Hothan_OlympiadBench_19`: present_not_selected → correct (actions 15 → 8)
- `openai__gsm8k__openai_gsm8k_50`: absent_from_tree → correct (actions 16 → 11)
- `openai__gsm8k__openai_gsm8k_53`: absent_from_tree → correct (actions 16 → 16)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_59`: absent_from_tree → correct (actions 12 → 10)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_5`: present_not_selected → output_or_extraction_mismatch (actions 14 → 14)
- `olympiadbench__Hothan_OlympiadBench_32`: absent_from_tree → correct (actions 2 → 14)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_70`: present_not_selected → correct (actions 16 → 12)
- `olympiadbench__Hothan_OlympiadBench_39`: absent_from_tree → correct (actions 16 → 16)
- `openai__gsm8k__openai_gsm8k_55`: present_not_selected → correct (actions 3 → 11)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_44`: present_not_selected → correct (actions 16 → 9)
- `olympiadbench__Hothan_OlympiadBench_45`: absent_from_tree → correct (actions 11 → 16)
- `openai__gsm8k__openai_gsm8k_33`: absent_from_tree → correct (actions 10 → 7)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_6`: absent_from_tree → correct (actions 10 → 10)
- `openai__gsm8k__openai_gsm8k_5`: absent_from_tree → correct (actions 10 → 10)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_50`: absent_from_tree → correct (actions 10 → 9)
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_16`: present_not_selected → correct (actions 12 → 12)
- `olympiadbench__Hothan_OlympiadBench_25`: absent_from_tree → correct (actions 14 → 14)
- `openai__gsm8k__openai_gsm8k_71`: absent_from_tree → correct (actions 10 → 2)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_26`: absent_from_tree → correct (actions 8 → 8)
- `olympiadbench__Hothan_OlympiadBench_42`: absent_from_tree → correct (actions 14 → 14)
- `openai__gsm8k__openai_gsm8k_6`: absent_from_tree → correct (actions 14 → 10)
- `olympiadbench__Hothan_OlympiadBench_54`: present_not_selected → correct (actions 6 → 9)
- `openai__gsm8k__openai_gsm8k_29`: absent_from_tree → correct (actions 10 → 10)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_6`: present_not_selected → correct (actions 16 → 2)
- `olympiadbench__Hothan_OlympiadBench_56`: present_not_selected → correct (actions 12 → 9)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_79`: present_not_selected → correct (actions 14 → 14)
- `olympiadbench__Hothan_OlympiadBench_74`: present_not_selected → correct (actions 6 → 6)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_80`: present_not_selected → correct (actions 16 → 2)
- `olympiadbench__Hothan_OlympiadBench_75`: absent_from_tree → correct (actions 12 → 2)
- `openai__gsm8k__openai_gsm8k_52`: present_not_selected → correct (actions 14 → 14)
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_91`: absent_from_tree → correct (actions 16 → 9)
- `olympiadbench__Hothan_OlympiadBench_68`: absent_from_tree → correct (actions 14 → 13)
- `openai__gsm8k__openai_gsm8k_62`: absent_from_tree → correct (actions 9 → 14)
- `olympiadbench__Hothan_OlympiadBench_40`: absent_from_tree → correct (actions 14 → 8)

## Worsened cases

_None in this run._

## Conclusion (auto-generated; interpret cautiously)

**Keep / promote to next tuning stage on this simulator slice** — large absent-from-tree reduction, no regressions on the frozen hundred-case loss set, and lower mean action/expansion cost despite the hard quota.

Optional variant **C** (hard coverage + low-marginal-gain cooldown) is registered as `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1_low_marginal_gain_cooldown_v1` but was not evaluated in this artifact; re-run `scripts/run_hundred_hard_early_root_depth2_coverage_eval_20260420.py --include-combo` to extend the comparison.

## Repro

```bash
pytest tests/test_low_marginal_gain_family_cooldown.py tests/test_hard_early_root_depth2_coverage.py -q
python scripts/run_hundred_hard_early_root_depth2_coverage_eval_20260420.py
```
