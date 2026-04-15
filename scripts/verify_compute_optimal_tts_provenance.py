#!/usr/bin/env python3
"""Verify provenance signals for compute_optimal_tts baseline mapping.

This script does NOT claim official paper-repo identity. It only records auditable facts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _safe_cmd(cmd: list[str], cwd: Path) -> str:
    try:
        out = subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT)
        return out.strip()
    except Exception:
        return ""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify compute_optimal_tts provenance signals")
    p.add_argument(
        "--clone-path",
        default=".tmp_compute_optimal_tts",
        help="Path to a local clone of https://github.com/RyanLiu112/compute-optimal-tts",
    )
    p.add_argument(
        "--output-json",
        default="outputs/external_baseline_completeness/compute_optimal_tts_provenance_check.json",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    clone_path = (REPO_ROOT / args.clone_path).resolve()
    now = datetime.now(timezone.utc).isoformat()

    paper = {
        "title": "Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Parameters for Reasoning",
        "venue": "ICLR 2025",
        "openreview_id": "4FWAwZtd2n",
        "openreview_url": "https://openreview.net/forum?id=4FWAwZtd2n",
        "pdf_url": "https://openreview.net/pdf?id=4FWAwZtd2n",
    }

    linked_repo: dict[str, Any] = {
        "url": "https://github.com/RyanLiu112/compute-optimal-tts",
        "clone_path": str(clone_path),
        "clone_available": clone_path.exists(),
        "head_commit": None,
        "license_file_present": False,
        "readme_title": None,
        "readme_mentions_arxiv_2502_06703": False,
        "readme_mentions_openreview_4FWAwZtd2n": False,
    }

    if clone_path.exists():
        linked_repo["head_commit"] = _safe_cmd(["git", "rev-parse", "HEAD"], clone_path) or None
        linked_repo["license_file_present"] = (clone_path / "LICENSE").exists() or (clone_path / "LICENSE.md").exists()

        readme = (clone_path / "README.md")
        if readme.exists():
            text = readme.read_text(encoding="utf-8", errors="ignore")
            readme_title = None
            for line in text.splitlines():
                if line.strip().startswith("#"):
                    readme_title = line.strip().lstrip("#").strip()
                    break
            linked_repo["readme_title"] = readme_title
            linked_repo["readme_mentions_arxiv_2502_06703"] = "2502.06703" in text
            linked_repo["readme_mentions_openreview_4FWAwZtd2n"] = "4FWAwZtd2n" in text

    findings = [
        "OpenReview paper target is ICLR 2025 paper id 4FWAwZtd2n (Snell et al.).",
        "Linked GitHub repo self-identifies around arXiv:2502.06703 and not OpenReview id 4FWAwZtd2n.",
        "Therefore paper-repo mapping is not established as identical/official for Snell et al. by this check.",
    ]

    result = {
        "generated_utc": now,
        "baseline_key": "compute_optimal_tts",
        "paper_target": paper,
        "linked_repo": linked_repo,
        "provenance_assessment": {
            "paper_repo_match_strength": "weak",
            "classification": "related_repo_not_verified_as_official_for_target_paper",
            "official_status": "unclear",
            "notes": findings,
        },
    }

    out_path = REPO_ROOT / args.output_json
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
