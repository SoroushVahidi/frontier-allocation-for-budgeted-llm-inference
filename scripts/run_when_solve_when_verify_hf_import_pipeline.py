#!/usr/bin/env python3
"""Build HF-backed import package and validate/export integration rows."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=True)


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "outputs" / "when_solve_when_verify_hf_import_pipeline" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    package_dir = REPO_ROOT / "outputs" / f"when_solve_when_verify_hf_import_package_{run_id}"
    _run(
        [
            sys.executable,
            "scripts/build_when_solve_when_verify_hf_import_package.py",
            "--output-dir",
            str(package_dir.relative_to(REPO_ROOT)),
        ]
    )

    verify = _run(
        [
            sys.executable,
            "scripts/verify_when_solve_when_verify_import.py",
            "--config",
            "configs/when_solve_when_verify_official_import_v1.json",
            "--results-path",
            str(package_dir),
            "--expected-dataset",
            "math128",
            "--expected-split",
            "test",
            "--official-repo-path",
            "external/when_solve_when_verify/upstream/sc-genrm-scaling",
        ]
    )
    verify_json = json.loads(verify.stdout)
    (out_dir / "validator_output.json").write_text(json.dumps(verify_json, indent=2) + "\n", encoding="utf-8")

    contract_path = out_dir / "contract_runtime.json"
    contract = {
        "baseline_key": "when_solve_when_verify",
        "baseline_display_name": "When To Solve, When To Verify",
        "integration_mode": "official_adjacent_import_validated",
        "canonical_benchmark_mix": ["math128"],
        "default_expected_split": "test",
        "coverage_policy": {"minimum_for_adjacent_row_export": ["math128"]},
        "dataset_import_packages": {
            "math128": {
                "results_path": str(package_dir.relative_to(REPO_ROOT)),
                "expected_dataset": "math128",
            }
        },
    }
    contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    integrate = _run(
        [
            sys.executable,
            "scripts/run_when_solve_when_verify_adjacent_integration.py",
            "--import-config",
            "configs/when_solve_when_verify_official_import_v1.json",
            "--contract-config",
            str(contract_path),
            "--official-repo-path",
            "external/when_solve_when_verify/upstream/sc-genrm-scaling",
            "--run-id",
            f"hf_import_{run_id}",
        ]
    )
    (out_dir / "integration_stdout.json").write_text(integrate.stdout, encoding="utf-8")

    summary = {
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "package_dir": str(package_dir.relative_to(REPO_ROOT)),
        "validator_status": verify_json.get("status"),
        "validator_verdict": verify_json.get("verdict"),
        "integration_run_id": f"hf_import_{run_id}",
        "integration_output_dir": f"outputs/when_solve_when_verify_adjacent_integration/hf_import_{run_id}",
    }
    (out_dir / "pipeline_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "run_dir": str(out_dir), **summary}, indent=2))


if __name__ == "__main__":
    main()
