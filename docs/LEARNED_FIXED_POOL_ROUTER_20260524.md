# Learned Fixed-Pool Reliability Router Prototype (2026-05-24)

## 1. Completed artifacts used
- Cohere canonical final-300 (GSM8K):
  - `outputs/canonical_final300_cohere_contract_matched_live_20260523T181948Z/cohere_real_model_cost_normalized_validation_20260523T181948Z/per_example_records.jsonl`
- Mistral merged full-300 (GSM8K):
  - `outputs/merged_repaired_cohere_mistral_selector_replay_20260524/mistral_full300_merged_per_example_records.jsonl`

Both passed integrity checks (`1200` rows, `300` examples, `4x300` methods, no duplicate `(example_id, method)`).

## 2. Scenario/example scope
- Scenarios: `2` (`cohere_gsm8k`, `mistral_gsm8k`)
- Total examples: `600`
- Total method rows consumed: `2400`

## 3. Features and labels built
- One row per example with identifiers (`scenario_id`, `provider`, `dataset`, `example_id`, `seed`, `budget`).
- Source answer/correctness labels for `{frontier, L1, S1, TALE}`.
- Selector/action labels:
  - `pooled4_correct`
  - `agreement_only_correct`
  - `always_s1_correct`
  - `dominant_source_action_correct` (fold-defined via beta-shrinkage regime)
  - `oracle_best_source_correct` (diagnostic)
  - `oracle_best_action_correct` (diagnostic)
- Runtime-legal feature families:
  - metadata one-hot
  - question morphology
  - answer-pattern/disagreement structure
  - output parse/length/clean-numeric features
  - fold-safe calibration priors (source accuracies, shrinkage, spread, dominance flags, pairwise same-answer/same-wrong rates)

## 4. Action set included
Deployable actions:
- `choose_frontier`
- `choose_L1`
- `choose_S1`
- `choose_TALE`
- `pooled4_with_fallback`
- `agreement_only_2of3_against_frontier`
- `raw_spread_regime_selector`
- `beta_shrinkage_regime_selector`

Diagnostic-only:
- `oracle_best_source`
- `oracle_best_action`

## 5. Learned variants trained
- Source-correctness logistic router (one-vs-rest over source correctness)
- Action-correctness logistic router (one-vs-rest over deployable actions)
- Action decision-tree router (`max_depth` chosen from `{2,3,4}` by fold performance)
- Action gradient-boosting router (`HistGradientBoostingClassifier`, low-complexity settings)

## 6. Within-scenario CV (5-fold)
Key accuracies:
- Cohere GSM8K (`within_cohere_gsm8k`):
  - `action_logistic_router_with_ids`: `87.00%` (261/300)
  - `source_logistic_router_with_ids`: `87.67%` (263/300)
  - `pooled4_with_fallback`: `85.67%` (257/300)
  - `S1`: `80.00%` (240/300)
- Mistral GSM8K (`within_mistral_gsm8k`):
  - `action_logistic_router_with_ids`: `90.33%` (271/300)
  - `source_logistic_router_with_ids`: `90.67%` (272/300)
  - `pooled4_with_fallback`: `85.67%` (257/300)
  - `S1`: `91.33%` (274/300)

Interpretation:
- On Cohere, learned routers beat pooled-4 by point estimate.
- On Mistral, learned routers remain below always-S1 by point estimate.

## 7. Pooled stratified CV (5-fold)
Combined 600-example pooled CV:
- `pooled_stratified_with_ids`:
  - `action_logistic_router_with_ids`: `87.00%` (522/600)
  - `source_logistic_router_with_ids`: `87.17%` (523/600)
  - `pooled4_with_fallback`: `85.67%` (514/600)
  - `S1`: `85.67%` (514/600)
- `pooled_stratified_no_ids` (ablation dropping provider/scenario IDs):
  - `action_logistic_router_no_ids`: `87.00%` (522/600)
  - `source_logistic_router_no_ids`: `87.00%` (522/600)

Interpretation:
- Pooled CV gain exists vs pooled-4 by point estimate (`+1.33pp` for action logistic).
- With-ID vs no-ID parity suggests the signal is not exclusively provider/scenario lookup.

## 8. Cross-scenario transfer
- Train Cohere -> Test Mistral (`transfer_cohere_gsm8k_to_mistral_gsm8k`):
  - `action_logistic_router_no_ids`: `85.67%`
  - `pooled4_with_fallback`: `85.67%`
  - `S1`: `91.33%`
- Train Mistral -> Test Cohere (`transfer_mistral_gsm8k_to_cohere_gsm8k`):
  - `action_logistic_router_no_ids`: `85.00%`
  - `pooled4_with_fallback`: `85.67%`
  - `S1`: `80.00%`

Interpretation:
- Transfer is weak and unstable (expected with only two scenarios).
- Router does not consistently beat pooled-4 under transfer.

## 9. Beat/tie checks requested
- Beat or tie pooled-4 on Cohere?
  - Yes, within Cohere CV: `87.00%` vs `85.67%`.
- Beat or tie S1/regime selector on Mistral?
  - No for S1 point estimate: `90.33%` vs `91.33%`.
  - No for regime selector tied to S1: `90.33%` vs `91.33%`.

## 10. Provider/scenario lookup risk
- No-ID ablation is essentially unchanged in pooled CV (`87.00%` vs `87.00%` for action logistic).
- Provider/scenario one-hot features are not dominant in top linear importances.
- Conclusion: not purely lookup-table behavior, but two-scenario data still leaves overfit risk high.

## 11. Most important features (diagnostic)
Top recurring signals across linear/tree models:
- `L1_S1_agree`
- `frontier_S1_agree`
- `external_majority_answer_excludes_S1`
- `unique_answer_count`
- `all_four_agree`
- `S1_raw_len`
- `S1_isolated`

## 12. Remaining failure cases
From pooled stratified with-IDs action logistic predictions:
- Router failures: `78` cases total (`47` Cohere, `31` Mistral)
- Router vs pooled-4 disagreements: `45`
  - Router right / pooled-4 wrong: `17`
  - Router wrong / pooled-4 right: `9`
- Router vs S1 disagreements: `54`

Detailed case files:
- `outputs/learned_fixed_pool_router_20260524/learned_router_failure_cases.csv`
- `outputs/learned_fixed_pool_router_20260524/learned_router_failure_casebook.md`

## 13. Data needed next
- Add completed MATH-500 scenario-5 artifact when full run is finished.
- Add completed Cerebras GSM8K scenario-3 artifact when full run is finished.
- Re-run same protocol with 3+ scenarios to reduce regime-entanglement and estimate transfer reliably.

## 14. Recommendation
This is a valid **offline prototype diagnostic** of a learned fixed-pool reliability router. Keep it as a paper-side algorithmic contribution candidate, but do not promote/runtime-claim from these two scenarios alone.

- Recommended next step:
  1. Freeze this bundle as prototype evidence.
  2. Expand to 3+ completed scenarios.
  3. Re-evaluate pooled CV + leave-scenario-out transfer before any stronger claim.
