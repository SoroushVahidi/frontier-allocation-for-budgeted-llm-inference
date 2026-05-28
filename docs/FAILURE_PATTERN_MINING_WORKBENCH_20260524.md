# FAILURE_PATTERN_MINING_WORKBENCH_20260524

Generated: 2026-05-24T16:27:34Z

## 1. Executive summary
Built an offline failure-pattern workbench over 1388 completed cases across four scenarios. The workbench outputs actionable failure clusters, mechanism diagnoses, candidate fixes, and a repeatable implementation loop.

## 2. Data sources and caveats
Included completed sources only (official + auxiliary): Cohere GSM8K canonical, Mistral GSM8K full300 replay, Mistral MATH-500 Scenario 5, Cohere MATH-500 auxiliary, C1 pooled voting analysis, and cross-scenario investigation.

## 3. Current algorithm failure overview
| algorithm | n_cases | n_wrong | wrong_rate | n_wrong_oracle_correct | n_wrong_best_source_correct | n_regressions_vs_pooled4 | n_recoveries_vs_pooled4 | n_regressions_vs_beta_shrinkage | n_recoveries_vs_beta_shrinkage | n_wrong_when_S1_correct | n_wrong_when_pooled4_correct | n_wrong_not_all_sources_wrong | n_all_sources_wrong |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agreement_only | 1388 | 826 | 0.595101 | 143 | 423 | 18 | 11 | 44 | 16 | 304 | 18 | 423 | 403 |
| always_S1 | 1388 | 822 | 0.592219 | 139 | 419 | 59 | 56 | 44 | 20 | 240 | 59 | 419 | 403 |
| pooled4 | 1388 | 819 | 0.590058 | 136 | 416 | 0 | 0 | 36 | 15 | 296 | 0 | 416 | 403 |
| beta_shrinkage | 1388 | 798 | 0.574928 | 115 | 395 | 15 | 36 | 0 | 0 | 260 | 15 | 395 | 403 |
| C1d | 1388 | 545 | 0.392651 | 113 | 142 | 47 | 321 | 32 | 285 | 53 | 47 | 142 | 403 |
| learned_router | 1388 | 545 | 0.392651 | 121 | 142 | 29 | 303 | 29 | 282 | 42 | 29 | 142 | 403 |
| C1a_t005 | 1388 | 542 | 0.39049 | 110 | 139 | 39 | 316 | 24 | 280 | 45 | 39 | 139 | 403 |

