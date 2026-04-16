#!/usr/bin/env python3
"""Verify s1 MODE B official/full import package against strict contract."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

REQUIRED_METADATA_FIELDS = [
    "source.type",
    "model.checkpoint",
    "dataset.name",
    "dataset.split",
    "prompt.template",
    "prompt.family",
    "budget.unit",
    "budget.settings",
    "token_accounting.prompt_tokens_field",
    "token_accounting.completion_tokens_field",
    "token_accounting.total_tokens_field",
    "decoding.temperature",
    "decoding.top_p",
    "decoding.max_new_tokens",
    "metrics.schema_version",
    "metrics.primary",
    "provenance.exported_at_utc",
    "provenance.source_uri",
    "provenance.artifact_id",
    "provenance.commit_or_version_if_available",
]

REQUIRED_RESULTS_COLUMNS = [
    "mode",
    "source_type",
    "dataset",
    "split",
    "model_checkpoint",
    "prompt_family",
    "prompt_template",
    "budget_setting",
    "accuracy",
    "exact_match",
    "avg_token_cost",
    "temperature",
    "top_p",
    "max_new_tokens",
    "artifact_id",
    "commit_or_version",
]

MODE_A_METHOD_MARKERS = {"adaptive_min_expand_1", "external_s1_budget_forcing"}
ALLOWED_SOURCE_TYPES = {"official", "author-produced", "imported"}


def _get_nested(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _parse_budget_setting(raw: str) -> int | None:
    text = str(raw).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    lowered = text.lower()
    if lowered.startswith("budget_"):
        candidate = lowered.split("budget_", 1)[1]
        if candidate.isdigit():
            return int(candidate)
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify s1 MODE B import package")
    p.add_argument("--results-path", required=True, help="Path to official package dir or to results.csv")
    p.add_argument("--expected-dataset", required=True)
    p.add_argument("--expected-split", default="test")
    p.add_argument("--expected-budgets", required=True, help="Comma separated integer action budgets")
    p.add_argument("--output-json", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    issues: list[str] = []
    errors: list[str] = []

    requested_path = Path(args.results_path)
    expected_budgets = {int(x.strip()) for x in args.expected_budgets.split(",") if x.strip()}

    package_dir: Path
    results_csv: Path
    metadata_json: Path
    if requested_path.is_dir():
        package_dir = requested_path
        results_csv = package_dir / "results.csv"
        metadata_json = package_dir / "metadata.json"
    else:
        package_dir = requested_path.parent
        results_csv = requested_path
        metadata_json = package_dir / "metadata.json"

    if not results_csv.exists():
        issues.append(f"missing_required_file: {results_csv}")
    if not metadata_json.exists():
        issues.append(f"missing_required_file: {metadata_json}")

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

        dataset_name = str(_get_nested(metadata, "dataset.name") or "")
        dataset_split = str(_get_nested(metadata, "dataset.split") or "")
        if dataset_name != args.expected_dataset:
            issues.append(
                f"dataset_mismatch: expected={args.expected_dataset}, observed={dataset_name}"
            )
        if dataset_split != args.expected_split:
            issues.append(f"split_mismatch: expected={args.expected_split}, observed={dataset_split}")

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
        method = str(row.get("method", "")).strip()
        source_type = str(row.get("source_type", "")).strip()
        dataset = str(row.get("dataset", "")).strip()
        split = str(row.get("split", "")).strip()

        if mode == "inference_only":
            issues.append(f"mode_a_mix_detected_row_{idx}")
        if method in MODE_A_METHOD_MARKERS:
            issues.append(f"mode_a_method_marker_detected_row_{idx}")
        if source_type and source_type not in ALLOWED_SOURCE_TYPES:
            issues.append(f"invalid_source_type_row_{idx}")
        if dataset != args.expected_dataset:
            issues.append(f"dataset_row_mismatch_{idx}")
        if split != args.expected_split:
            issues.append(f"split_row_mismatch_{idx}")

        budget = _parse_budget_setting(str(row.get("budget_setting", "")))
        if budget is None:
            issues.append(f"unparseable_budget_setting_row_{idx}")
        else:
            observed_budgets.add(budget)

        for metric_col in ["accuracy", "exact_match", "avg_token_cost", "temperature", "top_p", "max_new_tokens"]:
            value = str(row.get(metric_col, "")).strip()
            try:
                parsed = float(value)
                if metric_col in {"accuracy", "exact_match"} and not (0.0 <= parsed <= 1.0):
                    issues.append(f"metric_out_of_range_{metric_col}_row_{idx}")
            except ValueError:
                issues.append(f"non_numeric_{metric_col}_row_{idx}")

        normalized_rows.append(
            {
                "mode": "full_or_official",
                "source": "official_import_verified",
                "source_type": source_type,
                "dataset": dataset,
                "dataset_split": split,
                "model_checkpoint": row.get("model_checkpoint", ""),
                "prompt_family": row.get("prompt_family", ""),
                "prompt_template": row.get("prompt_template", ""),
                "budget_setting": row.get("budget_setting", ""),
                "accuracy": row.get("accuracy", ""),
                "exact_match": row.get("exact_match", ""),
                "avg_token_cost": row.get("avg_token_cost", ""),
                "temperature": row.get("temperature", ""),
                "top_p": row.get("top_p", ""),
                "max_new_tokens": row.get("max_new_tokens", ""),
                "artifact_id": row.get("artifact_id", ""),
                "commit_or_version": row.get("commit_or_version", ""),
            }
        )

    missing_budgets = sorted(expected_budgets - observed_budgets)
    if missing_budgets:
        issues.append(f"missing_expected_budgets: {missing_budgets}")

    verification = {
        "status": "valid" if not issues and not errors else "invalid",
        "requested_results_path": str(requested_path),
        "resolved_package_dir": str(package_dir),
        "required_files": {
            "metadata_json": str(metadata_json),
            "results_csv": str(results_csv),
        },
        "expected": {
            "dataset": args.expected_dataset,
            "split": args.expected_split,
            "budgets": sorted(expected_budgets),
        },
        "observed": {
            "num_rows": len(rows),
            "observed_budgets": sorted(observed_budgets),
        },
        "issues": sorted(set(issues)),
        "errors": errors,
        "imported_rows": normalized_rows if not issues and not errors else [],
    }

    out = json.dumps(verification, indent=2)
    if args.output_json:
        Path(args.output_json).write_text(out + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
