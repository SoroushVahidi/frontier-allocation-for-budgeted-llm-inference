# Canonical hundred-case failure statistics: strict_gate1_cap_k6 vs best exact-loss comparator

- Generated (UTC): `2026-04-21T16:01:20.590016+00:00`
- Output directory: `outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z`

## Method resolution
- **Selected finalized default method**: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1__deterministic_output_layer_repair_v1`
- **Selected best comparator for exact-loss surface**: `reasoning_beam2`
- **Resolution evidence distinction**: exact-loss comparator and broad/light bundle leaders are treated separately; details recorded in `selection_manifest.json`.
- **Comparator resolution rule**: compute direct-adversary strength on this method's exact-loss surface by maximizing `(ours wrong && comparator correct)`; tie-break by comparator accuracy and canonical doc hint.

## Selection rule for the 100 cases
0. **Simulator surface (expanded, documented in `selection_manifest.json`)**: same benchmark mix as the 20-case builder, with per-seed subset size 96 (vs 40) and additional seeds `{101,113,137}` plus budgets `{14,16}` to ensure 100 repair-consistent exact-loss cases exist under current exclusions.
1. **Eligibility**: On that grid, keep rows where strict_gate1_cap_k6 is incorrect and `reasoning_beam2` is correct.
2. **De-duplication**: Group by `(dataset, example_id)`; score groups by support across the grid (loss_support_count, max_budget_with_loss, observability_priority, lexical id) exactly as the 20-case builder.
3. **Exclusions**: Union of the repo’s prior exact-failure manifests (see `selection_manifest.json`) plus any checked-in `twenty_exact_current_full_vs_best_fresh_20260420/*/selected_case_manifest.json` if present.
4. **Coverage-aware ordering**: Within each dataset, preserve the global rank order; merge datasets in **round-robin** (lexicographic dataset name) so early picks span benchmarks before going deeper in one dataset.
5. **Exact verification**: For each candidate group, try `(seed, budget)` rows in descending budget/seed order until a pair passes full observed-tree replay with deterministic output-layer repair where canonical grading still shows **ours wrong / reasoning_beam2 correct** (stream tags `fresh_our` / `fresh_best` match the 20-case builder).

## Output files
- `outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/per_case_failure_statistics.json`
- `outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/aggregate_failure_statistics.json`
- `outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/failure_statistics_table.csv`
- `outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/selection_manifest.json`
- `outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/top10_most_important_losing_case_features.json`
- `outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/top10_most_important_losing_case_features.csv`

## Aggregate: failure_type
- `absent_from_tree`: 55 (55.0%)
- `present_not_selected`: 45 (45.0%)

## Aggregate: dataset
- `HuggingFaceH4/MATH-500`: 34 (34.0%)
- `olympiadbench`: 33 (33.0%)
- `openai/gsm8k`: 33 (33.0%)

## Aggregate: problem_regime_label
- `algebraic_manipulation`: 9 (9.0%)
- `counting_combinatorics`: 5 (5.0%)
- `geometry`: 10 (10.0%)
- `gsm8k_style_word_arithmetic`: 33 (33.0%)
- `number_theory`: 6 (6.0%)
- `other`: 34 (34.0%)
- `symbolic_series_or_formula`: 3 (3.0%)

## Aggregate: error_geometry (multi-label; counts sum >100%)
- `near_miss`: 58 (58.0% of cases carry this tag)
- `arithmetic_slip`: 44 (44.0% of cases carry this tag)
- `counting_error`: 21 (21.0% of cases carry this tag)
- `wrong_local_neighborhood`: 11 (11.0% of cases carry this tag)
- `other`: 11 (11.0% of cases carry this tag)
- `sign_or_parity_error`: 3 (3.0% of cases carry this tag)

## Aggregate: best_method_advantage_type (multi-label)
- `better_budget_efficiency`: 75 (75.0% of cases carry this tag)
- `earlier_correct_entry`: 69 (69.0% of cases carry this tag)
- `better_selection`: 45 (45.0% of cases carry this tag)
- `multiple_correct_beams`: 21 (21.0% of cases carry this tag)
- `less_collapse`: 13 (13.0% of cases carry this tag)

## Correct-answer coverage (in our tree)
- `multiple`: 1 (1.0%)
- `none`: 55 (55.0%)
- `single`: 44 (44.0%)

## Same-family expansion severity (ours)
- repeated_same_family_present: **88 / 100** (88.0%)
- distribution summaries: see `aggregate_failure_statistics.json` under `distributions`

## Answer-group maturity (ours)
- See `alternative_answer_group_count_and_maturity` per case and `distributions.num_answer_groups` / `dominant_answer_group_share` in the table.

## Cross-tabs (excerpt)
- Full tables in `aggregate_failure_statistics.json` under `cross_tabs`.

## Top 10 most important features of the losing cases
- Machine-readable source: `top10_most_important_losing_case_features.json` (plus CSV export).
1. **failure_type_absent_from_tree** — 55/100 (55.0%). Definition: Gold answer absent from strict_gate1_cap_k6 final tree under deterministic repair replay. Why it matters: Coverage remains the dominant residual failure mode. Next direction: Increase early family diversity and targeted entry to gold-bearing branches.
2. **failure_type_present_not_selected** — 45/100 (45.0%). Definition: Gold exists in our tree but final selected answer is wrong. Why it matters: Large secondary mode indicates selection/scoring opportunity. Next direction: Tune answer-group ranking and tie-break logic when gold is present.
3. **repeated_same_family_expansion_present** — 88/100 (88.0%). Definition: Observed repeated expansion in the same root family via event-level replay. Why it matters: Family concentration often co-occurs with absent-from-tree failures. Next direction: Strengthen anti-collapse gating under cap pressure.
4. **dominant_family_share_high** — 31/100 (31.0%). Definition: Max family share of expansions >=0.60 in a case. Why it matters: Expansion mass concentration reduces breadth and gold-entry probability. Next direction: Raise penalties for dominant-family reuse before F3-like depth.
5. **longest_same_family_run_ge3** — 83/100 (83.0%). Definition: Longest consecutive same-family expansion run is >=3. Why it matters: Long runs indicate local myopia episodes. Next direction: Add run-length-aware rescue branching.
6. **answer_group_monopoly** — 0/100 (0.0%). Definition: One answer group monopolizes support while alternatives exist. Why it matters: Group monopoly can suppress late-correct minority branches. Next direction: Require challenger-group verification when monopoly signal fires.
7. **comparator_earlier_correct_entry** — 69/100 (69.0%). Definition: Comparator shows earlier correct entry advantage tag. Why it matters: Comparator wins by entering correct basin sooner. Next direction: Bias first successful deepening toward under-explored families.
8. **comparator_better_budget_efficiency** — 75/100 (75.0%). Definition: Comparator reaches correctness with materially fewer actions. Why it matters: Budget-use inefficiency leaves less room for corrective exploration. Next direction: Reallocate verification vs expansion under cap_k6.
9. **comparator_less_collapse** — 13/100 (13.0%). Definition: Comparator has lower family-collapse concentration signal. Why it matters: Confirms collapse as practical failure accelerator. Next direction: Increase cross-family compulsory hops after repeated concentration.
10. **selection_advantage_signal** — 45/100 (45.0%). Definition: Comparator tagged with better_selection. Why it matters: Selection layer still explains a substantial subset. Next direction: Improve chosen-node confidence calibration and extraction consistency.

## Representative examples
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_68` — **absent_from_tree** — error_geometry: `near_miss, arithmetic_slip` — best_method_advantage: `earlier_correct_entry, better_budget_efficiency`
  - preview: 'When rolling a certain unfair six-sided die with faces numbered 1, 2, 3, 4, 5, and 6, the probability of obtaining face $F$ is greater than $1/6$, the probability of obtaining the face opposite face $F$ is less than $1/6$, the probability o'
- `olympiadbench__Hothan_OlympiadBench_72` — **absent_from_tree** — error_geometry: `near_miss, arithmetic_slip, counting_error` — best_method_advantage: `earlier_correct_entry`
  - preview: 'Let $T=0$. At some point during a given week, a law enforcement officer had issued $T+2$ traffic warnings, 20 tickets, and had made $T+5$ arrests. How many more tickets must the officer issue in order for the combined number of tickets and '
- `openai__gsm8k__openai_gsm8k_73` — **absent_from_tree** — error_geometry: `near_miss` — best_method_advantage: `earlier_correct_entry, multiple_correct_beams`
  - preview: 'Frances sells 20 cupcakes for $2 for each cupcake and  40  cookies at $1 each.  She buys five trays at $4 for each tray. How much money does Frances have left?'
- `olympiadbench__Hothan_OlympiadBench_84` — **absent_from_tree** — error_geometry: `other` — best_method_advantage: `earlier_correct_entry, multiple_correct_beams, better_budget_efficiency`
  - preview: 'Points $A(k, 3), B(3,1)$ and $C(6, k)$ form an isosceles triangle. If $\\angle A B C=\\angle A C B$, determine all possible values of $k$.'
- `olympiadbench__Hothan_OlympiadBench_71` — **absent_from_tree** — error_geometry: `near_miss, arithmetic_slip` — best_method_advantage: `earlier_correct_entry, less_collapse, better_budget_efficiency`
  - preview: 'Let $T=60$ . Lydia is a professional swimmer and can swim one-fifth of a lap of a pool in an impressive 20.19 seconds, and she swims at a constant rate. Rounded to the nearest integer, compute the number of minutes required for Lydia to swi'
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_78` — **present_not_selected** — error_geometry: `near_miss` — best_method_advantage: `better_selection, better_budget_efficiency`
  - preview: 'Three plus the reciprocal of a number equals 7 divided by that number.  What is the number?'
- `olympiadbench__Hothan_OlympiadBench_47` — **present_not_selected** — error_geometry: `wrong_local_neighborhood, arithmetic_slip` — best_method_advantage: `better_selection, better_budget_efficiency`
  - preview: 'Find all positive integers $n$, for which the numbers in the set $S=\\{1,2, \\ldots, n\\}$ can be colored red and blue, with the following condition being satisfied: the set $S \\times S \\times S$ contains exactly 2007 ordered triples $(x, y, z'
- `openai__gsm8k__openai_gsm8k_35` — **present_not_selected** — error_geometry: `near_miss` — best_method_advantage: `better_selection, earlier_correct_entry`
  - preview: 'John is a carpenter. For his friend Ali, he manufactured 4 wooden tables for $20 each and 2 roof frames for $10 each. How much does Ali have to pay John?'
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_40` — **present_not_selected** — error_geometry: `wrong_local_neighborhood, arithmetic_slip` — best_method_advantage: `better_selection, earlier_correct_entry, better_budget_efficiency`
  - preview: 'The distances from a point $P$ to five of the vertices of a regular octahedron are 3, 7, 8, 9, and 11.  Find the distance from $P$ to the sixth vertex.  [asy] import three;  size(125); currentprojection = perspective(6,3,1);  triple A, B, C'
- `openai__gsm8k__openai_gsm8k_80` — **present_not_selected** — error_geometry: `counting_error` — best_method_advantage: `better_selection, better_budget_efficiency`
  - preview: 'Russell works at a pet store and is distributing straw among the rodents. The rats are kept in 3 cages in equal groups and each rat is given 6 pieces of straw. There are 10 cages of hamsters that are kept alone and each hamster is given 5 p'

## Conclusions
- Most losses are still driven by absent gold in our search tree (coverage) rather than output-layer errors, with repeated same-family expansion pressure remaining a common companion pattern.

