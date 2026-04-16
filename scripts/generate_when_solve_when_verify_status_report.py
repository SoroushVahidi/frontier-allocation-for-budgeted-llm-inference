#!/usr/bin/env python3
"""Generate When-To-Solve-When-To-Verify conservative status artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate when_solve_when_verify status artifacts")
    p.add_argument(
        "--status-json",
        default="outputs/external_baseline_completeness/when_solve_when_verify_status.json",
    )
    p.add_argument(
        "--status-md",
        default="outputs/external_baseline_completeness/when_solve_when_verify_status.md",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc).isoformat()

    status: dict[str, Any] = {
        "generated_utc": now,
        "baseline_key": "when_solve_when_verify",
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
            "repo": "https://github.com/nishadsinghi/sc-genrm-scaling",
            "paper": "https://arxiv.org/abs/2504.01005",
            "hf_org": "https://huggingface.co/sc-genrm-scaling",
        },
        "protocol": {
            "validator_script": "scripts/verify_when_solve_when_verify_import.py",
            "required_package_files": ["metadata.json", "results.csv"],
            "required_workflow_stages": [
                "solution_generation",
                "verification_generation",
                "fixed_budget_evaluation",
            ],
            "required_strategy_coverage": [
                "self_consistency",
                "at_least_one_genrm_strategy",
            ],
            "comparability_scope": "adjacent_only",
        },
        "safe_claims": [
            "This repo supports reviewer-auditable adjacent import of SC-vs-GenRM fixed-budget results.",
            "Imported outputs are validated for stage declarations, strategy-family coverage, and adjacent-only scope.",
        ],
        "not_safe_claims": [
            "Direct in-repo reproduction of full upstream generation+verification stack.",
            "Control-space equivalence with this repo's frontier/action-native methods.",
        ],
    }

    out_json = REPO_ROOT / args.status_json
    out_md = REPO_ROOT / args.status_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# when_solve_when_verify status",
        "",
        f"- Generated (UTC): `{now}`",
        "- Baseline: `when_solve_when_verify`",
        "- Status: `runnable_adjacent`",
        "- Integration kind: `verified_import_only`",
        "",
        "## Conservative interpretation",
        "- This is an adjacent import protocol, not a full in-repo reproduction.",
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
            "- Strategy coverage must include `self_consistency` and at least one `genrm_*` strategy.",
            "- Comparability scope must be explicitly `adjacent_only`.",
            "",
            "## Safe vs unsafe claims",
            "Safe now:",
            "- Validated adjacent import for fixed-budget SC-vs-GenRM comparisons.",
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
