#!/usr/bin/env python3
"""Generate BEST-Route import-package templates aligned with repo validator contract."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "external" / "best_route_microsoft" / "package_templates"
DEFAULT_DATASETS = ["math500", "aime2024", "olympiadbench"]

REQUIRED_WORKFLOW_STAGES = [
    "mixed_prompt_construction",
    "multi_sample_response_generation",
    "armoRM_scoring",
    "proxy_reward_model_scoring",
    "router_training",
]

RESULTS_COLUMNS = [
    "mode",
    "source_type",
    "dataset",
    "split",
    "router_strategy",
    "budget_setting",
    "accuracy",
    "avg_token_cost",
    "candidate_arm_space",
    "comparability_scope",
    "artifact_id",
    "commit_or_version",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate BEST-Route import package templates for canonical datasets"
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Directory where per-dataset template packages are written",
    )
    parser.add_argument(
        "--datasets",
        default=",".join(DEFAULT_DATASETS),
        help="Comma-separated dataset labels (validator-facing) to generate",
    )
    parser.add_argument(
        "--include-gsm8k",
        action="store_true",
        help="Also generate a gsm8k template for consistency",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing template package files",
    )
    return parser.parse_args()


def _dataset_list(raw: str, include_gsm8k: bool) -> list[str]:
    datasets = [item.strip() for item in raw.split(",") if item.strip()]
    ordered: list[str] = []
    seen: set[str] = set()
    for dataset in datasets + (["gsm8k"] if include_gsm8k else []):
        if dataset not in seen:
            ordered.append(dataset)
            seen.add(dataset)
    return ordered


def _metadata(dataset: str) -> dict:
    return {
        "template_notice": {
            "is_template": True,
            "replace_before_treating_as_real_import": True,
            "description": "Placeholder package generated from validator contract; replace all TEMPLATE_* values with real BEST-Route export data.",
        },
        "source": {"type": "imported"},
        "upstream": {
            "repo_url": "https://github.com/microsoft/best-route-llm",
            "paper_url": "https://arxiv.org/abs/2506.22716",
            "workflow_stages_completed": REQUIRED_WORKFLOW_STAGES,
        },
        "dataset": {"name": dataset, "split": "test"},
        "budget": {"unit": "actions", "settings": [1, 2]},
        "candidate_arms": [
            {
                "arm_id": "template_llama3_8b_bo1",
                "model_name": "TEMPLATE_MODEL_NAME",
                "best_of_n": 1,
            },
            {
                "arm_id": "template_llama3_8b_bo3",
                "model_name": "TEMPLATE_MODEL_NAME",
                "best_of_n": 3,
            },
        ],
        "provenance": {
            "exported_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_uri": "TEMPLATE_SOURCE_URI_REPLACE_ME",
            "artifact_id": f"TEMPLATE_{dataset}_artifact",
            "commit_or_version_if_available": "TEMPLATE_COMMIT_OR_VERSION",
        },
    }


def _results_rows(dataset: str) -> list[dict[str, str]]:
    return [
        {
            "mode": "best_route_adjacent_import",
            "source_type": "imported",
            "dataset": dataset,
            "split": "test",
            "router_strategy": "TEMPLATE_ROUTER_STRATEGY",
            "budget_setting": "budget_1",
            "accuracy": "0.5000",
            "avg_token_cost": "100.0",
            "candidate_arm_space": "template_llama3_8b_bo1|template_llama3_8b_bo3",
            "comparability_scope": "adjacent_only",
            "artifact_id": f"TEMPLATE_{dataset}_artifact",
            "commit_or_version": "TEMPLATE_COMMIT_OR_VERSION",
        },
        {
            "mode": "best_route_adjacent_import",
            "source_type": "imported",
            "dataset": dataset,
            "split": "test",
            "router_strategy": "TEMPLATE_ROUTER_STRATEGY",
            "budget_setting": "budget_2",
            "accuracy": "0.5500",
            "avg_token_cost": "150.0",
            "candidate_arm_space": "template_llama3_8b_bo1|template_llama3_8b_bo3",
            "comparability_scope": "adjacent_only",
            "artifact_id": f"TEMPLATE_{dataset}_artifact",
            "commit_or_version": "TEMPLATE_COMMIT_OR_VERSION",
        },
    ]


def _write_template(package_dir: Path, dataset: str, force: bool) -> None:
    package_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = package_dir / "metadata.json"
    results_path = package_dir / "results.csv"

    if not force and (metadata_path.exists() or results_path.exists()):
        raise FileExistsError(
            f"Template package already exists for dataset={dataset} at {package_dir}; use --force to overwrite"
        )

    metadata_path.write_text(json.dumps(_metadata(dataset), indent=2) + "\n", encoding="utf-8")

    with results_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULTS_COLUMNS)
        writer.writeheader()
        for row in _results_rows(dataset):
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root).resolve()
    datasets = _dataset_list(args.datasets, args.include_gsm8k)
    if not datasets:
        raise ValueError("No datasets resolved; provide --datasets")

    created_paths: list[str] = []
    for dataset in datasets:
        package_dir = output_root / dataset
        _write_template(package_dir, dataset, force=args.force)
        created_paths.append(str(package_dir))

    print(
        json.dumps(
            {
                "output_root": str(output_root),
                "datasets": datasets,
                "created_packages": created_paths,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
