# Twenty-case old-vs-current tuned tree comparison (2026-04-20)

## Method identities
- Old method: `broad_diversity_aggregation_v1`
- Current method (promoted tuned): `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`
- Comparison target: `self_consistency_3`

## Case-set freeze
- Source manifest: `outputs/twenty_defeat_case_trees_20260419/manifest.json`.
- Case count: **20** (exactly frozen; unchanged).

## Aggregate summary
- Changed final answer: **20 / 20**
- Materially changed tree shape: **20 / 20**
- Reduced repeated same-family expansion: **20 / 20**
- Increased matured alternatives: **20 / 20**
- Current tree contains correct answer: **18 / 20**
- Current method selects correct answer: **17 / 20**
- Main old failure pattern status: **reduced**

## Per-case compact comparison
### Case 1: `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_3`
1. Ground truth: `2`
2. Old method answer (`broad_diversity_aggregation_v1`): `1`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `2`
4. `self_consistency_3` answer: `2`
5. Old tree summary: `created=2, depth=1, expand=8, verify=0, surviving_end=1`
6. Current tree summary: `created=4, depth=2, expand=7, verify=1, surviving_end=3`
7. Current repeats same family too much: `True`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

### Case 2: `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_5`
1. Ground truth: `18`
2. Old method answer (`broad_diversity_aggregation_v1`): `15`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `18`
4. `self_consistency_3` answer: `18`
5. Old tree summary: `created=2, depth=1, expand=8, verify=0, surviving_end=1`
6. Current tree summary: `created=4, depth=2, expand=7, verify=1, surviving_end=3`
7. Current repeats same family too much: `False`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

### Case 3: `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_8`
1. Ground truth: `110`
2. Old method answer (`broad_diversity_aggregation_v1`): `109`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `110`
4. `self_consistency_3` answer: `110`
5. Old tree summary: `created=4, depth=2, expand=8, verify=0, surviving_end=3`
6. Current tree summary: `created=4, depth=2, expand=6, verify=2, surviving_end=2`
7. Current repeats same family too much: `False`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

### Case 4: `HuggingFaceH4/aime_2024 / HuggingFaceH4_aime_2024_15`
1. Ground truth: `321`
2. Old method answer (`broad_diversity_aggregation_v1`): `324`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `321`
4. `self_consistency_3` answer: `321`
5. Old tree summary: `created=3, depth=2, expand=8, verify=0, surviving_end=2`
6. Current tree summary: `created=2, depth=1, expand=3, verify=0, surviving_end=0`
7. Current repeats same family too much: `False`
8. Alternatives matured better: `True`
9. Correct-answer status: `absent from old tree`
10. Verdict: `improved structurally`

### Case 5: `olympiadbench / Hothan_OlympiadBench_0`
1. Ground truth: `3`
2. Old method answer (`broad_diversity_aggregation_v1`): `5`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `3`
4. `self_consistency_3` answer: `3`
5. Old tree summary: `created=2, depth=1, expand=8, verify=0, surviving_end=1`
6. Current tree summary: `created=4, depth=3, expand=6, verify=2, surviving_end=3`
7. Current repeats same family too much: `True`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

### Case 6: `openai/gsm8k / openai_gsm8k_9`
1. Ground truth: `20`
2. Old method answer (`broad_diversity_aggregation_v1`): `18`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `20`
4. `self_consistency_3` answer: `20`
5. Old tree summary: `created=3, depth=2, expand=8, verify=0, surviving_end=2`
6. Current tree summary: `created=4, depth=2, expand=7, verify=1, surviving_end=3`
7. Current repeats same family too much: `True`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

### Case 7: `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_13`
1. Ground truth: `-27`
2. Old method answer (`broad_diversity_aggregation_v1`): `-26`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `-28`
4. `self_consistency_3` answer: `-27`
5. Old tree summary: `created=2, depth=1, expand=8, verify=0, surviving_end=1`
6. Current tree summary: `created=4, depth=2, expand=7, verify=1, surviving_end=3`
7. Current repeats same family too much: `True`
8. Alternatives matured better: `True`
9. Correct-answer status: `absent from current tree`
10. Verdict: `improved structurally`

### Case 8: `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_4`
1. Ground truth: `29`
2. Old method answer (`broad_diversity_aggregation_v1`): `27`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `29`
4. `self_consistency_3` answer: `29`
5. Old tree summary: `created=2, depth=1, expand=6, verify=0, surviving_end=1`
6. Current tree summary: `created=4, depth=2, expand=5, verify=1, surviving_end=3`
7. Current repeats same family too much: `True`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

### Case 9: `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_9`
1. Ground truth: `4`
2. Old method answer (`broad_diversity_aggregation_v1`): `7`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `4`
4. `self_consistency_3` answer: `4`
5. Old tree summary: `created=2, depth=1, expand=8, verify=0, surviving_end=1`
6. Current tree summary: `created=3, depth=1, expand=6, verify=2, surviving_end=2`
7. Current repeats same family too much: `False`
8. Alternatives matured better: `True`
9. Correct-answer status: `absent from old tree`
10. Verdict: `improved structurally`

### Case 10: `HuggingFaceH4/aime_2024 / HuggingFaceH4_aime_2024_1`
1. Ground truth: `809`
2. Old method answer (`broad_diversity_aggregation_v1`): `808`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `809`
4. `self_consistency_3` answer: `809`
5. Old tree summary: `created=4, depth=1, expand=8, verify=0, surviving_end=3`
6. Current tree summary: `created=4, depth=2, expand=8, verify=0, surviving_end=0`
7. Current repeats same family too much: `True`
8. Alternatives matured better: `True`
9. Correct-answer status: `absent from old tree`
10. Verdict: `improved structurally`

