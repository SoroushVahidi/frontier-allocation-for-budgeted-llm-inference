#!/usr/bin/env python3
"""Generate an evidence-backed HLE integration status report for this repository."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.hf_datasets import check_hf_dataset_access, sample_hf_examples


def _smoke_sample(dataset_name: str, size: int = 8) -> tuple[bool, str, list[dict[str, str]]]:
    try:
        rows = sample_hf_examples(dataset_name=dataset_name, pilot_size=size, seed=7)
        return True, "", rows
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}", []


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate HLE integration status report")
    parser.add_argument("--out-json", default="docs/hle_integration_report_2026_04_19.json")
    parser.add_argument("--out-csv", default="docs/hle_integration_report_2026_04_19.csv")
    args = parser.parse_args()

    variants = [
        "cais/hle",
        "cais/hle_text_only",
        "cais/hle_exact_answer",
        "cais/hle_mcq",
        "cais/hle_auto_gradable",
    ]
    access = {name: check_hf_dataset_access(name) for name in variants}
    smoke: dict[str, dict[str, object]] = {}
    for name in variants:
        ok, error, rows = _smoke_sample(name, size=8)
        smoke[name] = {
            "ok": ok,
            "error": error,
            "sample_size": len(rows),
            "sample_keys": sorted(rows[0].keys()) if rows else [],
            "sample_answer_types": sorted({r.get("answer_type", "") for r in rows if r.get("answer_type")}),
            "sample_has_image_flags": sorted({r.get("has_image", "") for r in rows if r.get("has_image")}),
        }

    report_row = {
        "dataset_name": "Humanity's Last Exam (HLE)",
        "source_name": "cais/hle",
        "access_successful": bool(access["cais/hle"].get("ok")),
        "integrated_scope": (
            "Canonical cais/hle plus subset registry keys for text-only, exact-answer, MCQ, "
            "and text-only auto-gradable slices."
        ),
        "status": "partially_added",
        "experiment_status": "partially_ready",
        "text_only_supported": True,
        "exact_answer_supported": True,
        "mcq_supported": True,
        "multimodal_present": True,
        "auto_gradable_supported": True,
        "loader_added": True,
        "config_added": True,
        "smoke_test_passed": all(s.get("ok") for s in smoke.values()),
        "reason_if_partial": (
            "Canonical HLE includes image-bearing and richer rationale-image fields; current pipeline is "
            "experiment-ready for text-only auto-gradable subsets, not full multimodal evaluation."
        ),
        "next_step_needed": (
            "Add multimodal rendering/evaluation policy and scorer hooks before claiming full HLE support."
        ),
        "variant_access": access,
        "variant_smoke": smoke,
    }

    json_path = Path(args.out_json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps([report_row], indent=2), encoding="utf-8")

    csv_path = Path(args.out_csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "dataset_name",
        "source_name",
        "access_successful",
        "integrated_scope",
        "status",
        "experiment_status",
        "text_only_supported",
        "exact_answer_supported",
        "mcq_supported",
        "multimodal_present",
        "auto_gradable_supported",
        "loader_added",
        "config_added",
        "smoke_test_passed",
        "reason_if_partial",
        "next_step_needed",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerow({k: report_row[k] for k in fields})

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
