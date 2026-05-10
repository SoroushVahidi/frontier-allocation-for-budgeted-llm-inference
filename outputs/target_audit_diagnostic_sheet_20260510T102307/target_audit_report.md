# Target-Audit Diagnostic Sheet
Created: `20260510T102307`
## Scope
Curated diagnostic sheet for conservative target-audit design. Built from existing local artifacts only; no model calls or live experiments.
## Cases Included
- `openai_gsm8k_30` `final_target_mismatch` `wrong_quantity_target` selected `121` vs gold `109`; correct-alt=`True` (pal_correct|gold_in_selector_candidate_pool)
- `openai_gsm8k_59` `final_target_mismatch` `total_vs_component` selected `287` vs gold `187`; correct-alt=`True` (pal_correct|gold_in_selector_candidate_pool)
- `openai_gsm8k_62` `final_target_mismatch` `unit_conversion` selected `50` vs gold `25000`; correct-alt=`True` (pal_correct|gold_in_selector_candidate_pool)
- `openai_gsm8k_217` `final_target_mismatch` `total_vs_component` selected `11` vs gold `15`; correct-alt=`True` (pal_correct|gold_in_selector_candidate_pool)
- `openai_gsm8k_245` `final_target_mismatch` `per_unit_vs_total` selected `14` vs gold `7`; correct-alt=`True` (pal_correct|gold_in_selector_candidate_pool)
- `openai_gsm8k_358` `final_target_mismatch` `per_unit_vs_total` selected `4` vs gold `20`; correct-alt=`True` (pal_correct|gold_in_selector_candidate_pool)
- `openai_gsm8k_1177` `final_target_mismatch` `subtotal_as_final` selected `150` vs gold `320`; correct-alt=`True` (pal_correct|gold_in_selector_candidate_pool)
- `openai_gsm8k_1180` `final_target_mismatch` `total_vs_component` selected `720` vs gold `1520`; correct-alt=`True` (pal_correct|gold_in_selector_candidate_pool)
- `openai_gsm8k_1218` `final_target_mismatch` `wrong_quantity_target` selected `180` vs gold `120`; correct-alt=`True` (pal_correct|gold_in_selector_candidate_pool)
- `openai_gsm8k_1155` `structural_commit_wrong` `wrong_quantity_target` selected `164.39999999999998` vs gold `342`; correct-alt=`True` (best_core4_correct|prior_patch_correct|winning_fair_baselines=l1|best_core4)
- `openai_gsm8k_1077` `structural_commit_wrong` `subtotal_as_final` selected `4` vs gold `5`; correct-alt=`True` (best_core4_correct|prior_patch_correct|winning_fair_baselines=l1|sc4|s1|tale|best_core4)
- `openai_gsm8k_1080` `structural_commit_wrong` `total_vs_component` selected `54` vs gold `48`; correct-alt=`True` (best_core4_correct|prior_patch_correct|winning_fair_baselines=tale|best_core4)
- `openai_gsm8k_1131` `structural_commit_wrong` `wrong_quantity_target` selected `10` vs gold `4`; correct-alt=`True` (best_core4_correct|prior_patch_correct|winning_fair_baselines=tale|best_core4)
- `openai_gsm8k_1147` `structural_commit_wrong` `elapsed_time_vs_participant_minutes` selected `2040` vs gold `34`; correct-alt=`False` ()
- `openai_gsm8k_1158` `structural_commit_wrong` `total_vs_component` selected `2180` vs gold `2280`; correct-alt=`False` ()

## Mismatch Subtype Counts
- `elapsed_time_vs_participant_minutes`: 1
- `per_unit_vs_total`: 2
- `subtotal_as_final`: 2
- `total_vs_component`: 5
- `unit_conversion`: 1
- `wrong_quantity_target`: 4

## Correct Alternate Evidence
- `pal_correct`: 9
- `gold_in_selector_candidate_pool`: 9
- `best_core4_correct`: 4
- `prior_patch_correct`: 4
- `best_core4`: 4
- `sc4`: 1
- `s1`: 1
- `tale`: 1

## Conservative Rule Candidate
When the final selected answer comes from `structural_commit` and conflicts with a clean PAL or candidate/baseline answer, run a target-consistency audit keyed to the problem ask: total/combined, per-unit vs total, time/unit conversion, subtotal/final, and wrong target quantity. Only override when the alternate candidate matches the requested target and the selected structural answer is explainably an intermediate/component/unit-mismatched value.

## Safety Rationale
Use as a guard on conflicting candidates, not a global reranker. Require positive evidence from problem-target cues plus an available correct-looking alternate candidate. No-op when evidence is ambiguous.

## Source Artifacts
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/cumulative_pal_vs_prod_casebook.csv`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/metadata/pal/openai_gsm8k_1177.json`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/metadata/pal/openai_gsm8k_1180.json`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/metadata/pal/openai_gsm8k_1218.json`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/metadata/production_equiv/openai_gsm8k_1177.json`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/metadata/production_equiv/openai_gsm8k_1180.json`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/metadata/production_equiv/openai_gsm8k_1218.json`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/responses/pal/openai_gsm8k_1177.json`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/responses/pal/openai_gsm8k_1180.json`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/responses/pal/openai_gsm8k_1218.json`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/responses/production_equiv/openai_gsm8k_1177.json`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/responses/production_equiv/openai_gsm8k_1180.json`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/responses/production_equiv/openai_gsm8k_1218.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/pal/openai_gsm8k_217.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/pal/openai_gsm8k_245.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/pal/openai_gsm8k_30.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/pal/openai_gsm8k_303.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/pal/openai_gsm8k_358.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/pal/openai_gsm8k_59.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/pal/openai_gsm8k_62.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/production_equiv/openai_gsm8k_217.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/production_equiv/openai_gsm8k_245.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/production_equiv/openai_gsm8k_30.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/production_equiv/openai_gsm8k_303.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/production_equiv/openai_gsm8k_358.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/production_equiv/openai_gsm8k_59.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/metadata/production_equiv/openai_gsm8k_62.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/relaxed_pal_vs_prod_casebook_new.csv`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/pal/openai_gsm8k_217.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/pal/openai_gsm8k_245.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/pal/openai_gsm8k_30.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/pal/openai_gsm8k_303.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/pal/openai_gsm8k_358.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/pal/openai_gsm8k_59.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/pal/openai_gsm8k_62.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/production_equiv/openai_gsm8k_217.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/production_equiv/openai_gsm8k_245.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/production_equiv/openai_gsm8k_30.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/production_equiv/openai_gsm8k_303.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/production_equiv/openai_gsm8k_358.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/production_equiv/openai_gsm8k_59.json`
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/responses/production_equiv/openai_gsm8k_62.json`
- `outputs/production_equiv_v1_retry_commit_loss_audit_20260508T204005Z/production_equiv_loss_bank_detailed.csv`
