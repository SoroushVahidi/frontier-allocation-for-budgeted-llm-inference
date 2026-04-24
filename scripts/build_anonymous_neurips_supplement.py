#!/usr/bin/env python3
"""Build anonymous NeurIPS 2026 supplementary package staging directory and ZIP."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

SUPPLEMENT_ROOT = Path("dist/neurips2026_anonymous_supplement")
ZIP_BASE = Path("dist/neurips2026_anonymous_supplement")

TOP_LEVEL_FILES = [
    "QUICKSTART.md",
    "pyproject.toml",
    "requirements.txt",
    "Makefile",
    "LICENSE",
]

TOP_LEVEL_DIRS = [
    "experiments",
    "scripts",
    "configs",
    "tests",
    "references",
    "outputs/paper_plot_data",
    "outputs/paper_tables",
    "outputs/paper_figures",
]

DOCS_WHITELIST = [
    "docs/NEURIPS_PAPER_ARTIFACTS.md",
    "docs/PAPER_SOURCE_OF_TRUTH.md",
    "docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md",
    "docs/PAPER_REPRODUCTION_CHECKLIST.md",
    "docs/REPO_MAP.md",
    "docs/CANONICAL_START_HERE.md",
    "docs/CANONICAL_INSTALL_AND_DEV.md",
    "scripts/CANONICAL_START_HERE.md",
]

EXCLUDE_DIR_NAMES = {
    ".git",
    ".github",
    "archive",
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

README_TEXT = """# Anonymous Supplementary Package

This is the anonymous supplementary package for **“Adaptive Frontier Allocation for Budgeted LLM Inference.”**

It supports reproduction of the manuscript-facing figures and tables.

## Main Commands

```bash
make check
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Output Roots

- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_tables/`

## Claim Surface and Method Semantics

- Claims are tied to the matched manuscript-facing surface.
- `strict_f3` is the manuscript-facing internal method on that surface.
- `strict_gate1_cap_k6` is a broader operational default on a different surface and should not be collapsed with `strict_f3`.
- External baselines are near-direct matched-substrate adapter baselines, not full official reproductions.
- Real-model OpenAI smoke evidence, if present, is development-only and not used as headline evidence.
"""

REPRODUCIBILITY_TEXT = """# Reproducibility

## Environment

- Python >= 3.10

## Install Dependencies

```bash
python -m pip install -r requirements.txt
python -m pip install -e .[dev]
```

## Validate Package

```bash
make check
```

## Regenerate Manuscript-Facing Artifacts

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Expected Regenerated Outputs

- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_tables/`

## Scope Notes

- The paper artifact runner regenerates figures/tables from committed canonical machine-readable bundles.
- It does **not** recompute every historical raw experiment artifact present in the broader project history.
- No API keys are required for reproducing the paper-facing artifact package.
- Optional API-backed real-model scripts are development-only and are not required for paper artifact reproduction.
"""

CLAIM_BOUNDARIES_TEXT = """# Claim Boundaries

- The main paper-facing claim is bounded to the matched manuscript-facing comparison surface.
- `strict_f3` is not claimed to universally dominate `strict_gate1_cap_k6`.
- The main comparison is our frontier-allocation family vs near-direct external budget-control baselines.
- Adjacent baselines are not merged into the main ranking because control spaces are non-equivalent.
- Real-model smoke validation is not headline-safe unless later explicitly promoted by canonical docs.
- Do not cite exploratory/historical outputs as paper evidence.
"""

ANONYMITY_TEXT = """# Anonymity

This package has been stripped of:

- Author names and GitHub usernames.
- Email addresses and private URLs.
- Local absolute paths and institutional identifiers.
- API keys, token-like secrets, and repository metadata.

Reviewer guidance:

- Use only this local package for evaluation.
- Do not depend on external private links or private repository history.

A de-anonymized public repository can be provided after acceptance.
"""


def should_skip(path: Path) -> bool:
    name = path.name
    if name in EXCLUDE_DIR_NAMES:
        return True
    rel = path.as_posix()
    if any(token in rel for token in EXCLUDE_SUBSTRINGS):
        return True
    for pattern in EXCLUDE_FILE_GLOBS:
        if path.match(pattern):
            return True
    return False


def copy_tree(src: Path, dst: Path) -> None:
    for current_root, dirnames, filenames in os.walk(src):
        current = Path(current_root)
        rel_root = current.relative_to(src)

        dirnames[:] = [d for d in dirnames if not should_skip(Path(d)) and not should_skip(rel_root / d)]

        (dst / rel_root).mkdir(parents=True, exist_ok=True)
        for filename in filenames:
            source_file = current / filename
            rel_file = rel_root / filename
            if should_skip(source_file) or should_skip(rel_file):
                continue
            (dst / rel_file.parent).mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, dst / rel_file)


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
            shutil.copy2(source, SUPPLEMENT_ROOT / relative)

    for relative in TOP_LEVEL_DIRS:
        source = repo_root / relative
        if source.exists():
            copy_tree(source, SUPPLEMENT_ROOT / relative)

    for relative in DOCS_WHITELIST:
        source = repo_root / relative
        if source.exists():
            destination = SUPPLEMENT_ROOT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    write_text(SUPPLEMENT_ROOT / "README.md", README_TEXT)
    write_text(SUPPLEMENT_ROOT / "REPRODUCIBILITY.md", REPRODUCIBILITY_TEXT)
    write_text(SUPPLEMENT_ROOT / "ANONYMITY.md", ANONYMITY_TEXT)
    write_text(SUPPLEMENT_ROOT / "CLAIM_BOUNDARIES.md", CLAIM_BOUNDARIES_TEXT)
    write_manifest(SUPPLEMENT_ROOT)

    archive_path = shutil.make_archive(str(ZIP_BASE), "zip", root_dir=SUPPLEMENT_ROOT)
    print(f"[build] staging_dir={SUPPLEMENT_ROOT}")
    print(f"[build] zip={archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
