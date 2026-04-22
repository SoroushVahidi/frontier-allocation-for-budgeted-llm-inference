#!/usr/bin/env python3
"""Verify Tree-PLV adjacent import package with conservative claim boundaries."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = REPO_ROOT / "configs" / "tree_plv_adjacent_comparison_contract_v1.json"

REQUIRED_METADATA_FIELDS = [
    "source.type",
    "upstream.repo_url",
    "upstream.paper_url",
    "upstream.workflow_stages_completed",
    "dataset.name",
    "dataset.split",
    "evaluation.budget.max_tree_depth_values",
    "evaluation.budget.num_candidates_values",
    "evaluation.budget.compute_budget_note",
    "models.base_model_family",
    "models.verifier_model_family",
    "provenance.exported_at_utc",
    "provenance.source_uri",
    "provenance.artifact_id",
    "provenance.commit_or_version_if_available",
]

REQUIRED_WORKFLOW_STAGES = [
    "tree_preference_pair_construction",
    "process_verifier_training_or_import",
    "benchmark_evaluation",
]

REQUIRED_RESULTS_COLUMNS = [
    "mode",
    "source_type",
    "dataset",
    "split",
    "base_model",
    "verifier_model",
    "search_policy",
    "max_tree_depth",
    "num_candidates",
    "accuracy",
    "num_examples",
    "artifact_id",
    "commit_or_version",
    "comparability_scope",
]

ALLOWED_SOURCE_TYPES = {"official", "author-produced", "imported"}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _get_nested(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _check_contract(contract_config: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "contract_path": str(contract_config),
        "contract_exists": contract_config.exists(),
        "contract_valid_json": False,
        "required_sections_ok": False,
        "issues": [],
    }
    if not contract_config.exists():
        result["issues"].append("missing_contract_config")
        return result

    try:
        payload = _read_json(contract_config)
    except json.JSONDecodeError as exc:
        result["issues"].append(f"invalid_contract_json: {exc}")
        return result

    result["contract_valid_json"] = True
    required_sections = [
        "official_sources",
        "benchmark_contract",
        "budget_and_compute_normalization",
        "paper_ingredients",
        "model_and_path_requirements",
        "artifact_requirements",
        "allowed_claims",
        "forbidden_claims",
    ]
    missing = [s for s in required_sections if s not in payload]
    if missing:
        result["issues"].append(f"missing_contract_sections: {missing}")
    else:
        result["required_sections_ok"] = True
    return result


def _check_official_repo_path(official_repo_path: Path | None, contract_config: Path) -> dict[str, Any]:
    result = {
        "checked": official_repo_path is not None,
        "official_repo_path": str(official_repo_path) if official_repo_path else "",
        "exists": False,
        "layout_ok": False,
        "layout_checks": {},
        "license_visible": False,
        "issues": [],
    }
    if official_repo_path is None:
        return result

    result["exists"] = official_repo_path.exists()
    if not official_repo_path.exists():
        result["issues"].append("official_repo_path_missing")
        return result

    required_layout: list[str] = []
    try:
        contract = _read_json(contract_config)
        required_layout = [
            str(x)
            for x in contract.get("model_and_path_requirements", {}).get(
                "official_repo_layout_required", []
            )
        ]
    except json.JSONDecodeError:
        required_layout = []

    checks = {rel: (official_repo_path / rel).exists() for rel in required_layout}
    result["layout_checks"] = checks
    result["layout_ok"] = all(checks.values()) if checks else False
    if checks and not result["layout_ok"]:
        result["issues"].append("official_repo_layout_incomplete")

    license_names = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]
    result["license_visible"] = any((official_repo_path / name).exists() for name in license_names)
    if not result["license_visible"]:
        result["issues"].append("no_license_file_visible_in_repo_root")

    return result


def verify_tree_plv_import(
    *,
    requested_path: Path,
    expected_dataset: str,
    expected_split: str,
    contract_config: Path | None = None,
    official_repo_path: Path | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    errors: list[str] = []

    contract_path = contract_config or DEFAULT_CONTRACT
    contract_check = _check_contract(contract_path)
    if not contract_check.get("required_sections_ok", False):
        issues.append("contract_sections_incomplete")

    official_repo_check = _check_official_repo_path(official_repo_path, contract_path)

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
            metadata = _read_json(metadata_json)
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
        if "Hareta-Leila/Tree-PLV" not in upstream_repo:
            issues.append("upstream_repo_mismatch")

        paper_url = str(_get_nested(metadata, "upstream.paper_url") or "")
        if "2024.emnlp-main.125" not in paper_url and "2407.00390" not in paper_url:
            issues.append("upstream_paper_mismatch")

        workflow_stages = _get_nested(metadata, "upstream.workflow_stages_completed")
        if not isinstance(workflow_stages, list):
            issues.append("workflow_stages_not_list")
            workflow_stages = []
        missing_stages = [stage for stage in REQUIRED_WORKFLOW_STAGES if stage not in workflow_stages]
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

    normalized_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        mode = str(row.get("mode", "")).strip()
        source_type = str(row.get("source_type", "")).strip()
        dataset = str(row.get("dataset", "")).strip()
        split = str(row.get("split", "")).strip()
        scope = str(row.get("comparability_scope", "")).strip().lower()

        if mode != "tree_plv_adjacent_import":
            issues.append(f"invalid_mode_row_{idx}")
        if source_type and source_type not in ALLOWED_SOURCE_TYPES:
            issues.append(f"invalid_source_type_row_{idx}")
        if dataset != expected_dataset:
            issues.append(f"dataset_row_mismatch_{idx}")
        if split != expected_split:
            issues.append(f"split_row_mismatch_{idx}")
        if scope != "adjacent_only":
            issues.append(f"invalid_comparability_scope_row_{idx}")

        for int_col in ["max_tree_depth", "num_candidates", "num_examples"]:
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
                "mode": "tree_plv_adjacent_import",
                "source": "tree_plv_import_verified",
                "source_type": source_type,
                "dataset": dataset,
                "dataset_split": split,
                "base_model": row.get("base_model", ""),
                "verifier_model": row.get("verifier_model", ""),
                "search_policy": row.get("search_policy", ""),
                "max_tree_depth": row.get("max_tree_depth", ""),
                "num_candidates": row.get("num_candidates", ""),
                "accuracy": row.get("accuracy", ""),
                "num_examples": row.get("num_examples", ""),
                "artifact_id": row.get("artifact_id", ""),
                "commit_or_version": row.get("commit_or_version", ""),
                "comparability_scope": "adjacent_only",
            }
        )

    status = "valid" if not issues and not errors else "invalid"
    verdict = "import_validated" if status == "valid" else "blocked_incomplete_import"

    return {
        "baseline_key": "tree_plv",
        "status": status,
        "verdict": verdict,
        "issues": sorted(set(issues)),
        "errors": errors,
        "contract_check": contract_check,
        "official_repo_check": official_repo_check,
        "package_dir": str(package_dir),
        "requested_path": str(requested_path),
        "expected_dataset": expected_dataset,
        "expected_split": expected_split,
        "imported_rows": normalized_rows if verdict == "import_validated" else [],
        "safe_claim_scope": "adjacent_only",
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify Tree-PLV adjacent import package")
    p.add_argument("--results-path", required=True, help="Path to package dir or results.csv")
    p.add_argument("--expected-dataset", required=True)
    p.add_argument("--expected-split", default="test")
    p.add_argument("--contract-config", default=str(DEFAULT_CONTRACT))
    p.add_argument("--official-repo-path", default=None)
    p.add_argument("--output-json", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    report = verify_tree_plv_import(
        requested_path=Path(args.results_path).resolve(),
        expected_dataset=str(args.expected_dataset),
        expected_split=str(args.expected_split),
        contract_config=Path(args.contract_config).resolve() if args.contract_config else None,
        official_repo_path=Path(args.official_repo_path).resolve() if args.official_repo_path else None,
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