## 4. Ranked failure patterns
| provider | dataset | official_or_auxiliary | answer_pattern_bucket | majority_size | best_source_identity | only_source_correct_identity | S1_isolated | frontier_in_majority | external_majority_excludes_S1 | L1_TALE_agree | no_majority_flag | all_sources_wrong | q_numeric_complexity_bucket | decision_final_answer_cleanliness | decision_parse_success | n_cases | oracle_correct_count | oracle_correct_rate | current_algorithm_wrong_count | current_algorithm_wrong_rate | best_available_source | source_correct_most_often | pooled4_accuracy | beta_shrinkage_accuracy | C1d_accuracy | learned_router_accuracy | recovery_opportunity_count | regression_risk_count | scenario_concentration_top_share | scenario_count | pattern_scope | rank_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cohere | math500 | auxiliary | all_different | 1 | L1 | L1 | 1 | 0 | 0 | 0 | 1 | 0 | medium | clean_numeric | 1 | 7 | 7 | 1 | 7 | 1 | L1 | L1 | 0 | 0 | 1 | 0.285714 | 7 | 0 | 1 | 1 | auxiliary-only | 14 |
| cohere | math500 | auxiliary | no_majority | 2 | L1 | L1 | 0 | 0 | 0 | 0 | 1 | 0 | medium | clean_numeric | 1 | 5 | 5 | 1 | 5 | 1 | L1 | L1 | 0 | 0 | 1 | 0 | 5 | 0 | 1 | 1 | auxiliary-only | 10 |
| cohere | math500 | auxiliary | no_majority | 2 | L1 | L1 | 1 | 0 | 0 | 0 | 1 | 0 | medium | clean_numeric | 1 | 4 | 4 | 1 | 4 | 1 | L1 | L1 | 0 | 0 | 1 | 0.5 | 4 | 0 | 1 | 1 | auxiliary-only | 8 |
| cohere | gsm8k | official | all_agree | 4 | TALE | none | 0 | 1 | 0 | 1 | 0 | 0 | low | clean_numeric | 1 | 101 | 0 | 0 | 101 | 1 | frontier | frontier | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 1 | official-only | 0 |
| cohere | gsm8k | official | all_agree | 4 | TALE | none | 0 | 1 | 0 | 1 | 0 | 0 | medium | clean_numeric | 1 | 52 | 0 | 0 | 52 | 1 | frontier | frontier | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 1 | official-only | 0 |
| cohere | math500 | auxiliary | all_different | 1 | none | none | 1 | 0 | 0 | 0 | 1 | 1 | high | clean_numeric | 1 | 41 | 0 | 0 | 41 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | auxiliary-only | 0 |
| cohere | gsm8k | official | all_agree | 4 | TALE | none | 0 | 1 | 0 | 1 | 0 | 0 | very_low | clean_numeric | 1 | 31 | 0 | 0 | 31 | 1 | frontier | frontier | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 1 | official-only | 0 |
| cohere | math500 | auxiliary | all_different | 1 | none | none | 1 | 0 | 0 | 0 | 1 | 1 | medium | clean_numeric | 1 | 25 | 0 | 0 | 25 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | auxiliary-only | 0 |
| cohere | math500 | auxiliary | no_majority | 2 | none | none | 0 | 0 | 0 | 0 | 1 | 1 | high | clean_numeric | 1 | 18 | 0 | 0 | 18 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | auxiliary-only | 0 |
| cohere | math500 | auxiliary | no_majority | 2 | none | none | 0 | 0 | 0 | 0 | 1 | 1 | medium | clean_numeric | 1 | 18 | 0 | 0 | 18 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | auxiliary-only | 0 |
| cohere | math500 | auxiliary | all_different | 1 | none | none | 1 | 0 | 0 | 0 | 1 | 1 | low | clean_numeric | 1 | 17 | 0 | 0 | 17 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | auxiliary-only | 0 |
| mistral | math500 | official | all_different | 1 | none | none | 1 | 0 | 0 | 0 | 1 | 1 | high | clean_numeric | 1 | 14 | 0 | 0 | 14 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | official-only | 0 |
| cohere | math500 | auxiliary | no_majority | 2 | none | none | 0 | 0 | 0 | 0 | 1 | 1 | low | clean_numeric | 1 | 10 | 0 | 0 | 10 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | auxiliary-only | 0 |
| cohere | math500 | auxiliary | no_majority | 2 | none | none | 1 | 0 | 0 | 0 | 1 | 1 | high | clean_numeric | 1 | 10 | 0 | 0 | 10 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | auxiliary-only | 0 |
| cohere | math500 | auxiliary | no_majority | 2 | none | none | 1 | 0 | 0 | 0 | 1 | 1 | medium | clean_numeric | 1 | 10 | 0 | 0 | 10 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | auxiliary-only | 0 |
| mistral | math500 | official | all_agree | 4 | none | none | 0 | 1 | 0 | 1 | 0 | 1 | medium | clean_numeric | 1 | 9 | 0 | 0 | 9 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | official-only | 0 |
| cohere | math500 | auxiliary | 3-1_split | 3 | none | none | 1 | 1 | 1 | 1 | 0 | 1 | high | clean_numeric | 1 | 8 | 0 | 0 | 8 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | auxiliary-only | 0 |
| cohere | math500 | auxiliary | all_agree | 4 | none | none | 0 | 1 | 0 | 1 | 0 | 1 | low | clean_numeric | 1 | 8 | 0 | 0 | 8 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | auxiliary-only | 0 |
| mistral | math500 | official | all_different | 1 | none | none | 1 | 0 | 0 | 0 | 1 | 1 | medium | clean_numeric | 1 | 8 | 0 | 0 | 8 | 1 | frontier | frontier | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | official-only | 0 |
| cohere | gsm8k | official | 3-1_split | 3 | TALE | none | 0 | 1 | 0 | 0 | 0 | 0 | low | clean_numeric | 1 | 7 | 0 | 0 | 7 | 1 | frontier | frontier | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 1 | official-only | 0 |

