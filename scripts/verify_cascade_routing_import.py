#!/usr/bin/env python3
"""Verify Cascade Routing adjacent import package.

Conservative scope:
- Adjacent import only (not direct in-repo reproduction claim).
- Requires explicit upstream pipeline-stage coverage reflecting the real repo workflow.
- Requires strategy coverage spanning routing/cascading/cascade-routing settings.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

REQUIRED_METADATA_FIELDS = [
    "source.type",
    "upstream.repo_url",
    "upstream.paper_url",
    "upstream.workflow_stages_completed",
    "dataset.name",
    "dataset.split",
    "budget.unit",
    "budget.metric",
    "strategy_space",
    "provenance.exported_at_utc",
    "provenance.source_uri",
    "provenance.artifact_id",
    "provenance.commit_or_version_if_available",
]

REQUIRED_WORKFLOW_STAGES = [
    "query_generation_or_data_download",
    "dataset_preprocessing",
    "routing_and_cascading_experiment_execution",
    "postprocess_result_aggregation",
]

REQUIRED_RESULTS_COLUMNS = [
    "mode",
    "source_type",
    "dataset",
    "split",
    "benchmark",
    "strategy_family",
    "max_expected_cost",
    "quality_metric",
    "quality_value",
    "cost_metric",
    "cost_value",
    "artifact_id",
    "commit_or_version",
    "comparability_scope",
]

ALLOWED_SOURCE_TYPES = {"official", "author-produced", "imported"}
ALLOWED_STRATEGY_FAMILIES = {"routing", "cascading", "cascade_routing"}


def _get_nested(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify cascade_routing adjacent import package")
    p.add_argument("--results-path", required=True, help="Path to package dir or results.csv")
    p.add_argument("--expected-dataset", required=True)
    p.add_argument("--expected-split", default="test")
    p.add_argument("--output-json", default=None)
    return p.parse_args()


def verify_cascade_routing_import(*, requested_path: Path, expected_dataset: str, expected_split: str) -> dict[str, Any]:
    issues: list[str] = []
    errors: list[str] = []

    if requested_path.is_dir():
        package_dir = requested_path
        metadata_json = package_dir / "metadata.json"
        results_csv = package_dir / "results.csv"
    else:
        package_dir = requested_path.parent
        metadata_json = package_dir / "metadata.json"
        results_csv = requested_path

    if not metadata_json.exists():
        issues.append(f"missing_required_file: {metadata_json}")
    if not results_csv.exists():
        issues.append(f"missing_required_file: {results_csv}")

    metadata: dict[str, Any] = {}
    if metadata_json.exists():
        try:
            metadata = json.loads(metadata_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid_metadata_json: {exc}")

    if metadata:
        for field in REQUIRED_METADATA_FIELDS:
            value = _get_nested(metadata, field)
            if value is None or (isinstance(value, str) and not value.strip()):
                issues.append(f"missing_metadata_field: {field}")

        source_type = str(_get_nested(metadata, "source.type") or "")
        if source_type not in ALLOWED_SOURCE_TYPES:
            issues.append("invalid_source_type")

        upstream_repo = str(_get_nested(metadata, "upstream.repo_url") or "")
        if "eth-sri/cascade-routing" not in upstream_repo:
            issues.append("upstream_repo_mismatch")

        dataset_name = str(_get_nested(metadata, "dataset.name") or "")
        dataset_split = str(_get_nested(metadata, "dataset.split") or "")
        if dataset_name != expected_dataset:
            issues.append(f"dataset_mismatch: expected={expected_dataset}, observed={dataset_name}")
        if dataset_split != expected_split:
            issues.append(f"split_mismatch: expected={expected_split}, observed={dataset_split}")

        observed_stages = _get_nested(metadata, "upstream.workflow_stages_completed")
        if not isinstance(observed_stages, list):
            issues.append("workflow_stages_not_list")
            observed_stages = []
        missing_stages = [s for s in REQUIRED_WORKFLOW_STAGES if s not in observed_stages]
        if missing_stages:
            issues.append(f"missing_required_workflow_stages: {missing_stages}")

        strategy_space = _get_nested(metadata, "strategy_space")
        if not isinstance(strategy_space, list) or not strategy_space:
            issues.append("strategy_space_missing_or_empty")
        else:
            declared = {str(v).strip() for v in strategy_space}
            missing = sorted(ALLOWED_STRATEGY_FAMILIES - declared)
            if missing:
                issues.append(f"metadata_missing_strategy_families: {missing}")

    rows: list[dict[str, Any]] = []
    if results_csv.exists():
        with results_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            for col in REQUIRED_RESULTS_COLUMNS:
                if col not in header:
                    issues.append(f"missing_results_column: {col}")
            rows = [dict(r) for r in reader]

    if not rows:
        issues.append("no_results_rows")

    observed_strategies: set[str] = set()
    normalized_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        mode = str(row.get("mode", "")).strip()
        source_type = str(row.get("source_type", "")).strip()
        dataset = str(row.get("dataset", "")).strip()
        split = str(row.get("split", "")).strip()
        strategy = str(row.get("strategy_family", "")).strip()
        scope = str(row.get("comparability_scope", "")).strip().lower()

        if mode != "cascade_routing_adjacent_import":
            issues.append(f"invalid_mode_row_{idx}")
        if source_type and source_type not in ALLOWED_SOURCE_TYPES:
            issues.append(f"invalid_source_type_row_{idx}")
        if dataset != expected_dataset:
            issues.append(f"dataset_row_mismatch_{idx}")
        if split != expected_split:
            issues.append(f"split_row_mismatch_{idx}")
        if strategy not in ALLOWED_STRATEGY_FAMILIES:
            issues.append(f"invalid_strategy_family_row_{idx}")
        if scope != "adjacent_only":
            issues.append(f"invalid_comparability_scope_row_{idx}")

        observed_strategies.add(strategy)

        for numeric_col in ["max_expected_cost", "quality_value", "cost_value"]:
            value = str(row.get(numeric_col, "")).strip()
            try:
                parsed = float(value)
                if parsed < 0:
                    issues.append(f"negative_{numeric_col}_row_{idx}")
            except ValueError:
                issues.append(f"non_numeric_{numeric_col}_row_{idx}")

        normalized_rows.append(
            {
                "mode": "cascade_routing_adjacent_import",
                "source": "cascade_routing_import_verified",
                "source_type": source_type,
                "dataset": dataset,
                "dataset_split": split,
                "benchmark": row.get("benchmark", ""),
                "strategy_family": strategy,
                "max_expected_cost": row.get("max_expected_cost", ""),
                "quality_metric": row.get("quality_metric", ""),
                "quality_value": row.get("quality_value", ""),
                "cost_metric": row.get("cost_metric", ""),
                "cost_value": row.get("cost_value", ""),
                "artifact_id": row.get("artifact_id", ""),
                "commit_or_version": row.get("commit_or_version", ""),
                "comparability_scope": "adjacent_only",
            }
        )

    for needed in sorted(ALLOWED_STRATEGY_FAMILIES):
        if needed not in observed_strategies:
            issues.append(f"missing_strategy_family_{needed}")

    return {
        "status": "valid" if not issues and not errors else "invalid",
        "baseline": "cascade_routing",
        "integration_kind": "adjacent_import_validator",
        "package_dir": str(package_dir),
        "issues": issues,
        "errors": errors,
        "imported_rows": normalized_rows,
        "safe_claim_scope": "adjacent_only",
        "unsafe_claims": [
            "direct in-repo full reproduction of upstream cascade-routing experiments",
            "control-space-equivalent direct baseline claims versus this repo's frontier/action controllers",
        ],
    }


def main() -> None:
    args = parse_args()
    report = verify_cascade_routing_import(
        requested_path=Path(args.results_path),
        expected_dataset=args.expected_dataset,
        expected_split=args.expected_split,
    )

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))

    if report["status"] != "valid":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
