#!/usr/bin/env python3
"""Verify Majority-of-the-Bests (MoB) adjacent import package.

Conservative scope:
- Adjacent import only (not direct in-repo reproduction claim).
- Requires explicit workflow-stage declarations matching upstream MoB evaluation flow.
- Requires algorithm coverage including BoN and at least one MoB variant.
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
    "dataset.benchmarks",
    "models.generator_models",
    "models.reward_models",
    "budget.unit",
    "budget.num_samples",
    "algorithm_set",
    "provenance.exported_at_utc",
    "provenance.source_uri",
    "provenance.artifact_id",
    "provenance.commit_or_version_if_available",
]

REQUIRED_WORKFLOW_STAGES = [
    "dataset_loading_from_jsonl_gz",
    "algorithm_evaluation_via_main_py",
    "aggregated_csv_export",
]

REQUIRED_RESULTS_COLUMNS = [
    "mode",
    "source_type",
    "benchmark",
    "gen_model",
    "reward_model",
    "num_samples",
    "algorithm",
    "accuracy",
    "num_trials",
    "artifact_id",
    "commit_or_version",
    "comparability_scope",
]

ALLOWED_SOURCE_TYPES = {"official", "author-produced", "imported"}
ALLOWED_ALGORITHMS = {"bon", "sc", "wbon", "mob_adaptive_m", "mob_poly_m"}
REQUIRED_MOB_ALGORITHMS = {"mob_adaptive_m", "mob_poly_m"}


def _get_nested(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify MoB adjacent import package")
    p.add_argument("--results-path", required=True, help="Path to package dir or results.csv")
    p.add_argument("--expected-benchmark", required=True)
    p.add_argument("--expected-gen-model", required=True)
    p.add_argument("--expected-reward-model", required=True)
    p.add_argument("--expected-num-samples", type=int, required=True)
    p.add_argument("--output-json", default=None)
    return p.parse_args()


def verify_mob_import(
    *,
    requested_path: Path,
    expected_benchmark: str,
    expected_gen_model: str,
    expected_reward_model: str,
    expected_num_samples: int,
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
        if "arakhsha/mob" not in upstream_repo:
            issues.append("upstream_repo_mismatch")

        metadata_benchmarks = _get_nested(metadata, "dataset.benchmarks")
        if not isinstance(metadata_benchmarks, list) or expected_benchmark not in metadata_benchmarks:
            issues.append("benchmark_not_declared_in_metadata")

        gen_models = _get_nested(metadata, "models.generator_models")
        if not isinstance(gen_models, list) or expected_gen_model not in gen_models:
            issues.append("expected_gen_model_not_declared")

        reward_models = _get_nested(metadata, "models.reward_models")
        if not isinstance(reward_models, list) or expected_reward_model not in reward_models:
            issues.append("expected_reward_model_not_declared")

        declared_num_samples = _get_nested(metadata, "budget.num_samples")
        if isinstance(declared_num_samples, list):
            if expected_num_samples not in {int(x) for x in declared_num_samples}:
                issues.append("expected_num_samples_not_declared")
        else:
            issues.append("budget_num_samples_not_list")

        observed_stages = _get_nested(metadata, "upstream.workflow_stages_completed")
        if not isinstance(observed_stages, list):
            issues.append("workflow_stages_not_list")
            observed_stages = []
        missing_stages = [s for s in REQUIRED_WORKFLOW_STAGES if s not in observed_stages]
        if missing_stages:
            issues.append(f"missing_required_workflow_stages: {missing_stages}")

        algorithm_set = _get_nested(metadata, "algorithm_set")
        if not isinstance(algorithm_set, list) or not algorithm_set:
            issues.append("algorithm_set_missing_or_empty")
        else:
            observed_set = {str(a).strip() for a in algorithm_set}
            if "bon" not in observed_set:
                issues.append("algorithm_set_missing_bon")
            if not (REQUIRED_MOB_ALGORITHMS & observed_set):
                issues.append("algorithm_set_missing_mob_variant")

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

    observed_algorithms: set[str] = set()
    normalized_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        mode = str(row.get("mode", "")).strip()
        source_type = str(row.get("source_type", "")).strip()
        benchmark = str(row.get("benchmark", "")).strip()
        gen_model = str(row.get("gen_model", "")).strip()
        reward_model = str(row.get("reward_model", "")).strip()
        algorithm = str(row.get("algorithm", "")).strip()
        scope = str(row.get("comparability_scope", "")).strip().lower()

        if mode != "mob_adjacent_import":
            issues.append(f"invalid_mode_row_{idx}")
        if source_type and source_type not in ALLOWED_SOURCE_TYPES:
            issues.append(f"invalid_source_type_row_{idx}")
        if benchmark != expected_benchmark:
            issues.append(f"benchmark_row_mismatch_{idx}")
        if gen_model != expected_gen_model:
            issues.append(f"gen_model_row_mismatch_{idx}")
        if reward_model != expected_reward_model:
            issues.append(f"reward_model_row_mismatch_{idx}")
        if algorithm not in ALLOWED_ALGORITHMS:
            issues.append(f"invalid_algorithm_row_{idx}")
        if scope != "adjacent_only":
            issues.append(f"invalid_comparability_scope_row_{idx}")

        observed_algorithms.add(algorithm)

        num_samples_raw = str(row.get("num_samples", "")).strip()
        num_trials_raw = str(row.get("num_trials", "")).strip()
        accuracy_raw = str(row.get("accuracy", "")).strip()

        try:
            num_samples = int(float(num_samples_raw))
            if num_samples != expected_num_samples:
                issues.append(f"num_samples_row_mismatch_{idx}")
        except ValueError:
            issues.append(f"non_numeric_num_samples_row_{idx}")

        try:
            num_trials = int(float(num_trials_raw))
            if num_trials <= 0:
                issues.append(f"invalid_num_trials_row_{idx}")
        except ValueError:
            issues.append(f"non_numeric_num_trials_row_{idx}")

        try:
            accuracy = float(accuracy_raw)
            if not (0.0 <= accuracy <= 1.0):
                issues.append(f"accuracy_out_of_range_row_{idx}")
        except ValueError:
            issues.append(f"non_numeric_accuracy_row_{idx}")

        normalized_rows.append(
            {
                "mode": "mob_adjacent_import",
                "source": "mob_import_verified",
                "source_type": source_type,
                "benchmark": benchmark,
                "gen_model": gen_model,
                "reward_model": reward_model,
                "num_samples": row.get("num_samples", ""),
                "algorithm": algorithm,
                "accuracy": row.get("accuracy", ""),
                "num_trials": row.get("num_trials", ""),
                "artifact_id": row.get("artifact_id", ""),
                "commit_or_version": row.get("commit_or_version", ""),
                "comparability_scope": "adjacent_only",
            }
        )

    if "bon" not in observed_algorithms:
        issues.append("missing_bon_algorithm")
    if not (REQUIRED_MOB_ALGORITHMS & observed_algorithms):
        issues.append("missing_mob_algorithm_variant")

    return {
        "status": "valid" if not issues and not errors else "invalid",
        "baseline": "mob_majority_of_bests",
        "integration_kind": "adjacent_import_validator",
        "package_dir": str(package_dir),
        "issues": issues,
        "errors": errors,
        "imported_rows": normalized_rows,
        "safe_claim_scope": "adjacent_only",
        "unsafe_claims": [
            "direct in-repo full reproduction of upstream MoB experiments",
            "control-space-equivalent direct comparability claims versus frontier/action-native controllers",
        ],
    }


def main() -> None:
    args = parse_args()
    report = verify_mob_import(
        requested_path=Path(args.results_path),
        expected_benchmark=args.expected_benchmark,
        expected_gen_model=args.expected_gen_model,
        expected_reward_model=args.expected_reward_model,
        expected_num_samples=args.expected_num_samples,
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
