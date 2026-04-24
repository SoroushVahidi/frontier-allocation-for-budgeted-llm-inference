#!/usr/bin/env python3
"""Audit anonymized NeurIPS supplement content for identity leaks and size risks."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
from dataclasses import dataclass
from pathlib import Path

TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".csv",
    ".tsv",
    ".ini",
    ".cfg",
    ".sh",
    ".rst",
    ".gitignore",
}

FORBIDDEN_PATH_TOKENS = {
    ".git",
    ".github",
    ".env",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "archive",
    "logs",
    "jobs",
    "notebooks",
}

EXCLUDED_SCAN_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}

PATTERNS: list[tuple[str, str, str, re.Pattern[str]]] = [
    ("author_name", "blocking", "Author-identifying token", re.compile(r"\b(Soroush|Vahidi|SoroushVahidi)\b", re.IGNORECASE)),
    ("institution", "blocking", "Institution-identifying token", re.compile(r"\b(NJIT|New Jersey Institute of Technology)\b", re.IGNORECASE)),
    ("email", "blocking", "Email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    (
        "api_key_name",
        "blocking",
        "Secret environment variable token",
        re.compile(r"\b(OPENAI_API_KEY|COHERE_API_KEY|HF_TOKEN|GEMINI_API_KEY)\b"),
    ),
    (
        "api_key_like",
        "blocking",
        "API key-like token",
        re.compile(r"\b(sk-[A-Za-z0-9]{16,}|gsk_[A-Za-z0-9]{16,})\b"),
    ),
    ("bearer", "blocking", "Bearer token-like string", re.compile(r"Bearer\s+[A-Za-z0-9._\-]{16,}", re.IGNORECASE)),
    (
        "private_repo_url",
        "blocking",
        "Private/user-identifying GitHub URL",
        re.compile(r"github\.com/(Soroush|SoroushVahidi)", re.IGNORECASE),
    ),
    (
        "absolute_path",
        "warning",
        "Absolute local path token",
        re.compile(r"(/home/|/Users/|/mnt/|/scratch/|/project/|/run/user/)", re.IGNORECASE),
    ),
]

BLOCKING_BINARY_EXTENSIONS = {
    ".pkl",
    ".pt",
    ".pth",
    ".npy",
    ".npz",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".jpg",
    ".jpeg",
    ".png",
    ".pdf",
    ".mp4",
    ".parquet",
}


@dataclass
class Finding:
    severity: str
    category: str
    path: str
    line: int
    snippet: str
    detail: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=".", help="Path to audit (default: repository root)")
    parser.add_argument("--zip-path", default="dist/neurips2026_anonymous_supplement.zip", help="ZIP path to audit for size")
    parser.add_argument(
        "--output-root",
        default="outputs/anonymization_audit",
        help="Output root for report artifacts",
    )
    parser.add_argument("--max-file-size-mb", type=float, default=10.0, help="Warning threshold for large single files")
    parser.add_argument("--max-total-size-mb", type=float, default=100.0, help="Blocking threshold for total package size")
    parser.add_argument("--max-zip-size-mb", type=float, default=100.0, help="Blocking threshold for total ZIP size")
    return parser.parse_args()


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        data = path.read_bytes()[:2048]
    except OSError:
        return False
    return b"\x00" not in data


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_SCAN_DIRS]
        for filename in filenames:
            files.append(Path(current_root) / filename)
    return files


def add_path_token_findings(relative_path: Path, findings: list[Finding], force_blocking: bool) -> None:
    parts = set(relative_path.parts)
    matches = sorted(parts.intersection(FORBIDDEN_PATH_TOKENS))
    for token in matches:
        findings.append(
            Finding(
                severity="blocking" if force_blocking else "warning",
                category="forbidden_path",
                path=str(relative_path),
                line=0,
                snippet=token,
                detail="Forbidden/deanonymizing path token present",
            )
        )


def scan_text_content(relative_path: Path, content: str, findings: list[Finding]) -> None:
    for line_no, line in enumerate(content.splitlines(), start=1):
        for category, severity, detail, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        severity=severity,
                        category=category,
                        path=str(relative_path),
                        line=line_no,
                        snippet=line.strip()[:240],
                        detail=detail,
                    )
                )


def severity_rank(severity: str) -> int:
    return {"blocking": 0, "warning": 1, "okay": 2}.get(severity, 3)


def write_csv(path: Path, findings: list[Finding]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["severity", "category", "path", "line", "snippet", "detail"])
        for finding in sorted(findings, key=lambda f: (severity_rank(f.severity), f.path, f.line)):
            writer.writerow([finding.severity, finding.category, finding.path, finding.line, finding.snippet, finding.detail])


def write_size_report(path: Path, root: Path, files: list[Path]) -> int:
    total = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["path", "size_bytes", "size_mb"])
        for file_path in sorted(files):
            size = file_path.stat().st_size
            total += size
            writer.writerow([str(file_path.relative_to(root)), size, f"{size / (1024 * 1024):.4f}"])
        writer.writerow(["__TOTAL__", total, f"{total / (1024 * 1024):.4f}"])
    return total


def write_markdown_report(
    report_path: Path,
    root: Path,
    findings: list[Finding],
    total_bytes: int,
    max_total_size_mb: float,
    zip_path: Path,
    zip_size_bytes: int,
    max_zip_size_mb: float,
) -> None:
    counts = {"blocking": 0, "warning": 0, "okay": 0}
    for finding in findings:
        counts[finding.severity] += 1

    status = "okay"
    if counts["blocking"] > 0:
        status = "blocking"
    elif counts["warning"] > 0:
        status = "warning"

    lines: list[str] = []
    lines.append("# Anonymous Supplement Audit Report")
    lines.append("")
    lines.append(f"- Timestamp (UTC): {dt.datetime.now(dt.UTC).isoformat()}")
    lines.append(f"- Scanned path: `{root}`")
    lines.append(f"- Overall status: **{status.upper()}**")
    lines.append(f"- Findings: blocking={counts['blocking']}, warning={counts['warning']}")
    lines.append(f"- Total extracted size: {total_bytes / (1024 * 1024):.2f} MB")
    lines.append(f"- Total extracted budget: {max_total_size_mb:.2f} MB")
    lines.append(f"- ZIP path: `{zip_path}`")
    lines.append(f"- ZIP size: {zip_size_bytes / (1024 * 1024):.2f} MB")
    lines.append(f"- ZIP budget: {max_zip_size_mb:.2f} MB")
    lines.append("")

    lines.append("## Findings")
    lines.append("")
    if not findings:
        lines.append("No anonymization findings detected.")
    else:
        lines.append("| Severity | Category | Path | Line | Detail |")
        lines.append("|---|---|---|---:|---|")
        for finding in sorted(findings, key=lambda f: (severity_rank(f.severity), f.path, f.line))[:400]:
            lines.append(
                f"| {finding.severity} | {finding.category} | `{finding.path}` | {finding.line} | {finding.detail} |"
            )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.path).resolve()
    zip_path = Path(args.zip_path).resolve()
    output_root = Path(args.output_root).resolve()

    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = output_root / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    files = iter_files(root)
    findings: list[Finding] = []
    scanning_staging = "dist/neurips2026_anonymous_supplement" in str(root)

    max_file_bytes = int(args.max_file_size_mb * 1024 * 1024)
    for file_path in files:
        rel = file_path.relative_to(root)
        add_path_token_findings(rel, findings, force_blocking=scanning_staging)

        size = file_path.stat().st_size
        if size > max_file_bytes:
            findings.append(
                Finding(
                    severity="warning",
                    category="large_file",
                    path=str(rel),
                    line=0,
                    snippet="",
                    detail=f"Large file: {size / (1024 * 1024):.2f} MB",
                )
            )

        if file_path.suffix.lower() in BLOCKING_BINARY_EXTENSIONS and size > 5 * 1024 * 1024:
            findings.append(
                Finding(
                    severity="warning",
                    category="binary_artifact",
                    path=str(rel),
                    line=0,
                    snippet="",
                    detail="Large binary artifact; verify necessity for reviewer package",
                )
            )

        if is_text_file(file_path):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            scan_text_content(rel, content, findings)

    total_bytes = write_size_report(out_dir / "supplement_size_report.csv", root, files)
    if total_bytes > int(args.max_total_size_mb * 1024 * 1024):
        findings.append(
            Finding(
                severity="blocking",
                category="size_budget",
                path=str(root),
                line=0,
                snippet="",
                detail=f"Extracted size {total_bytes / (1024 * 1024):.2f} MB exceeds {args.max_total_size_mb:.2f} MB",
            )
        )

    zip_size_bytes = 0
    if zip_path.exists():
        zip_size_bytes = zip_path.stat().st_size
        if zip_size_bytes > int(args.max_zip_size_mb * 1024 * 1024):
            findings.append(
                Finding(
                    severity="blocking",
                    category="zip_size_budget",
                    path=str(zip_path),
                    line=0,
                    snippet="",
                    detail=f"ZIP size {zip_size_bytes / (1024 * 1024):.2f} MB exceeds {args.max_zip_size_mb:.2f} MB",
                )
            )
    elif scanning_staging:
        findings.append(
            Finding(
                severity="blocking",
                category="zip_missing",
                path=str(zip_path),
                line=0,
                snippet="",
                detail="Expected supplement ZIP is missing",
            )
        )

    write_csv(out_dir / "anonymous_audit_findings.csv", findings)
    write_markdown_report(
        out_dir / "anonymous_audit_report.md",
        root,
        findings,
        total_bytes,
        args.max_total_size_mb,
        zip_path,
        zip_size_bytes,
        args.max_zip_size_mb,
    )

    blocking_count = sum(1 for finding in findings if finding.severity == "blocking")
    warning_count = sum(1 for finding in findings if finding.severity == "warning")
    print(f"[audit] output_dir={out_dir}")
    print(f"[audit] scanned_path={root}")
    print(f"[audit] zip_path={zip_path}")
    print(f"[audit] findings: blocking={blocking_count}, warning={warning_count}")
    return 1 if blocking_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
