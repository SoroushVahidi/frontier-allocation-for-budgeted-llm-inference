# Expanded-pool run record: 20260428T143500Z

## Run type

Live Cohere expanded-loss-pool diagnostic (GSM8K only; multi-dataset live not used — see runner: comma `dataset-name` rejected for this profile in live mode, documented separately if needed).

## Slurm

- **Job ID:** 1011613
- **Sbatch:** `batch/run_semantic_diversity_expanded_pool_20260428T143500Z.sbatch`
- **Name:** `semdiv-exp-pool`

## Case-pool selection (same logic as dry, source: `loss_cases_absent_from_tree.jsonl`)

| Metric | Value |
|--------|------:|
| Candidate rows inspected | 189 |
| Rejected: empty question or gold | 163 |
| Rejected: dataset filter (GSM8K-only) | 0 |
| Rejected: ineligible loss pattern | 0 |
| Eligible after filters | 26 |
| Unique `example_id` in eligible pool | 16 |
| **Selected rows (case slots)** | **30** |
| **Unique `example_id` selected** | **16** |
| **Fallback duplicate / cycle rows** | **14** |
| Max cases requested | 30 |

**Reached 30 unique example IDs?** **No** — only **16** unique IDs exist in the filtered eligible pool from this JSONL; **14** slots reuse IDs (different seed/budget / cycling) per `--allow-duplicate-example-fallback`.

### Source strata

From `case_pool_expansion_audit.csv` / selection policy: absent-from-tree **confirmed** first, then **unverified**; internal method priority `strict_f3` > gate > anti-collapse > `dr_gate`; strata note in audit: *prioritize absent-from-tree confirmed > unverified; internal priority strict_f3 > gate > anti-collapse > dr_gate*.

### Datasets included

- **openai/gsm8k** only (live). Natural Plan / GPQA not included: **not** enabled in this run (avoid unsupported multi-dataset live path).

### Methods included

- `external_l1_max`
- `strict_f3`
- `direct_reserve_semantic_frontier_v1`
- `semantic_minimum_maturation_plus_direct_reserve_v1`

(`branching_necessity_gate_v1` not requested.)

## Dry run gate

Dry timestamp `20260428T143500Z_DRY`: **30 ≥ 20** selected rows → live submission allowed. Detail: `docs/SEMANTIC_DIVERSITY_EXPANDED_POOL_DRY_SELECTION_20260428T143500Z.md`.

## Readiness / API

- **COHERE_API_KEY** (submit host): **present** (not echoed).
- **Early window:** no `cohere_api_key_issue.md`; job progressed to trace writes → readiness **appeared OK** at startup.

## Outputs directory

`outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/`

## Logs

- `outputs/slurm_logs/semantic_diversity_expanded_pool_20260428T143500Z_1011613.out`
- `outputs/slurm_logs/semantic_diversity_expanded_pool_20260428T143500Z_1011613.err`

## If not 30 unique IDs: why

The merged loss pool (GSM8K, internal-wrong / external-correct, with question+gold) yields **16** distinct `example_id`s. Filling **30** case rows required **14** duplicate-ID fallbacks. To get **30 unique** IDs, **regenerate or merge additional loss JSONL** (e.g. other baselines, more runs, or other datasets in a **separately validated** pipeline), not just re-tune selection on the same file.

## Post-run (after job finishes)

Re-check: `manifest.json`, `per_case_results.csv`, `docs/SEMANTIC_DIVERSITY_CONTROLLER_DIAGNOSTIC_20260428T143500Z.md` (if analyzer succeeds), and any `run_failure_issue.md` from the runner.
