# Last 10 Wulver / Slurm jobs audit — adaptive-reasoning-budget-allocation

**Audit UTC timestamp:** `2026-05-02T22:08:57Z`
**Repository (cluster workdir):** `/mmfs1/home/sv96/adaptive-reasoning-budget-allocation`
**Also known as / local path:** `/home/sv96/adaptive-reasoning-budget-allocation`

## Commands used

```bash
date -u +%Y%m%dT%H%M%SZ

# Recent jobs filtered to this repo (WorkDir)
sacct --starttime 2026-05-02 -n --format=JobID,JobName,State,ExitCode,Elapsed,Start,End,Submit,WorkDir%140 \
  | grep -E 'adaptive-reasoning-budget-allocation'

sacct --starttime 2026-04-25 -n --format=JobID,JobName,State,ExitCode,Elapsed,End,WorkDir%110 \
  | grep mmfs1/home/sv96/adaptive-reasoning-budget-allocation | grep -v '.bat+' | grep -v '.ext+' | tail -25

# Compact detail for audited job IDs (main steps only)
sacct -j 1016416,1016461,1016482,1017716,1017718,1018203,1018219,1018248,1018285,1018287 \
  -X -n --parsable2 --format=JobID,JobName,State,ExitCode,Elapsed,Start,End,Submit

squeue -j 1018203
sacct -j 1018203 -X -n --format=State,Elapsed,ExitCode,End

ls -la logs/slurm/*1018219* logs/slurm/*1018248* logs/slurm/*gap* logs/slurm/main3_vs_best3_100_1018203* 2>/dev/null
wc -c logs/slurm/*.err logs/trace_loss_retry_1016461.err logs/best_on_losses_1016416.err logs/selector_33_1016482.err 2>/dev/null

find outputs -name batch_submission_info.json | sort

# Repo-wide search hints (grep; ripgrep not available in shell)
grep -R "Submitted batch job\|sbatch\|job_id\|10182" outputs logs docs 2>/dev/null | tail -40
```

**Machine-readable copy of commands:** `outputs/last_10_wulver_jobs_audit_20260502T220857Z/commands_used.txt`

## Assumptions and limitations

1. **“Last 10” definition:** Primary Slurm allocations (`sacct … -X`) with `WorkDir` exactly `/mmfs1/home/sv96/adaptive-reasoning-budget-allocation`, ordered by **`Submit`** time (newest first). This yields **seven** Slurm completions on **2026-05-02** plus three earlier jobs (2026-05-01 and 2026-04-30) to reach **10** distinct job IDs. Array/batch step rows (e.g. `*.bat+`) were excluded from the pool used to pick the window.
2. **Job ↔ artifact linkage:** When `outputs/**/batch_submission_info.json` or `run_env.log` names a `submitted_job_id` / `slurm_job_id`, that mapping is treated as authoritative. For **1017716** and **1017718**, no matching job id was found under `outputs/` in this checkout; logs under `logs/slurm/` named by job id were also absent — purpose is inferred **only from `sacct` `JobName`** (`l1-loss-dec-best-sel`).
3. **Freshness:** **1018203** was still **`RUNNING`** at audit time (**~1 h 30 min** elapsed on node `n0006`). Metrics for that job are therefore **partial / provisional** (`run_env.log` + live `logs/slurm/main3_vs_best3_100_1018203.out`).
4. **`sacct` retention:** Older jobs outside Slurm accounting windows would not appear; this audit only reflects what **`sacct`** returned during the audit run.
5. **Path-gap metrics:** `path_gap_summary.json` explicitly states proxy / diagnostic caveats — not claim-safe as “observed gold path” evidence.

## Summary table (10 jobs, newest submit first)

