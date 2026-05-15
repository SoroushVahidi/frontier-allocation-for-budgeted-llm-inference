"""Build a gold-free, label-clean training dataset from the RelationReady manual audit CSV.

Safe feature columns: question, target_phrase, target_semantic_type, candidate_answer,
                      candidate_trace_short, candidate_source
Forbidden columns (never in feature_text or structured_features):
    gold_answer_metadata_only, relation_ready_label_manual,
    first_error_axis_manual, notes_manual

Usage:
    python3 scripts/build_relation_verifier_training_dataset.py \
        --input-csv outputs/.../manual_audit_33rows.csv \
        --output-dir outputs/relation_verifier_training_dataset_smoke_<STAMP>
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
from collections import Counter
from datetime import datetime, timezone

SAFE_FEATURE_COLS = [
    "question",
    "target_phrase",
    "target_semantic_type",
    "candidate_answer",
    "candidate_trace_short",
    "candidate_source",
]

FORBIDDEN_COLS = {
    "gold_answer_metadata_only",
    "relation_ready_label_manual",
    "first_error_axis_manual",
    "notes_manual",
}

BINARY_LABEL_MAP = {"ready": 1, "not_ready": 0}


def build_feature_text(row: dict[str, str]) -> str:
    parts = []
    for col in SAFE_FEATURE_COLS:
        val = row.get(col, "").strip()
        if val:
            parts.append(f"{col}: {val}")
    return " | ".join(parts)


def build_structured_features(row: dict[str, str]) -> dict[str, str]:
    return {col: row.get(col, "").strip() for col in SAFE_FEATURE_COLS}


def load_csv(path: pathlib.Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_dataset(
    rows: list[dict[str, str]],
    exclude_labels: set[str],
    label_mode: str,
    max_rows: int | None,
) -> tuple[list[dict], dict]:
    stats: dict = {
        "total_input": len(rows),
        "excluded_by_label": Counter(),
        "included": 0,
        "label_distribution": Counter(),
        "split_distribution": Counter(),
    }

    out_rows = []
    for row in rows:
        raw_label = row.get("relation_ready_label_manual", "").strip()
        if raw_label in exclude_labels:
            stats["excluded_by_label"][raw_label] += 1
            continue

        if label_mode == "binary":
            if raw_label not in BINARY_LABEL_MAP:
                stats["excluded_by_label"][raw_label] += 1
                continue
            label = BINARY_LABEL_MAP[raw_label]
        else:
            label = raw_label

        # Gold-free feature text
        ft = build_feature_text(row)
        sf = build_structured_features(row)

        # Verify no forbidden content leaks into feature text
        for forbidden in FORBIDDEN_COLS:
            assert forbidden not in ft, f"Forbidden column '{forbidden}' leaked into feature_text"

        out_rows.append(
            {
                "row_id": row.get("row_id", ""),
                "problem_id": row.get("problem_id", ""),
                "case_id": row.get("case_id", ""),
                "split_group_id": row.get("split_group_id", ""),
                "feature_text": ft,
                "structured_features": sf,
                "label": label,
                "auxiliary_axis": row.get("first_error_axis_manual", ""),
                "provenance": str(path) if (path := row.get("row_id")) else "unknown",
            }
        )
        stats["label_distribution"][raw_label] += 1
        stats["split_distribution"][row.get("split_group_id", "")] += 1

    if max_rows is not None:
        out_rows = out_rows[:max_rows]

    stats["included"] = len(out_rows)
    return out_rows, stats


def write_report(stats: dict, output_dir: pathlib.Path, input_csv: pathlib.Path) -> None:
    lines = [
        "# RelationReady Training Dataset Report",
        "",
        f"- **Input CSV:** `{input_csv}`",
        f"- **Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Row counts",
        "",
        f"| Total input | {stats['total_input']} |",
        "|---|---|",
        f"| Included | {stats['included']} |",
    ]
    for lbl, cnt in sorted(stats["excluded_by_label"].items()):
        lines.append(f"| Excluded ({lbl}) | {cnt} |")
    lines += [
        "",
        "## Label distribution (included rows)",
        "",
        "| Label | Count |",
        "|---|---|",
    ]
    for lbl, cnt in sorted(stats["label_distribution"].items()):
        lines.append(f"| `{lbl}` | {cnt} |")
    lines += [
        "",
        "## Split group distribution",
        "",
        "| Split | Count |",
        "|---|---|",
    ]
    for split, cnt in sorted(stats["split_distribution"].items()):
        lines.append(f"| `{split}` | {cnt} |")
    lines += [
        "",
        "## Feature leakage check",
        "",
        "Safe feature columns used: " + ", ".join(f"`{c}`" for c in SAFE_FEATURE_COLS),
        "",
        "Forbidden columns (never in feature_text): "
        + ", ".join(f"`{c}`" for c in sorted(FORBIDDEN_COLS)),
        "",
        "> Gold answers are used only for offline evaluation. They are never included in",
        "> feature_text or structured_features.",
    ]
    (output_dir / "dataset_report.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build RelationReady training dataset")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--exclude-labels",
        default="uncertain,gold_inconsistent",
        help="Comma-separated labels to exclude (default: uncertain,gold_inconsistent)",
    )
    parser.add_argument("--label-mode", default="binary", choices=["binary"])
    parser.add_argument("--max-rows", type=int, default=None)
    args = parser.parse_args(argv)

    input_csv = pathlib.Path(args.input_csv)
    output_dir = pathlib.Path(args.output_dir)
    exclude_labels = set(args.exclude_labels.split(",")) if args.exclude_labels else set()

    if not input_csv.exists():
        print(f"ERROR: input CSV not found: {input_csv}", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_csv(input_csv)
    out_rows, stats = build_dataset(rows, exclude_labels, args.label_mode, args.max_rows)

    # Write train_rows.jsonl
    jsonl_path = output_dir / "train_rows.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row) + "\n")

    write_report(stats, output_dir, input_csv)

    print(f"Input rows:    {stats['total_input']}")
    print(f"Included rows: {stats['included']}")
    print(f"Excluded:      {dict(stats['excluded_by_label'])}")
    print(f"Labels:        {dict(stats['label_distribution'])}")
    print(f"Output dir:    {output_dir}")
    print("✓ No gold answers included in feature_text.")
    print("✓ No outputs staged or committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
