# FIX03_S1_NEAR_PEER_GATE_20260524

## 1. Executive summary
Best FIX-03 variant: `fix03a_spread03` with official pooled CV 0.7711; delta vs beta-shrinkage +0.0000; delta vs C1d +0.0000.

## 2. Data sources and caveats
Used completed offline artifacts only: Cohere GSM8K official, Mistral GSM8K official, Mistral MATH-500 official, Cohere MATH-500 auxiliary. Active Cohere official MATH-500 scenario4, Mistral train1000, Cerebras, and overnight supervisor artifacts were observed only and excluded.

## 3. FIX-03 variants
Implemented FIX03a-f families: near-peer S1 block, isolation gate, support-required gate, provider-free gate, overtrust-repair-only gate, and C1d-hybrid gate.

## 4. Evaluation protocol
Within-scenario 5-fold CV, official pooled stratified CV, official+aux pooled stratified CV, LOSO transfer, and full-artifact diagnostic (descriptive only).

## 5. Results by scenario
                        selector    n  correct  accuracy
              oracle_best_action 1388      985  0.709654
              oracle_best_source 1388      985  0.709654
                        C1a_t005 1388      846  0.609510
                 fix03b_c1d_np05 1388      843  0.607349
                             C1d 1388      843  0.607349
   fix03f_c1d_hybrid_np05_conf03 1388      839  0.604467
   fix03f_c1d_hybrid_np05_conf05 1388      839  0.604467
                 fix03b_c1d_np08 1388      838  0.603746
                 fix03b_c1d_np10 1388      837  0.603026
                  beta_shrinkage 1388      830  0.597983
                     fix03c_np05 1388      830  0.597983
               fix03a_s1margin05 1388      830  0.597983
    fix03e_overtrust_repair_np05 1388      830  0.597983
        fix03d_providerfree_np05 1388      830  0.597983
                fix03b_beta_np05 1388      830  0.597983
                 fix03a_spread05 1388      830  0.597983
                 fix03a_spread03 1388      830  0.597983
               fix03a_s1margin03 1388      830  0.597983
                     fix03c_np08 1388      829  0.597262
                     fix03c_np10 1388      827  0.595821
    fix03e_overtrust_repair_np08 1388      825  0.594380
   fix03f_c1d_hybrid_np08_conf03 1388      825  0.594380
                fix03b_beta_np08 1388      825  0.594380
   fix03f_c1d_hybrid_np08_conf05 1388      825  0.594380
best_individual_source_trainfold 1388      825  0.594380

## 6. Official macro results
                     selector   n  correct  accuracy
           oracle_best_action 900      765  0.850000
           oracle_best_source 900      765  0.850000
               beta_shrinkage 900      694  0.771111
            fix03a_s1margin08 900      694  0.771111
              fix03a_spread08 900      694  0.771111
              fix03a_spread05 900      694  0.771111
            fix03a_s1margin05 900      694  0.771111
            fix03a_s1margin03 900      694  0.771111
                     C1a_t005 900      694  0.771111
                          C1d 900      694  0.771111
fix03f_c1d_hybrid_np08_conf03 900      694  0.771111
fix03f_c1d_hybrid_np08_conf05 900      694  0.771111
 fix03e_overtrust_repair_np05 900      694  0.771111
 fix03e_overtrust_repair_np08 900      694  0.771111
fix03f_c1d_hybrid_np05_conf05 900      694  0.771111
fix03f_c1d_hybrid_np05_conf03 900      694  0.771111
             fix03b_beta_np05 900      694  0.771111
              fix03a_spread03 900      694  0.771111
                  fix03c_np08 900      694  0.771111
              fix03b_c1d_np05 900      694  0.771111
              fix03b_c1d_np08 900      694  0.771111
                  fix03c_np05 900      694  0.771111
     fix03d_providerfree_np08 900      694  0.771111
     fix03d_providerfree_np05 900      694  0.771111
             fix03b_beta_np08 900      694  0.771111

