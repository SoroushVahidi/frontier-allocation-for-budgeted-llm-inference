#!/usr/bin/env python3
"""Generate canonical text-only artifact bundle for priority dataset expansion."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.hf_datasets import check_hf_dataset_access, resolve_dataset_spec, sample_hf_examples

PRIORITY_DATASETS = [
    "allenai/drop",
    "TAUR-Lab/MuSR",
    "openeval/BIG-Bench-Hard",
    "deepmind/aqua_rat",
]

SCIENTIFIC_VALUE = {
    "allenai/drop": "Evidence-grounded paragraph reasoning with numerical/span extraction.",
    "TAUR-Lab/MuSR": "Long-context narrative disambiguation and multi-step soft reasoning.",
    "openeval/BIG-Bench-Hard": "Cross-domain reasoning breadth beyond math-heavy benchmarks.",
    "deepmind/aqua_rat": "Multiple-choice reasoning with explicit option-normalization pressure.",
}


def _dataset_status(spec_key: str, access: dict[str, Any], sample_result: dict[str, Any]) -> tuple[str, str]:
    if access.get("ok") and sample_result.get("ok"):
        return "integrated", "Load + schema probe + smoke sample succeeded."
    if access.get("ok") and not sample_result.get("ok"):
        return "partial", f"Access succeeded but smoke sampling failed: {sample_result.get('error', 'unknown')}"
    if (not access.get("ok")) and sample_result.get("ok"):
        return "partial", "Smoke sample succeeded while readiness check failed (inconsistent environment)."
    return "failed", f"Access failed: {access.get('error', 'unknown')}"


def _schema_fields(access: dict[str, Any], sample_result: dict[str, Any]) -> list[str]:
    fields = access.get("first_row_keys") or []
    if fields:
        return [str(f) for f in fields]
    sample = sample_result.get("sample")
    if isinstance(sample, dict):
        return sorted(sample.keys())
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate dataset expansion integration bundle")
    parser.add_argument("--output-root", default="outputs/dataset_expansion_integration")
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--pilot-size", type=int, default=2)
    args = parser.parse_args()

    out_dir = Path(args.output_root) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    created_utc = datetime.now(timezone.utc).isoformat()

    status_rows: list[dict[str, Any]] = []
    schema_rows: list[dict[str, str]] = []
    preview_rows: list[dict[str, Any]] = []

    for dataset in PRIORITY_DATASETS:
        spec = resolve_dataset_spec(dataset)
        access = check_hf_dataset_access(spec.key)
        try:
            sample = sample_hf_examples(spec.key, pilot_size=args.pilot_size, seed=args.seed)
            sample_result = {"ok": True, "sample": sample[0] if sample else None, "count": len(sample)}
        except Exception as exc:  # noqa: BLE001
            sample_result = {"ok": False, "sample": None, "count": 0, "error": f"{type(exc).__name__}: {exc}"}

        status, reason = _dataset_status(spec.key, access, sample_result)
        schema_fields = _schema_fields(access, sample_result)

        status_rows.append(
            {
                "dataset": spec.key,
                "repo_id": spec.repo_id,
                "priority_order": PRIORITY_DATASETS.index(spec.key) + 1,
                "status": status,
                "reason": reason,
                "access_ok": bool(access.get("ok")),
                "smoke_ok": bool(sample_result.get("ok")),
                "default_split": spec.default_split,
                "default_config": spec.default_config,
                "scientific_value": SCIENTIFIC_VALUE[spec.key],
                "provenance_note": spec.provenance_note,
                "error": access.get("error") or sample_result.get("error") or "",
            }
        )
        schema_rows.append(
            {
                "dataset": spec.key,
                "repo_id": spec.repo_id,
                "schema_fields": "|".join(schema_fields),
                "question_fields": "|".join(spec.question_fields),
                "answer_fields": "|".join(spec.answer_fields),
                "default_split": spec.default_split,
                "default_config": spec.default_config or "",
            }
        )

        if sample_result.get("sample"):
            preview_rows.append(
                {
                    "dataset": spec.key,
                    "repo_id": spec.repo_id,
                    "status": status,
                    "sample": sample_result["sample"],
                }
            )

    manifest = {
        "run_id": args.run_id,
        "created_utc": created_utc,
        "script": "scripts/generate_dataset_expansion_report.py",
        "datasets": PRIORITY_DATASETS,
        "output_dir": str(out_dir),
        "files": [
            "status.json",
            "summary.json",
            "summary.md",
            "manifest.json",
            "dataset_status_matrix.csv",
            "dataset_schema_summary.csv",
            "dataset_sample_preview.jsonl",
            "config_snapshot.json",
            "command_snapshot.txt",
        ],
    }
    summary = {
        "run_id": args.run_id,
        "created_utc": created_utc,
        "attempted_datasets": PRIORITY_DATASETS,
        "integrated": [r["dataset"] for r in status_rows if r["status"] == "integrated"],
        "partial": [r["dataset"] for r in status_rows if r["status"] == "partial"],
        "failed": [r["dataset"] for r in status_rows if r["status"] == "failed"],
        "status_rows": status_rows,
    }
    status = {
        "overall_status": "ok" if not summary["failed"] else "partial",
        "integrated_count": len(summary["integrated"]),
        "partial_count": len(summary["partial"]),
        "failed_count": len(summary["failed"]),
        "dataset_status": {r["dataset"]: r["status"] for r in status_rows},
    }

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    (out_dir / "config_snapshot.json").write_text(
        json.dumps(
            {
                "output_root": args.output_root,
                "run_id": args.run_id,
                "seed": args.seed,
                "pilot_size": args.pilot_size,
                "datasets": PRIORITY_DATASETS,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "command_snapshot.txt").write_text(
        "python scripts/generate_dataset_expansion_report.py "
        f"--output-root {args.output_root} --run-id {args.run_id} --seed {args.seed} --pilot-size {args.pilot_size}\n",
        encoding="utf-8",
    )

    with (out_dir / "dataset_status_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "dataset",
                "repo_id",
                "priority_order",
                "status",
                "reason",
                "access_ok",
                "smoke_ok",
                "default_split",
                "default_config",
                "scientific_value",
                "provenance_note",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerows(status_rows)

    with (out_dir / "dataset_schema_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "dataset",
                "repo_id",
                "schema_fields",
                "question_fields",
                "answer_fields",
                "default_split",
                "default_config",
            ],
        )
        writer.writeheader()
        writer.writerows(schema_rows)

    with (out_dir / "dataset_sample_preview.jsonl").open("w", encoding="utf-8") as handle:
        for row in preview_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary_md = [
        f"# Dataset expansion integration summary ({args.run_id})",
        "",
        f"Generated UTC: `{created_utc}`",
        "",
        "## Dataset status matrix",
        "",
        "| Priority | Dataset | Status | Access | Smoke | Notes |",
        "|---:|---|---|---|---|---|",
    ]
    for row in status_rows:
        summary_md.append(
            f"| {row['priority_order']} | {row['dataset']} | {row['status']} | {row['access_ok']} | {row['smoke_ok']} | {row['reason']} |"
        )
    summary_md.extend(["", "## Scientific contribution notes", ""])
    for dataset in PRIORITY_DATASETS:
        summary_md.append(f"- **{dataset}**: {SCIENTIFIC_VALUE[dataset]}")
    (out_dir / "summary.md").write_text("\n".join(summary_md) + "\n", encoding="utf-8")

    print(str(out_dir))


if __name__ == "__main__":
    main()
