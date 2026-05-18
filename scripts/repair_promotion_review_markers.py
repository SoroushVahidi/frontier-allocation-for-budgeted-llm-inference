"""Repair missing explicit node-expansion-order markers in already-emitted collection records.

Reads a JSONL input (e.g. all_generated_records.jsonl), adds the explicit
__unavailable_not_recorded__ marker to promotion_review_record rows where
node_expansion_order is silently absent (empty list or None), then rewrites
the promotion_review_validation for each repaired row.

Does NOT overwrite the input file. Writes a new file at --output.

Usage:
    python3 scripts/repair_promotion_review_markers.py \\
        --input outputs/<run>/all_generated_records.jsonl \\
        --output outputs/<run>/all_generated_records_repaired.jsonl \\
        --metrics-json outputs/<run>/repair_metrics.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

from scripts.failure_case_logging_schema import (
    EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER,
    _is_explicit_marker,
    _is_present,
    validate_promotion_review_record,
)


def _needs_repair(node_expansion_order: Any) -> bool:
    """Return True when node_expansion_order is absent and NOT already an explicit marker."""
    if _is_explicit_marker(node_expansion_order):
        return False
    if _is_present(node_expansion_order):
        return False
    return True


def repair_record(row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return (repaired_row, was_changed). Never mutates input."""
    prr = row.get("promotion_review_record")
    if not isinstance(prr, dict):
        return row, False

    node_val = prr.get("node_expansion_order")
    if not _needs_repair(node_val):
        return row, False

    repaired_prr = dict(prr)
    repaired_prr["node_expansion_order"] = EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER
    new_validation = validate_promotion_review_record(repaired_prr)

    repaired_row = dict(row)
    repaired_row["promotion_review_record"] = repaired_prr
    repaired_row["promotion_review_validation"] = new_validation
    return repaired_row, True


def repair_jsonl(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    *,
    metrics_path: pathlib.Path | None = None,
) -> dict[str, Any]:
    if output_path.resolve() == input_path.resolve():
        raise ValueError(
            f"--output must differ from --input; refusing to overwrite {input_path}"
        )

    total = 0
    repaired = 0
    before_yes = before_partial = before_no = 0
    after_yes = after_partial = after_no = 0
    still_partial_reasons: list[str] = []

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open(encoding="utf-8") as fin, output_path.open("w", encoding="utf-8") as fout:
        for raw_line in fin:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            row = json.loads(raw_line)
            total += 1

            pv = row.get("promotion_review_validation") or {}
            before_status = pv.get("enough_for_promotion_review", "unknown")
            if before_status == "yes":
                before_yes += 1
            elif before_status == "partial":
                before_partial += 1
            else:
                before_no += 1

            repaired_row, changed = repair_record(row)
            if changed:
                repaired += 1

            after_pv = repaired_row.get("promotion_review_validation") or {}
            after_status = after_pv.get("enough_for_promotion_review", "unknown")
            if after_status == "yes":
                after_yes += 1
            elif after_status == "partial":
                after_partial += 1
                still_partial_reasons.extend(after_pv.get("missing_required_fields", []))
            else:
                after_no += 1

            fout.write(json.dumps(repaired_row, ensure_ascii=False) + "\n")

    metrics: dict[str, Any] = {
        "input": str(input_path),
        "output": str(output_path),
        "total_rows": total,
        "rows_repaired": repaired,
        "before": {"yes": before_yes, "partial": before_partial, "no": before_no},
        "after": {"yes": after_yes, "partial": after_partial, "no": after_no},
        "yes_rate_before": round(before_yes / total, 4) if total else 0.0,
        "yes_rate_after": round(after_yes / total, 4) if total else 0.0,
        "still_partial_reasons": sorted(set(still_partial_reasons)),
    }

    if metrics_path:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return metrics


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--metrics-json", type=pathlib.Path, default=None)
    parser.add_argument("--overwrite", action="store_true", help="Allow output == input (unsafe).")
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if not args.overwrite and args.output.resolve() == args.input.resolve():
        print("ERROR: --output must differ from --input. Use --overwrite to bypass (not recommended).", file=sys.stderr)
        sys.exit(1)

    metrics = repair_jsonl(args.input, args.output, metrics_path=args.metrics_json)

    print(f"total_rows={metrics['total_rows']}")
    print(f"rows_repaired={metrics['rows_repaired']}")
    print(f"before: yes={metrics['before']['yes']} partial={metrics['before']['partial']} no={metrics['before']['no']}")
    print(f"after:  yes={metrics['after']['yes']}  partial={metrics['after']['partial']}  no={metrics['after']['no']}")
    print(f"yes_rate_before={metrics['yes_rate_before']:.1%}  yes_rate_after={metrics['yes_rate_after']:.1%}")
    if metrics["still_partial_reasons"]:
        print(f"still_partial_reasons: {metrics['still_partial_reasons']}")
    if args.metrics_json:
        print(f"metrics written to {args.metrics_json}")
    print(f"repaired output written to {args.output}")


if __name__ == "__main__":
    main()
