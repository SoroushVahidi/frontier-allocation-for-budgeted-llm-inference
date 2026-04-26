#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shutil
from pathlib import Path
from typing import Iterable
import zipfile

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPORT_DIRNAME = "neurips2026_anonymous_artifact"
ZIP_NAME = "neurips2026_anonymous_artifact.zip"

TOP_LEVEL_FILES = [
    "README.md",
    "QUICKSTART.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "TODO.md",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "Makefile",
]

TOP_LEVEL_DIRS = [
    "configs",
    "datasets",
    "manuscript_integration",
    "references",
    "theory",
]

DOC_FILES = [
    "README.md",
    "CANONICAL_START_HERE.md",
    "CANONICAL_EXPERIMENT_STACK.md",
    "REPO_MAP.md",
    "CANONICAL_INSTALL_AND_DEV.md",
    "PAPER_SOURCE_OF_TRUTH.md",
    "PAPER_BASELINE_HONESTY_STATUS.md",
    "RESULTS_GUIDE.md",
    "PAPER_ARTIFACT_MAP.md",
    "SAFE_CLAIMS_FOR_NEURIPS_2026.md",
    "PAPER_OPEN_GAPS_AND_RISKS.md",
    "REVIEWER_REPRO_AND_SCOPE_GUIDE.md",
    "CLAIM_BOUNDARIES.md",
    "METHOD_AND_VARIANT_MAP.md",
    "external_baseline_paper_readiness_decision_matrix.json",
]

TEST_FILES = [
    "__init__.py",
    "test_frontier_router.py",
    "test_paper_artifact_runner_claim_safety_integration.py",
    "test_claim_safety_statistical_table.py",
]

SCRIPT_FILES = [
    "README.md",
    "CANONICAL_START_HERE.md",
    "check_repo_health.py",
    "build_unified_claim_safety_statistical_audit.py",
    "run_anti_collapse_calibration_sweep.py",
]

OUTPUT_DIRS = [
    "README.md",
    "paper_tables",
    "paper_plot_data",
    "paper_figures",
    "paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3",
    "component_ablation_strict_f3_paper_surface",
    "unified_claim_safety_statistical_audit_20260424T200000Z",
    "anti_collapse_calibration_sweep_20260424TTESTACALZ",
    "canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z",
    "budget_aware_family_cap_eval_20260421T162842Z",
]

DISALLOWED_OUTPUT_NAME_PATTERNS = (
    "*cohere*",
    "*openai*",
    "*real_model*",
    "*direct_reserve_candidate_scorer*",
    "*api*validation*",
    "*provider*",
)

REMOVE_PATTERNS = [
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".venv",
    ".env",
    "*.log",
    "*.out",
    "*.err",
    "*.sbatch",
    "*.slurm",
    "logs",
    "jobs",
    "batch",
    "archive",
]

TEXT_FILE_GLOBS = (
    "*.md",
    "*.txt",
    "*.py",
    "*.toml",
    "*.yaml",
    "*.yml",
    "*.json",
    "*.csv",
    "*.tex",
    "*.rst",
    "*.cfg",
    "*.ini",
    "*.sh",
)

LEAK_PATTERNS = [
    r"Soroush",
    r"Vahidi",
    r"\bsv96\b",
    r"NJIT",
    r"github\.com/SoroushVahidi",
    r"/home/",
    r"/Users/",
    r"Wulver",
    r"OPENAI_API_KEY",
    r"HF_TOKEN",
    r"GEMINI_API_KEY",
    r"COHERE_API_KEY",
    r"/(home|Users)/[^\\s'\"]+",
    r"[A-Za-z]:\\\\[^\\s'\"]+",
]


def _matches_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def _ignore_filter(_dir: str, names: list[str]) -> list[str]:
    ignored: list[str] = []
    for n in names:
        if _matches_any(n, REMOVE_PATTERNS):
            ignored.append(n)
    return ignored


def _copy_path(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, ignore=_ignore_filter, dirs_exist_ok=True)
    elif src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _write_anonymous_readme(export_root: Path) -> None:
    (export_root / "README.md").write_text(
        "# Anonymous NeurIPS 2026 Supplement Artifact\n\n"
        "This package is an anonymous reviewer-facing artifact for NeurIPS 2026.\n\n"
        "Canonical reproduction path (no external API keys required):\n\n"
        "```bash\n"
        "python scripts/check_repo_health.py\n"
        "python -m pytest\n"
        "python scripts/paper/run_all_neurips_paper_artifacts.py\n"
        "```\n\n"
        "Canonical generated outputs appear in:\n"
        "- `outputs/paper_tables/`\n"
        "- `outputs/paper_plot_data/`\n"
        "- `outputs/paper_figures/`\n\n"
        "Real-model/provider diagnostics are not part of the canonical reviewer reproduction path unless explicitly included and scoped in claim-boundary docs.\n",
        encoding="utf-8",
    )


def _anonymity_scan(export_root: Path, report_path: Path) -> int:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    findings: list[tuple[str, int, str, str]] = []
    regexes = [re.compile(p, re.IGNORECASE) for p in LEAK_PATTERNS]
    for p in export_root.rglob("*"):
        if not p.is_file():
            continue
        if not _matches_any(p.name, TEXT_FILE_GLOBS):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            for rgx in regexes:
                m = rgx.search(line)
                if m:
                    findings.append((str(p.relative_to(export_root)), i, rgx.pattern, line[:220]))
                    break
    with report_path.open("w", encoding="utf-8") as f:
        f.write("path,line,pattern,snippet\n")
        for path, line, pat, snip in findings:
            safe = snip.replace("\n", " ").replace('"', "'")
            f.write(f'"{path}",{line},"{pat}","{safe}"\n')
    return len(findings)


