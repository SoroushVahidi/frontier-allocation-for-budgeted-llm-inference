#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

FOCUS_PREFIXES = [
    "outputs/external_loss_casebook_20260430T184023Z/",
    "outputs/external_loss_casebook_broad_20260430T185500Z/",
    "outputs/large_selector_tournament_20260430T182316Z/",
    "outputs/l1_defeat_selector_wulver_20260430T182316Z/",
    "logs/loss_casebook_200_1016382.",
    "logs/loss_casebook_broad_",
]

EXPLICIT_CHECKS = [
    "outputs/external_loss_casebook_broad_20260430T185500Z/loss_summary.json",
    "outputs/external_loss_casebook_broad_20260430T185500Z/loss_summary.md",
    "outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_combined_200.csv",
    "outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_combined_200.jsonl",
    "outputs/external_loss_casebook_broad_20260430T185500Z/cohere_annotation_cache.jsonl",
    "outputs/large_selector_tournament_20260430T182316Z/selector_tournament/selector_summary.csv",
    "outputs/large_selector_tournament_20260430T182316Z/selector_tournament/selector_summary.json",
]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)


def bytes_h(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.1f}{u}"
        x /= 1024
    return f"{n}B"


def classify(path: str) -> str:
    p = path.lower()
    if "__pycache__" in p or p.endswith(".pyc"):
        return "cache"
    if p.startswith("logs/") or ".log" in p:
        return "log"
    if "cache" in p:
        return "cache"
    if "per_example_records" in p:
        return "per_example_records"
    if "casebook" in p and p.endswith(".jsonl"):
        return "raw_casebook"
    if (p.endswith(".json") or p.endswith(".csv") or p.endswith(".md")) and any(k in p for k in ["summary", "report", "artifact_scan"]):
        return "summary_or_report"
    if "selector" in p:
        return "selector_output"
    if "loss_casebook" in p:
        return "loss_casebook_output"
    if "discovery" in p:
        return "discovery_output"
    if p.startswith("jobs/") and p.endswith(".sbatch"):
        return "wulver_job_file"
    return "unknown"


def importance(path: str, size_bytes: int, category: str) -> str:
    p = path.lower()
    if "__pycache__" in p or p.endswith(".pyc"):
        return "low"
    if category == "summary_or_report" and size_bytes <= 2_000_000:
        return "high"
    if category in {"cache", "log", "raw_casebook", "per_example_records"}:
        return "low"
    if size_bytes > 20_000_000:
        return "low"
    if category in {"selector_output", "loss_casebook_output", "discovery_output", "unknown"}:
        return "medium"
    return "medium"


