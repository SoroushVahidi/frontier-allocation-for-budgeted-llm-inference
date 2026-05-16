"""Export likely-ready positive candidates from successful local runs for manual confirmation.

Targets per_example_records.jsonl (final_nodes + reasoning_text + exact_match),
unified_candidate_trace_enriched.jsonl (candidate_nodes + trace_text), and
full_failure_records.jsonl (all_candidate_traces).

Rows where exact_match=True are prioritised for selection — this is offline
filtering only; exact_match is never written to feature columns.
Gold answers appear only in gold_answer_metadata_only and only when
--include-gold-metadata is set.

Usage:
    python3 scripts/export_relation_verifier_positive_candidate_batch.py \
        --input-jsonl outputs/.../per_example_records.jsonl \
        --input-jsonl outputs/.../unified_candidate_trace_enriched.jsonl \
        --existing-labels-csv outputs/.../manual_audit_33rows.csv \
        --existing-labels-csv outputs/.../manual_audit_batch.csv \
        --output-dir outputs/relation_verifier_positive_candidate_batch_<STAMP> \
        --batch-size 100
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
    "is_correct_offline_metadata",   # offline selection signal — never a feature
    "gold_answer_metadata_only",
    "relation_ready_label_manual",
    "first_error_axis_manual",
    "notes_manual",
]


# ---------------------------------------------------------------------------
# Shared helpers (identical to build_relation_verifier_training_pool so that
# row_ids are consistent across all RelationReady scripts)
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
    flags: list[str] = []
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


def _readiness_score(flags: str, is_correct: bool, trace_short: str) -> int:
    """Higher score = more likely a confirmable ready example."""
    score = 0
    if is_correct:
        score += 10            # strongest signal: offline evaluation says correct
    if "has_code" in flags:
        score += 4
    if "has_arithmetic" in flags:
        score += 3
    if "opaque" not in flags:
        score += 2
    if len(trace_short.strip()) > 100:
        score += 1
    return score


def _is_non_opaque(trace_short: str) -> bool:
    flags = _trace_quality_flags(trace_short, "x")
    return "opaque" not in flags and len(trace_short.strip()) >= 30


def _make_row(
    row_id: str,
    problem_id: str,
    case_id: str,
    candidate_source: str,
    question: str,
    candidate_answer: str,
    trace_short: str,
    source_artifact: str,
    flags: str,
    is_correct: bool,
    gold_metadata: str,
) -> dict:
    return {
        "row_id": row_id,
        "problem_id": problem_id,
        "case_id": case_id,
        "candidate_source": candidate_source,
        "question": question,
        "target_phrase": "",
        "candidate_answer": candidate_answer,
        "candidate_trace_short": trace_short,
        "source_artifact": source_artifact,
        "trace_quality_flags": flags,
        "is_correct_offline_metadata": "yes" if is_correct else "no",
        "gold_answer_metadata_only": gold_metadata,
        "relation_ready_label_manual": "",
        "first_error_axis_manual": "",
        "notes_manual": "",
    }


# ---------------------------------------------------------------------------
# Source-specific loaders
# ---------------------------------------------------------------------------

def _detect_schema(row: dict) -> str:
    keys = set(row.keys())
    if "final_nodes" in keys and ("exact_match" in keys or "gold_answer" in keys):
        return "per_example_records"
    if "candidate_nodes" in keys:
        return "candidate_nodes"
    if "all_candidate_answers" in keys and "all_candidate_traces" in keys:
        return "failure_records"
    if "candidate_trace" in keys and "candidate_answer" in keys:
        return "seed_rows"
    if "candidate_trace_short" in keys and "candidate_answer" in keys:
        return "pool_rows"
    return "unknown"


def _load_per_example_records(rows: list[dict], source_artifact: str,
                               min_trace_chars: int) -> Iterator[dict]:
    """Extract final_nodes from per_example_records, prioritising exact_match rows."""
    for row in rows:
        q = (row.get("question") or "").strip()
        if not q:
            continue
        is_correct = bool(row.get("exact_match"))
        gold_meta = str(row.get("gold_answer") or row.get("gold_answer_canonical") or "")
        case_id = str(row.get("example_id") or "")
        method = str(row.get("method") or "")
        nodes = row.get("final_nodes") or []
        if isinstance(nodes, str):
            try:
                nodes = json.loads(nodes)
            except (json.JSONDecodeError, ValueError):
                nodes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            ca = str(
                node.get("predicted_answer") or
                node.get("numeric_leaf_value") or ""
            ).strip()
            if not ca:
                continue
            trace_short = _shorten_trace(node.get("reasoning_text", ""))
            if len(trace_short.strip()) < min_trace_chars:
                continue
            row_id = _make_row_id(q, ca, trace_short)
            flags = _trace_quality_flags(trace_short, ca)
            yield _make_row(
                row_id=row_id,
                problem_id=case_id,
                case_id=case_id,
                candidate_source=node.get("branch_id") or method or "unknown",
                question=q,
                candidate_answer=ca,
                trace_short=trace_short,
                source_artifact=source_artifact,
                flags=flags,
                is_correct=is_correct,
                gold_metadata=gold_meta,
            )


def _load_candidate_nodes(rows: list[dict], source_artifact: str,
                          min_trace_chars: int) -> Iterator[dict]:
    for row in rows:
        q = (row.get("problem_statement") or row.get("question") or "").strip()
        if not q:
            continue
        case_id = row.get("case_id", "")
        gold_meta = str(row.get("gold_answer_metadata_only") or
                        row.get("gold_answer") or "")
        is_correct = bool(row.get("current_answer_is_correct") or
                          row.get("gold_in_aggregate_answer_groups"))
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
            if len(trace_short.strip()) < min_trace_chars:
                continue
            row_id = _make_row_id(q, ca, trace_short)
            flags = _trace_quality_flags(trace_short, ca)
            yield _make_row(
                row_id=row_id,
                problem_id=case_id,
                case_id=case_id,
                candidate_source=node.get("source_family") or node.get("candidate_id") or "unknown",
                question=q,
                candidate_answer=ca,
                trace_short=trace_short,
                source_artifact=source_artifact,
                flags=flags,
                is_correct=is_correct,
                gold_metadata=gold_meta,
            )


def _load_failure_records(rows: list[dict], source_artifact: str,
                          min_trace_chars: int) -> Iterator[dict]:
    for row in rows:
        q = (row.get("question") or "").strip()
        if not q:
            continue
        gold_meta = str(row.get("gold_answer_metadata_only") or "")
        case_id = row.get("case_id", "")
        answers = row.get("all_candidate_answers") or []
        traces = row.get("all_candidate_traces") or []
        while len(traces) < len(answers):
            traces.append("")
        for i, (ca, trace_raw) in enumerate(zip(answers, traces)):
            ca = str(ca).strip()
            trace_short = _shorten_trace(trace_raw)
            if len(trace_short.strip()) < min_trace_chars:
                continue
            row_id = _make_row_id(q, ca, trace_short)
            flags = _trace_quality_flags(trace_short, ca)
            yield _make_row(
                row_id=row_id,
                problem_id=case_id,
                case_id=case_id,
                candidate_source=f"cohere_run_cand_{i}",
                question=q,
                candidate_answer=ca,
                trace_short=trace_short,
                source_artifact=source_artifact,
                flags=flags,
                is_correct=False,  # failure records are by definition failures
                gold_metadata=gold_meta,
            )


def _load_pool_rows(rows: list[dict], source_artifact: str,
                    min_trace_chars: int) -> Iterator[dict]:
    for row in rows:
        q = (row.get("question") or "").strip()
        ca = str(row.get("candidate_answer") or "").strip()
        if not q or not ca:
            continue
        trace_short = (row.get("candidate_trace_short") or "")[:TRACE_SHORT_MAX]
        if len(trace_short.strip()) < min_trace_chars:
            continue
        row_id = row.get("row_id") or _make_row_id(q, ca, trace_short)
        flags = row.get("trace_quality_flags") or _trace_quality_flags(trace_short, ca)
        yield _make_row(
            row_id=row_id,
            problem_id=row.get("problem_id", row.get("case_id", "")),
            case_id=row.get("case_id", ""),
            candidate_source=row.get("candidate_source", ""),
            question=q,
            candidate_answer=ca,
            trace_short=trace_short,
            source_artifact=source_artifact,
            flags=flags,
            is_correct=False,
            gold_metadata=row.get("gold_answer_metadata_only", ""),
        )


def iter_source(path: pathlib.Path, raw_rows: list[dict],
                min_trace_chars: int) -> Iterator[dict]:
    if not raw_rows:
        return
    schema = _detect_schema(raw_rows[0])
    artifact = str(path)
    if schema == "per_example_records":
        yield from _load_per_example_records(raw_rows, artifact, min_trace_chars)
    elif schema == "candidate_nodes":
        yield from _load_candidate_nodes(raw_rows, artifact, min_trace_chars)
    elif schema == "failure_records":
        yield from _load_failure_records(raw_rows, artifact, min_trace_chars)
    elif schema == "pool_rows":
        yield from _load_pool_rows(raw_rows, artifact, min_trace_chars)
    else:
        print(f"  [warn] unrecognised schema for {path.name}, skipping", file=sys.stderr)


# ---------------------------------------------------------------------------
# Exclusion helpers
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

def _write_batch_csv(rows: list[dict], out_path: pathlib.Path,
                     include_gold: bool) -> None:
    cols = [c for c in AUDIT_CSV_COLUMNS
            if include_gold or c != "gold_answer_metadata_only"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_batch_md(rows: list[dict], out_path: pathlib.Path,
                    include_gold: bool, stamp: str) -> None:
    lines = [
        "# RelationReady — Positive/Ready Candidate Labeling Batch",
        "",
        f"Generated: {stamp}",
        f"Rows: {len(rows)}",
        "",
        "**Labeling convention:** A row is `ready` only if the trace AND answer",
        "together establish the target relation through visible reasoning steps.",
        "A final answer with no reasoning steps is `not_ready`.",
        "",
        "**Note on `is_correct_offline_metadata`:** This field indicates whether",
        "the run's offline evaluation judged this case correct. It is metadata only",
        "and must not be used as a labeling shortcut — read the trace and judge",
        "whether the reasoning itself establishes the relation.",
        "",
        "Label choices: `ready` | `not_ready` | `uncertain` | `gold_inconsistent`",
        "Axis (if not_ready): `source_fact_missing` | `unit_scale_error` |",
        "`process_state_error` | `relation_type_error` | `arithmetic_error` | `other`",
        "",
        "---",
        "",
    ]
    for i, row in enumerate(rows, 1):
        lines += [
            f"## Row {i} — `{row['row_id']}`",
            "",
            f"**Source:** `{row['candidate_source']}` | **Case:** `{row['case_id']}`",
            f"**Flags:** `{row['trace_quality_flags']}`"
            f" | **Offline correct (metadata):** `{row['is_correct_offline_metadata']}`",
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


def _write_report(rows: list[dict], out_path: pathlib.Path,
                  all_extracted: int, excluded_labeled: int,
                  excluded_opaque: int, selected: int,
                  stamp: str, sources: list[str]) -> None:
    flag_dist = Counter(r["trace_quality_flags"] for r in rows)
    src_dist = Counter(r["candidate_source"] for r in rows)
    correct_count = sum(1 for r in rows if r["is_correct_offline_metadata"] == "yes")
    lines = [
        "# RelationReady Positive-Candidate Batch Report",
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
        "| Stage | Count |",
        "|---|---|",
        f"| Total extracted from sources | {all_extracted} |",
        f"| Excluded (already labeled) | {excluded_labeled} |",
        f"| Excluded (opaque/short trace) | {excluded_opaque} |",
        f"| **Selected for batch** | **{selected}** |",
        f"| Of which: offline-correct (metadata) | {correct_count} |",
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
        "## Candidate source distribution (top 10)",
        "",
        "| Source | Count |",
        "|---|---|",
    ]
    for s, c in src_dist.most_common(10):
        lines.append(f"| `{s}` | {c} |")
    lines += [
        "",
        "## Leakage checks",
        "",
        "- `is_correct_offline_metadata` is metadata only, never in feature_text: ✓",
        "- Gold answers excluded from feature columns by default: ✓",
        "- Manual label columns blank: ✓",
        "- No API imports: ✓",
        "",
        "> These rows require manual human confirmation before use in training.",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Export likely-ready positive RelationReady candidates"
    )
    parser.add_argument("--input-jsonl", dest="input_jsonls", metavar="PATH",
                        action="append", required=True)
    parser.add_argument("--existing-labels-csv", dest="existing_labels_csvs",
                        metavar="PATH", action="append", default=[])
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--min-trace-chars", type=int, default=80,
                        help="Minimum trace length in characters (default 80)")
    parser.add_argument("--exclude-opaque", default="true",
                        choices=["true", "false"],
                        help="Exclude opaque/final-only traces (default true)")
    parser.add_argument("--include-gold-metadata", action="store_true", default=False)
    parser.add_argument("--selection", default="ready_candidates",
                        choices=["ready_candidates"])
    args = parser.parse_args(argv)

    exclude_opaque = args.exclude_opaque.lower() == "true"
    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Load exclusion list
    label_csv_paths = [pathlib.Path(p) for p in args.existing_labels_csvs]
    labeled_ids = load_labeled_ids(label_csv_paths)
    print(f"Already-labeled row_ids: {len(labeled_ids)}")

    # Extract all candidates
    all_candidates: list[dict] = []
    seen_ids: set[str] = set()
    sources: list[str] = []
    for jsonl_str in args.input_jsonls:
        p = pathlib.Path(jsonl_str)
        sources.append(str(p))
        if not p.exists():
            print(f"  [warn] not found: {p}", file=sys.stderr)
            continue
        raw: list[dict] = []
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    raw.append(json.loads(line))
        before = len(all_candidates)
        for row in iter_source(p, raw, args.min_trace_chars):
            if row["row_id"] in seen_ids:
                continue
            seen_ids.add(row["row_id"])
            all_candidates.append(row)
        print(f"  {p.name}: +{len(all_candidates) - before} new rows")

    all_extracted = len(all_candidates)
    print(f"Total extracted (deduped): {all_extracted}")

    # Exclude already labeled
    not_labeled = [r for r in all_candidates if r["row_id"] not in labeled_ids]
    excluded_labeled = all_extracted - len(not_labeled)
    print(f"Excluded (already labeled): {excluded_labeled}")

    # Exclude opaque if requested
    if exclude_opaque:
        candidates = [r for r in not_labeled if "opaque" not in r["trace_quality_flags"]]
        excluded_opaque = len(not_labeled) - len(candidates)
    else:
        candidates = not_labeled
        excluded_opaque = 0
    print(f"Excluded (opaque/short): {excluded_opaque}")

    # Sort by readiness score
    candidates.sort(
        key=lambda r: _readiness_score(
            r["trace_quality_flags"],
            r["is_correct_offline_metadata"] == "yes",
            r["candidate_trace_short"],
        ),
        reverse=True,
    )
    batch = candidates[: args.batch_size]
    print(f"Selected for batch: {len(batch)}")

    if not batch:
        print("No eligible candidates found.", file=sys.stderr)
        sys.exit(1)

    # Strip gold unless requested
    for row in batch:
        if not args.include_gold_metadata:
            row["gold_answer_metadata_only"] = ""

    csv_path = out_dir / "positive_candidate_batch.csv"
    md_path = out_dir / "positive_candidate_batch.md"
    report_path = out_dir / "positive_candidate_report.md"

    _write_batch_csv(batch, csv_path, args.include_gold_metadata)
    _write_batch_md(batch, md_path, args.include_gold_metadata, stamp)
    _write_report(batch, report_path,
                  all_extracted=all_extracted,
                  excluded_labeled=excluded_labeled,
                  excluded_opaque=excluded_opaque,
                  selected=len(batch),
                  stamp=stamp,
                  sources=sources)

    correct_count = sum(1 for r in batch if r["is_correct_offline_metadata"] == "yes")
    has_code = sum(1 for r in batch if "has_code" in r["trace_quality_flags"])
    has_arith = sum(1 for r in batch if "has_arithmetic" in r["trace_quality_flags"])
    flag_dist = Counter(r["trace_quality_flags"] for r in batch)

    print()
    print(f"Output dir:            {out_dir}")
    print(f"Batch CSV:             {csv_path.name}")
    print(f"Batch Markdown:        {md_path.name}")
    print(f"Report:                {report_path.name}")
    print(f"Rows in batch:         {len(batch)}")
    print(f"  offline-correct:     {correct_count}")
    print(f"  has_code:            {has_code}")
    print(f"  has_arithmetic:      {has_arith}")
    print(f"Flag distribution:     {dict(flag_dist)}")
    print("✓ No APIs called.")
    print("✓ No outputs staged or committed.")
    print("✓ Gold and correctness metadata excluded from feature columns by default.")


if __name__ == "__main__":
    main()