## 5. Detailed failure clusters
| cluster_id | cluster_label | definition | n_cases | count_by_scenario | likely_failure_mechanism | possible_fix | expected_benefit | regression_risk | zero_extra_call_fix_possible | needs_generation_or_budget |
|---|---|---|---|---|---|---|---|---|---|---|
| I_MATH_all_sources_wrong | MATH_all_sources_wrong | all sources wrong; selector cannot recover | 403 | {"cohere_math500_aux": 268, "mistral_math500": 97, "cohere_gsm8k": 20, "mistral_gsm8k": 18} | generation ceiling / insufficient reasoning budget | hardness detector + budget escalation | requires generation/budget changes, not selector tweaks | n/a (selector-irrecovable) | False | True |
| F_S1_overtrusted | S1_overtrusted | S1 selected and wrong while pooled4/L1/frontier could be correct | 313 | {"cohere_gsm8k": 237, "cohere_math500_aux": 52, "mistral_math500": 20, "mistral_gsm8k": 4} | S1 trust transferred into near-peer regimes | S1-trust gate conditioned on reliability spread | reduce S1-overtrust regressions | low | True | False |
| G_S1_undertrusted | S1_undertrusted | S1 correct but selector chooses another wrong answer | 296 | {"cohere_gsm8k": 240, "cohere_math500_aux": 20, "mistral_gsm8k": 19, "mistral_math500": 17} | majority or fallback overrules dominant S1 | dominant-source inclusion majority (C1d) | recover S1 isolated wins | low | True | False |
| E_frontier_fallback_wrong | frontier_fallback_wrong | frontier fallback selected and wrong while some external source was correct | 162 | {"cohere_math500_aux": 65, "cohere_gsm8k": 43, "mistral_math500": 31, "mistral_gsm8k": 23} | provider/dataset mismatch in fallback default | provider/dataset-calibrated fallback hierarchy | recover fallback errors in non-frontier-dominant slices | medium | True | False |
| J_agreement_fragility | agreement_fragility | agreement-only fails under no-majority or wrong-majority conditions | 143 | {"cohere_math500_aux": 73, "mistral_math500": 42, "mistral_gsm8k": 28} | agreement logic lacks robust fallback | agreement + calibrated C1d fallback | recover brittle agreement failures | low-medium | True | False |
| K_weighted_vote_amplifies_bad_sources | weighted_vote_amplifies_bad_sources | weighted/log-odds voting regresses versus simple pooling | 121 | {"cohere_math500_aux": 87, "mistral_math500": 33, "mistral_gsm8k": 1} | small reliability gaps amplified too strongly | shrinked/clipped weights; avoid raw log-odds in near-peer | remove avoidable weighted-vote regressions | low | True | False |
| C_no_majority_bad_fallback | no_majority_bad_fallback | no majority, fallback answer wrong while another source was correct | 115 | {"cohere_math500_aux": 63, "mistral_math500": 29, "mistral_gsm8k": 23} | fallback defaults to frontier without local evidence | calibrated no-majority fallback to dominant/best source | recover no-majority misses | low-medium | True | False |
| H_L1_or_frontier_best_on_Cohere_MATH | L1_or_frontier_best_on_Cohere_MATH | Cohere MATH slice where L1/frontier outperforms S1/TALE | 84 | {"cohere_math500_aux": 84} | provider-specific mismatch for budget-forcing prompts | provider/dataset calibration hierarchy | prevent S1 bias in Cohere-MATH-like slices | medium | True | False |
| A_dominant_source_outvoted | dominant_source_outvoted | dominant source correct but pooled/majority selects another answer | 70 | {"cohere_math500_aux": 34, "mistral_gsm8k": 19, "mistral_math500": 17} | majority ignores source reliability asymmetry | strengthen C1d dominant-source override with conservative gate | recover S1-isolated wins in dominant-source regimes | low-medium (false dominance in near-peer) | True | False |
| B_near_peer_false_dominance | near_peer_false_dominance | selector trusts a dominant source in near-peer conditions where pooled vote was right | 47 | {"cohere_math500_aux": 32, "mistral_math500": 13, "mistral_gsm8k": 2} | dominance trigger too aggressive under small source spread | near-peer gate: block dominance when spread < threshold | cuts dominant-source false positives | medium | True | False |
| D_external_majority_wrong | external_majority_wrong | external sources agree but are wrong | 31 | {"cohere_gsm8k": 14, "cohere_math500_aux": 8, "mistral_math500": 7, "mistral_gsm8k": 2} | prompt-family correlated error | external-majority skepticism when frontier disagrees | recover correlated external-majority failures | medium-high | True | False |

