"""Export copy-paste-friendly Markdown labeling batches from a manual_audit_batch.csv.

Gold answers are excluded by default. Use --include-gold-metadata to include them
as clearly-marked metadata (never in feature text).

Usage:
    python3 scripts/export_relation_verifier_labeling_batch_text.py \
        --input-csv outputs/.../manual_audit_batch.csv \
        --output-dir outputs/.../labeling_batches \
        --priority high \
        --start-index 0 \
        --batch-size 10
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys
from datetime import datetime, timezone

LABEL_CHOICES = ["ready", "not_ready", "uncertain", "gold_inconsistent"]
AXIS_CHOICES = [
    "source_fact_missing",
    "unit_scale_error",
    "process_state_error",
    "relation_type_error",
    "arithmetic_error",
    "other",
    "",
]


def load_csv(path: pathlib.Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def enrich_with_pool_jsonl(rows: list[dict], csv_path: pathlib.Path) -> list[dict]:
    """If suggested_priority is absent from the CSV, load it from pool_rows.jsonl
    in the same directory (written by the pool builder)."""
    import json

    if rows and rows[0].get("suggested_priority", "") != "":
        return rows
    pool_jsonl = csv_path.parent / "pool_rows.jsonl"
    if not pool_jsonl.exists():
        return rows
    priority_map: dict[str, str] = {}
    with open(pool_jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                rid = r.get("row_id", "")
                if rid:
                    priority_map[rid] = r.get("suggested_priority", "normal")
    for row in rows:
        if not row.get("suggested_priority", ""):
            row["suggested_priority"] = priority_map.get(row.get("row_id", ""), "normal")
    return rows


def filter_by_priority(rows: list[dict], priority: str) -> list[dict]:
    if priority == "all":
        return rows
    return [r for r in rows if r.get("suggested_priority", "").strip() == priority]


def truncate_trace(trace: str, max_chars: int) -> str:
    if len(trace) <= max_chars:
        return trace
    return trace[:max_chars] + f"\n… [truncated at {max_chars} chars]"


def format_row(
    seq_num: int,
    row: dict[str, str],
    max_trace_chars: int,
    include_gold: bool,
) -> str:
    lines = [
        f"---",
        f"## Row {seq_num}",
        f"",
        f"**row_id:** `{row.get('row_id', '')}`  ",
        f"**problem_id:** `{row.get('problem_id', '')}`  ",
        f"**case_id:** `{row.get('case_id', '')}`  ",
        f"**split_group_id:** `{row.get('split_group_id', '') or '(none)'}`  ",
        f"**candidate_source:** `{row.get('candidate_source', '')}`  ",
        f"**source_artifact:** `{row.get('source_artifact', '')}`  ",
        f"**suggested_priority:** `{row.get('suggested_priority', '')}`  ",
        f"**trace_quality_flags:** `{row.get('trace_quality_flags', '')}`  ",
        f"",
        f"### Question",
        f"",
        row.get("question", "").strip(),
        f"",
    ]

    target_phrase = row.get("target_phrase", "").strip()
    target_type = row.get("target_semantic_type", "").strip()
    if target_phrase:
        lines += [f"**target_phrase:** {target_phrase}  "]
    if target_type:
        lines += [f"**target_semantic_type:** {target_type}  "]
    if target_phrase or target_type:
        lines.append("")

    lines += [
        f"### Candidate answer",
        f"",
        f"`{row.get('candidate_answer', '').strip()}`",
        f"",
        f"### Candidate trace",
        f"",
        truncate_trace(row.get("candidate_trace_short", "").strip(), max_trace_chars),
        f"",
    ]

    if include_gold:
        gold = row.get("gold_answer_metadata_only", "").strip()
        lines += [
            f"### Gold answer (METADATA ONLY — do not use as feature)",
            f"",
            f"`{gold if gold else '(not provided)'}`",
            f"",
        ]

    lines += [
        f"### Labels to fill in",
        f"",
        f"**relation_ready_label_manual:** _(fill: {' | '.join(LABEL_CHOICES)})_  ",
        f"**first_error_axis_manual:** _(fill: {' | '.join(a for a in AXIS_CHOICES if a)})_  ",
        f"**notes_manual:** _(optional free text)_  ",
        f"",
    ]
    return "\n".join(lines)


def write_labeling_batch(
    batch_rows: list[dict],
    start_index: int,
    priority: str,
    output_dir: pathlib.Path,
    max_trace_chars: int,
    include_gold: bool,
) -> pathlib.Path:
    end_index = start_index + len(batch_rows) - 1
    filename = f"labeling_batch_{priority}_{start_index}_{end_index}.md"
    out_path = output_dir / filename

    header = [
        f"# RelationReady Labeling Batch",
        f"",
        f"- **Priority:** `{priority}`",
        f"- **Rows:** {start_index} – {end_index} (indices within priority group)",
        f"- **Count:** {len(batch_rows)}",
        f"- **Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"- **Gold metadata included:** {'YES — marked METADATA ONLY' if include_gold else 'NO'}",
        f"",
        f"## Instructions",
        f"",
        f"For each row below, fill in:",
        f"- `relation_ready_label_manual`: one of `{' | '.join(LABEL_CHOICES)}`",
        f"- `first_error_axis_manual`: one of `{' | '.join(a for a in AXIS_CHOICES if a)}` (leave blank if ready)",
        f"- `notes_manual`: optional short explanation",
        f"",
        f"**Definition:** A candidate is `ready` if its trace and answer correctly",
        f"establish the target relation asked in the question — i.e., the candidate",
        f"answer is correct AND the reasoning trace is sound and complete.",
        f"",
    ]

    row_blocks = []
    for i, row in enumerate(batch_rows):
        row_blocks.append(format_row(start_index + i, row, max_trace_chars, include_gold))

    footer = [
        f"",
        f"---",
        f"_End of batch ({len(batch_rows)} rows). Return labels as a CSV or fill-in above._",
    ]

    content = "\n".join(header) + "\n" + "\n".join(row_blocks) + "\n".join(footer)
    out_path.write_text(content, encoding="utf-8")
    return out_path


def write_batch_report(
    output_dir: pathlib.Path,
    input_csv: pathlib.Path,
    priority: str,
    total_in_priority: int,
    start_index: int,
    batch_size: int,
    exported: int,
    include_gold: bool,
    batch_file: pathlib.Path,
) -> pathlib.Path:
    lines = [
        f"# Labeling Batch Export Report",
        f"",
        f"- **Input CSV:** `{input_csv}`",
        f"- **Priority filter:** `{priority}`",
        f"- **Total rows in priority group:** {total_in_priority}",
        f"- **Start index:** {start_index}",
        f"- **Batch size requested:** {batch_size}",
        f"- **Rows exported:** {exported}",
        f"- **Gold metadata included:** {'YES — labeled METADATA ONLY' if include_gold else 'NO (default)'}",
        f"- **Batch file:** `{batch_file.name}`",
        f"- **Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"",
        f"## Safety",
        f"",
        f"> Gold answers are {'included as clearly-labeled metadata only' if include_gold else 'excluded from this batch'}.",
        f"> Manual label fields (`relation_ready_label_manual`, etc.) are blank placeholders.",
        f"> No API calls were made.",
    ]
    report_path = output_dir / "labeling_batch_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export RelationReady labeling batch")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--priority", default="high", choices=["high", "medium", "normal", "all"])
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--include-gold-metadata", action="store_true", default=False)
    parser.add_argument("--max-trace-chars", type=int, default=1200)
    args = parser.parse_args(argv)

    input_csv = pathlib.Path(args.input_csv)
    output_dir = pathlib.Path(args.output_dir)

    if not input_csv.exists():
        print(f"ERROR: input CSV not found: {input_csv}", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_csv(input_csv)
    rows = enrich_with_pool_jsonl(rows, input_csv)
    filtered = filter_by_priority(rows, args.priority)
    total_in_priority = len(filtered)

    if args.start_index >= total_in_priority:
        print(
            f"ERROR: start-index {args.start_index} >= total rows in priority group {total_in_priority}",
            file=sys.stderr,
        )
        return 1

    batch = filtered[args.start_index : args.start_index + args.batch_size]

    batch_file = write_labeling_batch(
        batch_rows=batch,
        start_index=args.start_index,
        priority=args.priority,
        output_dir=output_dir,
        max_trace_chars=args.max_trace_chars,
        include_gold=args.include_gold_metadata,
    )

    report_path = write_batch_report(
        output_dir=output_dir,
        input_csv=input_csv,
        priority=args.priority,
        total_in_priority=total_in_priority,
        start_index=args.start_index,
        batch_size=args.batch_size,
        exported=len(batch),
        include_gold=args.include_gold_metadata,
        batch_file=batch_file,
    )

    print(f"Priority group '{args.priority}': {total_in_priority} rows total")
    print(f"Exported rows {args.start_index}–{args.start_index + len(batch) - 1} ({len(batch)} rows)")
    print(f"Gold metadata: {'included (METADATA ONLY)' if args.include_gold_metadata else 'excluded'}")
    print(f"Batch file: {batch_file}")
    print(f"Report: {report_path}")
    print("✓ No APIs called.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
