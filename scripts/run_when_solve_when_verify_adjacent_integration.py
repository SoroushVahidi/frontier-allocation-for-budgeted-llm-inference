#!/usr/bin/env python3
"""Run When-To-Solve-When-To-Verify adjacent import integration contract."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from verify_when_solve_when_verify_import import _load_config, verify_when_solve_when_verify_import

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMPORT_CONFIG = REPO_ROOT / "configs" / "when_solve_when_verify_official_import_v1.json"
DEFAULT_CONTRACT_CONFIG = REPO_ROOT / "configs" / "when_solve_when_verify_adjacent_comparison_contract_v1.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs" / "when_solve_when_verify_adjacent_integration"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run when_solve_when_verify adjacent integration contract")
    p.add_argument("--import-config", default=str(DEFAULT_IMPORT_CONFIG))
    p.add_argument("--contract-config", default=str(DEFAULT_CONTRACT_CONFIG))
    p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p.add_argument("--official-repo-path", default=None)
    p.add_argument("--run-id", default=None)
    return p.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    import_config_path = Path(args.import_config).resolve()
    contract_config_path = Path(args.contract_config).resolve()
    import_config = _load_config(import_config_path)
    contract = _read_json(contract_config_path)

    split = str(contract.get("default_expected_split", "test"))
    datasets = contract.get("dataset_import_packages", {})
    if not isinstance(datasets, dict):
        raise ValueError("contract_config.dataset_import_packages must be a dict")

    validation_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    validation_payloads: dict[str, Any] = {}
    missing_packages: list[str] = []

    for canonical_dataset, spec_any in datasets.items():
        spec = spec_any if isinstance(spec_any, dict) else {}
        results_path_raw = spec.get("results_path")
        expected_dataset = str(spec.get("expected_dataset", "")).strip()

        if not results_path_raw:
            missing_packages.append(canonical_dataset)
            validation_rows.append(
                {
                    "canonical_dataset": canonical_dataset,
                    "expected_dataset": expected_dataset,
                    "expected_split": split,
                    "status": "missing_package",
                    "verdict": "blocked_missing_import_package",
                    "results_path": "",
                    "num_imported_rows": 0,
                }
            )
            continue

        package_path = REPO_ROOT / str(results_path_raw)
        verification = verify_when_solve_when_verify_import(
            requested_path=package_path,
            expected_dataset=expected_dataset,
            expected_split=split,
            config=import_config,
            official_repo_path=args.official_repo_path,
        )
        validation_payloads[canonical_dataset] = verification

        imported_rows = verification.get("imported_rows", [])
        imported_count = len(imported_rows) if isinstance(imported_rows, list) else 0
        validation_rows.append(
            {
                "canonical_dataset": canonical_dataset,
                "expected_dataset": expected_dataset,
                "expected_split": split,
                "status": verification.get("status", "invalid"),
                "verdict": verification.get("verdict", "unknown"),
                "results_path": str(package_path),
                "num_imported_rows": imported_count,
                "num_issues": len(verification.get("issues", [])),
                "num_warnings": len(verification.get("warnings", [])),
            }
        )

        if verification.get("verdict") == "import_validated" and isinstance(imported_rows, list):
            for row in imported_rows:
                comparison_rows.append(
                    {
                        "baseline_id": "when_solve_when_verify",
                        "baseline_mode": "adjacent_import_validated",
                        "canonical_dataset": canonical_dataset,
                        "dataset": row.get("dataset", ""),
                        "split": row.get("dataset_split", ""),
                        "generator_model": row.get("generator_model", ""),
                        "verifier_model": row.get("verifier_model", ""),
                        "strategy_family": row.get("strategy_family", ""),
                        "num_solutions": row.get("num_solutions", ""),
                        "num_verifications": row.get("num_verifications", ""),
                        "compute_budget_tokens": row.get("compute_budget_tokens", ""),
                        "success_rate": row.get("success_rate", ""),
                        "comparability_scope": "adjacent_only",
                        "artifact_id": row.get("artifact_id", ""),
                        "commit_or_version": row.get("commit_or_version", ""),
                        "source": "scripts/verify_when_solve_when_verify_import.py",
                    }
                )

    validated_datasets = [
        row["canonical_dataset"]
        for row in validation_rows
        if row.get("verdict") == "import_validated"
    ]

    minimum = contract.get("coverage_policy", {}).get("minimum_for_adjacent_row_export", [])
    minimum_set = set(minimum) if isinstance(minimum, list) else set()
    minimum_met = minimum_set.issubset(set(validated_datasets))

    status_payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "baseline_key": "when_solve_when_verify",
        "integration_mode_selected": "stronger_import_validated_comparator_with_reproducible_artifact_contract",
        "status": "import_validated" if minimum_met else "blocked_incomplete_import",
        "control_equivalence": "adjacent",
        "validated_datasets": validated_datasets,
        "missing_packages_for_canonical_mix": missing_packages,
        "canonical_mix": contract.get("canonical_benchmark_mix", []),
        "minimum_required_datasets": sorted(minimum_set),
        "minimum_required_met": minimum_met,
        "safe_claims_now": [
            "When-To-Solve-When-To-Verify adjacent import rows are reproducibly exportable for validated datasets.",
            "Control-space equivalence is not claimed; rows remain adjacent_only.",
        ],
        "unsafe_claims_now": [
            "Full upstream SC-vs-GenRM reproduction in this repository.",
            "Frontier-allocation equivalence with strict_gate1_cap_k6 or branch-level controllers.",
        ],
    }

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "script": "scripts/run_when_solve_when_verify_adjacent_integration.py",
        "import_config": str(import_config_path.relative_to(REPO_ROOT)),
        "contract_config": str(contract_config_path.relative_to(REPO_ROOT)),
        "output_dir": str(run_dir.relative_to(REPO_ROOT)),
        "commands": [
            "python scripts/run_when_solve_when_verify_adjacent_integration.py --import-config configs/when_solve_when_verify_official_import_v1.json --contract-config configs/when_solve_when_verify_adjacent_comparison_contract_v1.json"
        ],
        "artifacts": [
            "manifest.json",
            "status.json",
            "validation_results.json",
            "validation_status.csv",
            "comparison_ready_rows.csv",
        ],
    }

    _write_json(run_dir / "manifest.json", manifest)
    _write_json(run_dir / "status.json", status_payload)
    _write_json(run_dir / "validation_results.json", validation_payloads)
    _write_csv(run_dir / "validation_status.csv", validation_rows)
    _write_csv(run_dir / "comparison_ready_rows.csv", comparison_rows)

    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "status": status_payload["status"],
                "validated_datasets": validated_datasets,
                "missing_packages_for_canonical_mix": missing_packages,
                "comparison_rows": len(comparison_rows),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
