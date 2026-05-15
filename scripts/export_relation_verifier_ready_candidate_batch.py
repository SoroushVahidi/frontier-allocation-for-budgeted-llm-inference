"""Export a targeted batch of likely-ready RelationReady candidates for manual labeling.

Scans multiple local JSONL artifacts (failure records, unified evidence, seed rows,
candidate_nodes files) for non-opaque, reasoning-bearing traces and exports a batch
of candidates not already present in any existing labeled CSV.

Gold answers are excluded from the output by default.  Use --include-gold-metadata
to include them as clearly-marked metadata columns (never in feature_text).

Usage:
    python3 scripts/export_relation_verifier_ready_candidate_batch.py \
        --input-jsonl outputs/.../full_failure_records.jsonl \
        --input-jsonl outputs/.../unified_candidate_trace_enriched.jsonl \
        --existing-labels-csv outputs/.../manual_audit_33rows.csv \
        --existing-labels-csv outputs/.../manual_audit_batch.csv \
        --output-dir outputs/relation_verifier_ready_candidate_batch_<STAMP> \
        --batch-size 50
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Iterator

TRACE_SHORT_MAX = 300

AUDIT_CSV_COLUMNS = [
    "row_id",
    "problem_id",
    "case_id",
    "candidate_source",
    "question",
    "target_phrase",
    "candidate_answer",
    "candidate_trace_short",
    "source_artifact",
    "trace_quality_flags",
    "gold_answer_metadata_only",
    "relation_ready_label_manual",
    "first_error_axis_manual",
    "notes_manual",
]


# ---------------------------------------------------------------------------
# Shared helpers (mirrors build_relation_verifier_training_pool logic exactly
# so row_ids are consistent across scripts)
# ---------------------------------------------------------------------------

def _content_hash(question: str, candidate_answer: str, trace_short: str) -> str:
    key = f"{question.strip()}|{str(candidate_answer).strip()}|{trace_short[:80]}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _make_row_id(question: str, candidate_answer: str, trace_short: str) -> str:
    return "rrpool_" + _content_hash(question, candidate_answer, trace_short)


def _shorten_trace(trace_raw: object) -> str:
    if trace_raw is None:
        return ""
    if isinstance(trace_raw, dict):
        for key in ("reasoning_text", "step", "code", "trace_text"):
            val = trace_raw.get(key, "")
            if val and str(val).strip():
                return str(val).strip()[:TRACE_SHORT_MAX]
        return json.dumps(trace_raw)[:TRACE_SHORT_MAX]
    if isinstance(trace_raw, str):
        try:
            parsed = json.loads(trace_raw)
            return _shorten_trace(parsed)
        except (json.JSONDecodeError, ValueError):
            return trace_raw.strip()[:TRACE_SHORT_MAX]
    return str(trace_raw)[:TRACE_SHORT_MAX]


def _trace_quality_flags(trace_short: str, candidate_answer: str) -> str:
    flags = []
    t = trace_short.lower()
    has_code = any(kw in t for kw in ("print(", "answer =", "= answer", "def ", "for "))
    has_arithmetic = bool(re.search(r"\d[\s]*[\+\-\*\/][\s]*\d", t))
    is_opaque = (
        not trace_short.strip()
        or (len(trace_short.strip()) < 20 and not has_arithmetic)
        or ("final" in t and "step" not in t and not has_arithmetic and not has_code)
    )
    if has_code:
        flags.append("has_code")
    if has_arithmetic:
        flags.append("has_arithmetic")
    if is_opaque:
        flags.append("opaque")
    if candidate_answer and str(candidate_answer).strip():
        flags.append("answer_present")
    return "|".join(flags) if flags else "none"


def _readiness_score(flags: str, trace_short: str) -> int:
    """Higher = more likely ready.  Used for batch ordering only."""
    score = 0
    if "has_code" in flags:
        score += 4
    if "has_arithmetic" in flags:
        score += 3
    if "opaque" not in flags:
        score += 2
    if len(trace_short.strip()) > 100:
        score += 1
    return score


# ---------------------------------------------------------------------------
# Source-specific loaders
# ---------------------------------------------------------------------------

def _detect_schema(row: dict) -> str:
    keys = set(row.keys())
    if "candidate_nodes" in keys:
        return "candidate_nodes"
    if "all_candidate_answers" in keys and "all_candidate_traces" in keys:
        return "failure_records"
    if "candidate_trace" in keys and "candidate_answer" in keys:
        return "seed_rows"
    if "candidate_trace_short" in keys and "candidate_answer" in keys:
        return "pool_rows"
    return "unknown"


def _load_candidate_nodes(rows: list[dict], source_artifact: str) -> Iterator[dict]:
    """Handle unified_candidate_trace_enriched.jsonl and similar files with
    candidate_nodes lists where each node has trace_text / final_answer."""
    for row in rows:
        q = (row.get("problem_statement") or row.get("question") or "").strip()
        if not q:
            continue
        case_id = row.get("case_id", "")
        gold_meta = str(row.get("gold_answer_metadata_only", "") or
                        row.get("gold_answer", "") or "")
        nodes = row.get("candidate_nodes") or []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            ca = str(node.get("final_answer") or node.get("normalized_answer") or "").strip()
            if not ca:
                continue
            trace_raw = (node.get("trace_text") or node.get("step_text") or
                         node.get("reasoning_trace") or "")
            trace_short = _shorten_trace(trace_raw)
            row_id = _make_row_id(q, ca, trace_short)
            flags = _trace_quality_flags(trace_short, ca)
            yield {
                "row_id": row_id,
                "problem_id": case_id,
                "case_id": case_id,
                "candidate_source": node.get("source_family", node.get("candidate_id", "unknown")),
                "question": q,
                "target_phrase": "",
                "candidate_answer": ca,
                "candidate_trace_short": trace_short,
                "source_artifact": source_artifact,
                "trace_quality_flags": flags,
                "gold_answer_metadata_only": gold_meta,
                "relation_ready_label_manual": "",
                "first_error_axis_manual": "",
                "notes_manual": "",
            }


def _load_failure_records(rows: list[dict], source_artifact: str) -> Iterator[dict]:
    for row in rows:
        q = row.get("question", "").strip()
        if not q:
            continue
        gold_meta = str(row.get("gold_answer_metadata_only", ""))
        case_id = row.get("case_id", "")
        answers = row.get("all_candidate_answers") or []
        traces = row.get("all_candidate_traces") or []
        while len(traces) < len(answers):
            traces.append("")
        for i, (ca, trace_raw) in enumerate(zip(answers, traces)):
            ca = str(ca).strip()
            trace_short = _shorten_trace(trace_raw)
            row_id = _make_row_id(q, ca, trace_short)
            flags = _trace_quality_flags(trace_short, ca)
            yield {
                "row_id": row_id,
                "problem_id": case_id,
                "case_id": case_id,
                "candidate_source": f"cohere_run_cand_{i}",
                "question": q,
                "target_phrase": "",
                "candidate_answer": ca,
                "candidate_trace_short": trace_short,
                "source_artifact": source_artifact,
                "trace_quality_flags": flags,
                "gold_answer_metadata_only": gold_meta,
                "relation_ready_label_manual": "",
                "first_error_axis_manual": "",
                "notes_manual": "",
            }


def _load_seed_rows(rows: list[dict], source_artifact: str) -> Iterator[dict]:
    for row in rows:
        q = (row.get("question", "") or "").strip()
        ca = str(row.get("candidate_answer", "")).strip()
        if not q or not ca:
            continue
        trace_raw = row.get("candidate_trace", "") or ""
        trace_short = _shorten_trace(trace_raw)
        row_id = row.get("row_id") or _make_row_id(q, ca, trace_short)
        flags = _trace_quality_flags(trace_short, ca)
        yield {
            "row_id": row_id,
            "problem_id": row.get("problem_id", row.get("case_id", "")),
            "case_id": row.get("case_id", ""),
            "candidate_source": row.get("candidate_source", ""),
            "question": q,
            "target_phrase": row.get("target_phrase", ""),
            "candidate_answer": ca,
            "candidate_trace_short": trace_short,
            "source_artifact": source_artifact,
            "trace_quality_flags": flags,
            "gold_answer_metadata_only": "",
            "relation_ready_label_manual": "",
            "first_error_axis_manual": "",
            "notes_manual": "",
        }


def _load_pool_rows(rows: list[dict], source_artifact: str) -> Iterator[dict]:
    for row in rows:
        q = (row.get("question", "") or "").strip()
        ca = str(row.get("candidate_answer", "")).strip()
        if not q or not ca:
            continue
        trace_short = (row.get("candidate_trace_short") or "")[:TRACE_SHORT_MAX]
        row_id = row.get("row_id") or _make_row_id(q, ca, trace_short)
        flags = row.get("trace_quality_flags") or _trace_quality_flags(trace_short, ca)
        yield {
            "row_id": row_id,
            "problem_id": row.get("problem_id", row.get("case_id", "")),
            "case_id": row.get("case_id", ""),
            "candidate_source": row.get("candidate_source", ""),
            "question": q,
            "target_phrase": row.get("target_phrase", ""),
            "candidate_answer": ca,
            "candidate_trace_short": trace_short,
            "source_artifact": source_artifact,
            "trace_quality_flags": flags,
            "gold_answer_metadata_only": row.get("gold_answer_metadata_only", ""),
            "relation_ready_label_manual": "",
            "first_error_axis_manual": "",
            "notes_manual": "",
        }


def iter_source(path: pathlib.Path, raw_rows: list[dict]) -> Iterator[dict]:
    if not raw_rows:
        return
    schema = _detect_schema(raw_rows[0])
    artifact = str(path)
    if schema == "candidate_nodes":
        yield from _load_candidate_nodes(raw_rows, artifact)
    elif schema == "failure_records":
        yield from _load_failure_records(raw_rows, artifact)
    elif schema == "seed_rows":
        yield from _load_seed_rows(raw_rows, artifact)
    elif schema == "pool_rows":
        yield from _load_pool_rows(raw_rows, artifact)
    else:
        print(f"  [warn] unrecognised schema for {path.name}, skipping", file=sys.stderr)


# ---------------------------------------------------------------------------
# Exclusion list
# ---------------------------------------------------------------------------

def load_labeled_ids(csv_paths: list[pathlib.Path]) -> set[str]:
    labeled: set[str] = set()
    for p in csv_paths:
        if not p.exists():
            print(f"  [warn] labels CSV not found: {p}", file=sys.stderr)
            continue
        with open(p, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                labeled.add(row["row_id"])
    return labeled


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _write_batch_csv(
    rows: list[dict],
    out_path: pathlib.Path,
    include_gold: bool,
) -> None:
    cols = [c for c in AUDIT_CSV_COLUMNS
            if include_gold or c != "gold_answer_metadata_only"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_batch_md(
    rows: list[dict],
    out_path: pathlib.Path,
    include_gold: bool,
    stamp: str,
) -> None:
    lines = [
        "# RelationReady — Ready-Candidate Labeling Batch",
        "",
        f"Generated: {stamp}",
        f"Rows: {len(rows)}",
        "",
        "**Labeling convention:** A row is `ready` only if the trace AND answer",
        "together establish the target relation through visible reasoning steps.",
        "A final answer with no reasoning steps is `not_ready`.",
        "",
        "Label choices: `ready` | `not_ready` | `uncertain` | `gold_inconsistent`",
        "Axis choices: `source_fact_missing` | `unit_scale_error` | `process_state_error`",
        "             `relation_type_error` | `arithmetic_error` | `other`",
        "",
        "---",
        "",
    ]
    for i, row in enumerate(rows, 1):
        lines += [
            f"## Row {i} — `{row['row_id']}`",
            "",
            f"**Source:** `{row['candidate_source']}` | **Case:** `{row['case_id']}`",
            f"**Flags:** `{row['trace_quality_flags']}`",
            "",
            f"**Question:**",
            f"> {row['question']}",
            "",
            f"**Candidate answer:** `{row['candidate_answer']}`",
            "",
            "**Trace:**",
            "```",
            row["candidate_trace_short"] or "(empty)",
            "```",
        ]
        if include_gold and row.get("gold_answer_metadata_only"):
            lines += [
                "",
                f"*(gold metadata — not a feature)*: `{row['gold_answer_metadata_only']}`",
            ]
        lines += [
            "",
            "**Label:** ______  **Axis:** ______  **Notes:** ______",
            "",
            "---",
            "",
        ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _write_report(
    rows: list[dict],
    out_path: pathlib.Path,
    all_extracted: int,
    excluded_already_labeled: int,
    excluded_opaque: int,
    selected: int,
    stamp: str,
    sources: list[str],
) -> None:
    flag_dist = Counter(r["trace_quality_flags"] for r in rows)
    src_dist = Counter(r["candidate_source"] for r in rows)
    lines = [
        "# RelationReady Ready-Candidate Batch Report",
        "",
        f"- **Generated:** {stamp}",
        "",
        "## Sources",
        "",
    ]
    for s in sources:
        lines.append(f"- `{s}`")
    lines += [
        "",
        "## Row counts",
        "",
        f"| Stage | Count |",
        "|---|---|",
        f"| Total extracted from sources | {all_extracted} |",
        f"| Excluded (already labeled) | {excluded_already_labeled} |",
        f"| Excluded (opaque/no-reasoning trace) | {excluded_opaque} |",
        f"| **Selected for batch** | **{selected}** |",
        "",
        "## Trace quality flag distribution",
        "",
        "| Flags | Count |",
        "|---|---|",
    ]
    for f, c in flag_dist.most_common():
        lines.append(f"| `{f}` | {c} |")
    lines += [
        "",
        "## Candidate source distribution",
        "",
        "| Source | Count |",
        "|---|---|",
    ]
    for s, c in src_dist.most_common():
        lines.append(f"| `{s}` | {c} |")
    lines += [
        "",
        "## Leakage checks",
        "",
        "- Gold answers excluded from feature columns by default: ✓",
        "- No API imports: ✓",
        "- Manual label columns blank: ✓",
        "",
        "> Metrics must not be treated as production-verifier performance.",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export likely-ready RelationReady candidates")
    parser.add_argument("--input-jsonl", dest="input_jsonls", metavar="PATH",
                        action="append", required=True,
                        help="Input JSONL artifact (repeat for multiple)")
    parser.add_argument("--existing-labels-csv", dest="existing_labels_csvs",
                        metavar="PATH", action="append", default=[],
                        help="Labeled CSV to exclude from output (repeat)")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--include-gold-metadata", action="store_true", default=False,
                        help="Include gold_answer_metadata_only column in output")
    parser.add_argument("--selection", default="ready_candidates",
                        choices=["ready_candidates"],
                        help="Row selection strategy")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Load already-labeled row_ids for exclusion
    label_csv_paths = [pathlib.Path(p) for p in args.existing_labels_csvs]
    labeled_ids = load_labeled_ids(label_csv_paths)
    print(f"Already-labeled row_ids loaded: {len(labeled_ids)}")

    # Extract all candidates from input artifacts
    all_candidates: list[dict] = []
    seen_ids: set[str] = set()
    sources: list[str] = []
    for jsonl_path_str in args.input_jsonls:
        p = pathlib.Path(jsonl_path_str)
        sources.append(str(p))
        if not p.exists():
            print(f"  [warn] input not found: {p}", file=sys.stderr)
            continue
        raw: list[dict] = []
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    raw.append(json.loads(line))
        count_before = len(all_candidates)
        for row in iter_source(p, raw):
            rid = row["row_id"]
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            all_candidates.append(row)
        print(f"  {p.name}: extracted {len(all_candidates) - count_before} new rows")

    all_extracted = len(all_candidates)
    print(f"Total extracted (deduped): {all_extracted}")

    # Exclude already labeled
    not_labeled = [r for r in all_candidates if r["row_id"] not in labeled_ids]
    excluded_already_labeled = all_extracted - len(not_labeled)
    print(f"Excluded (already labeled): {excluded_already_labeled}")

    # Exclude opaque (no visible reasoning)
    non_opaque = [r for r in not_labeled if "opaque" not in r["trace_quality_flags"]]
    excluded_opaque = len(not_labeled) - len(non_opaque)
    print(f"Excluded (opaque traces): {excluded_opaque}")

    # Sort by readiness score descending, then select batch
    non_opaque.sort(
        key=lambda r: _readiness_score(r["trace_quality_flags"], r["candidate_trace_short"]),
        reverse=True,
    )
    batch = non_opaque[: args.batch_size]
    print(f"Selected for batch: {len(batch)}")

    if not batch:
        print("No eligible candidates found.  Check your input artifacts and exclusion CSVs.",
              file=sys.stderr)
        sys.exit(1)

    # Strip gold from output unless requested
    for row in batch:
        if not args.include_gold_metadata:
            row["gold_answer_metadata_only"] = ""

    # Write outputs
    csv_path = out_dir / "ready_candidate_batch.csv"
    md_path = out_dir / "ready_candidate_batch.md"
    report_path = out_dir / "ready_candidate_report.md"

    _write_batch_csv(batch, csv_path, args.include_gold_metadata)
    _write_batch_md(batch, md_path, args.include_gold_metadata, stamp)
    _write_report(
        batch, report_path,
        all_extracted=all_extracted,
        excluded_already_labeled=excluded_already_labeled,
        excluded_opaque=excluded_opaque,
        selected=len(batch),
        stamp=stamp,
        sources=sources,
    )

    flag_dist = Counter(r["trace_quality_flags"] for r in batch)
    has_code_count = sum(1 for r in batch if "has_code" in r["trace_quality_flags"])
    has_arith_count = sum(1 for r in batch if "has_arithmetic" in r["trace_quality_flags"])
    print()
    print(f"Output dir:       {out_dir}")
    print(f"Batch CSV:        {csv_path.name}")
    print(f"Batch Markdown:   {md_path.name}")
    print(f"Report:           {report_path.name}")
    print(f"Rows in batch:    {len(batch)}")
    print(f"  has_code:       {has_code_count}")
    print(f"  has_arithmetic: {has_arith_count}")
    print(f"Flag distribution: {dict(flag_dist)}")
    print("✓ No APIs called.")
    print("✓ No outputs staged or committed.")
    print("✓ Gold metadata excluded from feature columns by default.")


if __name__ == "__main__":
    main()