## 7. LOSO transfer results
                        selector    n  correct  accuracy
              oracle_best_action 1388      985  0.709654
              oracle_best_source 1388      985  0.709654
                        C1a_t005 1388      846  0.609510
                             C1d 1388      843  0.607349
                 fix03b_c1d_np10 1388      832  0.599424
                 fix03b_c1d_np05 1388      832  0.599424
                 fix03b_c1d_np08 1388      832  0.599424
                  beta_shrinkage 1388      830  0.597983
                     fix03c_np08 1388      821  0.591499
                     fix03c_np10 1388      821  0.591499
                     fix03c_np05 1388      821  0.591499
    fix03e_overtrust_repair_np05 1388      819  0.590058
    fix03e_overtrust_repair_np10 1388      819  0.590058
        fix03d_providerfree_np10 1388      819  0.590058
        fix03d_providerfree_np08 1388      819  0.590058
        fix03d_providerfree_np05 1388      819  0.590058
                fix03b_beta_np05 1388      819  0.590058
    fix03e_overtrust_repair_np08 1388      819  0.590058
                fix03b_beta_np10 1388      819  0.590058
                fix03b_beta_np08 1388      819  0.590058
                  agreement_only 1388      811  0.584294
                       always_S1 1388      806  0.580692
                              S1 1388      806  0.580692
best_individual_source_trainfold 1388      806  0.580692
   fix03f_c1d_hybrid_np08_conf05 1388      803  0.578530

## 8. S1 overtrust/undertrust analysis
                      variant  S1_overtrust_recoveries  S1_undertrust_regressions  near_peer_regressions  mistral_dominant_regressions
              fix03a_spread03                        0                          0                      0                             0
              fix03a_spread05                        0                          0                      0                             0
              fix03a_spread08                        0                          0                      0                             0
            fix03a_s1margin03                        0                          0                      0                             0
            fix03a_s1margin05                        0                          0                      0                             0
            fix03a_s1margin08                        0                          0                      0                             0
             fix03b_beta_np05                        0                          0                      0                             0
             fix03b_beta_np08                        0                          0                      0                             0
                  fix03c_np05                        0                          0                      0                             0
                  fix03c_np08                        0                          0                      0                             0
     fix03d_providerfree_np05                        0                          0                      0                             0
     fix03d_providerfree_np08                        0                          0                      0                             0
 fix03e_overtrust_repair_np05                        0                          0                      0                             0
 fix03e_overtrust_repair_np08                        0                          0                      0                             0
              fix03b_c1d_np05                        0                          6                      0                             0
              fix03b_c1d_np08                        0                          6                      0                             0
fix03f_c1d_hybrid_np05_conf03                        0                          6                      0                             0
fix03f_c1d_hybrid_np05_conf05                        0                          6                      0                             0
fix03f_c1d_hybrid_np08_conf03                        0                          6                      0                             0
fix03f_c1d_hybrid_np08_conf05                        0                          6                      0                             0
                  fix03c_np10                        4                          5                      5                             5
             fix03b_beta_np10                       12                         22                     22                            22
     fix03d_providerfree_np10                       12                         22                     22                            22
 fix03e_overtrust_repair_np10                       12                         22                     22                            22
              fix03b_c1d_np10                       13                         28                     35                            22

## 9. Failure/regression casebook
See `outputs/fix03_s1_near_peer_gate_20260524/fix03_best_variant_casebook.md` and companion CSV files.

