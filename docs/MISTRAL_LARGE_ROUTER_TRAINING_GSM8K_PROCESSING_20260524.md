# MISTRAL_LARGE_ROUTER_TRAINING_GSM8K_PROCESSING_20260524

## Integrity
{
  "raw_rows": 4000,
  "effective_rows": 4000,
  "duplicate_overage": 0,
  "method_counts_raw": {
    "direct_reserve_semantic_frontier_v2": 1000,
    "external_l1_max": 1000,
    "external_s1_budget_forcing": 1000,
    "external_tale_prompt_budgeting": 1000
  },
  "method_counts_effective": {
    "direct_reserve_semantic_frontier_v2": 1000,
    "external_l1_max": 1000,
    "external_s1_budget_forcing": 1000,
    "external_tale_prompt_budgeting": 1000
  },
  "duplicate_keys": [],
  "failures_raw": 0,
  "failures_effective": 0
}

## Method/Selector Summary
          selector  accuracy  correct    n
oracle_best_action     0.968      968 1000
oracle_best_source     0.968      968 1000
                S1     0.947      947 1000
               C1d     0.947      947 1000
         always_S1     0.947      947 1000
          C1a_t005     0.947      947 1000
    beta_shrinkage     0.947      947 1000
           pooled4     0.944      944 1000
    agreement_only     0.893      893 1000
          frontier     0.821      821 1000
                L1     0.778      778 1000
              TALE     0.690      690 1000

## Subset Sizes
- routing_decisive_subset: 439
- all_sources_wrong_subset: 32
- selector_fixable_subset: 147

## Leakage Note
Auxiliary train1000 data remains separate from official test averages.

## Learned-router v2 readiness
Ready for offline lightweight training; no heavy training run launched in this pass.
