#!/usr/bin/env python3
"""Verify ReST-MCTS adjacent import package.

Conservative scope:
- Adjacent import only (not direct in-repo reproduction claim).
- Requires explicit workflow-stage declarations aligned to upstream ReST-MCTS pipeline.
- Requires explicit MCTS-search result rows under fixed search settings.
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
    "models.policy_model_family",
    "models.value_model_family",
    "search.iteration_limits",
    "search.branch_factors",
    "self_training.iterations_completed",
    "provenance.exported_at_utc",
    "provenance.source_uri",
    "provenance.artifact_id",
    "provenance.commit_or_version_if_available",
]

REQUIRED_WORKFLOW_STAGES = [
    "value_model_bootstrap_or_training",
    "mcts_trace_generation",
    "policy_self_training",
    "benchmark_evaluation",
]

REQUIRED_RESULTS_COLUMNS = [
    "mode",
    "source_type",
    "dataset",
    "split",
    "policy_model",
    "value_model",
    "search_mode",
    "self_training_iteration",
    "iteration_limit",
    "branch",
    "accuracy",
    "num_examples",
    "artifact_id",
    "commit_or_version",
    "comparability_scope",
]

ALLOWED_SOURCE_TYPES = {"official", "author-produced", "imported"}
ALLOWED_SEARCH_MODES = {"mcts", "cot", "tot"}


def _get_nested(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify ReST-MCTS adjacent import package")
    p.add_argument("--results-path", required=True, help="Path to package dir or results.csv")
    p.add_argument("--expected-dataset", required=True)
    p.add_argument("--expected-split", default="test")
    p.add_argument("--output-json", default=None)
    return p.parse_args()


def verify_rest_mcts_import(*, requested_path: Path, expected_dataset: str, expected_split: str) -> dict[str, Any]:
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
        if "THUDM/ReST-MCTS" not in upstream_repo:
            issues.append("upstream_repo_mismatch")

        observed_stages = _get_nested(metadata, "upstream.workflow_stages_completed")
        if not isinstance(observed_stages, list):
            issues.append("workflow_stages_not_list")
            observed_stages = []
        missing_stages = [s for s in REQUIRED_WORKFLOW_STAGES if s not in observed_stages]
        if missing_stages:
            issues.append(f"missing_required_workflow_stages: {missing_stages}")

        dataset_name = str(_get_nested(metadata, "dataset.name") or "")
        dataset_split = str(_get_nested(metadata, "dataset.split") or "")
        if dataset_name != expected_dataset:
            issues.append(f"dataset_mismatch: expected={expected_dataset}, observed={dataset_name}")
        if dataset_split != expected_split:
            issues.append(f"split_mismatch: expected={expected_split}, observed={dataset_split}")

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

    observed_search_modes: set[str] = set()
    normalized_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        mode = str(row.get("mode", "")).strip()
        source_type = str(row.get("source_type", "")).strip()
        dataset = str(row.get("dataset", "")).strip()
        split = str(row.get("split", "")).strip()
        search_mode = str(row.get("search_mode", "")).strip().lower()
        scope = str(row.get("comparability_scope", "")).strip().lower()

        if mode != "rest_mcts_adjacent_import":
            issues.append(f"invalid_mode_row_{idx}")
        if source_type and source_type not in ALLOWED_SOURCE_TYPES:
            issues.append(f"invalid_source_type_row_{idx}")
        if dataset != expected_dataset:
            issues.append(f"dataset_row_mismatch_{idx}")
        if split != expected_split:
            issues.append(f"split_row_mismatch_{idx}")
        if search_mode not in ALLOWED_SEARCH_MODES:
            issues.append(f"invalid_search_mode_row_{idx}")
        if scope != "adjacent_only":
            issues.append(f"invalid_comparability_scope_row_{idx}")

        observed_search_modes.add(search_mode)

        for int_col in ["self_training_iteration", "iteration_limit", "branch", "num_examples"]:
            value = str(row.get(int_col, "")).strip()
            try:
                parsed = int(float(value))
                if parsed <= 0:
                    issues.append(f"non_positive_{int_col}_row_{idx}")
            except ValueError:
                issues.append(f"non_numeric_{int_col}_row_{idx}")

        accuracy_raw = str(row.get("accuracy", "")).strip()
        try:
            accuracy = float(accuracy_raw)
            if not (0.0 <= accuracy <= 1.0):
                issues.append(f"accuracy_out_of_range_row_{idx}")
        except ValueError:
            issues.append(f"non_numeric_accuracy_row_{idx}")

        normalized_rows.append(
            {
                "mode": "rest_mcts_adjacent_import",
                "source": "rest_mcts_import_verified",
                "source_type": source_type,
                "dataset": dataset,
                "dataset_split": split,
                "policy_model": row.get("policy_model", ""),
                "value_model": row.get("value_model", ""),
                "search_mode": search_mode,
                "self_training_iteration": row.get("self_training_iteration", ""),
                "iteration_limit": row.get("iteration_limit", ""),
                "branch": row.get("branch", ""),
                "accuracy": row.get("accuracy", ""),
                "num_examples": row.get("num_examples", ""),
                "artifact_id": row.get("artifact_id", ""),
                "commit_or_version": row.get("commit_or_version", ""),
                "comparability_scope": "adjacent_only",
            }
        )

    if "mcts" not in observed_search_modes:
        issues.append("missing_mcts_search_mode")

    return {
        "status": "valid" if not issues and not errors else "invalid",
        "baseline": "rest_mcts",
        "integration_kind": "adjacent_import_validator",
        "package_dir": str(package_dir),
        "issues": sorted(set(issues)),
        "errors": errors,
        "imported_rows": normalized_rows if not issues and not errors else [],
        "safe_claim_scope": "adjacent_only",
        "unsafe_claims": [
            "direct in-repo full reproduction of upstream ReST-MCTS self-training stack",
            "control-space-equivalent direct comparability claims versus frontier/action-native controllers",
        ],
    }


def main() -> None:
    args = parse_args()
    report = verify_rest_mcts_import(
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
