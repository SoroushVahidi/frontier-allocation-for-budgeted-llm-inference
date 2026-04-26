#!/usr/bin/env python3
"""Build a lightweight repository cleanup and anonymity audit."""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _tracked_files() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files"], cwd=REPO, text=True)
    return [REPO / line for line in out.splitlines() if line.strip()]


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    extra = [key for row in rows for key in row if key not in fields]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields + sorted(set(extra)), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO))


def _classify(path: Path) -> str:
    rel = _rel(path)
    name = path.name.lower()
    if rel.startswith(("outputs/paper_tables/", "outputs/paper_plot_data/", "outputs/paper_figures/")):
        return "paper_facing_canonical"
    if rel.startswith("scripts/paper/") or rel in {
        "docs/PAPER_SOURCE_OF_TRUTH.md",
        "docs/SAFE_CLAIMS_FOR_NEURIPS_2026.md",
        "docs/RESULTS_GUIDE.md",
    }:
        return "paper_facing_canonical"
    if rel.startswith("outputs/real_model_ours_vs_external_validation_20260425T_WULVER"):
        return "provenance_only"
    if "wulver" in rel.lower() or "retry_error_log" in name or "api_key_readiness" in name:
        return "provenance_only"
    if any(k in rel for k in ("learned_scorer", "direct_reserve", "cohere_direct_reserve")):
        return "diagnostic_current"
    if rel.startswith(("outputs/real_model_", "outputs/cohere_real_model_", "outputs/bounded_real_")):
        return "appendix_supporting"
    if rel.startswith("outputs/") and any(k in rel.lower() for k in ("failed", "dry", "smoke", "test")):
        return "deprecated_or_failed"
    if rel.startswith(("outputs/", "docs/")) and re.search(r"20\d{6}T|2026[-_]", rel):
        return "provenance_only"
    if rel.startswith(("tests/", "experiments/", "scripts/")):
        return "appendix_supporting"
    if rel.startswith((".cursor/", "terminals/")) or ".venv/" in rel:
        return "local_private_or_should_not_ship"
    return "unknown_needs_review"


def _purpose(path: Path) -> str:
    rel = _rel(path)
    if rel.startswith("docs/"):
        return "documentation/report"
    if rel.startswith("scripts/"):
        return "script/tooling"
    if rel.startswith("tests/"):
        return "test"
    if rel.startswith("outputs/"):
        return "generated artifact"
    if rel.startswith("experiments/"):
        return "library/runtime code"
    return "repository file"


