# STRICT_F3_VS_EXTERNAL_L1_MAX_MORE_LOSS_CASES_20260425T150500Z

## Required questions answered
1. Matched examples collected: **30**.
2. strict_f3-loss / external_l1_max-win cases collected: **9**.
3. Reached 100 loss cases: **False**.
4. If not reached: Insufficient observed strict_f3-loss/external-win volume in collected matched pairs and/or incomplete slices due runtime/API limits; see incomplete_slices.csv.
5. Cases available for manual inspection: **9** (`loss_cases_for_manual_inspection.md`).
6. Dominant operation types among loss cases: unknown (9).
7. Share absent-from-tree among losses: 1.0.
8. Share present-in-tree but not selected among losses: 0.0.
9. Share parse/extraction failures among losses: 0.0.
10. Absent-from-tree nearest-path/proximity pattern: median_depth=NA, mean_nearest_score=0.0.
11. Loss concentration by budget: {4: 3, 6: 4, 8: 2}.
12. Loss concentration by seed: {11: 4, 23: 5}.
13. Unavailable fields that must be added later: ['answer_support_score', 'branch_local_continuation_score', 'commit_margin'].

## Notes
- Path proximity uses a heuristic token-and-number overlap score (`heuristic_jaccard_numbers_keywords`).
- If dataset gold rationale is unavailable, fallback source is `question + gold answer`.

## Output package
- `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T150500Z/`
