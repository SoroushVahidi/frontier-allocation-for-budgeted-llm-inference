# FAILURE_PATTERN_WORKBENCH_OFFICIAL4_20260524

Generated: 2026-05-24T19:49:47.107177+00:00

## 1. Scope
Official-only failure workbench over four official scenarios (Cohere GSM8K, Mistral GSM8K, Cohere MATH-500, Mistral MATH-500).

## 2. Selector matrix (official4)
          selector  cohere_gsm8k  cohere_math500  mistral_gsm8k  mistral_math500  official_macro_mean
oracle_best_action      0.933333        0.450000       0.940000         0.676667             0.750000
          C1a_t005      0.836667        0.293333       0.913333         0.563333             0.651667
               C1d      0.836667        0.293333       0.913333         0.563333             0.651667
    beta_shrinkage      0.836667        0.293333       0.913333         0.563333             0.651667
           pooled4      0.836667        0.293333       0.910000         0.556667             0.649167
                S1      0.800000        0.280000       0.913333         0.563333             0.639167
    agreement_only      0.823333        0.330000       0.846667         0.536667             0.634167
          frontier      0.790000        0.290000       0.786667         0.400000             0.566667
                L1      0.796667        0.243333       0.726667         0.456667             0.555833
              TALE      0.806667        0.253333       0.670000         0.480000             0.552500

## 3. Key cluster summary
                                 cluster_id                            cluster_label                                                       definition  n_cases                                                                       count_by_scenario                                likely_failure_mechanism                                  possible_fix                   expected_benefit regression_risk  zero_extra_call_fix_possible  needs_generation_or_budget
                       O1_all_sources_wrong                        all_sources_wrong                  all four sources wrong (selector-irrecoverable)      300 {"cohere_gsm8k": 20, "cohere_math500": 165, "mistral_gsm8k": 18, "mistral_math500": 97}                                      generation ceiling    budget escalation / generation improvement                 selector-only none             n/a                         False                        True
             O4_beta_c1d_wrong_oracle_right              beta_c1d_wrong_oracle_right           beta and C1d both wrong while oracle action is correct      118   {"cohere_gsm8k": 29, "cohere_math500": 47, "mistral_gsm8k": 8, "mistral_math500": 34}       action-choice error with available correct source  pattern-specific action table (RG-EB-Action)     high selector-recoverable mass          medium                          True                       False
                    O5_fix03_revisit_signal                     fix03_revisit_signal     S1 correct but beta wrong in no-majority / near-peer regions       35                                              {"cohere_gsm8k": 12, "cohere_math500": 23}           possible S1 under-use on hard near-peer cases     revisit FIX-03 with official4 constraints                targeted recoveries      low-medium                          True                       False
       O2_cohere_math_agreement_win_vs_beta        cohere_math_agreement_win_vs_beta official Cohere MATH where agreement_only correct and beta wrong       20                                                                  {"cohere_math500": 20} external 2-of-3 majority overrides beta/pooled fallback agreement-only gate in near-peer hard regimes recover beta misses on Cohere MATH          medium                          True                       False
O3_cohere_math_agreement_regression_vs_beta cohere_math_agreement_regression_vs_beta official Cohere MATH where agreement_only wrong and beta correct        9                                                                   {"cohere_math500": 9}         wrong external-majority or majority-noise defer        agreement gate + confidence skepticism                  bound regressions          medium                          True                       False

## 4. Candidate fixes
fix_id                        candidate                                                   motivation  expected_recoveries_signal  regression_risk_signal                                                  required_features  zero_extra_call                                evaluation_protocol           implement_now
 AG-01              agreement_only_gate official Cohere MATH shows agreement_only > pooled4/beta/C1d                          20                       9 external_2of3_agreement, no_majority_flag, provider/dataset regime             True         paired official4 replay + regression audit              test-first
 AG-02 hard_near_peer_fallback_selector            near-peer slices where pooled fallback is brittle                          36                      54              near-peer regime flags, external majority reliability             True                 subset-specific replay by scenario       after AG-01 audit
 AG-03    pattern_specific_action_table    oracle gap remains large when beta and C1d are both wrong                         118                       0                       pattern bucket + source reliability features             True cross-scenario CV on official4 + auxiliary holdout design now, train later

## 5. Safety
- offline only
- no API calls
- no active job interference
- no commit/push