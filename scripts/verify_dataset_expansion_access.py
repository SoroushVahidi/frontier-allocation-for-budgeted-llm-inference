#!/usr/bin/env python3
"""Readiness verification for the priority dataset-expansion package."""

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

from experiments.hf_datasets import check_hf_dataset_access, resolve_dataset_spec

PRIORITY_DATASETS = [
    "allenai/drop",
    "TAUR-Lab/MuSR",
    "openeval/BIG-Bench-Hard",
    "deepmind/aqua_rat",
]


def _status_label(access_ok: bool) -> str:
    return "ready" if access_ok else "blocked"


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify priority dataset expansion access")
    parser.add_argument("--output-dir", default="outputs/dataset_expansion_access")
    parser.add_argument("--datasets", default=",".join(PRIORITY_DATASETS))
    args = parser.parse_args()

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for dataset in datasets:
        try:
            spec = resolve_dataset_spec(dataset)
            access = check_hf_dataset_access(spec.key)
            rows.append(
                {
                    "dataset": spec.key,
                    "repo_id": spec.repo_id,
                    "default_split": spec.default_split,
                    "default_config": spec.default_config,
                    "status": _status_label(bool(access.get("ok"))),
                    "access_ok": bool(access.get("ok")),
                    "first_row_keys": access.get("first_row_keys", []),
                    "error": access.get("error", ""),
                    "provenance_note": spec.provenance_note,
                }
            )
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "dataset": dataset,
                    "repo_id": "",
                    "default_split": "",
                    "default_config": "",
                    "status": "blocked",
                    "access_ok": False,
                    "first_row_keys": [],
                    "error": f"{type(exc).__name__}: {exc}",
                    "provenance_note": "",
                }
            )

    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "datasets": datasets,
        "results": rows,
    }

    (out_dir / "readiness.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with (out_dir / "readiness.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "dataset",
                "repo_id",
                "default_split",
                "default_config",
                "status",
                "access_ok",
                "first_row_keys",
                "error",
                "provenance_note",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "first_row_keys": json.dumps(row.get("first_row_keys", []))})

    print(str(out_dir / "readiness.json"))
    print(str(out_dir / "readiness.csv"))


if __name__ == "__main__":
    main()
