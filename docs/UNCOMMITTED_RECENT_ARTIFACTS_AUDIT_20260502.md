# Uncommitted recent artifacts audit — adaptive-reasoning-budget-allocation

**Audit UTC timestamp:** `2026-05-02T22:55:51Z`

## Repository state at audit

| Field | Value |
|------|-------|
| **Branch** | `main` |
| **`HEAD`** | `21186a189b866e3034b3ac51aff763db0af488b8` |
| **Remote sync** | `main` aligned with **`origin/main`** at audit time (**no unpublished commits**) |

## Outputs and logs inspected

| Artifact / job | Paths |
|----------------|-------|
| **1018203** main3-vs-best3 (100 GSM8K / method, budget **6**) | `outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/`, `logs/slurm/main3_vs_best3_100_1018203.{out,err}` |
| **1018304** strategy-seeded discovery on **66** gold-absent diagnostic | `outputs/strategy_seeded_discovery_on_66_gold_absent_20260502T222129Z/`, `logs/slurm/strategy_seeded_discovery_66_gold_absent_1018304.{out,err}` |
| **1018248** score completion + rerun | `outputs/full_score_completion_88_external_losses_20260502T213834Z/`, `outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/`, matching Slurm logs |
| **1018287** path-gap diagnostic | `outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/` |
| Last-10 Wulver audit bundle | `outputs/last_10_wulver_jobs_audit_20260502T220857Z/`, `docs/LAST_10_WULVER_JOBS_AUDIT_20260502.md` |
| **Strategy-seeded final check / preflight** (newer **`20260502T22*`) | `outputs/strategy_seeded_discovery_final_check_20260502T225251Z/` (tracked curated subset); `outputs/strategy_seeded_discovery_final_check_TESTPREFLIGHT_20260502T224848Z/`; `scripts/run_strategy_seeded_discovery_final_check.py`; `batch/run_strategy_seeded_discovery_final_check_wulver.sbatch` |
| Loose cohere validation drops | **Untracked** small `method_validation_report.csv` under `outputs/cohere_real_model_cost_normalized_validation_20260502T222126Z/` and `...224859Z/`; **`outputs/cohere_real_model_cost_normalized_validation_FINCHK_20260502T225251Z/`** present on disk **fully ignored** (raw JSONL + `raw/`). |

Machine-readable bundle: **`outputs/uncommitted_recent_artifacts_audit_20260502T225551Z/`**.

---

## 1. Which new/recent files are untracked or ignored?

### Untracked (representative rows)

Paths under **`logs/slurm/*.out|.err|.jsonl`**, **`outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/*`** summaries not yet **`git add`ed**, plus small **standalone** **`method_validation_report.csv`** files in two **`cohere_real_model_*_20260502T22*_validation_*`** dirs. See **`outputs/uncommitted_recent_artifacts_audit_20260502T225551Z/untracked_files.csv`**.

### Ignored (`git status --ignored` + `git check-ignore -v`)

| Category | Typical paths | Typical `.gitignore` driver |
|-----------|---------------|------------------------------|
| **Per-case JSONL** | `per_case_*`, verifier caches | `outputs/**/*.jsonl` (+ targeted `per_example_records.jsonl`) |
| **Environment / runner dumps** | `run_env.log`, `runner_stdout_stderr.log` | `*.log` |
| **Embedded cohere RAW trees** under ignored parents | **`outputs/cohere_real_model_cost_normalized_validation_FINCHK_20260502T225251Z/`** | `outputs/*` umbrella + **`per_example_records.jsonl`** rule |

See **`ignored_files.csv`** with full `git check-ignore -v` text.

---

## 2. Which are intentionally not committed?

### Policy-aligned “local-only” (by design)

- **Raw Slurm `logs/slurm/*`** — large, noisy, environment-specific; superseded by `manifest.json` + committed summaries.
- **`.jsonl` case streams**, **`run_env.log`**, **`runner_stdout_stderr.log`**, **`*_stdout.log` sidecars** — size + potential path noise; **`outputs/**/*.jsonl`** excludes by default unless explicitly exempted (`missing_score_call_plan.jsonl`, `monitor_log.jsonl` exemptions exist for curated diagnostics only).
- **Ignored FINCHK validation tree** — redundant with summarized CSVs committed elsewhere (`strategy_seeded` bundle cost-normalization subtree); **`per_example_records.jsonl`** policy.

### Accidentally stale doc language (prior audit freeze)

Prior docs listed **1018203** as *running*. **`summary.json` now `status:"ok"`** with nonzero headline accuracies (**see §6**).

---

## 3. Recommended to commit as small summaries / code artifacts

Already on **`origin/main`** for **1018304**, **1018248**, **1018287**, **last_10_audit**, **`strategy_seeded_discovery_final_check_*` curated subsets**: those directories show extensive **`git ls-files`** hits.

**Newly recommended (missing at audit `HEAD`):** small **job 1018203** summary package only:

```
outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/summary.json
outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/summary.csv
outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/comparison_report.md
outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/comparison_table.csv
outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/method_level_metrics.csv
outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/manifest.json
outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/README.md
```

Plus this audit doc **`docs/UNCOMMITTED_RECENT_ARTIFACTS_AUDIT_20260502.md`** and bundle **`outputs/uncommitted_recent_artifacts_audit_20260502T225551Z/*`** (CSV/TXT/MD).

Secret scan (**`grep -R -n -i` keyword sweep**): only benign CSV header substring hits (`*_tokens_*` columns); **`command.sh`** / manifests — **clean**.

