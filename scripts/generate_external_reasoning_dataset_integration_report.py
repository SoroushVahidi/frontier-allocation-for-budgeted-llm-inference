#!/usr/bin/env python3
"""Generate external reasoning dataset integration artifacts for new-paper track."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.external_reasoning_datasets import run_external_reasoning_dataset_inspection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate external reasoning dataset integration report")
    parser.add_argument(
        "--output-root",
        default="outputs/external_reasoning_datasets",
        help="Root output folder; run_id subfolder is created under this path.",
    )
    parser.add_argument("--run-id", default=None, help="Optional run id. Defaults to UTC timestamp.")
    parser.add_argument("--sample-rows", type=int, default=2)
    return parser.parse_args()


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> None:
    args = parse_args()
    run_id = args.run_id or _default_run_id()
    out_dir = Path(args.output_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    inspection = run_external_reasoning_dataset_inspection(sample_rows=args.sample_rows)

    json_path = out_dir / "dataset_integration_report.json"
    json_path.write_text(json.dumps(inspection, indent=2, default=str), encoding="utf-8")

    csv_path = out_dir / "dataset_integration_report.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dataset_key",
                "hf_dataset_id",
                "access_ok",
                "license",
                "gated",
                "supervision_type",
                "structure_type",
                "row_count",
                "branch_scoring",
                "verifier_training",
                "pairwise_branch_ranking",
                "trajectory_supervision",
                "frontier_label_distance",
            ],
        )
        writer.writeheader()
        for row in inspection["results"]:
            use = row["usefulness"]
            writer.writerow(
                {
                    "dataset_key": row["dataset_key"],
                    "hf_dataset_id": row["hf_dataset_id"],
                    "access_ok": row["access_ok"],
                    "license": row.get("license"),
                    "gated": row.get("gated"),
                    "supervision_type": row["supervision_type"],
                    "structure_type": row["structure_type"],
                    "row_count": row.get("row_count"),
                    "branch_scoring": use.get("branch_scoring"),
                    "verifier_training": use.get("verifier_training"),
                    "pairwise_branch_ranking": use.get("pairwise_branch_ranking"),
                    "trajectory_supervision": use.get("trajectory_supervision"),
                    "frontier_label_distance": use.get("frontier_allocation_label_distance"),
                }
            )

    md_lines = [
        "# External reasoning dataset integration report",
        "",
        f"- Generated UTC: `{inspection['created_utc']}`",
        f"- Run id: `{run_id}`",
        f"- All integrated datasets accessible in this environment: `{inspection['all_access_ok']}`",
        "",
        "## Comparison table (integrated datasets)",
        "",
        "| Dataset key | HF dataset ID | Supervision | Structure | License | Gated | Access |",
        "|---|---|---|---|---|---:|---:|",
    ]

    for row in inspection["results"]:
        md_lines.append(
            f"| `{row['dataset_key']}` | `{row['hf_dataset_id']}` | `{row['supervision_type']}` | "
            f"`{row['structure_type']}` | `{row.get('license')}` | `{row.get('gated')}` | `{row.get('access_ok')}` |"
        )

    md_lines.extend(["", "## Detailed integrated-dataset notes", ""])
    for row in inspection["results"]:
        use = row["usefulness"]
        md_lines.extend(
            [
                f"### {row['dataset_key']} ({row['hf_dataset_id']})",
                f"- Variant candidates: `{row.get('variant_candidates')}`",
                f"- Selected config/split: `{row.get('selected_config')}` / `{row.get('selected_split')}`",
                f"- Split names: `{list(row.get('splits', {}).keys())}`",
                f"- Row count (selected split): `{row.get('row_count')}`",
                f"- Schema fields: `{row.get('schema_fields')}`",
                f"- Sample previews captured: `{len(row.get('sample_previews', []))}`",
                f"- Useful for branch scoring: `{use.get('branch_scoring')}`",
                f"- Useful for verifier training: `{use.get('verifier_training')}`",
                f"- Useful for pairwise branch ranking: `{use.get('pairwise_branch_ranking')}`",
                f"- Useful for trajectory supervision: `{use.get('trajectory_supervision')}`",
                f"- Distance from frontier-allocation labels: `{use.get('frontier_allocation_label_distance')}`",
                f"- Caveat note: {row.get('chosen_variant_reason')}",
                f"- Error (if any): `{row.get('error')}`",
                "",
            ]
        )

    md_lines.extend(["## Candidate audit (integrated and not-integrated decisions)", ""])
    for candidate in inspection.get("candidate_audit", []):
        md_lines.extend(
            [
                f"### {candidate['candidate_name']}",
                f"- Requested source: `{candidate['requested_source']}`",
                f"- Chosen source: `{candidate['chosen_source']}`",
                f"- Integration status: `{candidate['integration_status']}`",
                f"- Dataset key (if integrated): `{candidate.get('dataset_key')}`",
                f"- Reason: {candidate['reason']}",
                "",
            ]
        )

    md_lines.extend(
        [
            "## License + access caveats",
            "",
            "- Licenses are read from dataset card metadata/tags when available and should be manually re-checked before release.",
            "- This integration is download-on-demand; raw dataset dumps are not committed in this repository.",
            "- These datasets are integrated for potential future experiments only (not yet evidence of final-method training).",
            "",
            "## Artifacts",
            "",
            f"- `{json_path}`",
            f"- `{csv_path}`",
        ]
    )

    md_path = out_dir / "dataset_integration_report.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    access_path = out_dir / "dataset_access_status.json"
    access_status = {
        "created_utc": inspection["created_utc"],
        "dataset_count": inspection["dataset_count"],
        "all_access_ok": inspection["all_access_ok"],
        "access_rows": [
            {
                "dataset_key": row["dataset_key"],
                "hf_dataset_id": row["hf_dataset_id"],
                "access_ok": row["access_ok"],
                "error": row.get("error"),
            }
            for row in inspection["results"]
        ],
    }
    access_path.write_text(json.dumps(access_status, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "run_id": run_id,
                "json": str(json_path),
                "md": str(md_path),
                "csv": str(csv_path),
                "access_json": str(access_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