### Case 11: `HuggingFaceH4/aime_2024 / HuggingFaceH4_aime_2024_4`
1. Ground truth: `045`
2. Old method answer (`broad_diversity_aggregation_v1`): `44`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `43`
4. `self_consistency_3` answer: `045`
5. Old tree summary: `created=2, depth=1, expand=8, verify=0, surviving_end=1`
6. Current tree summary: `created=4, depth=2, expand=8, verify=0, surviving_end=2`
7. Current repeats same family too much: `True`
8. Alternatives matured better: `True`
9. Correct-answer status: `present in current tree but not selected`
10. Verdict: `improved structurally`

### Case 12: `olympiadbench / Hothan_OlympiadBench_1`
1. Ground truth: `67`
2. Old method answer (`broad_diversity_aggregation_v1`): `64`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `67`
4. `self_consistency_3` answer: `67`
5. Old tree summary: `created=4, depth=3, expand=8, verify=0, surviving_end=3`
6. Current tree summary: `created=4, depth=3, expand=7, verify=1, surviving_end=1`
7. Current repeats same family too much: `True`
8. Alternatives matured better: `True`
9. Correct-answer status: `absent from old tree`
10. Verdict: `improved structurally`

### Case 13: `openai/gsm8k / openai_gsm8k_12`
1. Ground truth: `9`
2. Old method answer (`broad_diversity_aggregation_v1`): `10`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `9`
4. `self_consistency_3` answer: `9`
5. Old tree summary: `created=2, depth=1, expand=4, verify=0, surviving_end=1`
6. Current tree summary: `created=3, depth=2, expand=4, verify=0, surviving_end=1`
7. Current repeats same family too much: `True`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

### Case 14: `openai/gsm8k / openai_gsm8k_3`
1. Ground truth: `160`
2. Old method answer (`broad_diversity_aggregation_v1`): `159`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `160`
4. `self_consistency_3` answer: `160`
5. Old tree summary: `created=2, depth=1, expand=6, verify=0, surviving_end=1`
6. Current tree summary: `created=2, depth=1, expand=3, verify=0, surviving_end=0`
7. Current repeats same family too much: `False`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

### Case 15: `openai/gsm8k / openai_gsm8k_8`
1. Ground truth: `213`
2. Old method answer (`broad_diversity_aggregation_v1`): `211`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `213`
4. `self_consistency_3` answer: `213`
5. Old tree summary: `created=2, depth=1, expand=8, verify=0, surviving_end=1`
6. Current tree summary: `created=4, depth=2, expand=7, verify=1, surviving_end=3`
7. Current repeats same family too much: `False`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

### Case 16: `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_0`
1. Ground truth: `46`
2. Old method answer (`broad_diversity_aggregation_v1`): `47`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `46`
4. `self_consistency_3` answer: `46`
5. Old tree summary: `created=2, depth=1, expand=8, verify=0, surviving_end=1`
6. Current tree summary: `created=4, depth=2, expand=7, verify=1, surviving_end=3`
7. Current repeats same family too much: `True`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

### Case 17: `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_1`
1. Ground truth: `0`
2. Old method answer (`broad_diversity_aggregation_v1`): `-3`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `2`
4. `self_consistency_3` answer: `0`
5. Old tree summary: `created=3, depth=2, expand=6, verify=0, surviving_end=2`
6. Current tree summary: `created=4, depth=2, expand=5, verify=1, surviving_end=3`
7. Current repeats same family too much: `False`
8. Alternatives matured better: `True`
9. Correct-answer status: `absent from current tree`
10. Verdict: `improved structurally`

### Case 18: `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_10`
1. Ground truth: `2000`
2. Old method answer (`broad_diversity_aggregation_v1`): `1999`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `2000`
4. `self_consistency_3` answer: `2000`
5. Old tree summary: `created=3, depth=2, expand=8, verify=0, surviving_end=2`
6. Current tree summary: `created=4, depth=2, expand=8, verify=0, surviving_end=1`
7. Current repeats same family too much: `True`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

### Case 19: `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_11`
1. Ground truth: `348`
2. Old method answer (`broad_diversity_aggregation_v1`): `351`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `348`
4. `self_consistency_3` answer: `348`
5. Old tree summary: `created=2, depth=1, expand=6, verify=0, surviving_end=1`
6. Current tree summary: `created=4, depth=2, expand=6, verify=0, surviving_end=3`
7. Current repeats same family too much: `False`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

### Case 20: `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_12`
1. Ground truth: `42`
2. Old method answer (`broad_diversity_aggregation_v1`): `45`
3. Current tuned answer (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`): `42`
4. `self_consistency_3` answer: `42`
5. Old tree summary: `created=2, depth=1, expand=6, verify=0, surviving_end=1`
6. Current tree summary: `created=3, depth=2, expand=5, verify=0, surviving_end=0`
7. Current repeats same family too much: `False`
8. Alternatives matured better: `True`
9. Correct-answer status: `selected in current tree`
10. Verdict: `improved structurally`

## Key success question answer
On the same 20 old defeat cases, the current tuned promoted method shows **reduced** branch-family collapse behavior (reduced same-family expansion in 20/20 cases).

## Output artifacts
- `outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/manifest.json`
- `outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/per_case_current_tree.json`
- `outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/per_case_comparison.json`
- `outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/summary.json`
- `outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/text_trees/*.txt`