def _apply_export_redactions(export_root: Path) -> None:
    targets = [
        export_root / "docs" / "RESULTS_GUIDE.md",
        export_root / "outputs" / "paper_tables" / "table_real_model_quantitative_audit_sources.csv",
    ]
    replacements = {
        "WULVER_COHERE_LONG": "CLUSTER_COHERE_LONG",
        "WULVER_COHERE_LONG_DETAIL": "CLUSTER_COHERE_LONG_DETAIL",
        "Wulver": "cluster",
        "wulver": "cluster",
    }
    for path in targets:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        path.write_text(text, encoding="utf-8")

    # Normalize absolute workspace path in claim-safety audit status.
    status_md = (
        export_root
        / "outputs"
        / "unified_claim_safety_statistical_audit_20260424T200000Z"
        / "STATUS.md"
    )
    if status_md.exists():
        text = status_md.read_text(encoding="utf-8")
        text = text.replace(
            "Output directory: `/workspace/adaptive-reasoning-budget-allocation/outputs/unified_claim_safety_statistical_audit_20260424T200000Z`",
            "Output directory: `outputs/unified_claim_safety_statistical_audit_20260424T200000Z`",
        )
        path_prefix = "/workspace/adaptive-reasoning-budget-allocation/"
        text = text.replace(path_prefix, "")
        status_md.write_text(text, encoding="utf-8")


def _prune_disallowed_output_dirs(export_root: Path) -> None:
    out_root = export_root / "outputs"
    if not out_root.exists():
        return
    for child in out_root.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if name in OUTPUT_DIRS:
            continue
        if _matches_any(name, DISALLOWED_OUTPUT_NAME_PATTERNS):
            shutil.rmtree(child, ignore_errors=True)


def _remove_sensitive_manifests(export_root: Path) -> None:
    # Remove manifest files that encode non-canonical runtime/API provenance.
    # Keep only manifests required by canonical scripts.
    protected = {
        export_root
        / "outputs"
        / "paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3"
        / "20260422T175142Z"
        / "eval_manifest.json"
    }
    for path in (export_root / "outputs").rglob("manifest*.json"):
        if path in protected:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if (
            "run_real_api_requested" in text
            or "real_api_enabled" in text
            or "/workspace/" in text
        ):
            path.unlink(missing_ok=True)


def _zip_export(export_root: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in export_root.rglob("*"):
            rel = p.relative_to(export_root.parent)
            name = p.name
            if _matches_any(name, REMOVE_PATTERNS):
                continue
            if p.is_file():
                zf.write(p, rel.as_posix())


def main() -> None:
    ap = argparse.ArgumentParser(description="Create sanitized anonymous NeurIPS reviewer artifact export.")
    ap.add_argument("--export-dir", default=EXPORT_DIRNAME)
    ap.add_argument("--zip-name", default=ZIP_NAME)
    args = ap.parse_args()

    export_root = REPO_ROOT / args.export_dir
    if export_root.exists():
        shutil.rmtree(export_root)
    export_root.mkdir(parents=True, exist_ok=True)

    for f in TOP_LEVEL_FILES:
        src = REPO_ROOT / f
        if src.exists():
            _copy_path(src, export_root / f)
    for d in TOP_LEVEL_DIRS:
        src = REPO_ROOT / d
        if src.exists():
            _copy_path(src, export_root / d)

    # Copy reviewer-facing docs only.
    docs_out = export_root / "docs"
    docs_out.mkdir(parents=True, exist_ok=True)
    for name in DOC_FILES:
        src = REPO_ROOT / "docs" / name
        if src.exists():
            _copy_path(src, docs_out / name)

    # Copy a minimal, offline-safe test set.
    tests_out = export_root / "tests"
    tests_out.mkdir(parents=True, exist_ok=True)
    for name in TEST_FILES:
        src = REPO_ROOT / "tests" / name
        if src.exists():
            _copy_path(src, tests_out / name)

    # Copy canonical script entrypoints only.
    scripts_out = export_root / "scripts"
    scripts_out.mkdir(parents=True, exist_ok=True)
    for name in SCRIPT_FILES:
        src = REPO_ROOT / "scripts" / name
        if src.exists():
            _copy_path(src, scripts_out / name)
    if (REPO_ROOT / "scripts" / "paper").exists():
        _copy_path(REPO_ROOT / "scripts" / "paper", scripts_out / "paper")

    # Copy minimal experiments module required by health check/tests.
    exp_out = export_root / "experiments"
    exp_out.mkdir(parents=True, exist_ok=True)
    for name in ("__init__.py", "frontier_router.py"):
        src = REPO_ROOT / "experiments" / name
        if src.exists():
            _copy_path(src, exp_out / name)

    out_root = export_root / "outputs"
    out_root.mkdir(parents=True, exist_ok=True)
    for d in OUTPUT_DIRS:
        src = REPO_ROOT / "outputs" / d
        if src.exists():
            _copy_path(src, out_root / d)

    # Remove explicit non-canonical/private dirs if copied via top-level globs.
    for rel in ("logs", "jobs", "batch", "archive", ".git", ".github"):
        p = export_root / rel
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    _write_anonymous_readme(export_root)
    _apply_export_redactions(export_root)
    _prune_disallowed_output_dirs(export_root)
    _remove_sensitive_manifests(export_root)

    report_path = REPO_ROOT / "outputs" / "local_only_anonymity_scan_report.csv"
    findings = _anonymity_scan(export_root, report_path)

    zip_path = REPO_ROOT / args.zip_name
    _zip_export(export_root, zip_path)

    print(f"Export created: {export_root}")
    print(f"Zip created: {zip_path}")
    print(f"Anonymity findings: {findings}")
    print(f"Local-only scan report: {report_path}")


if __name__ == "__main__":
    main()