PATTERNS: list[tuple[str, re.Pattern[str], str, str]] = [
    ("email_address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "medium", "scrub unless public citation/contact text"),
    ("local_home_path", re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+/[^\s)\"']*"), "high", "scrub or exclude from anonymous supplement"),
    ("api_key_env_name", re.compile(r"\b(?:OPENAI_API_KEY|COHERE_API_KEY|HF_TOKEN|HUGGINGFACE_HUB_TOKEN)\b"), "low", "keep if only variable name; never include values"),
    ("cursor_url", re.compile(r"https?://[^\\s)\"']*cursor[^\\s)\"']*", re.I), "medium", "exclude private agent links"),
    ("chat_task_url", re.compile(r"https?://[^\\s)\"']*(?:chatgpt|codex|openai)[^\\s)\"']*", re.I), "medium", "exclude private task links"),
    ("wulver_reference", re.compile(r"\bwulver\b|/scratch/[^\s)\"']+|/cluster/[^\s)\"']+", re.I), "medium", "move-to-provenance or exclude from anonymous supplement"),
    ("token_literal", re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{12,}"), "high", "scrub immediately"),
]


def _text_or_none(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:4096]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _inventory(files: list[Path], prefix: str) -> list[dict[str, Any]]:
    rows = []
    for path in files:
        rel = _rel(path)
        if not rel.startswith(prefix):
            continue
        rows.append(
            {
                "path": rel,
                "artifact_class": _classify(path),
                "purpose": _purpose(path),
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "recommendation": _recommendation(_classify(path), rel),
            }
        )
    return rows


def _recommendation(cls: str, rel: str) -> str:
    if cls == "paper_facing_canonical":
        return "keep as canonical source"
    if cls == "diagnostic_current":
        return "keep; label diagnostic-only"
    if cls == "appendix_supporting":
        return "keep as supporting evidence"
    if cls == "provenance_only":
        return "keep for provenance; exclude or scrub for anonymous supplement"
    if cls == "deprecated_or_failed":
        return "keep only if referenced; otherwise consolidate"
    if cls == "local_private_or_should_not_ship":
        return "exclude from anonymous supplement"
    return "review before claim use"


def _identity_scan(files: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in files:
        text = _text_or_none(path)
        if text is None:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name, pattern, severity, rec in PATTERNS:
                if pattern.search(line):
                    rows.append(
                        {
                            "path": _rel(path),
                            "line_number": line_no,
                            "matched_pattern": name,
                            "severity": severity,
                            "recommendation": rec,
                        }
                    )
    return rows


def _duplicates(files: list[Path]) -> list[dict[str, Any]]:
    groups: dict[str, list[str]] = {}
    for path in files:
        rel = _rel(path)
        stem = re.sub(r"20\d{6}T?[A-Z0-9_:-]*|2026[-_]\d{2}[-_]\d{2}", "<timestamp>", rel)
        groups.setdefault(stem, []).append(rel)
    rows = []
    for stem, vals in groups.items():
        if len(vals) < 2:
            continue
        cls = "provenance_only" if any(v.startswith(("docs/", "outputs/")) for v in vals) else "unknown_needs_review"
        rows.append(
            {
                "normalized_name": stem,
                "count": len(vals),
                "artifact_class": cls,
                "paths": ";".join(sorted(vals)[:20]),
                "recommendation": "consolidate interpretation in guide; retain evidence unless clearly duplicate debris",
            }
        )
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = p.parse_args()
    files = _tracked_files()
    out = REPO / "outputs" / f"repository_cleanup_audit_{args.timestamp}"
    out.mkdir(parents=True, exist_ok=True)

    artifact_rows = _inventory(files, "outputs/")
    docs_rows = _inventory(files, "docs/")
    script_rows = _inventory(files, "scripts/")
    test_rows = _inventory(files, "tests/")
    leak_rows = _identity_scan(files)
    duplicate_rows = _duplicates(files)
    counts = Counter(row["artifact_class"] for row in artifact_rows + docs_rows + script_rows + test_rows)
    recommendations = [
        {"topic": "canonical_claims", "recommendation": "Use paper artifacts and paper runner only for headline claims."},
        {"topic": "learned_scorer", "recommendation": "Keep RF/pairwise learned scorer diagnostic-current; HGB should not be recommended."},
        {"topic": "non_math", "recommendation": "Treat Wulver/non-math evidence as provenance-only or appendix-supporting until rerun with domain checks."},
        {"topic": "privacy", "recommendation": "Scrub or exclude high/medium identity-scan findings before anonymous supplement release."},
        {"topic": "cleanup", "recommendation": "Do not delete timestamped evidence; consolidate interpretation in docs first."},
    ]

    _write_csv(out / "artifact_inventory.csv", artifact_rows, ["path", "artifact_class", "purpose", "size_bytes", "recommendation"])
    _write_csv(out / "docs_inventory.csv", docs_rows, ["path", "artifact_class", "purpose", "size_bytes", "recommendation"])
    _write_csv(out / "script_inventory.csv", script_rows, ["path", "artifact_class", "purpose", "size_bytes", "recommendation"])
    _write_csv(out / "test_inventory.csv", test_rows, ["path", "artifact_class", "purpose", "size_bytes", "recommendation"])
    _write_csv(out / "identity_leak_scan.csv", leak_rows, ["path", "line_number", "matched_pattern", "severity", "recommendation"])
    _write_csv(out / "duplicate_or_stale_artifacts.csv", duplicate_rows, ["normalized_name", "count", "artifact_class", "paths", "recommendation"])
    _write_csv(out / "cleanup_recommendations.csv", recommendations, ["topic", "recommendation"])
    (out / "README.md").write_text(
        "\n".join(
            [
                "# Repository cleanup audit",
                "",
                f"- Timestamp: `{args.timestamp}`",
                f"- Tracked files scanned: {len(files)}",
                f"- Identity/private metadata findings: {len(leak_rows)}",
                "- Artifact class counts:",
                *[f"  - `{k}`: {v}" for k, v in sorted(counts.items())],
                "",
                "This audit is advisory and did not delete or rewrite evidence artifacts.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