| JobID   | JobName (sacct)           | State     | ExitCode | Elapsed  | Submit (UTC)        | End (UTC)           | Primary output / notes |
|---------|---------------------------|-----------|----------|----------|---------------------|---------------------|-------------------------|
| 1018287 | gapdiag-88-abs            | COMPLETED | 0:0      | 00:00:06 | 2026-05-02T17:59:57 | 2026-05-02T18:00:04 | `outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/` |
| 1018285 | gapdiag-88-abs            | COMPLETED | 0:0      | 00:00:06 | 2026-05-02T17:58:20 | 2026-05-02T17:58:29 | `outputs/gold_absent_path_gap_diagnostic_20260502T215820Z/` |
| 1018248 | scorefill-88-losses       | COMPLETED | 0:0      | 00:15:20 | 2026-05-02T17:38:34 | 2026-05-02T17:53:55 | Score completion + selector rerun dirs (see §4) |
| 1018219 | fullpipe-88-losses        | COMPLETED | 0:0      | 00:24:31 | 2026-05-02T17:06:10 | 2026-05-02T17:30:42 | `outputs/full_pipeline_best_selector_on_88_external_losses_20260502T210610Z/` |
| 1018203 | main3-vs-best3-100       | RUNNING   | —        | ~01:30+  | 2026-05-02T16:38:50 | Unknown             | `outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/` (in progress) |
| 1017718 | l1-loss-dec-best-sel      | COMPLETED | 0:0      | 00:37:30 | 2026-05-01T20:46:38 | 2026-05-01T21:24:09 | Output dir not linked from `outputs/` by job id in this tree |
| 1017716 | l1-loss-dec-best-sel      | FAILED    | 1:0      | 00:02:00 | 2026-05-01T20:39:22 | 2026-05-01T20:41:23 | Same as above; failed early |
| 1016482 | selector_33               | COMPLETED | 0:0      | 00:00:51 | 2026-04-30T17:24:45 | 2026-04-30T17:25:37 | `outputs/selector_on_gold_present_losses_20260430T211700Z/` |
| 1016461 | trace_loss_retry          | COMPLETED | 0:0      | 02:25:23 | 2026-04-30T16:46:18 | 2026-04-30T19:11:42 | `outputs/trace_complete_external_losses_retry_20260430T204900Z/` |
| 1016416 | best_on_losses            | COMPLETED | 0:0      | 00:00:18 | 2026-04-30T15:56:40 | 2026-04-30T15:56:59 | `outputs/best_methods_on_external_losses_20260430T195200Z/` |

### Failed / pending

- **1017716:** **FAILED**, `ExitCode 1:0` — rapid failure (~2 min); no Slurm `%j` logs matching this id found under `logs/slurm/`.
- **1018203:** **RUNNING** at audit (`squeue ST=R`) — outcome and final `summary.json` **pending**.
- **All other eight:** **COMPLETED** with **`0:0`** exit codes in `sacct -X`.

### Successful completed jobs

1018287, 1018285, 1018248, 1018219, 1017718, 1016482, 1016461, 1016416.

## Per-job detail

### 1018287 — gold-absent path-gap diagnostic (preferred second bundle)

- **Batch script (from `batch_submission_info.json`):** `batch/run_gold_absent_path_gap_diagnostic_wulver.sbatch`
- **Stdout / stderr:** `logs/slurm/gold_absent_path_gap_diagnostic_1018287.{out,err}` (stderr **empty**)
- **Output dir:** `outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/`
- **Purpose:** Path-gap diagnostic on **88** external-loss cases; uses `previous_run_dir` = fully score-completed selector run; **tightened premature-commit heuristic** vs 1018285 (see metrics).
- **Key metrics** (`path_gap_summary.json`): `gold_absent_cases=66`, `total_88_cases=88`, `count_premature_commit=15` (vs **66** in 1018285 run), `count_insufficient_depth=7`, `actual_paid_api_calls=0`, **`caveat`** field: proxy diagnostics only.
- **Claim-safety:** **Diagnostic / not claim-safe** for causal “why we lost” claims without the caveat.

### 1018285 — gold-absent path-gap diagnostic (first bundle)

- **Batch script:** Same `batch/run_gold_absent_path_gap_diagnostic_wulver.sbatch`
- **Logs:** `logs/slurm/gold_absent_path_gap_diagnostic_1018285.{out,err}` (stderr **empty**)
- **Output dir:** `outputs/gold_absent_path_gap_diagnostic_20260502T215820Z/`
- **Key metrics** (`path_gap_summary.json`): `count_premature_commit=66` (prior heuristic), otherwise same framing as 1018287; **`caveat`** identical.
- **Claim-safety:** **Diagnostic.**

