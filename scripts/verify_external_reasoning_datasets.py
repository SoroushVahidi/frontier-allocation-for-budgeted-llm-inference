#!/usr/bin/env python3
"""Verify access to external reasoning-supervision datasets (new-paper prep only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.external_reasoning_datasets import run_external_reasoning_dataset_inspection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify external reasoning dataset access")
    parser.add_argument("--output-dir", default="outputs/external_reasoning_datasets/latest_verify")
    parser.add_argument("--sample-rows", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = run_external_reasoning_dataset_inspection(sample_rows=args.sample_rows)

    json_path = output_dir / "external_reasoning_dataset_access.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md_lines = [
        "# External reasoning dataset access verification",
        "",
        f"- Generated UTC: `{report['created_utc']}`",
        f"- Dataset count: `{report['dataset_count']}`",
        f"- All accessible: `{report['all_access_ok']}`",
        "",
        "## Per-dataset status",
    ]
    for row in report["results"]:
        status = "✅" if row.get("access_ok") else "⚠️"
        md_lines.extend(
            [
                f"### {status} {row['dataset_key']} ({row['hf_dataset_id']})",
                f"- Supervision type: `{row['supervision_type']}`",
                f"- Structure type: `{row['structure_type']}`",
                f"- License (card): `{row.get('license')}`",
                f"- Gated: `{row.get('gated')}`",
                f"- Configs: `{row.get('configs')}`",
                f"- Splits: `{list(row.get('splits', {}).keys())}`",
                f"- Selected split: `{row.get('selected_split')}`",
                f"- Row count (if available): `{row.get('row_count')}`",
                f"- Schema fields: `{row.get('schema_fields')}`",
                f"- Error: `{row.get('error')}`",
                "",
            ]
        )
    md_lines.extend(["## Candidate audit status", ""])
    for candidate in report.get("candidate_audit", []):
        icon = "✅" if candidate.get("integration_status") == "integrated" else "⚠️"
        md_lines.extend(
            [
                f"- {icon} `{candidate['candidate_name']}`: {candidate['integration_status']} "
                f"(source={candidate['chosen_source']}) — {candidate['reason']}",
            ]
        )

    md_path = output_dir / "external_reasoning_dataset_access.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps({"json": str(json_path), "md": str(md_path)}, indent=2))


if __name__ == "__main__":
    main()
