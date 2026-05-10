# Repository/Evidence Synchronization Audit — 2026-05-10

## Overview
This report summarizes the synchronization status between the local machine and the GitHub repository `SoroushVahidi/frontier-allocation-for-budgeted-llm-inference`.

## Main Questions
1. **Latest pushed state of main?** `e28b1d4` (results: add offline PAL retry 300-case analysis (#361)).
2. **Is commit 4e862bb pushed?** **Yes**, to `origin/artifact-preservation-20260509`.
3. **Is docs/project_handoff_20260510/ pushed?** **Yes**, it is part of commit `4e862bb`.
4. **Which important local materials are tracked and pushed?**
   - `docs/project_handoff_20260510/`
   - `outputs/pal_retry_300case_analysis_20260506/`
   - `experiments/targeted_discovery_retry.py`
5. **Which important local materials are tracked but unpushed?**
   - Modified files in `/home/soroush/frontier-allocation-for-budgeted-llm-inference` (e.g., `experiments/output_layer_repair.py`).
6. **Which important local materials are untracked/local-only?**
   - Many new scripts and experiment outputs in `outputs/` (e.g., `external_full_suite_matched50_comparison_20260508T222631Z`).
   - New manifests and prompts.
7. **Which important materials are preserved only inside artifact-preservation archives?**
   - Raw `.jsonl` traces and API logs are preserved in the `artifact-preservation-20260509` branch but not in `main`.
8. **Which important materials are missing from GitHub/main?**
   - `outputs/external_full_suite_matched50_comparison_20260508T222631Z/external_full_suite_summary.json`
   - `manifests/target_staged_pal_retry_primary_11_20260507.json`

## Classification Summary
- **Latest Method:** Implementation files for `production_equiv_v1` and `structural_commit_v1` are mostly local/untracked.
- **External Baselines:** Matched-50 results are local-only.
- **Failure Banks:** `docs/project_handoff_20260510/` is pushed; other raw inventories are local.
- **Experiment Summaries:** Many reports are local-only.
- **Tests:** New tests for structural commit and PAL retry are local-only.
- **Manifests/Prompts:** Reproduction artifacts are local-only.

## Recommended Next Action
- Review and push `recommended_push_candidates.csv`.
- Merge `artifact-preservation-20260509` into a research-facing branch if appropriate.
