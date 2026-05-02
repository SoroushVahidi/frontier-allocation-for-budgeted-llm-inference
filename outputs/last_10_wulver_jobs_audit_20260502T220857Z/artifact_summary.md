# Last-10 Wulver jobs audit bundle — artifact summary

**Audit doc (human-readable):** `docs/LAST_10_WULVER_JOBS_AUDIT_20260502.md`
**UTC bundle timestamp:** 20260502T220857Z

## Purpose

Record the **last 10 Slurm jobs** with `WorkDir=/mmfs1/home/sv96/adaptive-reasoning-budget-allocation`: job ids, schedules, stdout/stderr hints, pointers to bounded output summaries, and **claim-safety** classification — without deleting or rewriting any timestamped experiment outputs.

## Job IDs covered (newest submit first)

1018287, 1018285, 1018248, 1018219, 1018203, 1017718, 1017716, 1016482, 1016461, 1016416

## Files in this bundle (`outputs/last_10_wulver_jobs_audit_20260502T220857Z/`)

| File | Role |
|---|---|
| `last_10_jobs.csv` | Machine-readable one row per job |
| `last_10_jobs.json` | Same, JSON with selection-rule metadata |
| `audit_report.md` | Snapshot copy of `docs/LAST_10_WULVER_JOBS_AUDIT_20260502.md` at bundle creation |
| `commands_used.txt` | Exact `sacct` / inspection commands echoed for reproducibility |
| `artifact_summary.md` | This file |

## Main conclusion (engineering)

1. **1018248** — After verifier **score completion** and rerun of the cached outcome-verifier selector on the **same 88 external-loss subset**, **`missing_score_count=0`**, **`fallback_due_to_missing_score_count=0`**, and **`comparison_vs_previous_run.json` reports zero correctness flips** vs the pre-merge run. Combined with **`correct_count` / `still_lost_count` unchanged (19 / 69)**, the remaining bottleneck on this slice reads as **discovery / tree coverage**, not unresolved verifier-score gaps.
2. **1018287** — Preferred **gold-absent path-gap proxy** diagnostic (Slurm **`gapdiag-88-abs`**): tightened premature-commit heuristic vs **1018285** (`count_premature_commit` **15** vs **66**); still subject to **`path_gap_summary.json` caveat** (estimates only).
3. **1018203** — **`main3-vs-best3-100`** was **`RUNNING` at audit time**; verify **`sacct` / `summary.json`** before any headline claim tied to final comparison metrics.

## Claim-safety caveats

- **Subset scope:** All 88-loss numbers are tied to **`outputs/best_methods_on_external_losses_20260430T195200Z/`** and downstream manifests — not broad GSM8k or automatic **`external_l1_max`** superiority.
- **Path-gap metrics:** Explicitly **proxy / diagnostic**; do not cite as observed gold reasoning paths (`path_gap_summary.json` includes a `caveat` field).
- **1018248 verifier noise:** **`api_error_count=5`** in summaries — acknowledge if asserting perfect verifier cleanliness.
- **1017716 / 1017718 (`l1-loss-dec-best-sel`):** Job-name–only linkage in tree; stdout under `logs/slurm/` missing — **historical provenance incomplete**.

## Commands to inspect key summaries

```bash
cat outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/summary.json
cat outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/path_gap_summary.json
cat outputs/last_10_wulver_jobs_audit_20260502T220857Z/last_10_jobs.csv
```
