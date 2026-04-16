#!/usr/bin/env python3
"""Generate MoB conservative status artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate mob_majority_of_bests status artifacts")
    p.add_argument(
        "--status-json",
        default="outputs/external_baseline_completeness/mob_majority_of_bests_status.json",
    )
    p.add_argument(
        "--status-md",
        default="outputs/external_baseline_completeness/mob_majority_of_bests_status.md",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc).isoformat()

    status: dict[str, Any] = {
        "generated_utc": now,
        "baseline_key": "mob_majority_of_bests",
        "status": "runnable_adjacent",
        "integration_kind": "verified_import_only",
        "status_taxonomy": [
            "runnable_direct",
            "runnable_adjacent",
            "mode_a_only",
            "mode_b_partial",
            "link_only",
            "discuss_only",
            "blocked",
        ],
        "upstream": {
            "repo": "https://github.com/arakhsha/mob",
            "paper": "https://openreview.net/forum?id=aEAbRPXV37",
            "venue_page": "https://neurips.cc/virtual/2025/poster/117285",
        },
        "protocol": {
            "validator_script": "scripts/verify_mob_import.py",
            "required_package_files": ["metadata.json", "results.csv"],
            "required_workflow_stages": [
                "dataset_loading_from_jsonl_gz",
                "algorithm_evaluation_via_main_py",
                "aggregated_csv_export",
            ],
            "required_algorithm_coverage": ["bon", "at_least_one_mob_variant"],
            "comparability_scope": "adjacent_only",
        },
        "safe_claims": [
            "This repo supports reviewer-auditable adjacent import of MoB evaluation outputs.",
            "Imported outputs are validated for workflow declarations, BoN+MoB algorithm coverage, and adjacent-only scope.",
        ],
        "not_safe_claims": [
            "Direct in-repo full reproduction of the upstream MoB benchmark stack.",
            "Control-equivalent direct comparability claims with frontier/action-native controllers.",
        ],
    }

    out_json = REPO_ROOT / args.status_json
    out_md = REPO_ROOT / args.status_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# mob_majority_of_bests status",
        "",
        f"- Generated (UTC): `{now}`",
        "- Baseline: `mob_majority_of_bests`",
        "- Status: `runnable_adjacent`",
        "- Integration kind: `verified_import_only`",
        "",
        "## Conservative interpretation",
        "- This is an adjacent import protocol, not full in-repo reproduction.",
        "- Imported outputs must pass strict contract validation.",
        "",
        "## Required import contract highlights",
        "- Required files: `metadata.json` and `results.csv`.",
        "- Required workflow-stage declarations:",
    ]
    for stage in status["protocol"]["required_workflow_stages"]:
        lines.append(f"  - {stage}")
    lines.extend(
        [
            "- Algorithm coverage must include `bon` and at least one `mob_*` variant.",
            "- Comparability scope must be explicitly `adjacent_only`.",
            "",
            "## Safe vs unsafe claims",
            "Safe now:",
            "- Validated adjacent import for MoB outputs.",
            "",
            "Not safe now:",
            "- Claiming direct in-repo reproduction or control-equivalent comparability.",
        ]
    )

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
