# RG-EB Action Router (2026-05-24)

## 1. Executive summary
- Implemented and evaluated RG-EB action-level empirical-Bayes router variants across official4 protocols and auxiliary-separated diagnostics.
- Best official pooled variant: **RGEB04_providerfree_mean_s5**.
- Best variant pooled accuracy: 66.42%

## 2. Data sources and caveats
- Headline results use only official four-scenario matrix (1200 rows).
- Auxiliary data (Mistral train1000 and Cohere MATH aux488) used only in separated auxiliary-training protocol summaries.
- Offline only; no API calls; active jobs observed only.

## 3. Action set and feature schema
- See `outputs/rg_eb_action_router_20260524/rg_eb_action_set_description.md`.
- See `outputs/rg_eb_action_router_20260524/rg_eb_feature_schema.md`.

## 4. RG-EB variants
- RGEB-01 mean-shrinkage coarse buckets
- RGEB-02 conservative LCB
- RGEB-03 provider/dataset-aware diagnostic
- RGEB-04 provider-free
- RGEB-05 hierarchical backoff
- RGEB-06 agreement-focused restricted action set
- RGEB-07 source/action hybrid
- RGEB-08 auxiliary-trained provider-free variant

## 5. Official four-scenario pooled results
- RGEB04_providerfree_mean_s5: 66.42% (macro 66.42%, worst 33.00%)
- beta_shrinkage: 65.17% (macro 65.17%, worst 29.33%)
- C1d: 65.17% (macro 65.17%, worst 29.33%)
- agreement_only: 63.42% (macro 63.42%, worst 33.00%)

## 6. Transfer/heldout results
- RGEB04_providerfree_mean_s5: 65.17% (macro 65.17%, worst 29.33%)
- RGEB04_providerfree_mean_s5: 63.33% (macro 63.33%, worst 27.00%)
- RGEB04_providerfree_mean_s5: 64.50% (macro 64.50%, worst 29.33%)

## 7. Auxiliary-training experiments
- RGEB04_providerfree_mean_s5: 66.00% (macro 66.00%, worst 31.78%)
- RGEB08_aux_trained_providerfree_mean_s5: 66.00% (macro 66.00%, worst 31.78%)

## 8. Scenario-specific analysis
- Cohere MATH detailed file: `outputs/rg_eb_action_router_20260524/rgeb_cohere_math_detailed.csv` (300 rows)
- Mistral dominant detailed file: `outputs/rg_eb_action_router_20260524/rgeb_mistral_dominant_detailed.csv` (600 rows)
- Cohere GSM8K detailed file: `outputs/rg_eb_action_router_20260524/rgeb_cohere_gsm8k_detailed.csv` (300 rows)

## 9. Failure/regression analysis
- Recoveries vs beta: 23
- Regressions vs beta: 8
- Recoveries vs C1d: 23
- Regressions vs C1d: 8
- Agreement-only wins captured: 18
- Agreement regressions avoided: 54

## 10. Candidate decision
- Keep RGEB-03 as lookup-risk diagnostic only.
- Use **RGEB04_providerfree_mean_s5** as router-v2 baseline candidate, pending stronger heldout stability evidence before promotion.

## 11. Manuscript implications
- Action-level routing is supported as an interpretable methodology, but safe claims remain conservative.

## 12. Router-v2 integration plan
- See `outputs/rg_eb_action_router_20260524/rgeb_router_v2_integration_plan.md`.

## 13. Next iteration recommendation
- Implement learned router-v2 next; avoid additional hand-crafted gates.

## 14. Safety confirmation
- No API calls launched: true
- Active jobs touched: false
- No commits/pushes performed
