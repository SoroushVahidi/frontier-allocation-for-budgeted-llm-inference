#!/usr/bin/env python3
"""Build an anonymous NeurIPS supplementary ZIP for reviewer use."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

TOP_LEVEL_FOLDER = "anonymous_supplement"
DEFAULT_ZIP_PATH = Path("dist/anonymous_supplement_neurips2026.zip")
DEFAULT_MANIFEST_PATH = Path("dist/anonymous_supplement_manifest.json")

ANON_README = """# Anonymous Supplement for "Frontier Allocation for Budgeted LLM Inference"

## Contents

- code and canonical artifacts for regenerating paper-facing figures/tables
- no API keys required
- no author-identifying repository metadata included

## Reviewer quickstart

1. unzip anonymous_supplement_neurips2026.zip
2. cd anonymous_supplement
3. python -m venv .venv
4. source .venv/bin/activate
5. pip install -r requirements.txt
6. make check
7. python scripts/paper/run_all_neurips_paper_artifacts.py

## Expected regenerated outputs

- outputs/paper_plot_data/
- outputs/paper_figures/
- outputs/paper_tables/

## Claim boundary

The artifact package regenerates the matched manuscript-facing paper artifacts.
It is not intended to rerun every historical experiment or API-backed exploratory run.
"""

ANON_MAKEFILE = """.PHONY: check

