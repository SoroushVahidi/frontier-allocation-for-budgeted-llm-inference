# FIX01_CONSERVATIVE_GATE_20260524

## 1. Executive summary
Best FIX-01 variant: `fix01a_lcb00_ov00` with official pooled CV 0.7633, delta vs beta-shrinkage -0.0078, delta vs C1d -0.0078.

## 2. Data sources and caveats
Used completed scenarios only: Cohere×GSM8K (official), Mistral×GSM8K (official), Mistral×MATH-500 (official), Cohere×MATH-500 auxiliary (noncanonical). Active official Cohere MATH/Cerebras/train1000 runs excluded.

## 3. FIX-01 variants
Implemented families: FIX01a (LCB-gap), FIX01b (prob-of-dominance), FIX01c (near-peer safety), FIX01d (pattern-aware), FIX01e (minimal safe), FIX01f (two-stage conservative gate).

## 4. Evaluation protocol
Within-scenario 5-fold CV, official pooled stratified CV, official+aux pooled CV, LOSO, and full-artifact diagnostic (labeled non-test-valid).

## 5. Results by scenario
                        selector    n  correct  accuracy
                        C1a_t005 1388      846  0.609510
                             C1d 1388      843  0.607349
                fix01b_tau75_d00 1388      843  0.607349
                  beta_shrinkage 1388      841  0.605908
                fix01b_tau85_d00 1388      829  0.597262
                fix01b_tau90_d00 1388      827  0.595821
                fix01b_tau75_d02 1388      827  0.595821
best_individual_source_trainfold 1388      825  0.594380
                         pooled4 1388      820  0.590778
                fix01b_tau95_d00 1388      814  0.586455
                fix01b_tau85_d02 1388      814  0.586455
               fix01a_lcb02_ov05 1388      809  0.582853
               fix01a_lcb00_ov08 1388      809  0.582853
               fix01a_lcb00_ov03 1388      809  0.582853
                fix01b_tau90_d05 1388      809  0.582853
                fix01b_tau95_d05 1388      809  0.582853
               fix01a_lcb02_ov08 1388      809  0.582853
               fix01a_lcb02_ov00 1388      809  0.582853
               fix01a_lcb02_ov03 1388      809  0.582853
               fix01a_lcb00_ov05 1388      809  0.582853

## 6. Official macro results
         selector   n  correct  accuracy
         C1a_t005 900      694  0.771111
              C1d 900      694  0.771111
   beta_shrinkage 900      694  0.771111
fix01a_lcb00_ov05 900      687  0.763333
fix01a_lcb00_ov03 900      687  0.763333
fix01a_lcb00_ov00 900      687  0.763333
fix01a_lcb02_ov00 900      687  0.763333
fix01a_lcb02_ov08 900      687  0.763333
fix01a_lcb00_ov08 900      687  0.763333
fix01a_lcb02_ov03 900      687  0.763333
fix01a_lcb02_ov05 900      687  0.763333
 fix01b_tau75_d05 900      687  0.763333
 fix01b_tau90_d05 900      687  0.763333
 fix01b_tau95_d00 900      687  0.763333
 fix01b_tau95_d02 900      687  0.763333
 fix01b_tau90_d00 900      687  0.763333
 fix01b_tau90_d02 900      687  0.763333
 fix01b_tau85_d05 900      687  0.763333
 fix01b_tau85_d02 900      687  0.763333
 fix01b_tau75_d00 900      687  0.763333

## 7. LOSO transfer results
                          selector    n  correct  accuracy
                          C1a_t005 1388      846  0.609510
                               C1d 1388      843  0.607349
                    beta_shrinkage 1388      841  0.605908
                           pooled4 1388      820  0.590778
                    agreement_only 1388      809  0.582853
  best_individual_source_trainfold 1388      806  0.580692
                         always_S1 1388      806  0.580692
                                S1 1388      806  0.580692
                  fix01b_tau75_d00 1388      799  0.575648
                  fix01b_tau85_d00 1388      799  0.575648
                 fix01a_lcb05_ov03 1388      788  0.567723
