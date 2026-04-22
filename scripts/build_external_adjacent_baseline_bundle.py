#!/usr/bin/env python3
"""Build manuscript-safe aggregate bundle for strengthened external adjacent baselines."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs" / "external_adjacent_baseline_bundle"
DEFAULT_REGISTRY_PATH = REPO_ROOT / "configs" / "external_baselines_registry.json"
DEFAULT_MATRIX_PATH = REPO_ROOT / "outputs" / "baseline_repair_and_status_audit_20260420T225833Z" / "baseline_status_matrix.json"

TARGET_BASELINES: list[dict[str, str]] = [
    {
        "baseline_id": "best_route_microsoft",
        "display_name": "BEST-Route",
        "doc": "docs/best_route_integration.md",
        "status_json": "outputs/external_baseline_completeness/best_route_status.json",
        "integration_output_family": "outputs/best_route_adjacent_integration",
        "repo_command": "python scripts/run_best_route_adjacent_integration.py --import-config configs/best_route_official_import_v1.json --contract-config configs/best_route_adjacent_comparison_contract_v1.json",
    },
    {
        "baseline_id": "when_solve_when_verify",
        "display_name": "when_solve_when_verify",
        "doc": "docs/when_solve_when_verify_integration.md",
        "status_json": "outputs/external_baseline_completeness/when_solve_when_verify_status.json",
        "integration_output_family": "outputs/when_solve_when_verify_adjacent_integration",
        "repo_command": "python scripts/run_when_solve_when_verify_adjacent_integration.py --import-config configs/when_solve_when_verify_official_import_v1.json --contract-config configs/when_solve_when_verify_adjacent_comparison_contract_v1.json",
    },
    {
        "baseline_id": "rest_mcts",
        "display_name": "ReST-MCTS*",
        "doc": "docs/rest_mcts_integration.md",
        "status_json": "outputs/external_baseline_completeness/rest_mcts_status.json",
        "integration_output_family": "outputs/rest_mcts_adjacent_integration",
        "repo_command": "python scripts/run_rest_mcts_adjacent_integration.py --contract-config configs/rest_mcts_adjacent_comparison_contract_v2.json",
    },
]

CSV_COLUMNS = [
    "baseline_id",
    "display_name",
    "official_vs_unofficial",
    "status",
    "control_equivalence",
    "current_safest_comparison_scope",
    "artifact_backed_now",
    "repo_command_available",
    "paper_safe_now",
    "key_limitation",
    "registry_integration",
    "latest_integration_run_id",
    "latest_integration_status",
]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in columns})


def _list_run_dirs(path: Path) -> list[Path]:
    if not path.exists() or not path.is_dir():
        return []
    return sorted([p for p in path.iterdir() if p.is_dir() and p.name[:8].isdigit()], key=lambda p: p.name)


def _latest_run_status(output_family: str) -> tuple[str, str, str]:
    family_path = REPO_ROOT / output_family
    run_dirs = _list_run_dirs(family_path)
    if not run_dirs:
        return "", "not_found", "no_committed_run_artifact_found"

    latest = run_dirs[-1]
    status_path = latest / "status.json"
    if not status_path.exists():
        return latest.name, "status_missing", "latest_run_missing_status_json"

    try:
        status_payload = _read_json(status_path)
    except json.JSONDecodeError:
        return latest.name, "status_unreadable", "latest_run_status_json_unreadable"

    normalized = str(status_payload.get("status", "unknown"))
    return latest.name, normalized, ""


def _format_bool(v: Any) -> str:
    return "yes" if bool(v) else "no"


def _build_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# External adjacent baseline bundle summary")
    lines.append("")
    lines.append(f"Generated UTC: `{summary['meta']['generated_utc']}`")
    lines.append(f"Run ID: `{summary['meta']['run_id']}`")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("This bundle aggregates manuscript-safe status for the strengthened **official adjacent** baselines:")
    lines.append("- BEST-Route")
    lines.append("- when_solve_when_verify")
    lines.append("- ReST-MCTS*")
    lines.append("")
    lines.append("These remain **adjacent** (not control-equivalent direct frontier-allocation baselines).")
    lines.append("")
    lines.append("## Manuscript-safe matrix")
    lines.append("")
    header = "| baseline id | official vs unofficial | status | control equivalence | current safest comparison scope | artifact-backed now | repo command available | paper-safe now | key limitation |"
    sep = "|---|---|---|---|---|---|---|---|---|"
    lines.extend([header, sep])
    for row in summary["rows"]:
        lines.append(
            "| {baseline_id} | {official_vs_unofficial} | {status} | {control_equivalence} | {current_safest_comparison_scope} | {artifact_backed_now} | {repo_command_available} | {paper_safe_now} | {key_limitation} |".format(
                **row
            )
        )
    lines.append("")
    lines.append("## Out of scope")
    lines.append("")
    lines.append("- Full official upstream training/inference reproduction for all three baselines.")
    lines.append("- Reframing adjacent baselines as direct control-equivalent branch-allocation methods.")
    lines.append("- Taxonomy changes beyond conservative aggregation on top of current status artifacts.")
    lines.append("")
    lines.append("## Backing artifacts")
    lines.append("")
    for row in summary["rows"]:
        artifacts = ", ".join(row["backing_artifacts"])
        lines.append(f"- `{row['baseline_id']}`: {artifacts}")
    lines.append("")
    return "\n".join(lines)


def build_bundle(output_root: Path, run_id: str, registry_path: Path, matrix_path: Path) -> Path:
    registry = _read_json(registry_path)
    matrix = _read_json(matrix_path)

    matrix_rows = {row["baseline_id"]: row for row in matrix.get("baselines", [])}
    registry_rows = registry.get("baselines", {})

    rows: list[dict[str, Any]] = []

    for spec in TARGET_BASELINES:
        baseline_id = spec["baseline_id"]
        matrix_row = matrix_rows.get(baseline_id, {})
        registry_row = registry_rows.get(baseline_id, {})

        status_payload = {}
        status_path = REPO_ROOT / spec["status_json"]
        if status_path.exists():
            status_payload = _read_json(status_path)

        latest_run_id, latest_run_status, run_note = _latest_run_status(spec["integration_output_family"])

        status = str(matrix_row.get("status", registry_row.get("integration", "unknown")))
        control = str(matrix_row.get("control_equivalence", status_payload.get("control_equivalence", "unknown")))
        official_level = str(
            status_payload.get("resource_level")
            or ("official" if bool(registry_row.get("clone_url")) else "unofficial_or_unknown")
        )

        key_limitation = str(registry_row.get("blocker", "not_specified"))
        safest_scope = "adjacent_only"
        safe_wording = str(matrix_row.get("safe_wording_now", ""))
        if safe_wording:
            safest_scope = f"adjacent_only ({safe_wording})"

        artifacts = [
            spec["doc"],
            spec["status_json"],
            str(matrix_path.relative_to(REPO_ROOT)),
        ]
        if latest_run_id:
            artifacts.append(f"{spec['integration_output_family']}/{latest_run_id}/status.json")

        row = {
            "baseline_id": baseline_id,
            "display_name": spec["display_name"],
            "official_vs_unofficial": official_level,
            "status": status,
            "control_equivalence": control,
            "current_safest_comparison_scope": safest_scope,
            "artifact_backed_now": _format_bool(matrix_row.get("artifact_backed_now", False)),
            "repo_command_available": _format_bool(matrix_row.get("repo_command_available", False)),
            "paper_safe_now": _format_bool(matrix_row.get("paper_safe_now", False)),
            "key_limitation": key_limitation,
            "registry_integration": str(registry_row.get("integration", "unknown")),
            "latest_integration_run_id": latest_run_id,
            "latest_integration_status": latest_run_status,
            "recommended_repo_command": spec["repo_command"],
            "backing_artifacts": artifacts,
            "notes": run_note,
        }
        rows.append(row)

    summary = {
        "meta": {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "script": "scripts/build_external_adjacent_baseline_bundle.py",
            "output_dir": str((output_root / run_id).relative_to(REPO_ROOT)),
            "source_registry": str(registry_path.relative_to(REPO_ROOT)),
            "source_status_matrix": str(matrix_path.relative_to(REPO_ROOT)),
            "target_family": "external_adjacent_baseline_bundle",
        },
        "scope": {
            "included_baseline_ids": [s["baseline_id"] for s in TARGET_BASELINES],
            "manuscript_guardrails": [
                "adjacent official baselines are reviewer-relevant but not direct control-equivalent",
                "import-validated/partial-runnable rows must not be reported as full in-repo faithful reproductions",
                "near-direct MODE A baselines (s1/TALE/L1) remain a separate family",
            ],
        },
        "rows": rows,
    }

    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_dir / "summary.json", summary)
    _write_csv(run_dir / "summary.csv", rows, CSV_COLUMNS)

    manuscript_columns = [
        "baseline_id",
        "display_name",
        "official_vs_unofficial",
        "status",
        "control_equivalence",
        "current_safest_comparison_scope",
        "artifact_backed_now",
        "repo_command_available",
        "paper_safe_now",
        "key_limitation",
    ]
    _write_csv(run_dir / "manuscript_table.csv", rows, manuscript_columns)

    md = _build_markdown(summary)
    (run_dir / "summary.md").write_text(md, encoding="utf-8")
    (run_dir / "README.md").write_text(
        "# External adjacent baseline bundle run\n\n"
        f"- Run ID: `{run_id}`\n"
        "- Primary artifacts: `summary.json`, `summary.csv`, `summary.md`, `manuscript_table.csv`\n"
        "- Rebuild command:\n"
        "  - `python scripts/build_external_adjacent_baseline_bundle.py`\n",
        encoding="utf-8",
    )

    return run_dir


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build external adjacent baseline aggregate bundle")
    p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH))
    p.add_argument("--status-matrix-path", default=str(DEFAULT_MATRIX_PATH))
    p.add_argument("--run-id", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = build_bundle(
        output_root=Path(args.output_root).resolve(),
        run_id=run_id,
        registry_path=Path(args.registry_path).resolve(),
        matrix_path=Path(args.status_matrix_path).resolve(),
    )
    print(json.dumps({"run_dir": str(run_dir.relative_to(REPO_ROOT)), "run_id": run_id}, indent=2))


if __name__ == "__main__":
    main()
