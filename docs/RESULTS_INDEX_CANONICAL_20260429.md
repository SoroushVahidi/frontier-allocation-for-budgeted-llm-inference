# RESULTS_INDEX_CANONICAL_20260429

> Canonical index separating claim-eligible vs diagnostic/provenance outputs.

| class | path | timestamp | methods tested | dataset/budget/seed/provider | sample size | main result | safe to cite? | superseded? | supports conclusion |
|---|---|---|---|---|---:|---|---|---|---|
| canonical paper-facing | `outputs/paper_tables/`, `outputs/paper_plot_data/`, `outputs/paper_figures/` | regenerated | paper promoted set | paper contract | n/a | official manuscript artifacts | yes | no | headline claims only |
| real-model diagnostic | `outputs/real_model_ours_vs_external_validation_20260424T_OPENAI_REAL_MAIN/` | 2026-04-24 | strict/internal + external baselines | OpenAI real-model slice | mixed | provider realism diagnostic | with caution | no | supporting-only real-model evidence |
| real-model diagnostic | `outputs/real_model_ours_vs_external_validation_20260424T_COHERE_REAL_MAIN/` | 2026-04-24 | strict/internal + external baselines | Cohere real-model slice | mixed | provider realism diagnostic | with caution | no | supporting-only real-model evidence |
| real-model diagnostic | `outputs/cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN/` | 2026-04-25 | strict_f3/strict_gate1/strict_f2/external_l1/dr variants | cohere gsm8k mixed budgets seeds | staged | cost-normalized audit slice | with caution | partly | failure-mode and cost-normalized diagnostics |
| small-sample/preflight | `docs/COHERE_DR_V2_VS_EXTERNAL_L1_100CASE_VALIDATION_20260429T_COHERE_DR_V2_VS_L1_100CASE.md` | 2026-04-29 | dr_v2 vs external_l1_max | cohere gsm8k b4 s11 | partial/targeted | preflight indicator only | no (broad claims) | pending | informs next run planning |
| failed/incomplete | codex-local chunk progress ledgers | ongoing | 9-method cohere slice | cohere gsm8k b2 s11 | incomplete | slice not fully completed | no | n/a | provenance + resumable progress |
| superseded | thresholded-ordered zero-score diagnostics | historical | dr_v2_thresholded_ordered | diagnostic | small | negative diagnostic path | no | yes | avoid repeated dead-end experiments |
| provenance-only | launch logs / fallback notes | historical | mixed | mixed | n/a | execution provenance only | no | n/a | reproducibility trace only |