### 1018248 — verifier score completion + fully scored selector rerun

- **Batch script (`batch_submission_info.json`):** `batch/run_full_score_completion_on_88_external_losses_wulver.sbatch`
- **Logs:** `logs/slurm/full_score_completion_88_external_losses_1018248.{out,err}` (stderr **empty**)
- **Output dirs:**
  - `outputs/full_score_completion_88_external_losses_20260502T213834Z/`
  - `outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/` (final selector rerun)
- **Purpose:** Fill missing verifier scores used by cached selector scores; rerun selector evaluation on **88** cases.
- **Key metrics** (final `summary.json`): `total_cases=88`, `evaluated_cases=88`, **`correct_count=19`**, **`wrong_count=69`**, **`missing_score_count=0`**, **`fallback_due_to_missing_score_count=0`**, **`selected_candidate_not_in_pool_count=0`**, `gold_absent_count=66`, `discovery_failure_count=66`, `selector_recoverable_count=22`, `expected_api_calls=134`, `actual_api_calls=134`, **`api_error_count=5`**, `parse_error_count=0`.
- **`score_merge_report.json`:** `new_score_count=134`, `missing_after_merge_count=0`, `parse_error_count=0`, `api_error_count=5`.
- **`comparison_vs_previous_run.json`:** All **88** cases **unchanged** vs pre-merge (`cases_newly_fixed_after_score_completion=0`, `cases_became_wrong_after_score_completion=0`) — scores were backfilled but **decisions did not move**.
- **Claim-safety:** **Claim-safe for “merge completed without missing scores”** given artifacts; **not** a broad accuracy claim — still the **selected 88-loss subset** with documented gold policy in `summary_report.md` / `manifest.json`.

### 1018219 — full pipeline + best selector on 88 external-loss cases

- **Batch script:** `batch/run_full_pipeline_best_selector_on_88_external_losses_wulver.sbatch`
- **Logs:** `logs/slurm/full_pipeline_best_selector_on_88_external_losses_1018219.{out,err}` (stderr **empty**)
- **Output dir:** `outputs/full_pipeline_best_selector_on_88_external_losses_20260502T210610Z/`
- **Discovery sidecar:** `outputs/cohere_real_model_cost_normalized_validation_20260502T210610Z_DISCOVERY/`
- **Key metrics** (`summary.json`): same **19 / 69** split on 88 cases; **`missing_score_count=134`** (paired with **`fallback_due_to_missing_score_count=81`** in this pre–score-fill run), `api_call_count=0` (cache-only scoring path as recorded).
- **Claim-safety:** **`summary_report.md`** states subset evaluation and evaluation-only gold — **claim-safe only with those constraints**.

### 1018203 — main3 external vs best3 internal (100 cases / method, in progress)

- **Batch script:** `batch/run_main3_external_vs_best3_internal_100case_wulver.sbatch`
- **Logs:** `logs/slurm/main3_vs_best3_100_1018203.{out,err}` (stderr **empty** at audit)
- **Output dir (from `run_env.log`):** `outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/`
- **Observed progress:** Runner stage underway (Cohere `gsm8k`, budget **6**, multiple external/internal methods); **final `summary.json` already present from an earlier checkpoint** lists `status: ok` but **best_* accuracies 0.0** — treat as **intermediate until job finishes** (downstream aggregation may overwrite).
- **Claim-safety:** **Pending — do not quote final headline metrics until COMPLETED.**

### 1017718 / 1017716 — `l1-loss-dec-best-sel` (L1 loss decomposition / best-selector pair batch)

- **Batch script:** **Unknown in this checkout** (no `%j` logs under `logs/slurm/`, no `submitted_job_id` match under `outputs/`).
- **`sacct`:** 1017718 **COMPLETED** `0:0` (~37.5 min); 1017716 **FAILED** `1:0` (~2 min) — likely a quick retry after failure.
- **Likely script family:** `scripts/run_l1_loss_decomposition_for_best_selector.py` (see repo), but **not verified** to these job IDs.
- **Claim-safety:** **Historical / provenance incomplete** until logs or output dirs are joined to IDs.

### 1016482 — selector on gold-present losses (33 cases)

