#!/usr/bin/env python3
"""Generate OpenR conservative status artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate openr status artifacts")
    p.add_argument(
        "--status-json",
        default="outputs/external_baseline_completeness/openr_status.json",
    )
    p.add_argument(
        "--status-md",
        default="outputs/external_baseline_completeness/openr_status.md",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc).isoformat()

    status: dict[str, Any] = {
        "generated_utc": now,
        "baseline_key": "openr",
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
            "repo": "https://github.com/openreasoner/openr",
            "readme": "https://github.com/openreasoner/openr/blob/main/README.md",
            "paper": "https://arxiv.org/abs/2410.09671",
            "project_page": "https://openreasoner.github.io/",
        },
        "protocol": {
            "validator_script": "scripts/verify_openr_import.py",
            "required_package_files": ["metadata.json", "results.csv"],
            "required_workflow_stages": [
                "lm_rm_service_startup",
                "inference_evaluation_run",
                "result_artifact_export",
            ],
            "required_strategy_coverage": ["cot", "at_least_one_tree_search_method"],
            "comparability_scope": "adjacent_only",
        },
        "safe_claims": [
            "This repo supports reviewer-auditable adjacent import of OpenR inference outputs.",
            "Imported outputs are validated for workflow declarations, strategy coverage, and adjacent-only comparability scope.",
        ],
        "not_safe_claims": [
            "Direct in-repo full reproduction of upstream OpenR training/serving stack.",
            "Control-equivalent direct comparability claims with frontier/action-native controllers.",
        ],
    }

    out_json = REPO_ROOT / args.status_json
    out_md = REPO_ROOT / args.status_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# openr status",
        "",
        f"- Generated (UTC): `{now}`",
        "- Baseline: `openr`",
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
            "- Strategy coverage must include `cot` and at least one tree-search method (`beam_search`, `vanila_mcts`, or `rstar_mcts`).",
            "- Comparability scope must be explicitly `adjacent_only`.",
            "",
            "## Safe vs unsafe claims",
            "Safe now:",
            "- Validated adjacent import for OpenR outputs.",
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
