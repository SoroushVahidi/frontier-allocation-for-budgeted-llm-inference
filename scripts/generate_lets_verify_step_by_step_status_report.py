#!/usr/bin/env python3
"""Generate Let's Verify Step by Step status artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate lets_verify_step_by_step status artifacts")
    p.add_argument(
        "--status-json",
        default="outputs/external_baseline_completeness/lets_verify_step_by_step_status.json",
    )
    p.add_argument(
        "--status-md",
        default="outputs/external_baseline_completeness/lets_verify_step_by_step_status.md",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc).isoformat()

    status: dict[str, Any] = {
        "generated_utc": now,
        "baseline_key": "lets_verify_step_by_step",
        "display_name": "Let's Verify Step by Step",
        "status": "import_validated",
        "classification": "partial_runnable_adjacent",
        "control_equivalence": "adjacent",
        "resource_level": "official",
        "integration_kind": "official_adjacent_partial_runnable_contract_lane",
        "status_taxonomy": [
            "runnable_direct",
            "runnable_adjacent",
            "adapter_based",
            "import_validated",
            "discuss_only",
            "blocked",
            "broken_needs_repair",
        ],
        "upstream": {
            "repo": "https://github.com/openai/prm800k",
            "paper": "https://arxiv.org/abs/2305.20050",
            "paper_pdf": "https://arxiv.org/pdf/2305.20050.pdf",
            "doi": "https://doi.org/10.48550/arXiv.2305.20050",
        },
        "integration": {
            "contract": "configs/lets_verify_step_by_step_adjacent_comparison_contract_v1.json",
            "validator_script": "scripts/verify_lets_verify_step_by_step_import.py",
            "runner_script": "scripts/run_lets_verify_step_by_step_adjacent_integration.py",
            "validator_success_verdict": "import_validated",
            "runner_success_classification": "partial_runnable_adjacent",
        },
        "protocol": {
            "required_package_files": ["metadata.json", "results.csv"],
            "required_workflow_stages": [
                "dataset_ready",
                "verifier_scoring_or_import",
                "math_split_evaluation",
            ],
            "required_comparability_scope": "adjacent_only",
        },
        "safe_claims": [
            "This repo supports an artifact-backed partial-runnable adjacent lane for Let's Verify Step by Step using official public PRM800K assets.",
            "The lane validates official-source mapping, repo layout expectations, and contract-bound MATH import subset outputs.",
            "Comparisons are adjacent-only and explicitly not treated as branch-allocation control-equivalent.",
        ],
        "not_safe_claims": [
            "Full faithful end-to-end reproduction of the complete paper-scale training/evaluation pipeline.",
            "Direct control-equivalence to branch-level marginal frontier allocation methods.",
        ],
    }

    out_json = REPO_ROOT / args.status_json
    out_md = REPO_ROOT / args.status_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# lets_verify_step_by_step status",
        "",
        f"- Generated (UTC): `{now}`",
        "- Baseline: `lets_verify_step_by_step`",
        "- Status: `import_validated`",
        "- Classification: `partial_runnable_adjacent`",
        "- Control-equivalence: `adjacent`",
        "- Provenance level: `official`",
        "",
        "## Canonical integration hooks",
        "- Contract: `configs/lets_verify_step_by_step_adjacent_comparison_contract_v1.json`.",
        "- Validator: `scripts/verify_lets_verify_step_by_step_import.py`.",
        "- Runner: `scripts/run_lets_verify_step_by_step_adjacent_integration.py`.",
        "",
        "## Conservative interpretation",
        "- This lane is partial-runnable and adjacent-only.",
        "- It verifies public PRM800K assets and a contract-bound MATH import slice.",
        "- It does not claim full in-repo faithful reproduction.",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
