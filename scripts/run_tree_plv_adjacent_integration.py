#!/usr/bin/env python3
"""Run stable Tree-PLV adjacent integration contract lane."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from verify_tree_plv_import import verify_tree_plv_import

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = REPO_ROOT / "configs" / "tree_plv_adjacent_comparison_contract_v1.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs" / "tree_plv_adjacent_integration"
DEFAULT_OFFICIAL_REPO_PATH = Path("/tmp/tree_plv_upstream/Tree-PLV")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _check_official_repo(path: Path, required_layout: list[str]) -> dict[str, Any]:
    checks = {rel: (path / rel).exists() for rel in required_layout}
    license_visible = any((path / n).exists() for n in ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"])
    return {
        "official_repo_path": str(path),
        "exists": path.exists(),
        "layout_checks": checks,
        "layout_ok": all(checks.values()) if path.exists() else False,
        "license_visible": license_visible if path.exists() else False,
    }


def _try_clone_if_missing(path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return {"action": "skip_clone_already_present", "returncode": 0, "stdout": "", "stderr": ""}

    cmd = ["git", "clone", "--depth", "1", "https://github.com/Hareta-Leila/Tree-PLV.git", str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "action": "clone_official_repo",
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run stable Tree-PLV adjacent integration lane")
    p.add_argument("--contract-config", default=str(DEFAULT_CONTRACT))
    p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p.add_argument("--run-id", default=None)
    p.add_argument("--official-repo-path", default=str(DEFAULT_OFFICIAL_REPO_PATH))
    p.add_argument("--skip-clone", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_id = args.run_id or _utc_run_id()
    contract_path = Path(args.contract_config).resolve()
    output_root = Path(args.output_root).resolve()
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    contract = _read_json(contract_path)
    stable_subsets = contract.get("benchmark_contract", {}).get("stable_adjacent_subset", [])
    required_layout = contract.get("model_and_path_requirements", {}).get("official_repo_layout_required", [])
    required_outputs = contract.get("artifact_requirements", {}).get("required_outputs", [])

    commands = [
        f"python scripts/run_tree_plv_adjacent_integration.py --contract-config {contract_path.relative_to(REPO_ROOT)}"
    ]

    clone_result = {"action": "skip_clone_by_flag", "returncode": 0, "stdout": "", "stderr": ""}
    official_repo_path = Path(args.official_repo_path).resolve()
    if not args.skip_clone:
        clone_result = _try_clone_if_missing(official_repo_path)

    official_repo_check = _check_official_repo(official_repo_path, [str(x) for x in required_layout])

    validation_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    validation_reports: dict[str, Any] = {}

    for subset in stable_subsets:
        subset_id = str(subset.get("subset_id", "unknown_subset"))
        expected_dataset = str(subset.get("expected_dataset", "")).strip()
        results_path = REPO_ROOT / str(subset.get("results_path", ""))
        expected_split = str(contract.get("benchmark_contract", {}).get("default_expected_split", "test"))

        report = verify_tree_plv_import(
            requested_path=results_path,
            expected_dataset=expected_dataset,
            expected_split=expected_split,
            contract_config=contract_path,
            official_repo_path=official_repo_path,
        )
        validation_reports[subset_id] = report

        status = report.get("status", "invalid")
        issues = report.get("issues", [])
        imported_rows = report.get("imported_rows", []) if status == "valid" else []

        validation_rows.append(
            {
                "subset_id": subset_id,
                "expected_dataset": expected_dataset,
                "expected_split": expected_split,
                "results_path": str(results_path.relative_to(REPO_ROOT)) if results_path.exists() else str(results_path),
                "status": status,
                "num_issues": len(issues) if isinstance(issues, list) else 0,
                "imported_rows": len(imported_rows) if isinstance(imported_rows, list) else 0,
            }
        )

        if status == "valid" and isinstance(imported_rows, list):
            for row in imported_rows:
                comparison_rows.append(
                    {
                        "baseline_id": "tree_plv",
                        "baseline_mode": "adjacent_partial_runnable",
                        "subset_id": subset_id,
                        "dataset": row.get("dataset", ""),
                        "split": row.get("dataset_split", ""),
                        "base_model": row.get("base_model", ""),
                        "verifier_model": row.get("verifier_model", ""),
                        "search_policy": row.get("search_policy", ""),
                        "max_tree_depth": row.get("max_tree_depth", ""),
                        "num_candidates": row.get("num_candidates", ""),
                        "accuracy": row.get("accuracy", ""),
                        "comparability_scope": "adjacent_only",
                        "artifact_id": row.get("artifact_id", ""),
                        "commit_or_version": row.get("commit_or_version", ""),
                    }
                )

    subset_ok = all(r.get("status") == "valid" for r in validation_rows) and bool(validation_rows)
    partial_runnable_ok = subset_ok and official_repo_check.get("layout_ok", False)
    classification = "partial_runnable_adjacent" if partial_runnable_ok else "import_validated_adjacent"

    comparison_readiness = {
        "baseline": "tree_plv",
        "run_id": run_id,
        "classification": classification,
        "status": "ready_adjacent_partial_runnable" if partial_runnable_ok else "ready_adjacent_import_validated_only",
        "adjacent_only": True,
        "minimum_contract_met": subset_ok,
        "official_repo_layout_ok": official_repo_check.get("layout_ok", False),
        "official_repo_license_visible": official_repo_check.get("license_visible", False),
        "safe_claims": contract.get("allowed_claims", []),
        "unsafe_claims": contract.get("forbidden_claims", []),
    }

    status_payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_key": "tree_plv",
        "canonical_title": contract.get("canonical_title", "Tree-PLV"),
        "classification": classification,
        "control_equivalence": "adjacent",
        "integration_kind": "official_adjacent_contract_lane",
        "official_sources": contract.get("official_sources", {}),
        "stable_subsets_verified": [r["subset_id"] for r in validation_rows if r["status"] == "valid"],
        "stable_subsets_failed": [r["subset_id"] for r in validation_rows if r["status"] != "valid"],
        "official_repo_check": official_repo_check,
    }

    summary = {
        "baseline": "tree_plv",
        "classification": classification,
        "minimum_contract_met": subset_ok,
        "official_repo_layout_ok": official_repo_check.get("layout_ok", False),
        "official_repo_license_visible": official_repo_check.get("license_visible", False),
        "comparison_ready_rows": len(comparison_rows),
        "output_dir": str(run_dir.relative_to(REPO_ROOT)),
    }

    summary_md = "\n".join(
        [
            "# Tree-PLV adjacent integration summary",
            "",
            f"- Run ID: `{run_id}`",
            f"- Classification: `{classification}`",
            f"- Minimum contract met: `{subset_ok}`",
            f"- Official repo layout check: `{official_repo_check.get('layout_ok', False)}`",
            f"- Official repo root license file visible: `{official_repo_check.get('license_visible', False)}`",
            f"- Comparison rows exported: `{len(comparison_rows)}`",
            "",
            "## Scope guardrail",
            "",
            "- This run is **adjacent-only** and does not claim full faithful in-repo Tree-PLV reproduction.",
            "- Claims remain limited to contract-validated import evidence and cited-repo structure checks.",
        ]
    ) + "\n"

    config_snapshot = {
        "contract_config_path": str(contract_path.relative_to(REPO_ROOT)),
        "contract": contract,
        "args": {
            "output_root": str(output_root),
            "official_repo_path": str(official_repo_path),
            "skip_clone": args.skip_clone,
        },
    }

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "script": "scripts/run_tree_plv_adjacent_integration.py",
        "output_dir": str(run_dir.relative_to(REPO_ROOT)),
        "commands": commands,
        "clone_result": clone_result,
        "artifacts": required_outputs,
    }

    _write_json(run_dir / "status.json", status_payload)
    _write_json(run_dir / "comparison_readiness.json", comparison_readiness)
    _write_json(run_dir / "summary.json", summary)
    (run_dir / "summary.md").write_text(summary_md, encoding="utf-8")
    _write_json(run_dir / "manifest.json", manifest)
    _write_json(run_dir / "config_snapshot.json", config_snapshot)
    (run_dir / "commands_snapshot.txt").write_text("\n".join(commands) + "\n", encoding="utf-8")
    _write_json(run_dir / "verification_report.json", validation_reports)
    _write_json(run_dir / "official_repo_structure.json", official_repo_check)
    _write_csv(run_dir / "validation_status.csv", validation_rows)
    _write_csv(run_dir / "comparison_ready_rows.csv", comparison_rows)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
