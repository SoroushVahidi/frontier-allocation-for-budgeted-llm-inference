#!/usr/bin/env python3
"""Generate BEST-Route conservative status artifacts for this repository."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate BEST-Route status report artifacts")
    p.add_argument(
        "--status-json",
        default="outputs/external_baseline_completeness/best_route_status.json",
    )
    p.add_argument(
        "--status-md",
        default="outputs/external_baseline_completeness/best_route_status.md",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc).isoformat()

    status: dict[str, Any] = {
        "generated_utc": now,
        "baseline_key": "best_route_microsoft",
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
            "repo": "https://github.com/microsoft/best-route-llm",
            "paper": "https://arxiv.org/abs/2506.22716",
            "project_page": "https://www.microsoft.com/en-us/research/publication/best-route-adaptive-llm-routing-with-test-time-optimal-compute/",
        },
        "protocol": {
            "validator_script": "scripts/verify_best_route_import.py",
            "required_package_files": ["metadata.json", "results.csv"],
            "required_workflow_stages": [
                "mixed_prompt_construction",
                "multi_sample_response_generation",
                "armoRM_scoring",
                "proxy_reward_model_scoring",
                "router_training",
            ],
            "candidate_arm_requirement": "model+best-of-n arms must include bo1 and at least one bo>1",
            "comparability_scope": "adjacent_only",
        },
        "safe_claims": [
            "This repo now supports a reviewer-auditable BEST-Route adjacent import path.",
            "Imports are validated for workflow-stage declarations, candidate-arm structure, and explicit adjacent-only scope.",
        ],
        "not_safe_claims": [
            "Direct apples-to-apples BEST-Route reproduction inside this repo.",
            "Control-space equivalence between BEST-Route bo-arm routing and this repo's frontier/action substrate.",
        ],
    }

    out_json = REPO_ROOT / args.status_json
    out_md = REPO_ROOT / args.status_md
    out_json.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# BEST-Route status",
        "",
        f"- Generated (UTC): `{now}`",
        "- Baseline: `best_route_microsoft`",
        "- Status: `runnable_adjacent`",
        "- Integration kind: `verified_import_only`",
        "",
        "## Conservative interpretation",
        "- This is an **adjacent import protocol**, not an in-repo full reproduction.",
        "- Imported artifacts must pass strict contract validation before use.",
        "",
        "## Required import contract highlights",
        "- Required files: `metadata.json` and `results.csv`.",
        "- Required workflow-stage declarations:",
    ]

    for stage in status["protocol"]["required_workflow_stages"]:
        lines.append(f"  - {stage}")

    lines.extend(
        [
            "- Candidate arms must encode model+best-of-n variants and include both bo1 and bo>1.",
            "- Comparability scope must be explicitly `adjacent_only`.",
            "",
            "## Safe vs unsafe claims",
            "Safe now:",
            "- Reviewer-auditable BEST-Route import/validation path exists in this repo.",
            "",
            "Not safe now:",
            "- Claiming direct, apples-to-apples in-repo BEST-Route reproduction.",
        ]
    )

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