- **Batch script (from `#SBATCH` in repo):** `jobs/run_selector_on_gold_present_losses_wulver_20260430T211700Z.sbatch`
- **Logs:** `logs/selector_33_1016482.out`, `logs/selector_33_1016482.err` (stderr **empty**)
- **Output dir:** `outputs/selector_on_gold_present_losses_20260430T211700Z/` (`stdout` references `docs/SELECTOR_ON_GOLD_PRESENT_LOSSES_*.md`)
- **Claim-safety:** **Diagnostic slice** (33-case gold-present losses).

### 1016461 — trace-complete retry for external losses (budgeted toward 200)

- **Batch script:** `jobs/run_trace_complete_external_losses_200_wulver_retry_20260430T204900Z.sbatch`
- **Logs:** `logs/trace_loss_retry_1016461.{out,err}` (stderr **empty**)
- **Output dir:** `outputs/trace_complete_external_losses_retry_20260430T204900Z/`
- **Key metrics** (`trace_complete_loss_summary.json`): **16** trace-complete cases collected (target 200; **0** newly generated in this run’s summary), regime **selector_failures**.
- **Claim-safety:** **Diagnostic / lineage** — important for merging traces into later path-gap summaries (`merged_jsonl_paths` in gap diagnostics cite this bundle).

### 1016416 — best methods baseline on external losses (88-case setup)

- **Batch script:** `jobs/run_best_methods_on_external_losses_100_wulver_20260430T195200Z.sbatch`
- **Logs:** `logs/best_on_losses_1016416.{out,err}` (stderr **empty**)
- **Output dir:** `outputs/best_methods_on_external_losses_20260430T195200Z/`
- **Key metrics** (`best_methods_external_loss_summary.json`): **88** selected cases; **`external_l1_max` accuracy ~0.1932** on that slice; `discovery_failure_count=66`, `selector_recoverable_count=22` (consistent with downstream 88-loss story).
- **Claim-safety:** **Subset methodology** — see summary JSON fields and later `manifest.json` in downstream runs.

## Outputs worth revisiting later

- **88-loss pipeline:** `outputs/full_pipeline_best_selector_on_88_external_losses_20260502T210610Z/summary.json`, `summary_report.md`, `manifest.json`, `run_config.json`
- **Score fill + rerun:** `outputs/full_score_completion_88_external_losses_20260502T213834Z/score_merge_report.{json,md}`, `outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/comparison_vs_previous_run.json`
- **Path gap:** `outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/path_gap_summary.json`, `path_gap_report.md` (preferred **8287**)
- **Long benchmark (when done):** `outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/summary.json` (verify after **1018203** COMPLETED)

## Interpretation (what the recent jobs show together)

The **most recent slab of work on 2026-05-02** is a coherent chain: (**1018219**) run the discovery + cached-selector evaluation on the **same 88 external-loss IDs** surfaced from the **April 30** baseline (**1016416**) and trace lineage (**1016461**); (**1018248**) prove the missing verifier scores were **mergeable** and **eliminated fallbacks**, without changing correctness counts on that slice (**comparison_vs_previous_run**); (**8285 → 8287**) iterate **gold-absent path-gap proxy classification**, chiefly tightening **`count_premature_commit`** from **66 → 15** while keeping explicit **non–claim-safe** caveat text. Separately (**1018203**), a **100×100** external-vs-internal GSM8k comparison was **still running**, so its headline numerical story is **not final** yet.

## Claim-safety caveats

1. **`path_gap_*` artifacts:** Explicitly labeled **proxies**, not reconstructed gold reasoning paths (`path_gap_summary.json` caveat field).
2. **88-loss runs:** Repeatedly flagged as **subset / evaluation-only gold** in `summary_report.md` — do not extrapolate to full-test or external-baseline dominance without separate runs.
3. **Selector score merge:** **`api_error_count=5`** on score completion — investigate `completed_verifier_scores.jsonl` / logs if asserting **zero verifier noise** beyond JSON summaries.
4. **Missing linkage for L1 decomposition jobs (**1017716/1017718**):** **Do not cite** unpublished paths/metrics tied to those IDs until stdout/stderr or `outputs/` reference is recovered.
