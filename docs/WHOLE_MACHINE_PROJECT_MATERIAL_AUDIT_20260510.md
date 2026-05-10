# Whole-Machine Project Material Audit (2026-05-10)

## Executive Summary
A whole-machine audit was performed to ensure all critical research material for the `frontier-allocation` project is contained within the canonical GitHub repository. 

- **GitHub Repo Completeness**: **High**. Most critical method implementations, baseline registrations, and failure datasets are present.
- **Missing Material**: Several diagnostic tests and specialized evaluation scripts were found in a local archive (`~/frontier-allocation-old-folders-archive-20260510/research-next-wt/`) that are not in the main repo.
- **Newer Versions**: No newer versions of core controllers or algorithm logic were found outside the repo; the GitHub versions are the latest.

## Latest Method Implementations
- **Inside Repo**: `DirectReserveFrontierGateController`, `L1LengthControlController`, `S1BudgetForcingController`, `TALEPromptBudgetingController`, and `production_equiv_v1` logic are all fully committed.
- **Outside Repo**: Older versions and exact duplicates were found in archives. No unique algorithmic improvements were found outside.

## Comparison Results and External Baselines
- **Inside Repo**: Registration for `external_l1_max`, `external_l1_exact`, `external_s1_budget_forcing`, `external_tale_prompt_budgeting`, and `external_zhai_cpo_mode_a` exists in `experiments/frontier_matrix_core.py`.
- **Outside Repo**: Specialized scripts for "matched-50" calibration and "stage3" integrated replays were found in the archive.

## Failure/Test Case Datasets
- **Inside Repo**: `full_latest_method_failures.csv`, `target_audit_diagnostic_cases.jsonl`, and the recent `gold_absent` analysis files are all committed.
- **Outside Repo**: Duplicate failure casebooks were found.

## Handoff/Reproducibility
- **Confirmed**: `AGENTS.md`, `docs/CODEX_WEB_HANDOFF_20260510.md`, and `START_HERE_CURRENT.md` are all present and up-to-date.

## Missing-Material Table

| Priority | Outside Path | Recommended Destination | Reason | Size | Action |
| :--- | :--- | :--- | :--- | :--- | :--- |
| High | `.../tests/test_main_table_external_baselines.py` | `tests/` | Validates external baselines | 5KB | Import |
| High | `.../tests/test_gsm8k_structural_validator_eval.py` | `tests/` | Validates structural commitment | 3KB | Import |
| High | `.../tests/test_targeted_discovery_retry_v1.py` | `tests/` | Validates discovery retries | 6KB | Import |
| Medium | `.../scripts/run_external_baseline_matched50_live.py`| `scripts/` | Matched-50 calibration script | 13KB | Import |
| Medium | `.../scripts/mine_gold_absent_external_schema.py` | `scripts/` | Failure mining utility | 26KB | Import |

## Safety Warnings
- **No real secrets found**: Scans for `.env`, `key`, and `token` returned only files related to "token counting" or "anonymization audits".
- **Large Files**: Several `live_run.log` files in the archive are >100KB but contain useful trace evidence. They are not strictly needed in the repo but are good for provenance.

## Import Plan
I will import the identified high-priority tests and scripts into the repository to ensure full reproducibility for the next agent.

---
*Audit conducted by Gemini 3 Flash on 2026-05-10.*
