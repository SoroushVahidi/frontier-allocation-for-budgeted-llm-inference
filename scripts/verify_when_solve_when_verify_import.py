#!/usr/bin/env python3
"""Verify When-To-Solve-When-To-Verify official adjacent import packages.

Conservative scope:
- official/import-validated lane only (no direct in-repo full-stack reproduction claim);
- fixed-budget solve-vs-verify import contract only;
- optional local official clone checks for expected markers and entrypoint families.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "when_solve_when_verify_official_import_v1.json"

REQUIRED_METADATA_FIELDS = [
    "source.type",
    "upstream.repo_url",
    "upstream.paper_url",
    "upstream.workflow_stages_completed",
    "dataset.name",
    "dataset.split",
    "budget.unit",
    "budget.fixed_budget_interpretation",
    "strategy_space",
    "provenance.exported_at_utc",
    "provenance.source_uri",
    "provenance.artifact_id",
    "provenance.commit_or_version_if_available",
]

REQUIRED_WORKFLOW_STAGES = [
    "solution_generation",
    "verification_generation",
    "fixed_budget_evaluation",
]

REQUIRED_RESULTS_COLUMNS = [
    "mode",
    "source_type",
    "dataset",
    "split",
    "generator_model",
    "verifier_model",
    "strategy_family",
    "num_solutions",
    "num_verifications",
    "compute_budget_tokens",
    "success_rate",
    "artifact_id",
    "commit_or_version",
    "comparability_scope",
]

ALLOWED_SOURCE_TYPES = {"official", "author-produced", "imported"}
ALLOWED_STRATEGY_FAMILIES = {"self_consistency", "genrm_best_of_n", "genrm_weighted_sc"}


def _get_nested(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


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

    markers_raw = official.get("expected_repo_markers", [])
    markers = [str(x) for x in markers_raw] if isinstance(markers_raw, list) else []

    entrypoints = official.get("expected_repo_entrypoints", {}) if isinstance(official, dict) else {}
    generation_any = entrypoints.get("generation_any", []) if isinstance(entrypoints, dict) else []
    verification_any = entrypoints.get("verification_any", []) if isinstance(entrypoints, dict) else []
    evaluation_any = entrypoints.get("evaluation_any", []) if isinstance(entrypoints, dict) else []

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

    generation_hits: list[str] = []
    verification_hits: list[str] = []
    evaluation_hits: list[str] = []

    if local_clone_exists and local_path:
        for marker in markers:
            if (local_path / marker).exists():
                marker_hits.append(marker)
            else:
                missing_markers.append(marker)

        for p in generation_any if isinstance(generation_any, list) else []:
            if (local_path / str(p)).exists():
                generation_hits.append(str(p))
        for p in verification_any if isinstance(verification_any, list) else []:
            if (local_path / str(p)).exists():
                verification_hits.append(str(p))
        for p in evaluation_any if isinstance(evaluation_any, list) else []:
            if (local_path / str(p)).exists():
                evaluation_hits.append(str(p))

        if missing_markers:
            issues.append(f"incomplete_local_official_clone_missing_markers: {missing_markers}")
        if generation_any and not generation_hits:
            issues.append("incomplete_local_official_clone_missing_generation_entrypoint")
        if verification_any and not verification_hits:
            issues.append("incomplete_local_official_clone_missing_verification_entrypoint")
        if evaluation_any and not evaluation_hits:
            issues.append("incomplete_local_official_clone_missing_evaluation_entrypoint")

    return {
        "clone_url": clone_url,
        "configured_expected_local_clone_path": configured_rel,
        "resolved_local_clone_path": str(local_path) if local_path else "",
        "local_clone_exists": local_clone_exists,
        "marker_hits": marker_hits,
        "missing_markers": missing_markers,
        "entrypoint_hits": {
            "generation_any": generation_hits,
            "verification_any": verification_hits,
            "evaluation_any": evaluation_hits,
        },
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify when_solve_when_verify official adjacent import package")
    p.add_argument("--results-path", required=True, help="Path to package dir or results.csv")
    p.add_argument("--expected-dataset", required=True)
    p.add_argument("--expected-split", default="test")
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="Import config JSON")
    p.add_argument("--official-repo-path", default=None, help="Optional explicit path to official repo clone")
    p.add_argument("--output-json", default=None)
    return p.parse_args()


def verify_when_solve_when_verify_import(
    *, requested_path: Path, expected_dataset: str, expected_split: str, config: dict[str, Any] | None = None, official_repo_path: str | None = None
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

    loaded_config = config if config is not None else _load_config(DEFAULT_CONFIG)

    official_repo_check = _verify_official_repo(
        config=loaded_config,
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
        if "nishadsinghi/sc-genrm-scaling" not in upstream_repo:
            issues.append("upstream_repo_mismatch")

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

    observed_strategies: set[str] = set()
    normalized_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        mode = str(row.get("mode", "")).strip()
        source_type = str(row.get("source_type", "")).strip()
        dataset = str(row.get("dataset", "")).strip()
        split = str(row.get("split", "")).strip()
        strategy = str(row.get("strategy_family", "")).strip()
        scope = str(row.get("comparability_scope", "")).strip().lower()

        if mode != "when_solve_when_verify_adjacent_import":
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

        for int_col in ["num_solutions", "num_verifications", "compute_budget_tokens"]:
            value = str(row.get(int_col, "")).strip()
            try:
                parsed = int(float(value))
                if parsed < 0:
                    issues.append(f"negative_{int_col}_row_{idx}")
            except ValueError:
                issues.append(f"non_numeric_{int_col}_row_{idx}")

        success_rate = str(row.get("success_rate", "")).strip()
        try:
            sr = float(success_rate)
            if not (0.0 <= sr <= 1.0):
                issues.append(f"success_rate_out_of_range_row_{idx}")
        except ValueError:
            issues.append(f"non_numeric_success_rate_row_{idx}")

        normalized_rows.append(
            {
                "mode": "when_solve_when_verify_adjacent_import",
                "source": "when_solve_when_verify_import_verified",
                "source_type": source_type,
                "dataset": dataset,
                "dataset_split": split,
                "generator_model": row.get("generator_model", ""),
                "verifier_model": row.get("verifier_model", ""),
                "strategy_family": strategy,
                "num_solutions": row.get("num_solutions", ""),
                "num_verifications": row.get("num_verifications", ""),
                "compute_budget_tokens": row.get("compute_budget_tokens", ""),
                "success_rate": row.get("success_rate", ""),
                "artifact_id": row.get("artifact_id", ""),
                "commit_or_version": row.get("commit_or_version", ""),
                "comparability_scope": "adjacent_only",
            }
        )

    if "self_consistency" not in observed_strategies:
        issues.append("missing_self_consistency_strategy")
    if not any(s.startswith("genrm_") for s in observed_strategies):
        issues.append("missing_genrm_strategy")

    if any("blocked_missing_required_local_official_clone" in i for i in issues):
        verdict = "blocked_missing_official_repo"
    elif issues or errors:
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
        "official_repo_check": official_repo_check,
        "expected": {
            "dataset": expected_dataset,
            "split": expected_split,
            "required_workflow_stages": REQUIRED_WORKFLOW_STAGES,
            "required_strategies": ["self_consistency", "genrm_best_of_n_or_genrm_weighted_sc"],
            "comparability_scope": "adjacent_only",
        },
        "observed": {
            "num_rows": len(rows),
            "observed_strategy_families": sorted(observed_strategies),
        },
        "issues": sorted(set(issues)),
        "warnings": sorted(set(warnings)),
        "errors": errors,
        "imported_rows": normalized_rows if verdict == "import_validated" else [],
    }


def main() -> None:
    args = parse_args()
    config = _load_config(Path(args.config))
    verification = verify_when_solve_when_verify_import(
        requested_path=Path(args.results_path),
        expected_dataset=args.expected_dataset,
        expected_split=args.expected_split,
        config=config,
        official_repo_path=args.official_repo_path,
    )

    out = json.dumps(verification, indent=2)
    if args.output_json:
        Path(args.output_json).write_text(out + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
