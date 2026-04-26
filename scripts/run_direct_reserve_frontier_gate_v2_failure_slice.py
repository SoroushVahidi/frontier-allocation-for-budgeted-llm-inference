#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


SOURCE_DIAG = REPO_ROOT / "outputs" / "direct_reserve_frontier_gate_failure_slice_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN_DIAGNOSTIC_ACTUAL"
SOURCE_REPLAY = REPO_ROOT / "outputs" / "cohere_real_model_cost_normalized_validation_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN"


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
        for row in rows:
            w.writerow(row)


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


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _load_gate_metadata() -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for line in (SOURCE_REPLAY / "per_example_records.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("method") != "direct_reserve_frontier_gate_v1":
            continue
        out[(str(row["example_id"]), str(row["seed"]), str(row["budget"]))] = dict(row.get("result_metadata") or {})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline v2 diagnostic over the traced frontier-gate failure slice.")
    ap.add_argument("--timestamp", default=_now_ts())
    args = ap.parse_args()

    out_dir = REPO_ROOT / "outputs" / f"direct_reserve_frontier_gate_v2_failure_slice_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    v1_rows = _read_csv(SOURCE_DIAG / "per_case_results.csv")
    gate_meta = _load_gate_metadata()
    rows: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for row in v1_rows:
        key = (row["example_id"], row["seed"], row["budget"])
        md = gate_meta.get(key, {})
        direct_answer = str(md.get("direct_reserve_answer") or row["direct_reserve_answer"])
        # The failure-slice audit defines the incumbent as the external/near-direct
        # answer being protected, not necessarily the controller's internal first
        # direct attempt. Use the traced combined support pool from v1 metadata.
        incumbent_answer = str(row["external_l1_max_prediction"] or direct_answer)
        incumbent_group = _norm(incumbent_answer)
        traced_support_counts = md.get("answer_group_support_counts")
        if not isinstance(traced_support_counts, dict):
            traced_support_counts = {}
        incumbent_seen = int(traced_support_counts.get(incumbent_group, 0) or 0) > 0
        v1_override = bool(_as_int(row["frontier_override_triggered"]))
        guard_applied = bool(v1_override and incumbent_seen)

        if guard_applied:
            v2_prediction = incumbent_answer
            v2_correct = int(_norm(v2_prediction) == _norm(row["gold_answer"]))
            override = 0
            reserve_used = 1
            reason = "v2_blocked_incumbent_seen_in_frontier_support"
        else:
            v2_prediction = row["direct_reserve_frontier_gate_prediction"]
            v2_correct = _as_int(row["direct_reserve_frontier_gate_correct"])
            override = _as_int(row["frontier_override_triggered"])
            reserve_used = _as_int(row["reserve_used"])
            reason = row["override_reason"]

        helpful = int(override and not _as_int(row["external_l1_max_correct"]) and v2_correct)
        harmful = int(override and _as_int(row["external_l1_max_correct"]) and not v2_correct)
        preserved = int(_as_int(row["external_l1_max_correct"]) and v2_correct)
        harmed = int(_as_int(row["external_l1_max_correct"]) and not v2_correct)

        out_row = {
            **row,
            "direct_reserve_frontier_gate_v1_prediction": row["direct_reserve_frontier_gate_prediction"],
            "direct_reserve_frontier_gate_v1_correct": row["direct_reserve_frontier_gate_correct"],
            "direct_reserve_frontier_gate_v2_prediction": v2_prediction,
            "direct_reserve_frontier_gate_v2_correct": v2_correct,
            "v2_frontier_override_triggered": override,
            "v2_reserve_used": reserve_used,
            "incumbent_seen_in_frontier_support": int(incumbent_seen),
            "v2_protected_incumbent_answer": incumbent_answer,
            "v2_incumbent_support_guard_applied": int(guard_applied),
            "v2_override_block_reason": "incumbent_seen_in_frontier_support" if guard_applied else "not_blocked",
            "v2_override_reason": reason,
            "v2_helpful_override": helpful,
            "v2_harmful_override": harmful,
            "v2_direct_solved_preserved": preserved,
            "v2_direct_solved_harmed": harmed,
            "artifact_sensitive_helpful_case": int(key == ("openai_gsm8k_2", "11", "8")),
        }
        rows.append(out_row)
        audits.append(
            {
                "example_id": row["example_id"],
                "seed": row["seed"],
                "budget": row["budget"],
                "v1_override": int(v1_override),
                "v2_override": override,
                "v2_guard_applied": int(guard_applied),
                "v2_block_reason": out_row["v2_override_block_reason"],
                "external_l1_max_correct": row["external_l1_max_correct"],
                "v1_correct": row["direct_reserve_frontier_gate_correct"],
                "v2_correct": v2_correct,
                "artifact_sensitive_helpful_case": out_row["artifact_sensitive_helpful_case"],
            }
        )

    n = len(rows)
    summary = {
        "diagnostic_type": "offline_saved_trace_v2_diagnostic",
        "diagnostic_only": 1,
        "matched_examples": n,
        "external_l1_max_accuracy": sum(_as_int(r["external_l1_max_correct"]) for r in rows) / n,
        "strict_f3_accuracy": sum(_as_int(r["strict_f3_correct"]) for r in rows) / n,
        "direct_reserve_frontier_gate_v1_accuracy": sum(_as_int(r["direct_reserve_frontier_gate_v1_correct"]) for r in rows) / n,
        "direct_reserve_frontier_gate_v2_accuracy": sum(_as_int(r["direct_reserve_frontier_gate_v2_correct"]) for r in rows) / n,
        "v1_total_overrides": sum(_as_int(r["frontier_override_triggered"]) for r in rows),
        "v2_total_overrides": sum(_as_int(r["v2_frontier_override_triggered"]) for r in rows),
        "v2_helpful_overrides": sum(_as_int(r["v2_helpful_override"]) for r in rows),
        "v2_harmful_overrides": sum(_as_int(r["v2_harmful_override"]) for r in rows),
        "v2_direct_solved_preserved": sum(_as_int(r["v2_direct_solved_preserved"]) for r in rows),
        "v2_direct_solved_harmed": sum(_as_int(r["v2_direct_solved_harmed"]) for r in rows),
        "v2_blocks_harmful_v1_overrides": int(sum(_as_int(r["v2_harmful_override"]) for r in rows) == 0),
        "v2_preserves_reported_helpful_override": int(any(_as_int(r["artifact_sensitive_helpful_case"]) and _as_int(r["v2_frontier_override_triggered"]) for r in rows)),
        "artifact_sensitive_helpful_case_present": 1,
        "larger_real_model_pilot_justified": "no",
    }

    _write_csv(out_dir / "per_case_results.csv", rows)
    _write_csv(out_dir / "summary.csv", [summary])
    _write_csv(out_dir / "override_audit.csv", audits)
    (out_dir / "README.md").write_text(
        "# Direct Reserve Frontier Gate V2 Failure Slice Diagnostic\n\n"
        f"- Diagnostic type: `{summary['diagnostic_type']}`\n"
        "- `direct_reserve_frontier_gate_v2` is diagnostic-only and not canonical.\n"
        f"- Matched examples: {n}\n"
        f"- v1 accuracy: {summary['direct_reserve_frontier_gate_v1_accuracy']:.4f}\n"
        f"- v2 accuracy: {summary['direct_reserve_frontier_gate_v2_accuracy']:.4f}\n"
        f"- `external_l1_max` accuracy: {summary['external_l1_max_accuracy']:.4f}\n"
        f"- v2 overrides: {summary['v2_total_overrides']}\n"
        f"- v2 helpful overrides: {summary['v2_helpful_overrides']}\n"
        f"- v2 harmful overrides: {summary['v2_harmful_overrides']}\n\n"
        "The preserved reported-helpful override is artifact-sensitive because the earlier audit found it depends on output repair rather than a clean frontier-answer rescue. "
        "A larger real-model pilot is not justified yet, and the manuscript should not be changed.\n",
        encoding="utf-8",
    )
    (REPO_ROOT / "docs" / "DIRECT_RESERVE_FRONTIER_GATE_V2_STATUS.md").write_text(
        "# DIRECT_RESERVE_FRONTIER_GATE_V2_STATUS\n\n"
        f"- Output directory: `{out_dir.relative_to(REPO_ROOT)}`\n"
        "- Variant: `direct_reserve_frontier_gate_v2`\n"
        "- Status: diagnostic-only; not canonical.\n"
        f"- Matched examples: {n}\n"
        f"- `external_l1_max` accuracy: {summary['external_l1_max_accuracy']:.4f}\n"
        f"- `strict_f3` accuracy: {summary['strict_f3_accuracy']:.4f}\n"
        f"- v1 accuracy: {summary['direct_reserve_frontier_gate_v1_accuracy']:.4f}\n"
        f"- v2 accuracy: {summary['direct_reserve_frontier_gate_v2_accuracy']:.4f}\n"
        f"- v2 total overrides: {summary['v2_total_overrides']}\n"
        f"- v2 helpful overrides: {summary['v2_helpful_overrides']}\n"
        f"- v2 harmful overrides: {summary['v2_harmful_overrides']}\n"
        f"- v2 blocks harmful v1 overrides: {summary['v2_blocks_harmful_v1_overrides']}\n"
        f"- v2 preserves reported helpful override: {summary['v2_preserves_reported_helpful_override']}\n\n"
        "Interpretation: v2 improves the saved-trace reported surface metric by blocking both harmful v1 overrides, but the only preserved helpful override remains artifact-sensitive. "
        "Do not edit the manuscript or run a larger real-model pilot yet.\n",
        encoding="utf-8",
    )
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
