#!/usr/bin/env python3
"""Verify BEST-Route adjacent import package against a conservative contract.

This validator is intentionally strict about provenance and explicit about comparability:
- Accepts only adjacent import mode (not direct apples-to-apples reproduction claims).
- Requires explicit BEST-Route workflow-stage declarations.
- Requires model+best-of-n candidate-arm declarations (bo1 and bo>1 present).
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
    "budget.settings",
    "candidate_arms",
    "provenance.exported_at_utc",
    "provenance.source_uri",
    "provenance.artifact_id",
    "provenance.commit_or_version_if_available",
]

REQUIRED_WORKFLOW_STAGES = [
    "mixed_prompt_construction",
    "multi_sample_response_generation",
    "armoRM_scoring",
    "proxy_reward_model_scoring",
    "router_training",
]

REQUIRED_RESULTS_COLUMNS = [
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

ALLOWED_SOURCE_TYPES = {"official", "author-produced", "imported"}


def _get_nested(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _parse_budget_setting(raw: str) -> int | None:
    text = str(raw).strip().lower()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text.startswith("budget_"):
        cand = text.split("budget_", 1)[1]
        if cand.isdigit():
            return int(cand)
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify BEST-Route adjacent import package")
    p.add_argument("--results-path", required=True, help="Path to package dir or to results.csv")
    p.add_argument("--expected-dataset", required=True)
    p.add_argument("--expected-split", default="test")
    p.add_argument("--expected-budgets", required=True, help="Comma-separated integer budgets")
    p.add_argument("--output-json", default=None)
    return p.parse_args()


def verify_best_route_import(
    *,
    requested_path: Path,
    expected_dataset: str,
    expected_split: str,
    expected_budgets: set[int],
) -> dict[str, Any]:
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
        if "microsoft/best-route-llm" not in upstream_repo:
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

        candidate_arms = _get_nested(metadata, "candidate_arms")
        if not isinstance(candidate_arms, list) or not candidate_arms:
            issues.append("candidate_arms_missing_or_empty")
            candidate_arms = []

        observed_best_of_n: set[int] = set()
        for idx, arm in enumerate(candidate_arms):
            if not isinstance(arm, dict):
                issues.append(f"candidate_arm_not_object_{idx}")
                continue
            arm_id = str(arm.get("arm_id", "")).strip()
            model_name = str(arm.get("model_name", "")).strip()
            if not arm_id:
                issues.append(f"candidate_arm_missing_arm_id_{idx}")
            if not model_name:
                issues.append(f"candidate_arm_missing_model_name_{idx}")
            try:
                bon = int(arm.get("best_of_n"))
                if bon < 1:
                    issues.append(f"candidate_arm_invalid_best_of_n_{idx}")
                else:
                    observed_best_of_n.add(bon)
            except Exception:
                issues.append(f"candidate_arm_invalid_best_of_n_{idx}")

        if 1 not in observed_best_of_n:
            issues.append("candidate_arms_missing_bo1")
        if not any(v > 1 for v in observed_best_of_n):
            issues.append("candidate_arms_missing_bo_gt_1")

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

    observed_budgets: set[int] = set()
    normalized_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        mode = str(row.get("mode", "")).strip()
        source_type = str(row.get("source_type", "")).strip()
        dataset = str(row.get("dataset", "")).strip()
        split = str(row.get("split", "")).strip()
        comparability = str(row.get("comparability_scope", "")).strip().lower()
        arm_space = str(row.get("candidate_arm_space", "")).strip().lower()

        if mode != "best_route_adjacent_import":
            issues.append(f"invalid_mode_row_{idx}")
        if source_type and source_type not in ALLOWED_SOURCE_TYPES:
            issues.append(f"invalid_source_type_row_{idx}")
        if dataset != expected_dataset:
            issues.append(f"dataset_row_mismatch_{idx}")
        if split != expected_split:
            issues.append(f"split_row_mismatch_{idx}")
        if comparability != "adjacent_only":
            issues.append(f"invalid_comparability_scope_row_{idx}")
        if "bo" not in arm_space:
            issues.append(f"missing_bo_marker_in_candidate_arm_space_row_{idx}")

        budget = _parse_budget_setting(str(row.get("budget_setting", "")))
        if budget is None:
            issues.append(f"unparseable_budget_setting_row_{idx}")
        else:
            observed_budgets.add(budget)

        for metric_col in ["accuracy", "avg_token_cost"]:
            value = str(row.get(metric_col, "")).strip()
            try:
                parsed = float(value)
                if metric_col == "accuracy" and not (0.0 <= parsed <= 1.0):
                    issues.append(f"metric_out_of_range_{metric_col}_row_{idx}")
                if metric_col == "avg_token_cost" and parsed < 0.0:
                    issues.append(f"metric_negative_{metric_col}_row_{idx}")
            except ValueError:
                issues.append(f"non_numeric_{metric_col}_row_{idx}")

        normalized_rows.append(
            {
                "mode": "best_route_adjacent_import",
                "source": "best_route_import_verified",
                "source_type": source_type,
                "dataset": dataset,
                "dataset_split": split,
                "router_strategy": row.get("router_strategy", ""),
                "budget_setting": row.get("budget_setting", ""),
                "accuracy": row.get("accuracy", ""),
                "avg_token_cost": row.get("avg_token_cost", ""),
                "candidate_arm_space": row.get("candidate_arm_space", ""),
                "comparability_scope": "adjacent_only",
                "artifact_id": row.get("artifact_id", ""),
                "commit_or_version": row.get("commit_or_version", ""),
            }
        )

    missing_budgets = sorted(expected_budgets - observed_budgets)
    if missing_budgets:
        issues.append(f"missing_expected_budgets: {missing_budgets}")

    return {
        "status": "valid" if not issues and not errors else "invalid",
        "requested_results_path": str(requested_path),
        "resolved_package_dir": str(package_dir),
        "required_files": {
            "metadata_json": str(metadata_json),
            "results_csv": str(results_csv),
        },
        "expected": {
            "dataset": expected_dataset,
            "split": expected_split,
            "budgets": sorted(expected_budgets),
            "required_workflow_stages": REQUIRED_WORKFLOW_STAGES,
            "comparability_scope": "adjacent_only",
        },
        "observed": {
            "num_rows": len(rows),
            "observed_budgets": sorted(observed_budgets),
        },
        "issues": sorted(set(issues)),
        "errors": errors,
        "imported_rows": normalized_rows if not issues and not errors else [],
    }


def main() -> None:
    args = parse_args()
    expected_budgets = {int(x.strip()) for x in args.expected_budgets.split(",") if x.strip()}

    verification = verify_best_route_import(
        requested_path=Path(args.results_path),
        expected_dataset=args.expected_dataset,
        expected_split=args.expected_split,
        expected_budgets=expected_budgets,
    )

    out = json.dumps(verification, indent=2)
    if args.output_json:
        Path(args.output_json).write_text(out + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
