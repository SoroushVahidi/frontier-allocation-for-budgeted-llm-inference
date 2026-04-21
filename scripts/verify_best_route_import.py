#!/usr/bin/env python3
"""Verify BEST-Route adjacent import package against a conservative contract.

This validator is intentionally strict about provenance and explicit about comparability:
- Accepts only adjacent import mode (not direct apples-to-apples reproduction claims).
- Requires explicit BEST-Route workflow-stage declarations.
- Requires model+best-of-n candidate-arm declarations (bo1 and bo>1 present).
- Optionally validates a local official clone path when present.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "best_route_official_import_v1.json"

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
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="BEST-Route import config JSON")
    p.add_argument("--official-repo-path", default=None, help="Optional explicit local path to official repo clone")
    p.add_argument("--output-json", default=None)
    return p.parse_args()


def _load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _verify_official_repo(
    *,
    config: dict[str, Any],
    explicit_path: str | None,
    issues: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    official = config.get("official", {}) if isinstance(config, dict) else {}
    clone_url = str(official.get("repo_url", "")).strip()
    configured_rel = str(official.get("expected_local_clone_path", "")).strip()
    require_existing = bool(official.get("require_existing_local_clone", False))
    markers = official.get("expected_repo_markers", [])
    entry_any = official.get("expected_repo_entrypoints_any", [])

    local_path: Path | None = None
    if explicit_path:
        local_path = Path(explicit_path)
    elif configured_rel:
        local_path = REPO_ROOT / configured_rel

    local_clone_exists = bool(local_path and local_path.exists())

    if not clone_url:
        issues.append("missing_official_repo_url_in_config")
    if not clone_url and not local_clone_exists:
        issues.append("missing_official_repo_reference_and_local_clone")

    if require_existing and not local_clone_exists:
        issues.append("blocked_missing_required_local_official_clone")

    if local_path and not local_clone_exists:
        warnings.append(f"local_official_clone_not_found: {local_path}")

    marker_hits: list[str] = []
    missing_markers: list[str] = []
    entry_hits: list[str] = []

    if local_clone_exists and local_path:
        for marker in markers if isinstance(markers, list) else []:
            if (local_path / str(marker)).exists():
                marker_hits.append(str(marker))
            else:
                missing_markers.append(str(marker))

        for entry in entry_any if isinstance(entry_any, list) else []:
            if (local_path / str(entry)).exists():
                entry_hits.append(str(entry))

        if missing_markers:
            issues.append(f"incomplete_local_official_clone_missing_markers: {missing_markers}")
        if entry_any and not entry_hits:
            issues.append("incomplete_local_official_clone_missing_expected_entrypoints")

    return {
        "clone_url": clone_url,
        "configured_expected_local_clone_path": configured_rel,
        "resolved_local_clone_path": str(local_path) if local_path else "",
        "local_clone_exists": local_clone_exists,
        "marker_hits": marker_hits,
        "missing_markers": missing_markers,
        "entrypoint_hits_any": entry_hits,
    }


def verify_best_route_import(
    *,
    requested_path: Path,
    expected_dataset: str,
    expected_split: str,
    expected_budgets: set[int],
    config: dict[str, Any],
    official_repo_path: str | None,
) -> dict[str, Any]:
    issues: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    if requested_path.is_dir():
        package_dir = requested_path
        metadata_json = package_dir / "metadata.json"
        results_csv = package_dir / "results.csv"
    else:
        package_dir = requested_path.parent
        metadata_json = package_dir / "metadata.json"
        results_csv = requested_path

    official_repo_check = _verify_official_repo(
        config=config,
        explicit_path=official_repo_path,
        issues=issues,
        warnings=warnings,
    )

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

    has_errors = bool(issues or errors)
    blocking_repo_issue = any(
        marker in set(issues)
        for marker in {
            "missing_official_repo_reference_and_local_clone",
            "blocked_missing_required_local_official_clone",
            "missing_official_repo_url_in_config",
        }
    )
    if has_errors and blocking_repo_issue:
        verdict = "blocked_missing_official_repo"
    elif has_errors:
        verdict = "blocked_incomplete_import"
    else:
        verdict = "import_validated"

    return {
        "status": "valid" if verdict == "import_validated" else "invalid",
        "verdict": verdict,
        "requested_results_path": str(requested_path),
        "resolved_package_dir": str(package_dir),
        "required_files": {
            "metadata_json": str(metadata_json),
            "results_csv": str(results_csv),
        },
        "official_repo_validation": official_repo_check,
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
        "warnings": sorted(set(warnings)),
        "errors": errors,
        "imported_rows": normalized_rows if verdict == "import_validated" else [],
    }


def main() -> None:
    args = parse_args()
    expected_budgets = {int(x.strip()) for x in args.expected_budgets.split(",") if x.strip()}
    config_path = Path(args.config)
    config = _load_config(config_path)

    verification = verify_best_route_import(
        requested_path=Path(args.results_path),
        expected_dataset=args.expected_dataset,
        expected_split=args.expected_split,
        expected_budgets=expected_budgets,
        config=config,
        official_repo_path=args.official_repo_path,
    )

    verification["config_path"] = str(config_path)
    out = json.dumps(verification, indent=2)
    if args.output_json:
        Path(args.output_json).write_text(out + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