Optional **not defaulted:** untracked **`command.sh`** and **`monitor_log.txt`** (**not** `.log` suffix rule) remain small provenance aids but were **out-of-scope for default commit**.

---

## 4. Recommended to remain local-only

| Bucket | Paths / patterns | Reasons |
|--------|-------------------|---------|
| **Large / line-oriented** | `per_case_results.jsonl`, verifier JSONL blobs, **`cohere_*FINCHK*` tree** | Hundreds of KB–MB+, reproducible derived tables exist as CSV summaries |
| **Logs / dumps** | `run_env.log`, `runner_stdout_stderr.log`, **`slurm_discovery_stdout.log`** | **`*.log` ignore**; paths + partial env snapshots |
| **Raw Slurm** | **`logs/slurm/*1018203*`, `*1018304*`, adjacent job logs** | Transient scheduling noise |
| **Redundant duplicates** | second-stage **`cohere_*method_validation_report.csv`** without manifest tie-in | Thin slices; superseded by fuller bundle summaries already tracked |
| **Risk if forced** | Forcing JSONL **`git add -f`** | Violates deliberate `.gitignore` contracts unless reviewed |

---

## 5. Important latest results vs GitHub `main`

| Item | On `origin/main` at **`21186a1`**? | Gap |
|------|-------------------------------------|-----|
| **1018203 headline CSV/JSON/MD** bundle | **No** (**entire output dir previously untracked**) | Needed small curated commit |
| **1018304** discovery bundle | **Yes** (dense `git ls-files` coverage incl. summaries, comparison vs DR‑v2) | Raw JSONLs still ignored **by policy** |
| **1018248** score merge + rerun | **Yes** summaries; large JSONLs ignored | Matches policy |
| **1018287** path-gap diagnostic | **Yes** summarized artifacts | JSONLs + `run_env.log` ignored |
| **last_10 Wulver audit** | **Yes** tracked | Doc still referenced **RUNNING** for **1018203** — needs text refresh |

---

## 6. Job **1018203** — main3-vs-best3 (artifact sense)

Completion evidence: **`outputs/...203851Z/summary.json`**:

- **`status`** = **`ok`**, **`timestamp_utc`** **`2026-05-02T22:36:41Z`**
- **`dataset`** **`openai/gsm8k`**, **`target_cases_per_method`** **100**, **`budget`** **6**, **`seed`** **`20260501`**
- **Headline deltas:** **`best_external_method`** **`external_l1_max`** @ **0.92**; **`best_internal_method`** **`strict_gate1_cap_k6`** @ **0.57**; gap **`best_internal_minus_best_external`** ≈ **-0.35**

**Interpretation caveat (explicit):**

- Narrow **100-case** diagnostic slice (**not** a universal GSM8k claim surface).
- Strengthens *bounded* narrative that curated **best internal strict_gate1_cap_k6** headline on this pairing **trails **`external_l1_max`** materially** vs prior cache-limited stories — still **subset-scoped**.
- Companion runner output reference: `runner_output_dir` → `outputs/cohere_real_model_cost_normalized_validation_20260502T203851Z/` (**distinct timestamp**; inspect separately if reproducibility chaining required).

Ignored heavy artifacts retained locally: **`per_case_results.jsonl`, `runner_stdout_stderr.log`, `run_env.log`**.

---

## 7. Job **1018304** — strategy-seeded discovery (66-case gold-absent pilot)

Tracked curated bundle already present (`discovery_summary.{json,csv}`, `comparison_vs_dr_v2.{json,md}`, **`summary_report.md`**, manifests, **`per_case_*.csv`**, trimmed cohere **`SSDFV1` CSV summaries**).

**`discovery_summary.json` highlights:**

- **`new_method`** **`strategy_seeded_semantic_diversity_frontier_v1`**
- **Gold-presence deltas vs cached DR‑v2 (`baseline_*` ↔ `new_*`):** **`baseline_gold_present_count` 49**, **`new_gold_present_count` 42**

**Interpretation caveat (explicit):**

- Treat as **diagnostic pilot** on **`66`** intentional gold-absent pool — **baseline alignment / implementation QA** debates remain unresolved.
- **`paid_api_call_count_total`:** **0** in summary JSON (**cache-only path** semantics as recorded).

---

## 8. Latest headline summaries already committed?

| Job / bundle | HEADline JSON/CSV/MD on GitHub? |
|--------------|----------------------------------|
| **1018304** (**66-case**) | **Yes** (**already tracked**) |
| **1018203** (**100-case**) | **No** (**pending commit**) |
| **`last_10` audit CSV/JSON/MD** | **Yes** |
| **`strategy_seeded_discovery_final_check_20260502T225251Z`** core audit subset | **Yes** (**JSONLs like `monitor_log.jsonl`, `allowed_cases*.jsonl` intentionally omitted**) |

---

## 9. Doc updates triggered

Stale statements removed/updated (`START_HERE_CURRENT.md`, `CURRENT_PROJECT_STATUS.md`) where they still asserted **1018203 incomplete**.

**LAST_10 audit:** appended **Post-freeze addendum** (completion + **`1018304`** omission note).

**`ARTIFACT_STATUS_TABLE.md`:** add rows for **`main3_external_*203851Z`** + **`strategy_seeded_discovery_on_66_gold_*222129Z`**.

---

## 10. Verification commands

See **`outputs/uncommitted_recent_artifacts_audit_20260502T225551Z/commands_used.txt`** (verbatim log).
