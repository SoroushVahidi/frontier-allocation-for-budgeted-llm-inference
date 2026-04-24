#!/usr/bin/env python3
"""Build an anonymized NeurIPS 2026 supplement staging directory and ZIP."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

SUPPLEMENT_ROOT = Path("dist/neurips2026_anonymous_supplement")
ZIP_BASE = Path("dist/neurips2026_anonymous_supplement")
ZIP_PATH = Path("dist/neurips2026_anonymous_supplement.zip")

TOP_LEVEL_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "Makefile",
    "QUICKSTART.md",
]

TOP_LEVEL_DIRS = [
    "experiments",
    "configs",
    "tests",
    "outputs/paper_plot_data",
    "outputs/paper_tables",
    "outputs/paper_figures",
]

SCRIPT_WHITELIST = [
    "scripts/paper",
    "scripts/check_repo_health.py",
    "scripts/smoke_test.py",
    "scripts/build_anonymous_neurips_supplement.py",
]

SUPPLEMENT_EXCLUDE_PATHS = {
    "scripts/audit_anonymous_supplement.py",
    "scripts/verify_compute_optimal_tts_provenance.py",
}

DOCS_WHITELIST = [
    "docs/NEURIPS_PAPER_ARTIFACTS.md",
    "docs/PAPER_SOURCE_OF_TRUTH.md",
    "docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md",
    "docs/PAPER_REPRODUCTION_CHECKLIST.md",
    "docs/REPO_MAP.md",
    "docs/CANONICAL_START_HERE.md",
    "docs/CANONICAL_INSTALL_AND_DEV.md",
    "scripts/CANONICAL_START_HERE.md",
    "docs/ANONYMOUS_SUPPLEMENT_PREPARATION.md",
]

EXCLUDE_DIR_NAMES = {
    ".git",
    ".github",
    "archive",
    "logs",
    "jobs",
    "notebooks",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".ipynb_checkpoints",
}

EXCLUDE_FILE_GLOBS = [
    "*.env",
    ".env*",
    "*.log",
    "*.tmp",
    "*.bak",
    "*.ipynb",
]

EXCLUDE_SUBSTRINGS = [
    "real_model_ours_vs_external_validation_20260424T_OPENAI_REAL_SMOKE",
]

RESTRICTED_PATTERNS = [
    re.compile(r"\b(Soroush|Vahidi|SoroushVahidi|NJIT|New Jersey Institute of Technology)\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(OPENAI_API_KEY|COHERE_API_KEY|HF_TOKEN|GEMINI_API_KEY)\b"),
    re.compile(r"\b(sk-[A-Za-z0-9]{16,}|gsk_[A-Za-z0-9]{16,})\b"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{16,}", re.IGNORECASE),
    re.compile(r"github\.com/(Soroush|SoroushVahidi)", re.IGNORECASE),
    re.compile(r"(/home/|/Users/|/mnt/|/scratch/|/project/|/run/user/)", re.IGNORECASE),
]

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
}

README_TEXT = """# Anonymous Supplementary Package

This is the anonymous supplement for NeurIPS 2026 submission review.

## Main Commands

```bash
make check
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Output Roots

- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_tables/`

## Scope and Claim Boundaries

This package is restricted to reviewer-facing reproducibility materials and
claim-boundary documentation for manuscript-facing evidence only.
"""

REPRODUCIBILITY_TEXT = """# Reproducibility

## Environment

- Python >= 3.10

## Install

```bash
python -m pip install -r requirements.txt
python -m pip install -e .[dev]
```

## Validate

```bash
make check
```

## Regenerate Paper Artifacts

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Expected Outputs

- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_tables/`
"""

CLAIM_BOUNDARIES_TEXT = """# Claim Boundaries

- Main claims are bounded to manuscript-facing, matched-surface comparisons.
- `strict_f3` and `strict_gate1_cap_k6` are distinct and not collapsed.
- Adjacent baselines are not treated as control-equivalent to main comparisons.
- Real-model smoke outputs are development-only unless explicitly promoted.
- Historical exploratory outputs are out of scope for paper claims.
"""

ANONYMITY_TEXT = """# Anonymity

This supplement excludes author identities, institutional identifiers,
private links, local absolute paths, and secrets.

Reviewers should evaluate only this package and avoid any external identity
resolution attempts.
"""


def should_skip(path: Path) -> bool:
    if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
        return True
    rel = path.as_posix()
    if any(token in rel for token in EXCLUDE_SUBSTRINGS):
        return True
    return any(path.match(pattern) for pattern in EXCLUDE_FILE_GLOBS)


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        sample = path.read_bytes()[:2048]
    except OSError:
        return False
    return b"\x00" not in sample


def contains_restricted_content(path: Path) -> bool:
    if not is_text_file(path):
        return False
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return any(pattern.search(content) for pattern in RESTRICTED_PATTERNS)


def copy_file(src: Path, dst: Path) -> bool:
    if should_skip(src):
        return False
    if contains_restricted_content(src):
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def copy_tree(src: Path, dst: Path) -> None:
    for source_file in src.rglob("*"):
        if not source_file.is_file():
            continue
        rel = source_file.relative_to(src)
        if should_skip(rel) or should_skip(source_file):
            continue
        copy_file(source_file, dst / rel)


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_manifest(staging_root: Path) -> None:
    entries: list[tuple[str, int]] = []
    total = 0
    for file_path in sorted(staging_root.rglob("*")):
        if not file_path.is_file():
            continue
        size = file_path.stat().st_size
        total += size
        entries.append((str(file_path.relative_to(staging_root)), size))

    lines = [
        "# Manifest",
        "",
        f"Total files: {len(entries)}",
        f"Total size: {total / (1024 * 1024):.2f} MB",
        "",
        "| Path | Size (bytes) |",
        "|---|---:|",
    ]
    lines.extend([f"| `{path}` | {size} |" for path, size in entries])
    (staging_root / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    if SUPPLEMENT_ROOT.exists():
        shutil.rmtree(SUPPLEMENT_ROOT)
    SUPPLEMENT_ROOT.mkdir(parents=True, exist_ok=True)

    for relative in TOP_LEVEL_FILES:
        source = repo_root / relative
        if source.exists():
            copy_file(source, SUPPLEMENT_ROOT / relative)

    for relative in TOP_LEVEL_DIRS:
        source = repo_root / relative
        if source.exists() and source.is_dir():
            copy_tree(source, SUPPLEMENT_ROOT / relative)

    for relative in SCRIPT_WHITELIST + DOCS_WHITELIST:
        if relative in SUPPLEMENT_EXCLUDE_PATHS:
            continue
        source = repo_root / relative
        if not source.exists():
            continue
        destination = SUPPLEMENT_ROOT / relative
        if source.is_dir():
            copy_tree(source, destination)
        else:
            copy_file(source, destination)

    write_text(SUPPLEMENT_ROOT / "README.md", README_TEXT)
    write_text(SUPPLEMENT_ROOT / "REPRODUCIBILITY.md", REPRODUCIBILITY_TEXT)
    write_text(SUPPLEMENT_ROOT / "ANONYMITY.md", ANONYMITY_TEXT)
    write_text(SUPPLEMENT_ROOT / "CLAIM_BOUNDARIES.md", CLAIM_BOUNDARIES_TEXT)
    write_manifest(SUPPLEMENT_ROOT)

    archive_path = shutil.make_archive(str(ZIP_BASE), "zip", root_dir=SUPPLEMENT_ROOT)
    zip_size_mb = ZIP_PATH.stat().st_size / (1024 * 1024) if ZIP_PATH.exists() else 0.0
    print(f"[build] staging_dir={SUPPLEMENT_ROOT}")
    print(f"[build] zip={archive_path}")
    print(f"[build] zip_size_mb={zip_size_mb:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