## 6. Mechanism diagnoses
See `outputs/failure_pattern_mining_workbench_20260524/failure_mechanism_diagnoses.md` for per-pattern causal hypotheses and evidence-linked reasoning.

## 7. Candidate fixes
| fix_id | target_failure_cluster | zero_extra_call | description | required_features | implementation_complexity | expected_recoveries | expected_regressions | scenarios_likely_helped | scenarios_at_risk | evaluation_protocol | status | target_cluster | scenarios_helped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FIX-01 | dominant_source_outvoted, S1_undertrusted | True | Strengthen C1d dominance rule with conservative activation gates. | dominant_source, S1_isolated, provider/dataset regime spread | low | medium-high | low | mistral_gsm8k, mistral_math500 | cohere_gsm8k near-peer | paired replay vs pooled4 and beta-shrinkage across all scenarios | implement now | dominant_source_outvoted, S1_undertrusted | mistral_gsm8k, mistral_math500 |
| FIX-02 | no_majority_bad_fallback | True | Narrow no-majority fallback to calibrated high-confidence dominant-source cases. | no_majority_flag, dominance margin, source reliability | low | medium | low | mistral_gsm8k | cohere near-peer | isolate no-majority subset, compare fallback variants | implement now | no_majority_bad_fallback | mistral_gsm8k |
| FIX-03 | S1_overtrusted, near_peer_false_dominance | True | S1-trust gate to block S1 override in Cohere-like near-peer regimes. | provider, dataset, source spread, regime label | low | medium | low | cohere_gsm8k, cohere_math500_aux | mistral dominant slices | threshold sweep with regression audit on Mistral | implement now | S1_overtrusted, near_peer_false_dominance | cohere_gsm8k, cohere_math500_aux |
| FIX-04 | external_majority_wrong | True | External-majority skepticism when L1+TALE family historically correlates on errors. | L1_TALE_agree, frontier disagreement markers | medium | low-medium | medium | cohere_math500 official candidate | global if frontier is weak | wait for official Cohere MATH scenario then replay | test after Cohere official Scenario 4 | external_majority_wrong | cohere_math500 official candidate |
| FIX-05 | cross-pattern reliability mismatch | True | Pattern-specific RG-EB-Action table keyed by regime/pattern/provider/dataset. | answer_pattern_bucket, regime features, provider, dataset | medium | medium-high | medium | cross-scenario | low-support cells | cross-scenario CV and holdout transfer | test after Cerebras | cross-pattern reliability mismatch | cross-scenario |
| FIX-06 | MATH_all_sources_wrong | False | Hardness detector to escalate budget on high all-sources-wrong risk cases. | question complexity and topic features | high | selector-only none; generation-level potential | budget waste risk | math500 scenarios | none selector-side | predictive precision/recall on held-out MATH cases | needs larger training data | MATH_all_sources_wrong | math500 scenarios |
| FIX-07 | multi-pattern routing errors | True | Learned router v2 with Mistral train1000 + auxiliary routing-decisive cases. | full unified feature table and larger routing-decisive pool | high | medium-high | overfit risk | all scenarios | transfer to unseen provider/dataset | train/holdout by scenario with paired regression audit | test after Mistral train1000 | multi-pattern routing errors | all scenarios |
| FIX-08 | provider-dataset mismatch | True | Provider/dataset calibration hierarchy for default fallback policies. | provider, dataset, regime | low | medium | low-medium | cohere_math500_aux, cohere_gsm8k | mistral if over-applied | scenario-conditional replay against uniform policy | implement now | provider-dataset mismatch | cohere_math500_aux, cohere_gsm8k |
| FIX-09 | evaluation focus drift | True | Oracle-gap targeting: evaluate/train on routing-decisive cases only. | oracle flag + source-correctness counts | low | meta-improvement in fix quality | none | all | none | all reports include routing-decisive slice metrics | implement now | evaluation focus drift | all |

