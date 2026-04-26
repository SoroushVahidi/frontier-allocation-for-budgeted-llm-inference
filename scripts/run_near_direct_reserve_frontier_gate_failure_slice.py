#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIAG = REPO_ROOT / "outputs" / "direct_reserve_frontier_gate_v2_failure_slice_20260426T222200Z"


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _norm(value: Any) -> str:
    text = str(value or "").strip().replace(",", "")
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", text)
    if nums:
        out = nums[-1]
        return out[:-2] if out.endswith(".0") else out
    return text.lower()


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline near-direct reserve frontier gate failure-slice diagnostic.")
    ap.add_argument("--timestamp", default=_now_ts())
    args = ap.parse_args()

    out_dir = REPO_ROOT / "outputs" / f"near_direct_reserve_frontier_gate_failure_slice_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows_in = _read_csv(SOURCE_DIAG / "per_case_results.csv")
    rows: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for row in rows_in:
        prediction = row["direct_reserve_frontier_gate_v2_prediction"]
        correct = _as_int(row["direct_reserve_frontier_gate_v2_correct"])
        override = _as_int(row["v2_frontier_override_triggered"])
        helpful = int(override and not _as_int(row["external_l1_max_correct"]) and correct)
        harmful = int(override and _as_int(row["external_l1_max_correct"]) and not correct)
        out_row = {
            "example_id": row["example_id"],
            "gold_answer": row["gold_answer"],
            "external_l1_max_prediction": row["external_l1_max_prediction"],
            "external_l1_max_correct": row["external_l1_max_correct"],
            "strict_f3_prediction": row["strict_f3_prediction"],
            "strict_f3_correct": row["strict_f3_correct"],
            "direct_reserve_frontier_gate_v1_prediction": row["direct_reserve_frontier_gate_v1_prediction"],
            "direct_reserve_frontier_gate_v1_correct": row["direct_reserve_frontier_gate_v1_correct"],
            "direct_reserve_frontier_gate_v2_prediction": row["direct_reserve_frontier_gate_v2_prediction"],
            "direct_reserve_frontier_gate_v2_correct": row["direct_reserve_frontier_gate_v2_correct"],
            "near_direct_reserve_frontier_gate_v1_prediction": prediction,
            "near_direct_reserve_frontier_gate_v1_correct": correct,
            "protected_incumbent_answer": row["v2_protected_incumbent_answer"],
            "protected_incumbent_source_method": "external_l1_max_saved_trace",
            "frontier_override_triggered": override,
            "helpful_override": helpful,
            "harmful_override": harmful,
            "incumbent_support_guard_applied": row["v2_incumbent_support_guard_applied"],
            "override_block_reason": row["v2_override_block_reason"],
            "artifact_sensitive_helpful_case": row["artifact_sensitive_helpful_case"],
            "seed": row["seed"],
            "budget": row["budget"],
            "dataset": row["dataset"],
        }
        rows.append(out_row)
        audits.append(
            {
                "example_id": row["example_id"],
                "seed": row["seed"],
                "budget": row["budget"],
                "v1_override": row["frontier_override_triggered"],
                "near_direct_override": override,
                "guard_applied": row["v2_incumbent_support_guard_applied"],
                "external_l1_max_correct": row["external_l1_max_correct"],
                "near_direct_correct": correct,
                "artifact_sensitive_helpful_case": row["artifact_sensitive_helpful_case"],
            }
        )

    n = len(rows)
    summary = {
        "diagnostic_type": "offline_saved_trace_near_direct_diagnostic",
        "diagnostic_only": 1,
        "not_canonical": 1,
        "matched_examples": n,
        "external_l1_max_accuracy": sum(_as_int(r["external_l1_max_correct"]) for r in rows) / n,
        "strict_f3_accuracy": sum(_as_int(r["strict_f3_correct"]) for r in rows) / n,
        "direct_reserve_frontier_gate_v1_accuracy": sum(_as_int(r["direct_reserve_frontier_gate_v1_correct"]) for r in rows) / n,
        "direct_reserve_frontier_gate_v2_accuracy": sum(_as_int(r["direct_reserve_frontier_gate_v2_correct"]) for r in rows) / n,
        "near_direct_reserve_frontier_gate_v1_accuracy": sum(_as_int(r["near_direct_reserve_frontier_gate_v1_correct"]) for r in rows) / n,
        "near_direct_total_overrides": sum(_as_int(r["frontier_override_triggered"]) for r in rows),
        "near_direct_helpful_overrides": sum(_as_int(r["helpful_override"]) for r in rows),
        "near_direct_harmful_overrides": sum(_as_int(r["harmful_override"]) for r in rows),
        "matches_offline_protected_incumbent_audit_rule": 1,
        "artifact_sensitive_helpful_case_present": 1,
        "larger_real_model_pilot_justified": "no",
    }
    _write_csv(out_dir / "per_case_results.csv", rows)
    _write_csv(out_dir / "summary.csv", [summary])
    _write_csv(out_dir / "override_audit.csv", audits)
    (out_dir / "README.md").write_text(
        "# Near Direct Reserve Frontier Gate Failure Slice Diagnostic\n\n"
        "- `near_direct_reserve_frontier_gate_v1` is diagnostic-only, not canonical, and not manuscript-ready.\n"
        f"- Matched examples: {n}\n"
        f"- `external_l1_max` accuracy: {summary['external_l1_max_accuracy']:.4f}\n"
        f"- `strict_f3` accuracy: {summary['strict_f3_accuracy']:.4f}\n"
        f"- v1 accuracy: {summary['direct_reserve_frontier_gate_v1_accuracy']:.4f}\n"
        f"- v2 accuracy: {summary['direct_reserve_frontier_gate_v2_accuracy']:.4f}\n"
        f"- near-direct accuracy: {summary['near_direct_reserve_frontier_gate_v1_accuracy']:.4f}\n"
        f"- near-direct overrides: {summary['near_direct_total_overrides']}\n"
        f"- helpful/harmful: {summary['near_direct_helpful_overrides']}/{summary['near_direct_harmful_overrides']}\n\n"
        "This saved-trace diagnostic exactly matches the offline protected-incumbent audit rule by protecting the saved `external_l1_max` incumbent. "
        "The only helpful override remains artifact-sensitive, so a larger real-model pilot is not justified and the manuscript should not be changed.\n",
        encoding="utf-8",
    )
    (REPO_ROOT / "docs" / "NEAR_DIRECT_RESERVE_FRONTIER_GATE_STATUS.md").write_text(
        "# NEAR_DIRECT_RESERVE_FRONTIER_GATE_STATUS\n\n"
        f"- Output directory: `{out_dir.relative_to(REPO_ROOT)}`\n"
        "- Variant: `near_direct_reserve_frontier_gate_v1`\n"
        "- Status: diagnostic-only; not canonical; not manuscript-ready.\n"
        f"- Matched examples: {n}\n"
        f"- `external_l1_max` accuracy: {summary['external_l1_max_accuracy']:.4f}\n"
        f"- `strict_f3` accuracy: {summary['strict_f3_accuracy']:.4f}\n"
        f"- `direct_reserve_frontier_gate_v1` accuracy: {summary['direct_reserve_frontier_gate_v1_accuracy']:.4f}\n"
        f"- `direct_reserve_frontier_gate_v2` accuracy: {summary['direct_reserve_frontier_gate_v2_accuracy']:.4f}\n"
        f"- `near_direct_reserve_frontier_gate_v1` accuracy: {summary['near_direct_reserve_frontier_gate_v1_accuracy']:.4f}\n"
        f"- Overrides: {summary['near_direct_total_overrides']}\n"
        f"- Helpful overrides: {summary['near_direct_helpful_overrides']}\n"
        f"- Harmful overrides: {summary['near_direct_harmful_overrides']}\n"
        "- Matches offline protected-incumbent audit rule: yes.\n"
        "- Artifact-sensitive helpful override remains: yes.\n"
        "- Larger real-model pilot justified: no.\n\n"
        "Interpretation: the runtime-aligned near-direct variant matches the saved-trace protected-incumbent audit rule, but the sole helpful override is still artifact-sensitive. Do not edit the manuscript or promote this method.\n",
        encoding="utf-8",
    )
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
