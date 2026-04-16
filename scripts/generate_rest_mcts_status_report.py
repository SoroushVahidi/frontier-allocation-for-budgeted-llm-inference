#!/usr/bin/env python3
"""Generate ReST-MCTS conservative status artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate rest_mcts status artifacts")
    p.add_argument(
        "--status-json",
        default="outputs/external_baseline_completeness/rest_mcts_status.json",
    )
    p.add_argument(
        "--status-md",
        default="outputs/external_baseline_completeness/rest_mcts_status.md",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc).isoformat()

    status: dict[str, Any] = {
        "generated_utc": now,
        "baseline_key": "rest_mcts",
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
            "repo": "https://github.com/THUDM/ReST-MCTS",
            "readme": "https://github.com/THUDM/ReST-MCTS/blob/main/README.md",
            "paper": "https://arxiv.org/abs/2406.03816",
            "project_page": "https://rest-mcts.github.io/",
        },
        "protocol": {
            "validator_script": "scripts/verify_rest_mcts_import.py",
            "required_package_files": ["metadata.json", "results.csv"],
            "required_workflow_stages": [
                "value_model_bootstrap_or_training",
                "mcts_trace_generation",
                "policy_self_training",
                "benchmark_evaluation",
            ],
            "required_search_coverage": ["mcts"],
            "comparability_scope": "adjacent_only",
        },
        "safe_claims": [
            "This repo supports reviewer-auditable adjacent import of ReST-MCTS outputs.",
            "Imported outputs are validated for upstream workflow declarations, fixed search metadata, and explicit adjacent-only scope.",
        ],
        "not_safe_claims": [
            "Direct in-repo full reproduction of upstream ReST-MCTS self-training and training-stack results.",
            "Control-equivalent direct comparability claims with frontier/action-native controllers.",
        ],
    }

    out_json = REPO_ROOT / args.status_json
    out_md = REPO_ROOT / args.status_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# rest_mcts status",
        "",
        f"- Generated (UTC): `{now}`",
        "- Baseline: `rest_mcts`",
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
            "- Results must include `mcts` search rows with explicit search settings and metrics.",
            "- Comparability scope must be explicitly `adjacent_only`.",
            "",
            "## Safe vs unsafe claims",
            "Safe now:",
            "- Validated adjacent import for ReST-MCTS outputs.",
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
