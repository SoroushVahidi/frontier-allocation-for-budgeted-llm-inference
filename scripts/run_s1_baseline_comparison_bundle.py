#!/usr/bin/env python3
"""Build a reviewer-facing comparison bundle from one or more s1 baseline runs."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create s1 baseline comparison bundle")
    p.add_argument(
        "--run-dirs",
        required=True,
        help="Comma-separated list of run directories produced by run_s1_budget_forcing_baseline.py",
    )
    p.add_argument("--output-dir", default="outputs/s1_baseline/comparison_bundle")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    input_dirs = [Path(x.strip()) for x in args.run_dirs.split(",") if x.strip()]

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    merged_summary: list[dict[str, Any]] = []
    merged_comparison: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []

    for rd in input_dirs:
        summary = _read_csv(rd / "summary.csv")
        comparison = _read_csv(rd / "comparison_to_ours.csv")
        manifest_path = rd / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        manifests.append({"run_dir": str(rd), **manifest})

        for row in summary:
            merged_summary.append({"source_run_dir": str(rd), **row})
        for row in comparison:
            merged_comparison.append({"source_run_dir": str(rd), **row})

    best_rows: list[dict[str, Any]] = []
    # Best method per (source_run_dir, budget) by mean_accuracy then lower cost.
    keyed: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in merged_summary:
        key = (str(row.get("source_run_dir", "")), str(row.get("budget_actions", "")))
        keyed.setdefault(key, []).append(row)

    for (src, budget), rows in sorted(keyed.items(), key=lambda x: (x[0][0], float(x[0][1] or 0))):
        rows_sorted = sorted(
            rows,
            key=lambda r: (-float(r.get("mean_accuracy", 0.0)), float(r.get("mean_avg_token_cost_equivalent", 0.0))),
        )
        if rows_sorted:
            best_rows.append(
                {
                    "source_run_dir": src,
                    "budget_actions": budget,
                    "best_method": rows_sorted[0].get("method", ""),
                    "best_accuracy": rows_sorted[0].get("mean_accuracy", ""),
                    "best_cost": rows_sorted[0].get("mean_avg_token_cost_equivalent", ""),
                }
            )

    bundle_manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_run_dirs": [str(p) for p in input_dirs],
        "num_runs": len(input_dirs),
        "num_summary_rows": len(merged_summary),
        "num_pairwise_rows": len(merged_comparison),
    }

    note_lines = [
        "# s1 baseline comparison bundle",
        "",
        f"- generated_at_utc: `{bundle_manifest['created_utc']}`",
        f"- num_input_runs: `{bundle_manifest['num_runs']}`",
        "",
        "## Scope",
        "- This bundle merges multiple s1 baseline integration runs for manuscript table assembly.",
        "- Primary fair comparison remains MODE A: unchanged-base-model `adaptive_min_expand_1` vs `external_s1_budget_forcing`.",
        "- MODE B rows, if present, are secondary and should be labeled as including potential post-training.",
    ]

    _write_csv(out_dir / "merged_summary.csv", merged_summary)
    _write_csv(out_dir / "merged_comparison_to_ours.csv", merged_comparison)
    _write_csv(out_dir / "best_method_by_budget.csv", best_rows)
    (out_dir / "bundle_manifest.json").write_text(json.dumps(bundle_manifest, indent=2), encoding="utf-8")
    (out_dir / "source_run_manifests.json").write_text(json.dumps(manifests, indent=2), encoding="utf-8")
    (out_dir / "note.md").write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
