# Anonymous Supplement Audit Report

- Timestamp (UTC): 2026-04-24T17:09:51.007568+00:00
- Scanned path: `/mmfs1/home/sv96/adaptive-reasoning-budget-allocation`
- Overall status: **WARNING**
- Findings: blocking=0, warning=155
- Total extracted size: 9.38 MB
- Total extracted budget: 100.00 MB
- ZIP path: `/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/dist/neurips2026_anonymous_supplement.zip`
- ZIP size: 1.48 MB
- ZIP budget: 100.00 MB

## Findings

| Severity | Category | Path | Line | Detail |
|---|---|---|---:|---|
| warning | forbidden_path | `archive/README.md` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `archive/historical_scripts/run_final_manuscript_eval.sh` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `archive/historical_scripts/run_heavy_real_routing_eval.sh` | 0 | Forbidden/deanonymizing path token present |
| warning | api_key_name | `archive/historical_scripts/run_heavy_real_routing_eval.sh` | 14 | Secret environment variable token name (not value) |
| warning | api_key_name | `archive/historical_scripts/run_heavy_real_routing_eval.sh` | 15 | Secret environment variable token name (not value) |
| warning | api_key_name | `archive/historical_scripts/run_heavy_real_routing_eval.sh` | 18 | Secret environment variable token name (not value) |
| warning | api_key_name | `archive/historical_scripts/run_heavy_real_routing_eval.sh` | 19 | Secret environment variable token name (not value) |
| warning | api_key_name | `archive/historical_scripts/run_heavy_real_routing_eval.sh` | 22 | Secret environment variable token name (not value) |
| warning | api_key_name | `archive/historical_scripts/run_heavy_real_routing_eval.sh` | 23 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/COHERE_BOUNDED_HARD_CASE_ADJUDICATION_PASS_2026_04_17.md` | 15 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/COHERE_BOUNDED_HARD_CASE_ADJUDICATION_PASS_2026_04_17.md` | 96 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/COHERE_PRODUCTION_KEY_RUNTIME_VERIFICATION_2026_04_17.md` | 6 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/DATASET_ADDITION_HF_TOKEN_FOLLOWUP_STATUS_2026_04_19.md` | 1 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/DATASET_ADDITION_HF_TOKEN_FOLLOWUP_STATUS_2026_04_19.md` | 5 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/DATASET_ADDITION_HF_TOKEN_FOLLOWUP_STATUS_2026_04_19.md` | 9 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/DATASET_ADDITION_HF_TOKEN_FOLLOWUP_STATUS_2026_04_19.md` | 23 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION_README.md` | 23 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/cross_controller_frontier.md` | 62 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/datasets_access.md` | 28 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/datasets_access.md` | 49 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/hle_integration_report_2026_04_19.json` | 29 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/hle_integration_report_2026_04_19.json` | 56 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/hle_integration_report_2026_04_19.json` | 83 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/hle_integration_report_2026_04_19.json` | 110 | Secret environment variable token name (not value) |
| warning | api_key_name | `docs/hle_integration_report_2026_04_19.json` | 137 | Secret environment variable token name (not value) |
| warning | absolute_path | `docs/l1_baseline_integration.md` | 7 | Absolute local path token |
| warning | api_key_name | `experiments/comparative_frontier_audit_real_model_note.md` | 17 | Secret environment variable token name (not value) |
| warning | api_key_name | `experiments/comparative_frontier_audit_wulver_note.md` | 24 | Secret environment variable token name (not value) |
| warning | api_key_name | `experiments/external_reasoning_datasets.py` | 376 | Secret environment variable token name (not value) |
| warning | api_key_name | `experiments/frontier_matrix_core.py` | 39 | Secret environment variable token name (not value) |
| warning | api_key_name | `experiments/frontier_matrix_core.py` | 41 | Secret environment variable token name (not value) |
| warning | api_key_name | `experiments/frontier_matrix_core.py` | 45 | Secret environment variable token name (not value) |
| warning | api_key_name | `experiments/hf_datasets.py` | 447 | Secret environment variable token name (not value) |
| warning | api_key_name | `experiments/hf_datasets.py` | 457 | Secret environment variable token name (not value) |
| warning | api_key_name | `experiments/hf_datasets.py` | 523 | Secret environment variable token name (not value) |
| warning | api_key_name | `experiments/pilot_gsm8k.md` | 32 | Secret environment variable token name (not value) |
| warning | absolute_path | `external/when_solve_when_verify/upstream/sc-genrm-scaling/environment.yml` | 274 | Absolute local path token |
| warning | absolute_path | `external/when_solve_when_verify/upstream/sc-genrm-scaling/llmonk/evaluate/configs/llama70b_gpqa.yaml` | 1 | Absolute local path token |
| warning | absolute_path | `external/when_solve_when_verify/upstream/sc-genrm-scaling/llmonk/evaluate/configs/llama70b_gpqa.yaml` | 2 | Absolute local path token |
| warning | absolute_path | `external/when_solve_when_verify/upstream/sc-genrm-scaling/llmonk/evaluate/configs/llama70b_math128.yaml` | 1 | Absolute local path token |
| warning | absolute_path | `external/when_solve_when_verify/upstream/sc-genrm-scaling/llmonk/evaluate/configs/llama70b_math128.yaml` | 2 | Absolute local path token |
| warning | absolute_path | `external/when_solve_when_verify/upstream/sc-genrm-scaling/llmonk/evaluate/configs/llama8b_math128.yaml` | 1 | Absolute local path token |
| warning | absolute_path | `external/when_solve_when_verify/upstream/sc-genrm-scaling/llmonk/evaluate/configs/llama8b_math128.yaml` | 2 | Absolute local path token |
| warning | absolute_path | `external/when_solve_when_verify/upstream/sc-genrm-scaling/llmonk/evaluate/configs/qwen7b_math128.yaml` | 1 | Absolute local path token |
| warning | absolute_path | `external/when_solve_when_verify/upstream/sc-genrm-scaling/llmonk/evaluate/configs/qwen7b_math128.yaml` | 2 | Absolute local path token |
| warning | absolute_path | `external/when_solve_when_verify/upstream/sc-genrm-scaling/llmonk/evaluate/configs/qwq32b_aime25.yaml` | 1 | Absolute local path token |
| warning | absolute_path | `external/when_solve_when_verify/upstream/sc-genrm-scaling/llmonk/evaluate/configs/qwq32b_aime25.yaml` | 2 | Absolute local path token |
| warning | forbidden_path | `jobs/README.md` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `jobs/RUN_COHERE_REAL_MAIN.md` | 0 | Forbidden/deanonymizing path token present |
| warning | api_key_name | `jobs/RUN_COHERE_REAL_MAIN.md` | 1 | Secret environment variable token name (not value) |
| warning | forbidden_path | `jobs/audit_openai_real_model_main_run.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | api_key_name | `jobs/audit_openai_real_model_main_run.sbatch` | 40 | Secret environment variable token name (not value) |
| warning | forbidden_path | `jobs/branch_scorer_v3_final_eval.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `jobs/branch_scorer_v3_heavy_ml.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `jobs/build_operational_controller_specification_20260424T164500Z.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | api_key_name | `jobs/build_operational_controller_specification_20260424T164500Z.sbatch` | 33 | Secret environment variable token name (not value) |
| warning | api_key_name | `jobs/build_operational_controller_specification_20260424T164500Z.sbatch` | 34 | Secret environment variable token name (not value) |
| warning | forbidden_path | `jobs/cohere_real_model_main_20260424.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | api_key_name | `jobs/cohere_real_model_main_20260424.sbatch` | 31 | Secret environment variable token name (not value) |
| warning | api_key_name | `jobs/cohere_real_model_main_20260424.sbatch` | 32 | Secret environment variable token name (not value) |
| warning | api_key_name | `jobs/cohere_real_model_main_20260424.sbatch` | 34 | Secret environment variable token name (not value) |
| warning | api_key_name | `jobs/cohere_real_model_main_20260424.sbatch` | 36 | Secret environment variable token name (not value) |
| warning | api_key_name | `jobs/cohere_real_model_main_20260424.sbatch` | 49 | Secret environment variable token name (not value) |
| warning | api_key_name | `jobs/cohere_real_model_main_20260424.sbatch` | 73 | Secret environment variable token name (not value) |
| warning | forbidden_path | `jobs/comparative_frontier_audit_wulver.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `jobs/heavy_real_routing_eval.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `jobs/multi_action_allocation_pass.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `jobs/openai_real_model_main_20260424.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | api_key_name | `jobs/openai_real_model_main_20260424.sbatch` | 48 | Secret environment variable token name (not value) |
| warning | api_key_name | `jobs/openai_real_model_main_20260424.sbatch` | 58 | Secret environment variable token name (not value) |
| warning | api_key_name | `jobs/openai_real_model_main_20260424.sbatch` | 74 | Secret environment variable token name (not value) |
| warning | forbidden_path | `jobs/oracle_label_pilot_hpc.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `jobs/paper_main_numeric_results_bundle_wulver.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `jobs/run_missing_cohere_real_model_main_slices_20260424T163922Z.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | api_key_name | `jobs/run_missing_cohere_real_model_main_slices_20260424T163922Z.sbatch` | 24 | Secret environment variable token name (not value) |
| warning | api_key_name | `jobs/run_missing_cohere_real_model_main_slices_20260424T163922Z.sbatch` | 25 | Secret environment variable token name (not value) |
| warning | forbidden_path | `jobs/run_missing_openai_real_model_main_slices_20260424T163922Z.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | api_key_name | `jobs/run_missing_openai_real_model_main_slices_20260424T163922Z.sbatch` | 24 | Secret environment variable token name (not value) |
| warning | api_key_name | `jobs/run_missing_openai_real_model_main_slices_20260424T163922Z.sbatch` | 25 | Secret environment variable token name (not value) |
| warning | forbidden_path | `jobs/wulver_hf_access_gap_audit.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `jobs/wulver_hf_adjacent_baseline_refresh.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `jobs/wulver_when_solve_verify_hf_import_pipeline.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `jobs/wulver_when_solve_verify_hf_smoke.sbatch` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/openai_real_model_main_run_audit_982232.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/openai_real_model_main_run_audit_982232.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/branch_scorer_v3_final_eval-935482.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/branch_scorer_v3_final_eval-935482.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/branch_scorer_v3_heavy_ml-914308.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/branch_scorer_v3_heavy_ml-914308.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/branch_scorer_v3_heavy_ml-935401.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/branch_scorer_v3_heavy_ml-935401.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/branch_scorer_v3_heavy_ml-935481.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/branch_scorer_v3_heavy_ml-935481.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/branch_scorer_v3_heavy_ml-937459.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/branch_scorer_v3_heavy_ml-937459.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/cohere-real-main-missing-982679.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/cohere-real-main-missing-982679.out` | 0 | Forbidden/deanonymizing path token present |
| warning | api_key_name | `logs/slurm/cohere-real-main-missing-982679.out` | 1 | Secret environment variable token name (not value) |
| warning | forbidden_path | `logs/slurm/cohere_real_main_979423.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/cohere_real_main_979423.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/heavy_real_routing_eval-914297.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/heavy_real_routing_eval-914297.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/hf_adj_refresh-963315.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/hf_adj_refresh-963315.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/hf_adjacent_suite-963281.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/hf_adjacent_suite-963281.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/hf_gap_audit-963316.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/hf_gap_audit-963316.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/openai_real_main_979302.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/openai_real_main_979302.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/paper_main_numeric_bundle-961552.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/paper_main_numeric_bundle-961552.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/wsv_hf_import-963314.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/wsv_hf_import-963314.out` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/wsv_hf_smoke-963313.err` | 0 | Forbidden/deanonymizing path token present |
| warning | forbidden_path | `logs/slurm/wsv_hf_smoke-963313.out` | 0 | Forbidden/deanonymizing path token present |
| warning | api_key_name | `scripts/build_hf_access_gap_audit.py` | 27 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/build_hf_access_gap_audit.py` | 76 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/build_hf_access_gap_audit.py` | 91 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/cohere_adjudicate_hard_pairs.py` | 141 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/cohere_adjudicate_hard_pairs.py` | 143 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/generate_dataset_integration_report.py` | 104 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_cohere_rerank_branch_allocation_experiment.py` | 205 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_cohere_rerank_branch_allocation_experiment.py` | 207 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_comparative_frontier_audit.py` | 609 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_comparative_frontier_audit.py` | 611 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_cross_strategy_frontier_allocation.py` | 108 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_new_paper_external_warmstart_branch_scorer.py` | 412 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_new_paper_external_warmstart_branch_scorer.py` | 414 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_new_paper_frontier_matrix.py` | 279 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_new_paper_frontier_matrix.py` | 360 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_pilot_gsm8k.py` | 94 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_real_model_fixed_budget_pilot.py` | 71 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_real_model_fixed_budget_pilot.py` | 73 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_real_model_fixed_budget_pilot.py` | 394 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_real_model_fixed_budget_pilot.py` | 395 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_real_model_ours_vs_external_validation.py` | 123 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_real_model_ours_vs_external_validation.py` | 125 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_worst_real_failure_casebook_with_reasoning.py` | 118 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_worst_real_failure_casebook_with_reasoning.py` | 120 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/run_worst_real_failure_casebook_with_reasoning.py` | 122 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/verify_cohere_runtime_key_and_limits.py` | 114 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/verify_cohere_runtime_key_and_limits.py` | 124 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/verify_cohere_runtime_key_and_limits.py` | 128 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/verify_cohere_runtime_key_and_limits.py` | 165 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/verify_cohere_runtime_key_and_limits.py` | 179 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/verify_cohere_runtime_key_and_limits.py` | 182 | Secret environment variable token name (not value) |
| warning | absolute_path | `scripts/verify_compute_optimal_tts_provenance.py` | 63 | Absolute local path token |
| warning | absolute_path | `scripts/verify_compute_optimal_tts_provenance.py` | 149 | Absolute local path token |
| warning | api_key_name | `scripts/verify_hf_dataset_access.py` | 151 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/wulver_comparative_frontier_audit.sh` | 42 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/wulver_comparative_frontier_audit.sh` | 44 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/wulver_comparative_frontier_audit.sh` | 48 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/wulver_comparative_frontier_audit.sh` | 81 | Secret environment variable token name (not value) |
| warning | api_key_name | `scripts/wulver_comparative_frontier_audit.sh` | 83 | Secret environment variable token name (not value) |
