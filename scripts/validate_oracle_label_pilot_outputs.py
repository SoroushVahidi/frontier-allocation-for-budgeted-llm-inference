#!/usr/bin/env python3
"""Validate oracle-label pilot outputs and build a quality report.

Can run in dry-run mode to validate pilot config settings without label files.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _safe_float(x: Any) -> float | None:
    if x is None:
        return None
    if not _is_number(x):
        return None
    v = float(x)
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate oracle-label pilot outputs")
    p.add_argument("--pilot-config", default="configs/stop_vs_act_oracle_label_pilot_v1.json")
    p.add_argument("--labels-jsonl", default="")
    p.add_argument("--manifest-json", default="")
    p.add_argument("--quality-report-out", default="")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def _validate_pilot_config(cfg: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    required_top = [
        "pilot_name",
        "teacher",
        "pilot_grid",
        "required_row_fields",
        "quality_gates",
        "expected_outputs",
    ]
    for key in required_top:
        if key not in cfg:
            errs.append(f"Missing config key: {key}")

    teacher = cfg.get("teacher", {})
    if int(teacher.get("horizon", 0)) <= 0:
        errs.append("teacher.horizon must be > 0")
    if int(teacher.get("paired_rollouts_per_state", 0)) <= 0:
        errs.append("teacher.paired_rollouts_per_state must be > 0")

    grid = cfg.get("pilot_grid", {})
    if int(grid.get("target_states_total", 0)) < int(grid.get("min_states_total", 0)):
        errs.append("pilot_grid.target_states_total must be >= min_states_total")

    gates = cfg.get("quality_gates", {})
    for g in [
        "min_schema_valid_rate",
        "min_gap_consistency_rate",
        "min_label_sign_consistency_rate",
        "min_non_missing_core_rate",
        "min_paired_randomness_rate",
    ]:
        val = gates.get(g)
        if not _is_number(val) or float(val) < 0.0 or float(val) > 1.0:
            errs.append(f"quality_gates.{g} must be in [0,1]")

    return errs


def _rate(num: int, den: int) -> float:
    return float(num / den) if den > 0 else 0.0


def _sign_label_from_gap(gap: float) -> int:
    return 1 if gap > 0.0 else 0


def _validate_rows(rows: list[dict[str, Any]], cfg: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    required_fields = list(cfg.get("required_row_fields", []))
    gates = dict(cfg.get("quality_gates", {}))
    tol = float(gates.get("gap_consistency_tolerance", 1e-6))

    errors: list[str] = []
    n = len(rows)
    if n == 0:
        errors.append("No label rows found")

    schema_ok = 0
    core_non_missing_ok = 0
    gap_consistency_ok = 0
    sign_consistency_ok = 0
    paired_true = 0

    gaps: list[float] = []
    q_acts: list[float] = []
    q_stops: list[float] = []

    per_row_errors = 0

    for idx, row in enumerate(rows):
        row_good = True
        for f in required_fields:
            if f not in row:
                row_good = False
        if row_good:
            schema_ok += 1

        q_act = _safe_float(row.get("q_act"))
        q_stop = _safe_float(row.get("q_stop"))
        gap = _safe_float(row.get("oracle_action_gap"))
        label = row.get("oracle_label_act")

        core_ok = all(x is not None for x in [q_act, q_stop, gap]) and label in {0, 1}
        if core_ok:
            core_non_missing_ok += 1

        if isinstance(row.get("paired_randomness_used"), bool) and bool(row.get("paired_randomness_used")):
            paired_true += 1

        if core_ok and q_act is not None and q_stop is not None and gap is not None:
            if abs((q_act - q_stop) - gap) <= tol:
                gap_consistency_ok += 1
            else:
                row_good = False

            if int(label) == _sign_label_from_gap(gap):
                sign_consistency_ok += 1
            else:
                row_good = False

            gaps.append(gap)
            q_acts.append(q_act)
            q_stops.append(q_stop)

        if not row_good:
            per_row_errors += 1
            if per_row_errors <= 5:
                errors.append(f"Row {idx} failed one or more checks")

    summary = {
        "rows": n,
        "schema_valid_rate": _rate(schema_ok, n),
        "core_non_missing_rate": _rate(core_non_missing_ok, n),
        "gap_consistency_rate": _rate(gap_consistency_ok, n),
        "label_sign_consistency_rate": _rate(sign_consistency_ok, n),
        "paired_randomness_rate": _rate(paired_true, n),
        "oracle_label_positive_rate": _rate(sum(1 for r in rows if r.get("oracle_label_act") == 1), n),
        "oracle_action_gap_mean": float(sum(gaps) / max(1, len(gaps))),
        "oracle_action_gap_abs_mean": float(sum(abs(g) for g in gaps) / max(1, len(gaps))),
        "q_act_mean": float(sum(q_acts) / max(1, len(q_acts))),
        "q_stop_mean": float(sum(q_stops) / max(1, len(q_stops))),
    }

    min_rows = int(cfg.get("pilot_grid", {}).get("min_states_total", 0))
    quality_pass = {
        "row_count_gate": n >= min_rows,
        "schema_gate": summary["schema_valid_rate"] >= float(gates.get("min_schema_valid_rate", 1.0)),
        "core_non_missing_gate": summary["core_non_missing_rate"] >= float(gates.get("min_non_missing_core_rate", 1.0)),
        "gap_consistency_gate": summary["gap_consistency_rate"] >= float(gates.get("min_gap_consistency_rate", 1.0)),
        "label_sign_gate": summary["label_sign_consistency_rate"] >= float(gates.get("min_label_sign_consistency_rate", 1.0)),
        "paired_randomness_gate": summary["paired_randomness_rate"] >= float(gates.get("min_paired_randomness_rate", 1.0)),
    }
    quality_pass["all_gates_pass"] = all(bool(v) for v in quality_pass.values())

    return {"summary": summary, "quality_gates": quality_pass}, errors


def main() -> None:
    args = parse_args()
    cfg = _load_json(Path(args.pilot_config))

    config_errors = _validate_pilot_config(cfg)
    if config_errors:
        for e in config_errors:
            print(f"CONFIG_ERROR: {e}")
        raise SystemExit(1)

    if args.dry_run:
        out = {
            "pilot_name": cfg.get("pilot_name"),
            "status": cfg.get("status"),
            "teacher": cfg.get("teacher"),
            "pilot_grid": cfg.get("pilot_grid"),
            "required_row_fields": cfg.get("required_row_fields"),
            "quality_gates": cfg.get("quality_gates"),
            "message": "Dry-run success: pilot config is internally valid. No label files were checked.",
        }
        print(json.dumps(out, indent=2))
        return

    if not args.labels_jsonl:
        raise SystemExit("--labels-jsonl is required unless --dry-run is set")

    labels_path = Path(args.labels_jsonl)
    rows = _read_jsonl(labels_path)

    report, row_errors = _validate_rows(rows, cfg)
    report["pilot_name"] = cfg.get("pilot_name")
    report["labels_path"] = str(labels_path)
    if args.manifest_json:
        manifest = _load_json(Path(args.manifest_json))
        report["manifest"] = manifest
    report["row_errors_preview"] = row_errors

    out_path = Path(args.quality_report_out) if args.quality_report_out else labels_path.parent / "oracle_label_quality_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

    if not bool(report["quality_gates"]["all_gates_pass"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