fix01f_conservative_tau90_d03_ov05 1388      788  0.567723
                 fix01a_lcb05_ov00 1388      788  0.567723
              fix01d_pattern_aware 1388      788  0.567723
                   fix01c_spread10 1388      788  0.567723
                 fix01a_lcb05_ov05 1388      788  0.567723
fix01f_conservative_tau95_d02_ov05 1388      788  0.567723
                   fix01c_spread03 1388      788  0.567723
                   fix01c_spread05 1388      788  0.567723
                 fix01a_lcb05_ov08 1388      788  0.567723

## 8. Pairwise recovery/regression
                           variant          baseline   n  wins  losses  ties  net  variant_acc  baseline_acc     delta  mcnemar_stat_cc
                 fix01a_lcb00_ov00 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                 fix01a_lcb00_ov03 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                 fix01a_lcb00_ov05 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                 fix01a_lcb00_ov08 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                 fix01a_lcb02_ov00 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                 fix01a_lcb02_ov03 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                 fix01a_lcb02_ov05 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                 fix01a_lcb02_ov08 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                  fix01b_tau75_d00 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                  fix01b_tau75_d02 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                  fix01b_tau75_d05 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                  fix01b_tau85_d00 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                  fix01b_tau85_d02 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                  fix01b_tau85_d05 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                  fix01b_tau90_d00 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                  fix01b_tau90_d02 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                  fix01b_tau90_d05 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                  fix01b_tau95_d00 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                  fix01b_tau95_d02 beta_shrinkage_ok 900    13      20   867   -7     0.763333      0.771111 -0.007778         1.090909
                  fix01b_tau95_d05 beta_shrinkage_ok 900    14      44   842  -30     0.737778      0.771111 -0.033333        14.500000
                 fix01a_lcb03_ov00 beta_shrinkage_ok 900    14      55   831  -41     0.725556      0.771111 -0.045556        23.188406
                 fix01a_lcb03_ov03 beta_shrinkage_ok 900    14      55   831  -41     0.725556      0.771111 -0.045556        23.188406
                 fix01a_lcb03_ov05 beta_shrinkage_ok 900    14      55   831  -41     0.725556      0.771111 -0.045556        23.188406
                 fix01a_lcb03_ov08 beta_shrinkage_ok 900    14      55   831  -41     0.725556      0.771111 -0.045556        23.188406
                 fix01a_lcb05_ov00 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
                 fix01a_lcb05_ov03 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
                 fix01a_lcb05_ov05 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
                 fix01a_lcb05_ov08 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
                   fix01c_spread03 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
                   fix01c_spread05 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
                   fix01c_spread08 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
                   fix01c_spread10 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
              fix01d_pattern_aware beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
fix01f_conservative_tau90_d02_ov05 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
fix01f_conservative_tau90_d02_ov08 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
fix01f_conservative_tau90_d03_ov05 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
fix01f_conservative_tau90_d03_ov08 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
fix01f_conservative_tau95_d02_ov05 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
fix01f_conservative_tau95_d02_ov08 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
fix01f_conservative_tau95_d03_ov05 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
fix01f_conservative_tau95_d03_ov08 beta_shrinkage_ok 900    19      61   820  -42     0.724444      0.771111 -0.046667        21.012500
               fix01e_minimal_safe beta_shrinkage_ok 900    17      63   820  -46     0.720000      0.771111 -0.051111        25.312500
                 fix01a_lcb00_ov00            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                 fix01a_lcb00_ov03            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                 fix01a_lcb00_ov05            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                 fix01a_lcb00_ov08            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                 fix01a_lcb02_ov00            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                 fix01a_lcb02_ov03            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                 fix01a_lcb02_ov05            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                 fix01a_lcb02_ov08            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                  fix01b_tau75_d00            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                  fix01b_tau75_d02            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                  fix01b_tau75_d05            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                  fix01b_tau85_d00            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                  fix01b_tau85_d02            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                  fix01b_tau85_d05            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                  fix01b_tau90_d00            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                  fix01b_tau90_d02            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                  fix01b_tau90_d05            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077
                  fix01b_tau95_d00            c1d_ok 900    16      23   861   -7     0.763333      0.771111 -0.007778         0.923077