@dataclass
class Row:
    path: str
    size_bytes: int
    mtime_utc: str
    ignore_rule: str
    category: str
    likely_importance: str
    focus_match: int


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "outputs" / f"ignored_unpushed_audit_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    sync_status = {
        "status_short": run(["git", "status", "--short"]).stdout.strip(),
        "head": run(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "origin_main": run(["git", "rev-parse", "origin/main"]).stdout.strip(),
        "status_ignored_short": run(["git", "status", "--ignored", "--short"]).stdout,
    }

    ignored = run(["git", "ls-files", "--others", "-i", "--exclude-standard"]).stdout.splitlines()
    rows: list[Row] = []
    for rel in sorted(set([x.strip() for x in ignored if x.strip()])):
        p = REPO_ROOT / rel
        if not p.exists() or p.is_dir():
            continue
        st = p.stat()
        chk = run(["git", "check-ignore", "-v", rel]).stdout.strip()
        rule = chk.split("\t")[0] if chk else ""
        cat = classify(rel)
        imp = importance(rel, st.st_size, cat)
        focus = int(any(rel.startswith(pref) for pref in FOCUS_PREFIXES))
        rows.append(
            Row(
                path=rel,
                size_bytes=st.st_size,
                mtime_utc=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                ignore_rule=rule,
                category=cat,
                likely_importance=imp,
                focus_match=focus,
            )
        )

    # full csv
    full_csv = out_dir / "ignored_files_full.csv"
    with full_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "path",
                "size_bytes",
                "mtime_utc",
                "ignore_rule",
                "category",
                "likely_importance",
                "focus_match",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(r.__dict__)

    # summary by category
    by_cat_count = Counter(r.category for r in rows)
    by_cat_size = defaultdict(int)
    for r in rows:
        by_cat_size[r.category] += r.size_bytes
    sum_csv = out_dir / "ignored_files_summary_by_category.csv"
    with sum_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["category", "file_count", "total_size_bytes", "total_size_human"])
        w.writeheader()
        for c in sorted(by_cat_count):
            w.writerow(
                {
                    "category": c,
                    "file_count": by_cat_count[c],
                    "total_size_bytes": by_cat_size[c],
                    "total_size_human": bytes_h(by_cat_size[c]),
                }
            )

    high_rows = [r for r in rows if r.likely_importance == "high"]
    high_csv = out_dir / "high_importance_ignored_files.csv"
    with high_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["path", "size_bytes", "mtime_utc", "ignore_rule", "category", "likely_importance", "focus_match"])
        w.writeheader()
        for r in sorted(high_rows, key=lambda x: (x.focus_match * -1, x.path)):
            w.writerow(r.__dict__)

    explicit = {}
    for p in EXPLICIT_CHECKS:
        c = run(["git", "check-ignore", "-v", p])
        explicit[p] = c.stdout.strip() if c.stdout.strip() else "TRACKABLE (no ignore match)"

    docs_untracked = run(["git", "ls-files", "--others", "--exclude-standard", "docs"]).stdout.splitlines()
    docs_untracked = [d for d in docs_untracked if d.strip()]

    add_force_lines = [f"git add -f \"{r.path}\"" for r in high_rows if r.path.startswith(("outputs/", "logs/", "archive/"))]

    report = out_dir / "ignored_unpushed_audit_report.md"
    report.write_text(
        "\n".join(
            [
                "# Ignored/Unpushed Artifact Audit",
                "",
                f"- generated_at_utc: {datetime.now(timezone.utc).isoformat()}",
                f"- head: `{sync_status['head']}`",
                f"- origin_main: `{sync_status['origin_main']}`",
                f"- head_equals_origin_main: `{sync_status['head'] == sync_status['origin_main']}`",
                f"- ignored_file_count: `{len(rows)}`",
                f"- total_ignored_size: `{bytes_h(sum(r.size_bytes for r in rows))}`",
                "",
                "## Counts By Category",
                "",
            ]
            + [f"- {c}: {by_cat_count[c]} files, {bytes_h(by_cat_size[c])}" for c in sorted(by_cat_count)]
            + [
                "",
                "## Focus Directory Snapshot",
                "",
            ]
            + [f"- {p}: {sum(1 for r in rows if r.path.startswith(p))} ignored files" for p in FOCUS_PREFIXES]
            + [
                "",
                "## Explicit `git check-ignore -v` Checks",
                "",
            ]
            + [f"- `{k}` -> `{v}`" for k, v in explicit.items()]
            + [
                "",
                "## High-Importance Ignored Files",
                "",
            ]
            + ([f"- `{r.path}` ({bytes_h(r.size_bytes)})" for r in high_rows[:100]] if high_rows else ["- none"])
            + [
                "",
                "## Recommended Keep Ignored",
                "",
                "- `*.jsonl` raw casebooks/per-example traces/caches",
                "- verifier/cohere cache files",
                "- large logs and bulky raw artifacts",
                "",
                "## Recommended Consider Tracking",
                "",
                "- lightweight summary/report artifacts currently ignored",
                "- focus run summaries if they support paper/repo decisions",
                "",
                "## `docs/` Untracked/Unpushed Check",
                "",
                f"- untracked_docs_count: `{len(docs_untracked)}`",
            ]
            + ([f"- `{d}`" for d in docs_untracked[:50]] if docs_untracked else ["- none"])
            + [
                "",
                "## Optional `git add -f` Commands (not executed)",
                "",
            ]
            + (add_force_lines[:200] if add_force_lines else ["- none"])
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"out_dir": str(out_dir), "ignored_count": len(rows), "high_count": len(high_rows)}, indent=2))


if __name__ == "__main__":
    main()
