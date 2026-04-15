#!/usr/bin/env python3
"""Build a reviewer-facing comparison bundle from one or more TALE baseline runs."""

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
    p = argparse.ArgumentParser(description="Create TALE baseline comparison bundle")
    p.add_argument("--run-dirs", required=True, help="Comma-separated TALE run directories")
    p.add_argument("--output-dir", default="outputs/tale_baseline/comparison_bundle")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_dirs = [Path(x.strip()) for x in args.run_dirs.split(",") if x.strip()]

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    merged_summary: list[dict[str, Any]] = []
    merged_comparison: list[dict[str, Any]] = []
    source_manifests: list[dict[str, Any]] = []

    for rd in run_dirs:
        summary_rows = _read_csv(rd / "summary.csv")
        comparison_rows = _read_csv(rd / "comparison_to_ours.csv")
        manifest_path = rd / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

        source_manifests.append({"run_dir": str(rd), **manifest})
        for row in summary_rows:
            merged_summary.append({"source_run_dir": str(rd), **row})
        for row in comparison_rows:
            merged_comparison.append({"source_run_dir": str(rd), **row})

    bundle_manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_run_dirs": [str(x) for x in run_dirs],
        "num_runs": len(run_dirs),
        "num_summary_rows": len(merged_summary),
        "num_comparison_rows": len(merged_comparison),
    }

    note_lines = [
        "# TALE baseline comparison bundle",
        "",
        f"- generated_at_utc: `{bundle_manifest['created_utc']}`",
        f"- num_input_runs: `{bundle_manifest['num_runs']}`",
        "",
        "## Scope",
        "- This bundle merges TALE baseline runs for manuscript table assembly.",
        "- Primary fair comparison is MODE A (`external_tale_prompt_budgeting`) vs our anchor under matched-average-compute rows.",
        "- MODE B rows remain secondary and separately labeled due potential post-training usage.",
    ]

    _write_csv(out_dir / "merged_summary.csv", merged_summary)
    _write_csv(out_dir / "merged_comparison_to_ours.csv", merged_comparison)
    (out_dir / "bundle_manifest.json").write_text(json.dumps(bundle_manifest, indent=2), encoding="utf-8")
    (out_dir / "source_run_manifests.json").write_text(json.dumps(source_manifests, indent=2), encoding="utf-8")
    (out_dir / "note.md").write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
