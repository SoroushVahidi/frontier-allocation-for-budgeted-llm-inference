# AG01_AGREEMENT_ONLY_GATE_20260524

## 1. Executive summary
Implemented 57 AG-01 variants with fold-safe calibration and evaluated across official four scenarios.

## 2. Data sources and caveats
- Official4 case table only for headline metrics.
- Auxiliary/train1000 used only for context (not in official averages).
- Offline replay only; no API calls.

## 3. AG-01 variant definitions
See `scripts/evaluate_ag01_agreement_only_gate.py` and `ag01_rule_dependencies.md`.

## 4. Evaluation protocol
within-scenario CV, pooled CV, LOSO, provider-heldout, dataset-heldout, full diagnostic.

## 5. Official four-scenario results
                      variant   family  n_folds  accuracy_mean  accuracy_std  official_macro_mean  worst_scenario_mean  oracle_regret_mean  delta_vs_beta_shrinkage  delta_vs_C1d  delta_vs_agreement_only
           oracle_best_action baseline        5       0.750000      0.020069             0.750000             0.450000            0.000000                 0.110833      0.110833                 0.115833
ag01f_cohere_math_lookup_diag     ag01        5       0.651667      0.016997             0.651667             0.330000            0.098333                 0.012500      0.012500                 0.017500
                      pooled4 baseline        5       0.648333      0.018559             0.648333             0.303333            0.101667                 0.009167      0.009167                 0.014167
                          C1d baseline        5       0.639167      0.024095             0.639167             0.280000            0.110833                 0.000000      0.000000                 0.005000
                     C1a_t005 baseline        5       0.639167      0.024095             0.639167             0.280000            0.110833                 0.000000      0.000000                 0.005000
            ag01e_mean_s5_b22     ag01        5       0.639167      0.024095             0.639167             0.280000            0.110833                 0.000000      0.000000                 0.005000
            ag01e_mean_s5_b11     ag01        5       0.639167      0.024095             0.639167             0.280000            0.110833                 0.000000      0.000000                 0.005000
                           S1 baseline        5       0.639167      0.024095             0.639167             0.280000            0.110833                 0.000000      0.000000                 0.005000
           ag01a_entropy_hard     ag01        5       0.639167      0.024095             0.639167             0.280000            0.110833                 0.000000      0.000000                 0.005000
      ag01a_providerfree_hard     ag01        5       0.639167      0.024095             0.639167             0.280000            0.110833                 0.000000      0.000000                 0.005000
                   ag01a_np03     ag01        5       0.639167      0.024095             0.639167             0.280000            0.110833                 0.000000      0.000000                 0.005000
                   ag01a_np05     ag01        5       0.639167      0.024095             0.639167             0.280000            0.110833                 0.000000      0.000000                 0.005000
           ag01b_beta_d00_s10     ag01        5       0.639167      0.024095             0.639167             0.280000            0.110833                 0.000000      0.000000                 0.005000
            ag01b_beta_d03_s5     ag01        5       0.639167      0.024095             0.639167             0.280000            0.110833                 0.000000      0.000000                 0.005000
           ag01b_beta_d05_s10     ag01        5       0.639167      0.024095             0.639167             0.280000            0.110833                 0.000000      0.000000                 0.005000

## 6. Official Cohere MATH detailed results
                      variant   n  accuracy
ag01f_cohere_math_lookup_diag 300      0.33
               agreement_only 300      0.33
            ag01e_mean_s5_b22 300      0.28
            ag01e_mean_s5_b11 300      0.28
               beta_shrinkage 300      0.28
                          C1d 300      0.28

## 7. Transfer/held-out results
See `ag01_leave_one_scenario_out_summary.csv`, `ag01_provider_heldout_summary.csv`, `ag01_dataset_heldout_summary.csv`.

## 8. Recovery/regression analysis
Best variant: ag01f_cohere_math_lookup_diag
- recoveries vs beta on Cohere MATH: 29
- regressions vs beta on Cohere MATH: 14

## 9. Best variant decision
Selected by official pooled CV: ag01f_cohere_math_lookup_diag

## 10. Router-v2 implications
agreement_only should be an action candidate; prefer routing integration over hard replacement.

## 11. Manuscript implications
AG-01 supports candidate-level improvement framing; no unconditional promotion claim.

## 12. Next iteration recommendation
Implement conservative AG-01 guard + full pattern-action router query.

## 13. Safety confirmation
- offline only
- no API calls
- no active-job interference
- no commit/push