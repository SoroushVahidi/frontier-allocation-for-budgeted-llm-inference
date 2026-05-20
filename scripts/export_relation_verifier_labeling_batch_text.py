"""Export copy-paste-friendly Markdown labeling batches from a manual_audit_batch.csv.

Gold answers are excluded by default. Use --include-gold-metadata to include them
as clearly-marked metadata (never in feature text).

Usage (standard sequential batch):
    python3 scripts/export_relation_verifier_labeling_batch_text.py \
        --input-csv outputs/.../manual_audit_batch.csv \
        --output-dir outputs/.../labeling_batches \
        --priority high \
        --start-index 0 \
        --batch-size 10

Usage (targeted likely-ready selection — ranks unlabeled rows by readiness signals):
    python3 scripts/export_relation_verifier_labeling_batch_text.py \
        --input-csv outputs/.../manual_audit_batch.csv \
        --output-dir outputs/.../labeling_batches \
        --priority all \
        --selection likely_ready \
        --start-index 0 \
        --batch-size 30
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


def is_unlabeled(row: dict[str, str]) -> bool:
    return not row.get("relation_ready_label_manual", "").strip()


def score_likely_ready(row: dict[str, str]) -> int:
    """Score a row by gold-free signals that correlate with a 'ready' label.

    Uses only trace_quality_flags and candidate_trace_short — no gold metadata.
    Higher score = more likely ready.
    """
    flags = row.get("trace_quality_flags", "").lower()
    trace = row.get("candidate_trace_short", "").strip()

    score = 0

    # Strong positive: executable code in the trace
    if "has_code" in flags:
        score += 3
    # Moderate positive: arithmetic present
    if "has_arithmetic" in flags:
        score += 2
    # Mild positive: answer is present (completeness signal)
    if "answer_present" in flags:
        score += 1

    # Multi-line trace suggests multi-step reasoning
    if "\n" in trace:
        score += 2

    # Penalty: opaque flag means the trace is hidden
    if "opaque" in flags:
        score -= 5

    # Penalty: trace is literally missing
    if trace.lower() == "model_step_missing":
        score -= 10

    # Penalty: trace is a JSON-final-only blob (no reasoning shown)
    stripped = trace.lstrip()
    if stripped.startswith('{"action": "final"') or stripped.startswith('{"action":"final"'):
        score -= 4

    return score


def select_likely_ready(
    rows: list[dict[str, str]],
    start_index: int,
    batch_size: int,
) -> tuple[list[dict[str, str]], int]:
    """Filter to unlabeled rows, score by readiness signals, return ranked slice.

    Returns (batch_rows, total_unlabeled_count).
    """
    unlabeled = [r for r in rows if is_unlabeled(r)]
    scored = sorted(unlabeled, key=score_likely_ready, reverse=True)
    batch = scored[start_index : start_index + batch_size]
    return batch, len(unlabeled)


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
    selection: str = "default",
) -> pathlib.Path:
    end_index = start_index + len(batch_rows) - 1
    sel_tag = "likelyready" if selection == "likely_ready" else priority
    filename = f"labeling_batch_{sel_tag}_{start_index}_{end_index}.md"
    out_path = output_dir / filename

    sel_note = " (ranked by likely-ready score)" if selection == "likely_ready" else ""
    header = [
        f"# RelationReady Labeling Batch",
        f"",
        f"- **Priority:** `{priority}`",
        f"- **Selection:** `{selection}`{sel_note}",
        f"- **Rows:** {start_index} – {end_index} (indices within selection)",
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
    selection: str = "default",
) -> pathlib.Path:
    lines = [
        f"# Labeling Batch Export Report",
        f"",
        f"- **Input CSV:** `{input_csv}`",
        f"- **Priority filter:** `{priority}`",
        f"- **Selection mode:** `{selection}`",
        f"- **Total rows in selection pool:** {total_in_priority}",
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
    parser.add_argument(
        "--selection",
        default="default",
        choices=["default", "likely_ready"],
        help=(
            "default: sequential slice within priority group. "
            "likely_ready: rank unlabeled rows by readiness signals, export top-N."
        ),
    )
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

    if args.selection == "likely_ready":
        # Filter by priority first, then rank unlabeled rows by readiness score
        priority_rows = filter_by_priority(rows, args.priority)
        batch, total_pool = select_likely_ready(priority_rows, args.start_index, args.batch_size)
        total_in_priority = total_pool
    else:
        filtered = filter_by_priority(rows, args.priority)
        total_in_priority = len(filtered)
        batch = filtered[args.start_index : args.start_index + args.batch_size]

    if not batch and args.start_index > 0:
        print(
            f"ERROR: start-index {args.start_index} exceeds available rows ({total_in_priority})",
            file=sys.stderr,
        )
        return 1

    if not batch:
        print(
            f"ERROR: no rows found for priority='{args.priority}' selection='{args.selection}'",
            file=sys.stderr,
        )
        return 1

    batch_file = write_labeling_batch(
        batch_rows=batch,
        start_index=args.start_index,
        priority=args.priority,
        output_dir=output_dir,
        max_trace_chars=args.max_trace_chars,
        include_gold=args.include_gold_metadata,
        selection=args.selection,
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
        selection=args.selection,
    )

    pool_label = "unlabeled rows in pool" if args.selection == "likely_ready" else f"rows in priority group '{args.priority}'"
    print(f"Selection '{args.selection}': {total_in_priority} {pool_label}")
    print(f"Exported rows {args.start_index}–{args.start_index + len(batch) - 1} ({len(batch)} rows)")
    print(f"Gold metadata: {'included (METADATA ONLY)' if args.include_gold_metadata else 'excluded'}")
    print(f"Batch file: {batch_file}")
    print(f"Report: {report_path}")
    print("✓ No APIs called.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