check:
\tpython3 -m ruff check scripts/paper tests
\tpython3 -m pytest -q tests/test_repository_structure.py
"""

REPRO_COMMANDS = [
    "python -m venv .venv",
    "source .venv/bin/activate",
    "pip install -r requirements.txt",
    "make check",
    "python scripts/paper/run_all_neurips_paper_artifacts.py",
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
    ".tex",
    ".gitignore",
}

SAFE_OPTIONAL_DOCS = [
    "docs/NEURIPS_PAPER_ARTIFACTS.md",
    "docs/PAPER_SOURCE_OF_TRUTH.md",
    "docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md",
    "docs/MANUSCRIPT_SUPPORT_DASHBOARD.md",
    "docs/PAPER_OPEN_GAPS_AND_RISKS.md",
]

OPTIONAL_PATTERNS: list[str] = []

UNSAFE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("name_soroush", re.compile(r"Soroush", re.IGNORECASE)),
    ("name_vahidi", re.compile(r"Vahidi", re.IGNORECASE)),
    ("username_soroushvahidi", re.compile(r"SoroushVahidi", re.IGNORECASE)),
    ("username_sv96", re.compile(r"\bsv96\b", re.IGNORECASE)),
    ("institution_njit", re.compile(r"\bNJIT\b", re.IGNORECASE)),
    ("institution_full", re.compile(r"New Jersey Institute of Technology", re.IGNORECASE)),
    ("wulver", re.compile(r"Wulver", re.IGNORECASE)),
    ("local_home_path", re.compile(r"/home/")),
    ("local_mnt_path", re.compile(r"/mnt/")),
    ("github_identity", re.compile(r"github\.com/SoroushVahidi", re.IGNORECASE)),
    ("openai_api_env", re.compile(r"\bOPENAI_API_KEY\b", re.IGNORECASE)),
    ("cohere_api_env", re.compile(r"\bCOHERE_API_KEY\b", re.IGNORECASE)),
    ("hf_token_env", re.compile(r"\bHF_TOKEN\b", re.IGNORECASE)),
    ("gemini_api_env", re.compile(r"\bGEMINI_API_KEY\b", re.IGNORECASE)),
    ("openai_key_prefix", re.compile(r"sk-[A-Za-z0-9]{8,}", re.IGNORECASE)),
    ("email_like", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]

PATH_EXCLUDE_TOKENS = {
    ".git",
    ".github",
    "jobs",
    "logs",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".ipynb_checkpoints",
}

PATH_EXCLUDE_GLOBS = [
    ".env",
    ".env.*",
    "*.env",
    "*.key",
    "*.pem",
    "*.token",
    "*.secret",
    "*.ipynb",
]


@dataclass(frozen=True)
class Candidate:
    rel_path: str
    required: bool
    source_type: str  # "file" | "generated"
    content: str | None = None


REQUIRED_STRUCTURE_FILES = [
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "Makefile",
    "docs/README.md",
    "docs/CANONICAL_INSTALL_AND_DEV.md",
    "docs/REPO_POLISH_PASS_2026_04_15.md",
    "scripts/README.md",
    "experiments/frontier_router.py",
    "tests/test_repository_structure.py",
    "docs/external_baseline_paper_readiness_decision_matrix.json",
]

REQUIRED_ANON_REPLACEMENTS = {
    "README.md": ANON_README,
    "docs/README.md": "# Docs\n\nAnonymous reviewer-facing documentation bundle.\n",
    "docs/CANONICAL_INSTALL_AND_DEV.md": (
        "# Canonical Install And Dev\n\n"
        "Use a local Python virtual environment and install from `requirements.txt`.\n"
        "Run `make check` before paper artifact regeneration.\n"
    ),
    "docs/REPO_POLISH_PASS_2026_04_15.md": (
        "# Repo Polish Pass (Anonymized)\n\n"
        "Repository structure checks and canonical documentation presence are maintained.\n"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Scan and prepare manifest, but do not write ZIP")
    parser.add_argument("--inspect", type=str, default="", help="Inspect an existing supplement ZIP and print summary")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--zip-path", type=Path, default=DEFAULT_ZIP_PATH)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    return parser.parse_args()


def _is_text(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        probe = path.read_bytes()[:2048]
    except OSError:
        return False
    return b"\x00" not in probe


def _scan_unsafe(path_label: str, content: str) -> list[str]:
    hits: list[str] = []
    for label, pattern in UNSAFE_PATTERNS:
        if pattern.search(content):
            hits.append(label)
    return hits


def _path_excluded(rel: str) -> bool:
    p = Path(rel)
    if any(part in PATH_EXCLUDE_TOKENS for part in p.parts):
        return True
    name = p.name
    for g in PATH_EXCLUDE_GLOBS:
        if Path(name).match(g) or p.match(g):
            return True
    return False


def _iter_dir_files(base: Path, relative_dir: str) -> Iterable[str]:
    root = base / relative_dir
    if not root.exists() or not root.is_dir():
        return []
    out: list[str] = []
    for fp in sorted(root.rglob("*")):
        if fp.is_file():
            out.append(str(fp.relative_to(base).as_posix()))
    return out


def _latest_valid_run(root: Path, required_files: set[str]) -> Path | None:
    if not root.exists() or not root.is_dir():
        return None
    valid: list[Path] = []
    for candidate in sorted([p for p in root.iterdir() if p.is_dir()]):
        if all((candidate / rf).exists() for rf in required_files):
            valid.append(candidate)
    return valid[-1] if valid else None


def collect_candidates(repo_root: Path) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[str] = set()

    def add_file(rel: str, required: bool = False) -> None:
        rel = rel.replace("\\", "/")
        if rel in seen:
            return
        seen.add(rel)
        candidates.append(Candidate(rel_path=rel, required=required, source_type="file"))

    def add_generated(rel: str, content: str) -> None:
        rel = rel.replace("\\", "/")
        if rel in seen:
            candidates[:] = [c for c in candidates if c.rel_path != rel]
        else:
            seen.add(rel)
        candidates.append(Candidate(rel_path=rel, required=True, source_type="generated", content=content))

    if (repo_root / "README.md").exists():
        add_file("README.md", required=True)
    for rel in ["requirements.txt", "pyproject.toml", "LICENSE"]:
        if (repo_root / rel).exists():
            add_file(rel, required=True)
    if (repo_root / "Makefile").exists():
        add_file("Makefile", required=True)
    if (repo_root / "docs" / "README.md").exists():
        add_file("docs/README.md", required=True)
    if (repo_root / "docs" / "CANONICAL_INSTALL_AND_DEV.md").exists():
        add_file("docs/CANONICAL_INSTALL_AND_DEV.md", required=True)
    if (repo_root / "docs" / "REPO_POLISH_PASS_2026_04_15.md").exists():
        add_file("docs/REPO_POLISH_PASS_2026_04_15.md", required=True)
    if (repo_root / "scripts" / "README.md").exists():
        add_file("scripts/README.md", required=True)
    if (repo_root / "experiments" / "frontier_router.py").exists():
        add_file("experiments/frontier_router.py", required=True)
    if (repo_root / "docs" / "external_baseline_paper_readiness_decision_matrix.json").exists():
        add_file("docs/external_baseline_paper_readiness_decision_matrix.json", required=True)
    if (repo_root / "environment.yml").exists():
        add_file("environment.yml")
    for rel in ["setup.cfg", "setup.py"]:
        if (repo_root / rel).exists():
            add_file(rel)

    for rel in _iter_dir_files(repo_root, "scripts/paper"):
        add_file(rel, required=True)
    if (repo_root / "tests" / "test_repository_structure.py").exists():
        add_file("tests/test_repository_structure.py", required=True)
    if (repo_root / "tests" / "README.md").exists():
        add_file("tests/README.md")

    for rel in ["outputs/paper_plot_data", "outputs/paper_figures", "outputs/paper_tables"]:
        for file_rel in _iter_dir_files(repo_root, rel):
            add_file(file_rel, required=True)

    req_latest = {
        "method_metrics.csv",
        "oracle_gap_summary.csv",
        "matched_comparison_summary.csv",
        "budget_frontier_summary.csv",
        "signal_slice_summary.csv",
        "summary.json",
    }
    full_latest = {
        "manifest.json",
        "per_seed_method_metrics.csv",
        "per_method_metrics.csv",
        "per_example_outcomes.csv",
        "per_budget_ranking.csv",
        "per_dataset_ranking.csv",
    }
    imported_latest = _latest_valid_run(repo_root / "outputs" / "imported_methodology_frontier_eval", req_latest)
    if imported_latest is not None:
        for rel in _iter_dir_files(repo_root, str(imported_latest.relative_to(repo_root))):
            add_file(rel, required=True)
    full_bundle_latest = _latest_valid_run(repo_root / "outputs" / "full_method_comparison_bundle", full_latest)
    if full_bundle_latest is not None:
        for rel in _iter_dir_files(repo_root, str(full_bundle_latest.relative_to(repo_root))):
            add_file(rel, required=True)

    explicit_output_dirs = [
        "outputs/paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3/20260422T175142Z",
        "outputs/component_ablation_strict_f3_paper_surface/20260422T180445Z",
        "outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z",
        "outputs/budget_aware_family_cap_eval_20260421T162842Z",
        "outputs/current_failure_output_layer_repair_20260420",
    ]
    for rel in explicit_output_dirs:
        for file_rel in _iter_dir_files(repo_root, rel):
            add_file(file_rel, required=True)

    for rel in SAFE_OPTIONAL_DOCS:
        if (repo_root / rel).exists():
            add_file(rel)

    for pattern in OPTIONAL_PATTERNS:
        for p in sorted(repo_root.glob(pattern)):
            if p.is_file():
                add_file(str(p.relative_to(repo_root).as_posix()))
            elif p.is_dir():
                for file_rel in _iter_dir_files(repo_root, str(p.relative_to(repo_root).as_posix())):
                    add_file(file_rel)

    add_generated("README.md", ANON_README)
    add_generated("Makefile", ANON_MAKEFILE)
    return candidates


def build_manifest_and_payload(
    repo_root: Path, candidates: list[Candidate]
) -> tuple[dict, dict[str, bytes], bool, list[dict], list[dict]]:
    included: list[dict] = []
    excluded: list[dict] = []
    payload: dict[str, bytes] = {}
    scan_findings: list[dict] = []
    unsafe_required = False

    for candidate in candidates:
        rel = candidate.rel_path
        if _path_excluded(rel):
            excluded.append({"path": rel, "reason": "path_excluded"})
            continue

        text_for_scan = ""
        is_text = False
        if candidate.source_type == "generated":
            assert candidate.content is not None
            data = candidate.content.encode("utf-8")
            text_for_scan = candidate.content
            is_text = True
        else:
            source = repo_root / rel
            if not source.exists() or not source.is_file():
                excluded.append({"path": rel, "reason": "missing"})
                if candidate.required:
                    unsafe_required = True
                continue
            data = source.read_bytes()
            if _is_text(source):
                text_for_scan = data.decode("utf-8", errors="ignore")
                is_text = True

        hits = _scan_unsafe(rel, text_for_scan) if is_text else []
        if hits:
            replacement = REQUIRED_ANON_REPLACEMENTS.get(rel)
            if replacement is not None:
                replacement_hits = _scan_unsafe(rel, replacement)
                if not replacement_hits:
                    data = replacement.encode("utf-8")
                    zpath = f"{TOP_LEVEL_FOLDER}/{rel}"
                    payload[zpath] = data
                    included.append(
                        {
                            "path": rel,
                            "zip_path": zpath,
                            "size_bytes": len(data),
                            "replacement_used": True,
                        }
                    )
                    excluded.append(
                        {
                            "path": rel,
                            "reason": "anonymized_replacement_used",
                            "unsafe_labels": hits,
                        }
                    )
                    continue
            finding = {"path": rel, "unsafe_labels": hits}
            scan_findings.append(finding)
            excluded.append({"path": rel, "reason": "anonymization_risk", "unsafe_labels": hits})
            if candidate.required:
                unsafe_required = True
            continue

        zpath = f"{TOP_LEVEL_FOLDER}/{rel}"
        payload[zpath] = data
        included.append({"path": rel, "zip_path": zpath, "size_bytes": len(data)})

    for req in REQUIRED_STRUCTURE_FILES:
        expected = f"{TOP_LEVEL_FOLDER}/{req}"
        if expected not in payload:
            excluded.append({"path": req, "reason": "required_missing_after_scan"})
            unsafe_required = True

    scan_passed = not unsafe_required
    manifest = {
        "timestamp_utc": dt.datetime.now(dt.UTC).isoformat(),
        "top_level_folder": TOP_LEVEL_FOLDER,
        "zip_path": str(DEFAULT_ZIP_PATH.as_posix()),
        "manifest_path": str(DEFAULT_MANIFEST_PATH.as_posix()),
        "reproduction_commands": REPRO_COMMANDS,
        "no_api_keys_required": True,
        "included_files": included,
        "excluded_files": excluded,
        "unsafe_pattern_scan": {
            "passed": scan_passed,
            "required_file_violations": unsafe_required,
            "findings": scan_findings,
        },
    }
    return manifest, payload, scan_passed, included, excluded


def write_zip(zip_path: Path, payload: dict[str, bytes]) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for zpath in sorted(payload):
            zf.writestr(zpath, payload[zpath])


def inspect_zip(path: Path) -> int:
    if not path.exists():
        print(f"[inspect] missing: {path}")
        return 1
    with zipfile.ZipFile(path, "r") as zf:
        infos = zf.infolist()
        names = [i.filename for i in infos]
        top = sorted({n.split("/", 1)[0] for n in names if "/" in n})
        print(f"[inspect] zip={path}")
        print(f"[inspect] files={len(infos)}")
        print(f"[inspect] top_level_roots={top}")
        print("[inspect] first_entries=")
        for n in sorted(names)[:40]:
            print(f"  - {n}")
    return 0


def main() -> int:
    args = parse_args()
    if args.inspect:
        return inspect_zip(Path(args.inspect))

    repo_root = args.repo_root.resolve()
    candidates = collect_candidates(repo_root)
    manifest, payload, scan_passed, included, excluded = build_manifest_and_payload(repo_root, candidates)

    args.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if not args.dry_run:
        if not scan_passed:
            print("[build] blocked: unsafe required files detected")
            print(f"[build] manifest={args.manifest_path}")
            return 1
        write_zip(args.zip_path, payload)
        print(f"[build] zip={args.zip_path}")

    print(f"[build] manifest={args.manifest_path}")
    print(f"[build] included={len(included)}")
    print(f"[build] excluded={len(excluded)}")
    print(f"[build] unsafe_scan_passed={scan_passed}")
    print("[build] reproduction_commands:")
    for cmd in REPRO_COMMANDS:
        print(f"  - {cmd}")
    return 0 if scan_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
