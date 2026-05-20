#!/usr/bin/env python3
"""Export a compact CSV for manual RelationReady seed auditing."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TRACE_SHORT_LIMIT = 800
OUTPUT_COLUMNS = [
    "row_id",
    "problem_id",
    "case_id",
    "split_group_id",
    "candidate_source",
    "question",
    "target_phrase",
    "target_semantic_type",
    "candidate_answer",
    "candidate_trace_short",
    "gold_answer_metadata_only",
    "relation_ready_label_manual",
    "first_error_axis_manual",
    "notes_manual",
]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _truncate(text: Any, limit: int = TRACE_SHORT_LIMIT) -> str:
    value = _stringify(text).strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def load_seed_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected object row in {path}, got {type(payload).__name__}")
            rows.append(payload)
    return rows


def export_audit_sheet(input_jsonl: Path, output_csv: Path) -> int:
    rows = load_seed_rows(input_jsonl)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
            gold_answer = row.get("gold_answer", row.get("gold_answer_metadata_only", ""))
            output_row = {
                "row_id": _stringify(row.get("row_id")),
                "problem_id": _stringify(row.get("problem_id")),
                "case_id": _stringify(row.get("case_id")),
                "split_group_id": _stringify(row.get("split_group_id")),
                "candidate_source": _stringify(row.get("candidate_source")),
                "question": _stringify(row.get("question")),
                "target_phrase": _stringify(row.get("target_phrase")),
                "target_semantic_type": _stringify(row.get("target_semantic_type")),
                "candidate_answer": _stringify(row.get("candidate_answer")),
                "candidate_trace_short": _truncate(row.get("candidate_trace", "")),
                "gold_answer_metadata_only": _stringify(gold_answer),
                "relation_ready_label_manual": "",
                "first_error_axis_manual": "",
                "notes_manual": "",
            }
            if provenance.get("source_path") and not output_row["notes_manual"]:
                output_row["notes_manual"] = f"source_path={provenance['source_path']}"
            writer.writerow(output_row)
    return len(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return export_audit_sheet(args.input_jsonl, args.output_csv)


if __name__ == "__main__":
    main()