## 9. Failure/regression analysis
See `outputs/fix01_conservative_gate_20260524/fix01_best_variant_casebook.md` and companion CSVs.

## 10. Best variant decision
          variant  official_macro_cv  official_plus_auxiliary_macro_cv  worst_official_scenario_acc  loso_min_acc  delta_vs_beta_shrinkage  delta_vs_C1d  false_dominance_activations  missed_dominance_recoveries  complexity overfitting_risk recommendation
fix01a_lcb00_ov00           0.763333                          0.567723                     0.556667      0.272541                -0.007778     -0.007778                            0                            9      medium           medium         reject
fix01a_lcb00_ov03           0.763333                          0.567723                     0.556667      0.272541                -0.007778     -0.007778                            0                            9      medium           medium         reject
fix01a_lcb00_ov05           0.763333                          0.567723                     0.556667      0.272541                -0.007778     -0.007778                            0                            9      medium           medium         reject
fix01a_lcb00_ov08           0.763333                          0.567723                     0.556667      0.272541                -0.007778     -0.007778                            0                            9      medium           medium         reject
fix01a_lcb02_ov00           0.763333                          0.567723                     0.556667      0.272541                -0.007778     -0.007778                            0                            9      medium           medium         reject
fix01a_lcb02_ov03           0.763333                          0.567723                     0.556667      0.272541                -0.007778     -0.007778                            0                            9      medium           medium         reject
fix01a_lcb02_ov05           0.763333                          0.567723                     0.556667      0.272541                -0.007778     -0.007778                            0                            9      medium           medium         reject
fix01a_lcb02_ov08           0.763333                          0.567723                     0.556667      0.272541                -0.007778     -0.007778                            0                            9      medium           medium         reject
 fix01b_tau75_d00           0.763333                          0.590778                     0.556667      0.272541                -0.007778     -0.007778                            0                            9 medium-high      medium-high         reject
 fix01b_tau75_d02           0.763333                          0.580692                     0.556667      0.272541                -0.007778     -0.007778                            0                            9 medium-high      medium-high         reject
 fix01b_tau75_d05           0.763333                          0.567723                     0.556667      0.272541                -0.007778     -0.007778                            0                            9 medium-high      medium-high         reject
 fix01b_tau85_d00           0.763333                          0.590778                     0.556667      0.272541                -0.007778     -0.007778                            0                            9 medium-high      medium-high         reject
 fix01b_tau85_d02           0.763333                          0.574207                     0.556667      0.272541                -0.007778     -0.007778                            0                            9 medium-high      medium-high         reject
 fix01b_tau85_d05           0.763333                          0.567723                     0.556667      0.272541                -0.007778     -0.007778                            0                            9 medium-high      medium-high         reject
 fix01b_tau90_d00           0.763333                          0.590778                     0.556667      0.272541                -0.007778     -0.007778                            0                            9 medium-high      medium-high         reject
 fix01b_tau90_d02           0.763333                          0.570605                     0.556667      0.272541                -0.007778     -0.007778                            0                            9 medium-high      medium-high         reject
 fix01b_tau90_d05           0.763333                          0.567723                     0.556667      0.272541                -0.007778     -0.007778                            0                            9 medium-high      medium-high         reject
 fix01b_tau95_d00           0.763333                          0.580692                     0.556667      0.272541                -0.007778     -0.007778                            0                            9 medium-high      medium-high         reject
 fix01b_tau95_d02           0.763333                          0.567723                     0.556667      0.272541                -0.007778     -0.007778                            0                            9 medium-high      medium-high         reject
 fix01b_tau95_d05           0.737778                          0.567723                     0.526667      0.272541                -0.033333     -0.033333                            0                           28 medium-high      medium-high         reject

## 11. Manuscript implication
Treat FIX-01 as selector-improvement evidence; avoid final promotion claim until official Cohere MATH and Cerebras scenarios complete.

## 12. Next iteration recommendation
Prioritize top FIX-01 variant refinement and FIX-03 near-peer S1 gate, then re-evaluate after active scenario completions.

## 13. Safety confirmation
Offline only; no API calls launched; no active-job interaction; no commit/push.
