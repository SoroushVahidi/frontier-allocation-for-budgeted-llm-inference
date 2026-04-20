# Near-miss correction bounded controller report (20260420T184849Z)

## Mechanism implemented
- Old method: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`
- New method: `broad_diversity_aggregation_strong_v1_anti_collapse_near_miss_correction_gate_v1`
- Added a bounded near-miss correction gate that activates only when the selected branch is done, top-support is not concentrated, repeated same-family expansion is already high, and nearby numeric done answers exist in the same family.
- On activation, the controller spawns a same-family corrective refinement child and forces one bounded local correction expansion.
- Added traceable metadata counters for activations and forced correction expands.

## Canonical materials read
- Fresh exact current-full-vs-best bundle doc: `docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md`
- Twenty-case improvement report: `docs/TWENTY_CASE_CURRENT_FULL_IMPROVEMENT_REPORT_20260420T181131Z.md`
- Targeted failure-bundle report: `docs/TARGETED_FAILURE_BUNDLE_REPORT_20260420T183801Z.md`
- Targeted machine-readable bundle: `outputs/targeted_failure_bundle_20260420T183801Z`

## Primary results: targeted 7-case near-miss absent-from-tree bundle
- Old correct: 5/7
- New correct: 3/7
- Improved cases: 1
- Worsened cases: 3
- Gold answer newly entered tree: 0
- Correction activations (total): 6

## Secondary transfer results: broader fresh 20-case surface
- Old correct: 12/20
- New correct: 8/20
- Improved cases: 4
- Worsened cases: 8
- Gold answer newly entered tree: 3
- Correction activations (total): 6

## Case movement
- Targeted improved: ['openai/gsm8k::openai_gsm8k_21']
- Targeted worsened: ['HuggingFaceH4/aime_2024::HuggingFaceH4_aime_2024_14', 'HuggingFaceH4/aime_2024::HuggingFaceH4_aime_2024_6', 'olympiadbench::Hothan_OlympiadBench_24']
- Broad improved: ['HuggingFaceH4/MATH-500::HuggingFaceH4_MATH-500_36', 'HuggingFaceH4/aime_2024::HuggingFaceH4_aime_2024_17', 'openai/gsm8k::openai_gsm8k_20', 'openai/gsm8k::openai_gsm8k_21']
- Broad worsened: ['HuggingFaceH4/MATH-500::HuggingFaceH4_MATH-500_34', 'HuggingFaceH4/aime_2024::HuggingFaceH4_aime_2024_14', 'HuggingFaceH4/aime_2024::HuggingFaceH4_aime_2024_20', 'HuggingFaceH4/aime_2024::HuggingFaceH4_aime_2024_6', 'olympiadbench::Hothan_OlympiadBench_24', 'olympiadbench::Hothan_OlympiadBench_30', 'openai/gsm8k::openai_gsm8k_14', 'openai/gsm8k::openai_gsm8k_19']

## Conclusion
- This direction is only better than width/depth challenger guard if it improves the targeted 7-case slice without unacceptable broad regression; otherwise it should be treated as a partial/failed attempt and revised.
- Artifacts: `outputs/near_miss_correction_eval_20260420T184849Z`
