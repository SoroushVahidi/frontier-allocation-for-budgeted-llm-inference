# COHERE_MATH500_OFFICIAL_SCENARIO4_PROCESSING_20260524

## Integrity
{
  "raw_rows": 1218,
  "effective_rows": 1200,
  "duplicate_overage": 18,
  "method_counts_raw": {
    "direct_reserve_semantic_frontier_v2": 309,
    "external_s1_budget_forcing": 305,
    "external_tale_prompt_budgeting": 303,
    "external_l1_max": 301
  },
  "method_counts_effective": {
    "direct_reserve_semantic_frontier_v2": 300,
    "external_l1_max": 300,
    "external_s1_budget_forcing": 300,
    "external_tale_prompt_budgeting": 300
  },
  "duplicate_keys": [
    "HuggingFaceH4_MATH-500_132||external_s1_budget_forcing||2",
    "HuggingFaceH4_MATH-500_155||direct_reserve_semantic_frontier_v2||2",
    "HuggingFaceH4_MATH-500_155||external_l1_max||2",
    "HuggingFaceH4_MATH-500_220||direct_reserve_semantic_frontier_v2||3",
    "HuggingFaceH4_MATH-500_220||external_s1_budget_forcing||3",
    "HuggingFaceH4_MATH-500_220||external_tale_prompt_budgeting||3",
    "HuggingFaceH4_MATH-500_243||direct_reserve_semantic_frontier_v2||3",
    "HuggingFaceH4_MATH-500_243||external_tale_prompt_budgeting||2",
    "HuggingFaceH4_MATH-500_29||direct_reserve_semantic_frontier_v2||3",
    "HuggingFaceH4_MATH-500_29||external_s1_budget_forcing||3",
    "HuggingFaceH4_MATH-500_95||direct_reserve_semantic_frontier_v2||3"
  ],
  "failures_raw": 24,
  "failures_effective": 6
}

## Selector Replay (diagnostic full-artifact)
          selector  accuracy  correct   n
oracle_best_action  0.450000      135 300
oracle_best_source  0.450000      135 300
    agreement_only  0.330000       99 300
           pooled4  0.293333       88 300
               C1d  0.293333       88 300
    beta_shrinkage  0.293333       88 300
          C1a_t005  0.293333       88 300
          frontier  0.290000       87 300
                S1  0.280000       84 300
         always_S1  0.280000       84 300
              TALE  0.253333       76 300
                L1  0.243333       73 300

## Failure Taxonomy
           category  count
  all_sources_wrong    165
  all_sources_agree     44
        no_majority    189
        s1_isolated    146
chosen_wrong_c1d_ok    212

## Comparison vs Cohere Aux / Mistral S5
             comparison_set           selector  accuracy
mistral_math500_official_s5           frontier  0.400000
mistral_math500_official_s5                 L1  0.456667
mistral_math500_official_s5                 S1  0.563333
mistral_math500_official_s5               TALE  0.480000
mistral_math500_official_s5            pooled4  0.550000
mistral_math500_official_s5     beta_shrinkage  0.563333
mistral_math500_official_s5     agreement_only  0.536667
mistral_math500_official_s5          always_S1  0.563333
mistral_math500_official_s5 oracle_best_source  0.676667

## Notes
C1d/C1a_t005 here are diagnostic full-artifact replays (train=test), not fold-safe test-valid metrics.
