# TYPED_STRATEGY_SEEDED_SMOKE_AUDIT_20260425T202856Z

Scope: Audit of `outputs/typed_strategy_seeded_eval_20260425T_TYPED_STRATEGY_SEEDED_SMOKE/` and supporting smoke report.

## Artifact Summary

- `summary.csv`: typed seeding has `absent_from_tree_rate=0.5` vs `strict_f3=0.6` (coverage improves), but no accuracy gain and no present-not-selected repairs.
- `slice_summary.csv`: mirrors summary for the smoke slice (`loss150`, `max_cases=10`).
- `per_case_results.csv`: all methods have `accuracy=0` in this smoke subset; typed branches often collapse into one dominant family.
- `per_case_strategy_metadata.jsonl`: typed prompts are injected and tracked; strategy prompt metadata is present for combinatorics rows.
- `per_branch_strategy_traces.jsonl`: traces exist but are not yet summarized into robust lexical diversity metrics.
- `typed_strategy_diversity_summary.csv`: prompt diversity is high (`avg_prompt_diversity_family_count=4.0`) but answer diversity is low (`avg_answer_diversity_group_count=0.9`, collapse rate `1.0`) for typed method.
- `answer_group_by_strategy_summary.csv`: many typed rows show only one family contributing to non-empty answer groups.
- `transition_summary.csv`: no `-> correct` transitions in this smoke run.
- `commit_guard_summary.csv`: commit guard triggers (`0.7`) on typed method but does not produce repairs.
- `verifier_diagnostics.csv`: heuristic verifier is used in many typed rows, no real verifier calls.
- `present_not_selected_repairs.csv`: empty in this smoke package.
- `absent_from_tree_repairs.csv`: empty in this smoke package.
- `hurt_cases.csv`: empty in this smoke package.
- `missing_fields_report.csv`: missing-field reporting is underpowered in this package (`dominant_typed_strategy_family` only), confirming insufficient scoring diagnostics.

## Required Diagnostic Answers

1. Which absent-from-tree cases were repaired?
   - None in the audited smoke package (`absent_from_tree_repairs.csv` is empty).

2. Which strategy family discovered the correct answer most often?
   - No correct predictions in this smoke run, so no family has successful discoveries.

3. Did typed strategy seeding create real answer diversity, or did branches collapse?
   - Branches mostly collapsed at answer level despite diverse prompt seeding; collapse rate is `1.0` for typed method in this package.

4. In present-not-selected cases, was correct answer supported by different strategy family than selected wrong answer?
   - Not diagnosable from this package due to missing group-level gold-vs-selected family score tables in per-case rows.

5. Did commit guard trigger in present-not-selected cases?
   - Frequently, yes (`trigger_rate=0.7` for typed), but it did not convert cases to correct.

6. If it triggered, why did it not change selection?
   - Verifier scores were weakly discriminative (clustered near `0.5`/`warn`), so guard had little ability to re-rank answer groups.

7. If it did not trigger, what missing trigger condition should be added?
   - Trigger when gold group is present but selected group dominates via single-family support and low verifier separation; also trigger on low support+score gap stability across top-2 groups.

8. Are verifier scores discriminative, or nearly constant?
   - Nearly constant in this smoke package (mostly `0.43` or `0.50` bands).

9. Which strategy family most often causes wrong high-confidence answers?
   - In this smoke subset, wrong selected groups are often single-family and frequently tied to `small_example_pattern_family`, `enumeration_or_decomposition_family`, or `direct_formula_family` depending on case; no robust high-confidence family ranking is possible without richer group-score exports.

10. Did any cases get hurt by typed seeding?
    - No explicit hurt cases flagged (`hurt_cases.csv` empty), though typed method still fails all sampled rows.

11. What exact metadata was still missing for scoring diagnosis?
    - Missing/insufficient in this package:
      - gold vs selected group score decomposition (support, verifier, diversity, final score)
      - per-group family support counts and ranks
      - explicit selection failure reason labels
      - selection ablation comparisons on fixed generated candidates
      - commit-guard change/no-change rationale at per-case granularity

