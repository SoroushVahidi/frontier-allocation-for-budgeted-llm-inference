# Output retention and Git commit policy (current)

Conservative **`outputs/` ↔ Git** contract aligned with `.gitignore` today. Goal: reviewers clone **summaries without multi‑MB caches**, cluster operators keep **heavy JSONL** locally.

Interpretation buddies: **`docs/ARTIFACT_STATUS_TABLE.md`**, **`docs/UNCOMMITTED_RECENT_ARTIFACTS_AUDIT_20260502.md`**, **`docs/LOCAL_ONLY_CLEANUP_CANDIDATES_20260502.md`**.

---

## Commit normally (tracked categories)

Unless an experiment explicitly forbids versioning:

| Category | Examples |
|----------|-----------|
| **Current docs / navigation** | `docs/*.md` promoted in **`DOCS_INDEX.md`** |
| **Runnable glue** | `scripts/*.py` entrypoints, **`experiments/*.py`**, **`batch/*.sbatch`** |
| **Curated summaries** | `summary.json` / `.csv`; `*_summary.json` / `.csv`; `comparison_*.json` / `.md` / `.csv` |
| **Reports / manifests / configs per bundle** | `*_report.md`, `comparison_report.md`, `manifest.json`, `run_config.json`, small `README.md` |
| **Repro breadcrumbs** | `batch_submission_info.json`; **`command.sh`**; **small monitor logs** (**`.txt`**) — **after** secret scan (**no API keys**, no bearer tokens, no pasted env dumps) |

`.gitignore` already **whitelist‑un‑ignores** many `**/summary*` and `**/discovery_summary*` paths—prefer named summary files inside timestamped dirs.

---

## Do **not** commit by default

| Bucket | Typical patterns |
|--------|-------------------|
| **Line/stream dumps** | `*.jsonl` per-case grids, verifier score streams, **`per_example_records.jsonl`**, **`progress_heartbeat.jsonl`** |
| **Caches** | any `*cache*.json(l)` under `outputs/`, verifier annotation caches listed in `.gitignore` |
| **Environment / runner blobs** | `run_env.log`, `runner_stdout_stderr.log`, bulky `*_stdout.log` |
| **`logs/slurm/*`** | raw `%j.{out,err}` cluster transcripts |
| **Large per-example raw payloads** | cohere raw subtrees, multi‑MB CSV unless explicitly curated |
| **Secrets** | anything containing API keys — **never** `git add -f` blindly |

Whole timestamped dirs should **almost never** be force-added wholesale.

---

## When **`git add -f`** is acceptable

Only if **all** hold:

1. **Single small file**, human‑reviewed.
2. Legitimately `.gitignored` umbrella (`outputs/*`) conflicts with explicit summary need.
3. **Passes** `.gitignore` intent (not JSONL caches / logs).
4. **Recorded** rationale in an audit or doc footer if recurrent.

Prefer adjusting `.gitignore` with narrowly scoped **`!`** rules when a **class** of summaries should recur.
