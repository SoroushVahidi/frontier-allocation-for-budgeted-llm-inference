#!/usr/bin/env python3
"""Generate Tree-PLV conservative status artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate tree_plv status artifacts")
    p.add_argument(
        "--status-json",
        default="outputs/external_baseline_completeness/tree_plv_status.json",
    )
    p.add_argument(
        "--status-md",
        default="outputs/external_baseline_completeness/tree_plv_status.md",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc).isoformat()

    status: dict[str, Any] = {
        "generated_utc": now,
        "baseline_key": "tree_plv",
        "display_name": "Tree-PLV",
        "status": "import_validated",
        "classification": "partial_runnable_adjacent",
        "control_equivalence": "adjacent",
        "resource_level": "official_paper_and_paper_cited_repo",
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
            "paper": "https://aclanthology.org/2024.emnlp-main.125/",
            "paper_pdf": "https://aclanthology.org/2024.emnlp-main.125.pdf",
            "doi": "https://doi.org/10.18653/v1/2024.emnlp-main.125",
            "arxiv": "https://arxiv.org/abs/2407.00390",
            "paper_cited_repo": "https://github.com/Hareta-Leila/Tree-PLV",
        },
        "integration": {
            "contract": "configs/tree_plv_adjacent_comparison_contract_v1.json",
            "validator_script": "scripts/verify_tree_plv_import.py",
            "runner_script": "scripts/run_tree_plv_adjacent_integration.py",
            "validator_success_verdict": "import_validated",
            "runner_success_classification": "partial_runnable_adjacent",
        },
        "protocol": {
            "required_package_files": ["metadata.json", "results.csv"],
            "required_workflow_stages": [
                "tree_preference_pair_construction",
                "process_verifier_training_or_import",
                "benchmark_evaluation",
            ],
            "required_comparability_scope": "adjacent_only",
        },
        "safe_claims": [
            "This repo supports a stable, artifact-backed Tree-PLV adjacent lane with explicit provenance and claim guardrails.",
            "The lane validates paper↔repo mapping, contract completeness, and a benchmark-slice import package with machine-readable outputs.",
            "Classification is partial_runnable_adjacent, with explicit non-equivalence to direct branch-level budget allocation control.",
        ],
        "not_safe_claims": [
            "Full faithful in-repo reproduction of complete Tree-PLV training/evaluation stack.",
            "Direct control-equivalence against branch-level marginal frontier allocation methods.",
            "Claiming verified official checkpoints when none are confirmed in this pass.",
        ],
    }

    out_json = REPO_ROOT / args.status_json
    out_md = REPO_ROOT / args.status_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# tree_plv status",
        "",
        f"- Generated (UTC): `{now}`",
        "- Baseline: `tree_plv`",
        "- Status: `import_validated`",
        "- Classification: `partial_runnable_adjacent`",
        "- Control-equivalence: `adjacent`",
        "- Provenance level: `official_paper_and_paper_cited_repo`",
        "",
        "## Canonical integration hooks",
        "- Contract: `configs/tree_plv_adjacent_comparison_contract_v1.json`.",
        "- Validator: `scripts/verify_tree_plv_import.py`.",
        "- Runner: `scripts/run_tree_plv_adjacent_integration.py`.",
        "",
        "## Conservative interpretation",
        "- This lane is partial-runnable and adjacent-only.",
        "- It validates paper↔repo provenance and a contract-bound benchmark import slice.",
        "- It does not claim full faithful in-repo reproduction.",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
