# Local-only cleanup candidates (do **not** auto-delete — 2026-05-02)

This memo lists artifact **categories commonly safe to prune on a workstation** after confirming **nothing references paths literally in docs.** **No deletion executed** in authoring pass — **preserve scientific provenance** on shared storage unless storage policy dictates otherwise.

Read **`docs/OUTPUT_RETENTION_POLICY_CURRENT.md`** before removing anything intentionally committed historically.

---

## Candidate categories

| Category | Typical locations | Typical Git state |
|---------|-------------------|-------------------|
| **Slurm transcripts** | `logs/slurm/*.out`, `logs/slurm/*.err`, `monitor_*.jsonl` | Untracked (should stay that way) |
| **Ignored JSONL rivers** | `outputs/**/*.jsonl` per `.gitignore` | Ignored (**`!!`** in scoped `git status --ignored`) |
| **Runner environment dumps** | `run_env.log`, `runner_stdout_stderr.log` cluster copies | Ignored (`*.log` / policy) |
| **Raw validation subtrees** | `outputs/cohere_real_model_*` without committed curated CSV subset | Mixed untracked/ignored |
| **Preflight / scratch trees** | `*_PRECHECK`, `*_PREFLIGHT*`, stale duplicate timestamps superseded elsewhere | Untracked |
| **Developer caches / `__pycache__`** | Under `experiments/` or `scripts/` | Ignored |

**Warning:** delete only paths **duplicate or superseded** by committed summaries **and unreferenced**. When uncertain, **`tar` archive** locally before delete.

---

## Inspection command pack

Survey ignored + junk candidates without mutating repo:

```bash
git status --ignored --short outputs logs/slurm
git status --short outputs logs/slurm
```

Optional size triage (**safe read-only**):

```bash
du -sh outputs/cohere_real_model_* 2>/dev/null | sort -h | tail
```

---

## Editorial note

Deleting timestamped **`outputs/`** directories is **out of scope** for routine doc polish—they remain **immutable provenance** even if inconveniently large — coordinate with **`docs/REPO_ORGANIZATION_GUIDE_20260501.md`** admins.