## 8. Implementation priority queue
| priority | fix_id | estimated_benefit | regression_risk | zero_extra_call_compatible | implementation_difficulty | evidence_strength | enough_completed_data_now | pending_runs_needed | loop |
|---|---|---|---|---|---|---|---|---|---|
| 1 | FIX-01 | high | low-medium | True | low | high | True | no | implement strengthened C1d; compare vs beta-shrinkage and pooled4; inspect regressions; tune; repeat |
| 2 | FIX-03 | high | low | True | low | high | True | no | add S1-trust gate for near-peer; replay all scenarios; verify no Mistral harm; tune threshold |
| 3 | FIX-02 | medium | low-medium | True | low | medium-high | True | no | narrow no-majority fallback to calibrated cases; compare vs baseline fallback; inspect no-majority regressions |
| 4 | FIX-08 | medium | medium | True | low | medium | True | no | apply provider/dataset hierarchy; replay; verify gains and guard Mistral |
| 5 | FIX-04 | medium | medium-high | True | medium | medium | False | Cohere official Scenario 4 | after official Cohere MATH completion, calibrate external-majority skepticism and rerun regression audit |
| 6 | FIX-05 | high | medium | True | medium | medium | False | Cerebras scenario completion | build RG-EB-Action table with richer cross-provider support after Cerebras |
| 7 | FIX-07 | high | high | True | high | medium | False | Mistral train1000 completion | train learned router v2 on expanded routing-decisive data, then cross-scenario holdout test |
| 8 | FIX-06 | generation-level | budget risk | False | high | medium | False | larger labeled MATH set | train hardness detector and evaluate budget-escalation policy |

## 9. What can be improved by selector alone
Selector-fixable cluster mass (sum of cluster counts where `needs_generation_or_budget=false`): 1382.

## 10. What requires better generation/more budget
Generation/budget-bound cluster mass (`MATH_all_sources_wrong` family): 403.

## 11. How to repeat this loop after new runs
1. Wait for run completion and integrity PASS.
2. Update source artifacts in this script if new canonical paths change.
3. Re-run `python3 scripts/build_failure_pattern_workbench.py`.
4. Re-check `failure_views_summary.csv` and top clusters.
5. Re-prioritize queue and implement top fix.

## 12. Safety confirmation
- Offline analysis only
- No API calls launched
- No active jobs touched
- No source artifact overwrite
- No commit/push
