# Direct-reserve learned scorer disjoint validation

Timestamp: `20260426T_DISJOINT_SCORER_VALIDATION`

## Outcome

A genuinely disjoint planned-case list was not available from the current planning source. The planner excluded 20 prior scorer problem IDs and found 0 candidate problem IDs after exclusion, so no Cohere validation or learned-scorer train/eval was run.

## Planner inputs

- Excluded package 1: `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T150000Z`
- Excluded package 2: `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T151700Z`
- Planning source: `outputs/matched_surface_multiseed_main_comparison_20260423T203259Z/raw_case_results.csv`
- Dataset: `openai/gsm8k`
- Budget: `4`
- Seed: `37`

## Disjoint plan result

- Plan output: `outputs/direct_reserve_disjoint_case_plan_20260426T_DISJOINT_SCORER_VALIDATION/`
- Excluded problem IDs: 20
- Candidate problem IDs before exclusion: 20
- Candidate problem IDs after exclusion: 0
- Planned new problem IDs: 0
- Overlap with first scorer slice: 0 planned IDs, therefore 0 overlap
- Overlap with previous overlapping validation slice: 0 planned IDs, therefore 0 overlap
- Total planned overlap: 0

The two excluded scorer slices contain the same 20 problem IDs, and the available planning source contains only those already-excluded IDs. Reusing them would not be a generalization test, so the planner wrote an insufficient-candidates report instead of silently reusing old IDs.

## Cohere API usage

Cohere API was not used. `COHERE_API_KEY` was present, but the disjoint plan had fewer than 15 problem IDs, so the bounded real API validation was blocked by the task constraints.

## Selected-gold rates and learned scorer results

No new examples were evaluated, so no disjoint-slice selected-gold rates, dataset sizes, learned RF/pairwise comparisons, support-count comparisons, improvement cases, degradation cases, control degradation, gold-present misses, gold-absent cases, model agreement, or learned-score margins are available for this timestamp.

## Cross-slice generalization

Cross-slice train/test was not run because there is no truly disjoint slice to test against. Training on the first slice and testing on the previous overlapping slice would repeat the known 20/20 overlap problem.

## Recommendation

Expand the planning source before any Cohere validation or runtime integration. The learned scorer is not ready for a diagnostic learned-override runtime method from this checkout because the required unseen GSM8K problem IDs were unavailable.

After adding a larger planning source with problem IDs outside the two scorer slices, rerun:

`python3 scripts/plan_disjoint_direct_reserve_scorer_cases.py --timestamp 20260426T_DISJOINT_SCORER_VALIDATION --exclude-output outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T150000Z --exclude-output outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T151700Z --loss-artifact <expanded_loss_artifact.csv> --max-cases 20 --absent-count 7 --present-count 6 --control-count 7 --seed 37 --dataset openai/gsm8k --budget 4`

Only if that plan has at least 15 rows and zero overlap, run the bounded Cohere validation with `--reuse-planned-cases` pointing at the new `planned_cases.csv`.