## 10. Best variant decision
                      variant  official_macro_cv  official_plus_auxiliary_macro_cv  worst_official_scenario_acc  loso_min_acc  delta_vs_beta_shrinkage  delta_vs_C1d  S1_overtrust_recoveries  S1_undertrust_regressions  near_peer_regressions  mistral_dominant_regressions near_peer_safety mistral_preservation complexity overfitting_risk                      recommendation
              fix03a_spread03           0.771111                          0.588617                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good     medium       low-medium                     keep diagnostic
              fix03a_spread05           0.771111                          0.578530                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good     medium       low-medium                     keep diagnostic
              fix03a_spread08           0.771111                          0.567723                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good     medium       low-medium                     keep diagnostic
            fix03a_s1margin03           0.771111                          0.588617                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good     medium       low-medium                     keep diagnostic
            fix03a_s1margin05           0.771111                          0.578530                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good     medium       low-medium                     keep diagnostic
            fix03a_s1margin08           0.771111                          0.567723                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good     medium       low-medium                     keep diagnostic
             fix03b_beta_np05           0.771111                          0.592219                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good     medium       low-medium                     keep diagnostic
             fix03b_beta_np08           0.771111                          0.590058                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good     medium       low-medium                     keep diagnostic
                  fix03c_np05           0.771111                          0.594380                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good     medium       low-medium                     keep diagnostic
                  fix03c_np08           0.771111                          0.595821                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good     medium       low-medium                     keep diagnostic
     fix03d_providerfree_np05           0.771111                          0.592219                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good        low              low                     keep diagnostic
     fix03d_providerfree_np08           0.771111                          0.590058                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good        low              low                     keep diagnostic
 fix03e_overtrust_repair_np05           0.771111                          0.592219                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good        low              low                     keep diagnostic
 fix03e_overtrust_repair_np08           0.771111                          0.590058                     0.563333      0.278689                 0.000000      0.000000                        0                          0                      0                             0             good                 good        low              low                     keep diagnostic
              fix03b_c1d_np05           0.771111                          0.601585                     0.563333      0.305328                 0.000000      0.000000                        0                          6                      0                             0             good                 good     medium       low-medium                     keep diagnostic
              fix03b_c1d_np08           0.771111                          0.599424                     0.563333      0.305328                 0.000000      0.000000                        0                          6                      0                             0             good                 good     medium       low-medium                     keep diagnostic
fix03f_c1d_hybrid_np05_conf03           0.771111                          0.585735                     0.563333      0.305328                 0.000000      0.000000                        0                          6                      0                             0             good                 good     medium           medium                     keep diagnostic
fix03f_c1d_hybrid_np05_conf05           0.771111                          0.585735                     0.563333      0.305328                 0.000000      0.000000                        0                          6                      0                             0             good                 good     medium           medium                     keep diagnostic
fix03f_c1d_hybrid_np08_conf03           0.771111                          0.574207                     0.563333      0.305328                 0.000000      0.000000                        0                          6                      0                             0             good                 good     medium           medium                     keep diagnostic
fix03f_c1d_hybrid_np08_conf05           0.771111                          0.574207                     0.563333      0.305328                 0.000000      0.000000                        0                          6                      0                             0             good                 good     medium           medium                     keep diagnostic
                  fix03c_np10           0.770000                          0.595821                     0.560000      0.278689                -0.001111     -0.001111                        4                          5                      5                             5             risk                 risk     medium       low-medium wait for Cohere official Scenario 4
             fix03b_beta_np10           0.760000                          0.590058                     0.553333      0.278689                -0.011111     -0.011111                       12                         22                     22                            22             risk                 risk     medium       low-medium                              reject
     fix03d_providerfree_np10           0.760000                          0.590058                     0.553333      0.278689                -0.011111     -0.011111                       12                         22                     22                            22             risk                 risk        low              low                              reject
 fix03e_overtrust_repair_np10           0.760000                          0.590058                     0.553333      0.278689                -0.011111     -0.011111                       12                         22                     22                            22             risk                 risk        low              low                              reject
              fix03b_c1d_np10           0.760000                          0.599424                     0.553333      0.305328                -0.011111     -0.011111                       13                         28                     35                            22             risk                 risk     medium       low-medium                              reject

## 11. Manuscript implication
Treat FIX-03 as selector-level offline evidence; do not promote as final runtime policy unless superiority over beta-shrinkage and C1d is clear and stable on official data.

## 12. Next iteration recommendation
Prioritize residual near-peer disagreement clusters and reassess after official Cohere MATH-500 and train1000 completions.

## 13. Safety confirmation
Offline only. No API calls launched. No active job interference. No commit/push.
