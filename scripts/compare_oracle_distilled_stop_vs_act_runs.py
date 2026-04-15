#!/usr/bin/env python3
"""Aggregate oracle-distilled student summaries into comparison-ready artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten(summary: dict[str, Any], path: str) -> dict[str, Any]:
    settings = dict(summary.get("settings", {}))
    data = dict(summary.get("dataset_summary", {}))
    evaln = dict(summary.get("evaluation", {}))
    student = dict(evaln.get("student", {}))
    anchor = dict(evaln.get("anchor_gain_gap_baseline", {}))
    diff = dict(evaln.get("student_minus_anchor", {}))

    return {
        "summary_path": path,
        "run_name": summary.get("run_name", Path(path).parent.name),
        "train_buckets": ",".join(settings.get("train_buckets", [])),
        "eval_buckets": ",".join(settings.get("eval_buckets", [])),
        "model_kind": settings.get("model_kind", ""),
        "non_claim_mode": bool(dict(summary.get("safety", {})).get("non_claim_mode", False)),
        "mock_rows_detected": int(data.get("mock_rows_detected", 0)),
        "train_rows": int(data.get("train_rows", 0)),
        "eval_rows": int(data.get("eval_rows", 0)),
        "student_accuracy": float(student.get("accuracy", 0.0)),
        "student_auc": float(student.get("roc_auc", 0.0)),
        "student_brier": float(student.get("brier", 0.0)),
        "anchor_accuracy": float(anchor.get("accuracy", 0.0)),
        "anchor_auc": float(anchor.get("roc_auc", 0.0)),
        "anchor_brier": float(anchor.get("brier", 0.0)),
        "delta_accuracy": float(diff.get("accuracy", 0.0)),
        "delta_auc": float(diff.get("roc_auc", 0.0)),
        "delta_brier": float(diff.get("brier", 0.0)),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare oracle-distilled stop-vs-act run summaries")
    p.add_argument("--summaries", nargs="+", required=True, help="One or more oracle_distilled_student_summary.json paths")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--anchor-summary", default="", help="Optional current-default anchor summary for reference metadata")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = [_flatten(_load_json(Path(path)), path) for path in args.summaries]
    rows_sorted = sorted(rows, key=lambda r: (r["non_claim_mode"], -r["delta_accuracy"], -r["student_accuracy"]))

    csv_path = out_dir / "oracle_distilled_student_comparison.csv"
    fields = [
        "run_name",
        "summary_path",
        "train_buckets",
        "eval_buckets",
        "model_kind",
        "non_claim_mode",
        "mock_rows_detected",
        "train_rows",
        "eval_rows",
        "student_accuracy",
        "anchor_accuracy",
        "delta_accuracy",
        "student_auc",
        "anchor_auc",
        "delta_auc",
        "student_brier",
        "anchor_brier",
        "delta_brier",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows_sorted:
            writer.writerow(row)

    best = rows_sorted[0] if rows_sorted else {}
    payload = {
        "status": "ok",
        "rows": rows_sorted,
        "num_runs": len(rows_sorted),
        "best_by_delta_accuracy": {
            "run_name": best.get("run_name", ""),
            "delta_accuracy": best.get("delta_accuracy", 0.0),
            "non_claim_mode": best.get("non_claim_mode", True),
        },
        "comparison_questions": {
            "accepted_only_vs_accepted_plus_borderline": "Compare rows where train_buckets differ.",
            "selective_filtering_help": "Compare delta_accuracy/delta_auc across train_buckets and mock vs non-mock modes.",
            "beat_current_default_anchor": "Requires supplying anchor summary from the unchanged default stop-vs-act path after real pilot labels are available.",
        },
        "anchor_summary_path": args.anchor_summary,
        "non_claim_warning": "Any run with non_claim_mode=true is diagnostic only and not evidence of real oracle-distilled gains.",
    }

    (out_dir / "oracle_distilled_student_comparison_summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    md_lines = [
        "# Oracle-distilled stop-vs-act comparison (scaffold)",
        "",
        f"- Runs compared: {len(rows_sorted)}",
        f"- CSV: `{csv_path}`",
        "",
        "| run_name | train_buckets | non_claim_mode | student_acc | anchor_acc | delta_acc |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows_sorted:
        md_lines.append(
            f"| {row['run_name']} | {row['train_buckets']} | {row['non_claim_mode']} | "
            f"{row['student_accuracy']:.4f} | {row['anchor_accuracy']:.4f} | {row['delta_accuracy']:+.4f} |"
        )
    md_lines += [
        "",
        "## Interpretation guardrails",
        "- If `non_claim_mode=true`, treat the run as wiring diagnostics only.",
        "- Final claims require real validated pilot labels plus anchor-baseline comparisons.",
    ]
    (out_dir / "oracle_distilled_student_comparison.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
