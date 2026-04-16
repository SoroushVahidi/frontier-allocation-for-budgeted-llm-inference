#!/usr/bin/env python3
"""Generate Cascade Routing conservative status artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate cascade_routing status artifacts")
    p.add_argument(
        "--status-json",
        default="outputs/external_baseline_completeness/cascade_routing_status.json",
    )
    p.add_argument(
        "--status-md",
        default="outputs/external_baseline_completeness/cascade_routing_status.md",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc).isoformat()

    status: dict[str, Any] = {
        "generated_utc": now,
        "baseline_key": "cascade_routing",
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
            "repo": "https://github.com/eth-sri/cascade-routing",
            "paper": "https://proceedings.mlr.press/v267/dekoninck25a.html",
            "openreview": "https://openreview.net/forum?id=rgDwRdMwoS",
            "project_page": "https://www.sri.inf.ethz.ch/publications/dekoninck2024cascaderouting",
        },
        "protocol": {
            "validator_script": "scripts/verify_cascade_routing_import.py",
            "required_package_files": ["metadata.json", "results.csv"],
            "required_workflow_stages": [
                "query_generation_or_data_download",
                "dataset_preprocessing",
                "routing_and_cascading_experiment_execution",
                "postprocess_result_aggregation",
            ],
            "required_strategy_coverage": ["routing", "cascading", "cascade_routing"],
            "comparability_scope": "adjacent_only",
        },
        "safe_claims": [
            "This repo supports reviewer-auditable adjacent import of cascade-routing outputs.",
            "Imported outputs are validated for upstream workflow-stage declarations, strategy-family coverage, and adjacent-only scope.",
        ],
        "not_safe_claims": [
            "Direct in-repo full reproduction of the upstream cascade-routing experiment stack.",
            "Control-equivalent direct comparability claims with frontier/action-native controllers.",
        ],
    }

    out_json = REPO_ROOT / args.status_json
    out_md = REPO_ROOT / args.status_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# cascade_routing status",
        "",
        f"- Generated (UTC): `{now}`",
        "- Baseline: `cascade_routing`",
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
            "- Strategy coverage must include `routing`, `cascading`, and `cascade_routing`.",
            "- Comparability scope must be explicitly `adjacent_only`.",
            "",
            "## Safe vs unsafe claims",
            "Safe now:",
            "- Validated adjacent import for cascade-routing outputs.",
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
