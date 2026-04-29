# SCRIPT_REGISTRY_CANONICAL_20260429

| script | class | purpose | safe to run? | needs API key? | expected outputs | related docs |
|---|---|---|---|---|---|---|
| `scripts/paper/run_all_neurips_paper_artifacts.py` | active canonical | regenerate paper-facing canonical artifacts | yes | no | paper tables/plots/figures | `docs/PAPER_SOURCE_OF_TRUTH.md` |
| `scripts/run_cohere_real_model_cost_normalized_validation.py` | dangerous/expensive API runner | real-model cost-normalized validation | with caution | yes | output run package + records | `docs/REAL_MODEL_EXPERIMENT_STATUS.md` |
| `scripts/run_outcome_verifier_selector_diagnostic.py` | active diagnostic | offline verifier-style selector rerank diagnostics | yes | no | diagnostic summaries | outcome verifier docs |
| `scripts/run_cobbe_style_outcome_verifier_diagnostic.py` | active diagnostic | Cobbe-style offline diagnostics | yes | no | diagnostic outputs | outcome verifier docs |
| `scripts/check_direct_reserve_v2_registry.py` | validation/checking | sanity check DR-v2 registration/metadata | yes | no | console checks | DR-v2 docs |
| `scripts/check_repository_status_consistency.py` | validation/checking | verify registry/docs/method status consistency | yes | no | pass/fail report | this registry set |
| `scripts/plan_cohere_real_model_chunks.py` | paper artifact builder / ops | create chunk plans for resumable runs | with caution | no | chunk plan csv | status docs |
| `scripts/run_cohere_chunk.py` | dangerous/expensive API runner | execute one planned Cohere chunk | with caution | yes | chunk output folder | status docs |
| `scripts/aggregate_cohere_chunks.py` | validation/checking | aggregate chunk outputs | yes | no | aggregated run artifacts | status docs |
