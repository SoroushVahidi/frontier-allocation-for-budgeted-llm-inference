"""Build a larger unlabeled RelationReady candidate pool from multiple local artifacts.

This script normalizes rows from diverse local output formats into a unified
audit-ready schema for manual labeling. Gold answers appear only as metadata
and are never included in feature_text.

Sources supported (auto-detected by field presence):
  - relation_verifier seed_rows.jsonl   (native RelationReady format)
  - failure_records.jsonl               (explodes all_candidate_answers/traces)
  - per_example_records.jsonl           (explodes final_nodes reasoning)
  - manual_audit_*.csv                  (existing labeled rows, for exclusion)

Usage:
    python3 scripts/build_relation_verifier_training_pool.py \
        --input-jsonl outputs/.../failures/full_failure_records.jsonl \
        --input-jsonl outputs/.../seed_rows.jsonl \
        --existing-labels-csv outputs/.../manual_audit_33rows.csv \
        --output-dir outputs/relation_verifier_training_pool_expansion_<STAMP>
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

AUDIT_CSV_COLUMNS = [
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
    "source_artifact",
    "trace_quality_flags",
    "suggested_priority",
    "gold_answer_metadata_only",
    "relation_ready_label_manual",
    "first_error_axis_manual",
    "notes_manual",
]

TRACE_SHORT_MAX = 200


# ---------------------------------------------------------------------------
# Helpers
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
        # Prefer reasoning_text, then step, then code, then stringify
        for key in ("reasoning_text", "step", "code"):
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


def _make_pool_row(
    row_id: str,
    problem_id: str,
    case_id: str,
    split_group_id: str,
    candidate_source: str,
    question: str,
    target_phrase: str,
    target_semantic_type: str,
    candidate_answer: str,
    trace_short: str,
    source_artifact: str,
    gold_metadata: str,
    failure_type: str = "",
    failure_hints: dict | None = None,
) -> dict:
    flags = _trace_quality_flags(trace_short, candidate_answer)
    priority = _suggested_priority(failure_type, failure_hints, flags)
    return {
        "row_id": row_id,
        "problem_id": problem_id,
        "case_id": case_id,
        "split_group_id": split_group_id,
        "candidate_source": candidate_source,
        "question": question,
        "target_phrase": target_phrase,
        "target_semantic_type": target_semantic_type,
        "candidate_answer": str(candidate_answer),
        "candidate_trace_short": trace_short,
        "source_artifact": source_artifact,
        "trace_quality_flags": flags,
        "gold_answer_metadata_only": gold_metadata,
        "suggested_priority": priority,
        "failure_type": failure_type,
        # Manual label columns — always blank in output
        "relation_ready_label_manual": "",
        "first_error_axis_manual": "",
        "notes_manual": "",
    }


def _suggested_priority(failure_type: str, failure_hints: dict | None, flags: str) -> str:
    if failure_type in ("present_not_selected", "output_layer_mismatch"):
        return "high"
    if failure_hints and failure_hints.get("trace_is_opaque"):
        return "high"
    if "opaque" in flags:
        return "medium"
    return "normal"


# ---------------------------------------------------------------------------
# Source-specific loaders
# ---------------------------------------------------------------------------

def _detect_schema(row: dict) -> str:
    """Return a schema tag based on available fields."""
    keys = set(row.keys())
    if "all_candidate_answers" in keys and "all_candidate_traces" in keys:
        return "failure_records"
    if "final_nodes" in keys and "reasoning_text" not in keys:
        return "per_example_records"
    if "candidate_trace" in keys and "candidate_source" in keys:
        return "seed_rows"
    if "candidate_relations" in keys:
        return "seed_rows"
    return "unknown"


def _load_seed_rows(rows: list[dict], source_artifact: str) -> Iterator[dict]:
    for row in rows:
        q = row.get("question", "").strip()
        ca = str(row.get("candidate_answer", "")).strip()
        trace_raw = row.get("candidate_trace", "") or ""
        trace_short = trace_raw.strip()[:TRACE_SHORT_MAX]
        if not q or not ca:
            continue
        row_id = row.get("row_id") or _make_row_id(q, ca, trace_short)
        yield _make_pool_row(
            row_id=row_id,
            problem_id=row.get("problem_id", row.get("case_id", "")),
            case_id=row.get("case_id", ""),
            split_group_id=row.get("split_group_id", ""),
            candidate_source=row.get("candidate_source", ""),
            question=q,
            target_phrase=row.get("target_phrase", ""),
            target_semantic_type=row.get("target_semantic_type", ""),
            candidate_answer=ca,
            trace_short=trace_short,
            source_artifact=source_artifact,
            gold_metadata="",  # seed rows don't have gold
        )


def _load_failure_records(rows: list[dict], source_artifact: str) -> Iterator[dict]:
    for row in rows:
        q = row.get("question", "").strip()
        gold_meta = str(row.get("gold_answer_metadata_only", ""))
        case_id = row.get("case_id", "")
        failure_type = row.get("failure_type", "")
        failure_hints = row.get("failure_hints") or {}
        answers = row.get("all_candidate_answers") or []
        traces = row.get("all_candidate_traces") or []
        if not q:
            continue
        # Pad traces to match answers length
        while len(traces) < len(answers):
            traces.append("")
        for i, (ca, trace_raw) in enumerate(zip(answers, traces)):
            ca = str(ca).strip()
            trace_short = _shorten_trace(trace_raw)
            row_id = _make_row_id(q, ca, trace_short)
            yield _make_pool_row(
                row_id=row_id,
                problem_id=case_id,
                case_id=case_id,
                split_group_id="",
                candidate_source=f"cohere_run_cand_{i}",
                question=q,
                target_phrase="",
                target_semantic_type="",
                candidate_answer=ca,
                trace_short=trace_short,
                source_artifact=source_artifact,
                gold_metadata=gold_meta,
                failure_type=failure_type,
                failure_hints=failure_hints,
            )


def _load_per_example_records(rows: list[dict], source_artifact: str) -> Iterator[dict]:
    for row in rows:
        q = row.get("question", "").strip()
        if not q:
            continue
        # gold is present as gold_answer — use as metadata only
        gold_meta = str(row.get("gold_answer", "") or row.get("gold_answer_canonical", ""))
        case_id = str(row.get("example_id", ""))
        failure_tag = row.get("failure_tag", "")
        final_nodes = row.get("final_nodes") or []
        if isinstance(final_nodes, str):
            try:
                final_nodes = json.loads(final_nodes)
            except (json.JSONDecodeError, ValueError):
                final_nodes = []
        for node in final_nodes:
            ca = str(node.get("predicted_answer", "") or node.get("numeric_leaf_value", "")).strip()
            trace_short = _shorten_trace(node.get("reasoning_text", ""))
            if not ca:
                continue
            row_id = _make_row_id(q, ca, trace_short)
            yield _make_pool_row(
                row_id=row_id,
                problem_id=case_id,
                case_id=case_id,
                split_group_id="",
                candidate_source=node.get("branch_id", "unknown"),
                question=q,
                target_phrase="",
                target_semantic_type="",
                candidate_answer=ca,
                trace_short=trace_short,
                source_artifact=source_artifact,
                gold_metadata=gold_meta,
                failure_type=failure_tag,
            )


def _load_csv_rows(rows: list[dict], source_artifact: str) -> Iterator[dict]:
    """Load a CSV that might be an existing manual audit or similar."""
    for row in rows:
        q = row.get("question", "").strip()
        ca = str(row.get("candidate_answer", "")).strip()
        if not q or not ca:
            continue
        trace_short = row.get("candidate_trace_short", "")[:TRACE_SHORT_MAX]
        row_id = row.get("row_id") or _make_row_id(q, ca, trace_short)
        yield _make_pool_row(
            row_id=row_id,
            problem_id=row.get("problem_id", row.get("case_id", "")),
            case_id=row.get("case_id", ""),
            split_group_id=row.get("split_group_id", ""),
            candidate_source=row.get("candidate_source", ""),
            question=q,
            target_phrase=row.get("target_phrase", ""),
            target_semantic_type=row.get("target_semantic_type", ""),
            candidate_answer=ca,
            trace_short=trace_short,
            source_artifact=source_artifact,
            gold_metadata=row.get("gold_answer_metadata_only", ""),
        )


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_csv_file(path: pathlib.Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def iter_source(path: pathlib.Path, raw_rows: list[dict]) -> Iterator[dict]:
    if not raw_rows:
        return
    schema = _detect_schema(raw_rows[0])
    artifact = str(path)
    if schema == "seed_rows":
        yield from _load_seed_rows(raw_rows, artifact)
    elif schema == "failure_records":
        yield from _load_failure_records(raw_rows, artifact)
    elif schema == "per_example_records":
        yield from _load_per_example_records(raw_rows, artifact)
    else:
        # Try as generic CSV/JSONL with candidate_answer field
        yield from _load_csv_rows(raw_rows, artifact)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def write_pool_report(
    output_dir: pathlib.Path,
    stats: dict,
    sources: list[str],
) -> None:
    lines = [
        "# RelationReady Training Pool Report",
        "",
        f"- **Generated:** {datetime.now(timezone.utc).isoformat()}",
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
        f"| Total candidates extracted | {stats['total_extracted']} |",
        "|---|---|",
        f"| After deduplication | {stats['after_dedupe']} |",
        f"| Excluded (already labeled) | {stats['excluded_labeled']} |",
        f"| Final pool size | {stats['final_pool']} |",
        "",
        "## Priority distribution",
        "",
        "| Priority | Count |",
        "|---|---|",
    ]
    for p, c in sorted(stats["priority_dist"].items()):
        lines.append(f"| `{p}` | {c} |")
    lines += [
        "",
        "## Candidate source distribution",
        "",
        "| Source | Count |",
        "|---|---|",
    ]
    for s, c in sorted(stats["source_dist"].items(), key=lambda x: -x[1])[:15]:
        lines.append(f"| `{s}` | {c} |")
    lines += [
        "",
        "## Failure type distribution",
        "",
        "| Failure type | Count |",
        "|---|---|",
    ]
    for ft, c in sorted(stats["failure_type_dist"].items(), key=lambda x: -x[1]):
        lines.append(f"| `{ft}` | {c} |")
    lines += [
        "",
        "## Feature leakage check",
        "",
        "> Gold answers appear only in `gold_answer_metadata_only` column.",
        "> They are never included in `candidate_trace_short` or any other feature column.",
        "",
        "Manual label columns (`relation_ready_label_manual`, `first_error_axis_manual`,",
        "`notes_manual`) are blank in all output rows.",
    ]
    (output_dir / "pool_report.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build RelationReady training pool")
    parser.add_argument("--input-jsonl", action="append", default=[], dest="input_jsonls")
    parser.add_argument("--input-csv", action="append", default=[], dest="input_csvs")
    parser.add_argument("--existing-labels-csv", action="append", default=[], dest="existing_labels")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--dedupe", default="true")
    parser.add_argument("--exclude-existing-labels", default="true")
    parser.add_argument("--priority-mode", default="diverse")
    args = parser.parse_args(argv)

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dedupe = args.dedupe.lower() != "false"
    exclude_existing = args.exclude_existing_labels.lower() != "false"

    # Load existing label row_ids and content hashes for exclusion
    existing_row_ids: set[str] = set()
    existing_hashes: set[str] = set()
    for csv_path_str in args.existing_labels:
        csv_path = pathlib.Path(csv_path_str)
        if not csv_path.exists():
            print(f"WARNING: existing-labels CSV not found: {csv_path}", file=sys.stderr)
            continue
        for row in load_csv_file(csv_path):
            rid = row.get("row_id", "").strip()
            if rid:
                existing_row_ids.add(rid)
            q = row.get("question", "").strip()
            ca = str(row.get("candidate_answer", "")).strip()
            ts = row.get("candidate_trace_short", "")[:80]
            if q and ca:
                existing_hashes.add(_content_hash(q, ca, ts))

    # Load and normalize all sources
    all_pool_rows: list[dict] = []
    sources_used: list[str] = []

    for jsonl_str in args.input_jsonls:
        p = pathlib.Path(jsonl_str)
        if not p.exists():
            print(f"WARNING: JSONL not found: {p}", file=sys.stderr)
            continue
        raw = load_jsonl(p)
        sources_used.append(str(p))
        before = len(all_pool_rows)
        all_pool_rows.extend(iter_source(p, raw))
        print(f"  {p.name}: {len(all_pool_rows) - before} candidates extracted")

    for csv_str in args.input_csvs:
        p = pathlib.Path(csv_str)
        if not p.exists():
            print(f"WARNING: CSV not found: {p}", file=sys.stderr)
            continue
        raw = load_csv_file(p)
        sources_used.append(str(p))
        before = len(all_pool_rows)
        all_pool_rows.extend(iter_source(p, raw))
        print(f"  {p.name}: {len(all_pool_rows) - before} candidates extracted")

    stats: dict = {"total_extracted": len(all_pool_rows)}

    # Deduplicate by row_id (content hash)
    if dedupe:
        seen: set[str] = set()
        deduped = []
        for row in all_pool_rows:
            rid = row["row_id"]
            if rid not in seen:
                seen.add(rid)
                deduped.append(row)
        all_pool_rows = deduped
    stats["after_dedupe"] = len(all_pool_rows)

    # Exclude already-labeled rows
    excluded = 0
    if exclude_existing:
        filtered = []
        for row in all_pool_rows:
            rid = row["row_id"]
            h = _content_hash(row["question"], row["candidate_answer"], row["candidate_trace_short"][:80])
            if rid in existing_row_ids or h in existing_hashes:
                excluded += 1
            else:
                filtered.append(row)
        all_pool_rows = filtered
    stats["excluded_labeled"] = excluded

    # Sort by priority: high → medium → normal
    priority_order = {"high": 0, "medium": 1, "normal": 2}
    all_pool_rows.sort(key=lambda r: priority_order.get(r.get("suggested_priority", "normal"), 2))

    if args.max_rows is not None:
        all_pool_rows = all_pool_rows[: args.max_rows]

    stats["final_pool"] = len(all_pool_rows)
    stats["priority_dist"] = dict(Counter(r.get("suggested_priority", "") for r in all_pool_rows))
    stats["source_dist"] = dict(Counter(r.get("candidate_source", "") for r in all_pool_rows))
    stats["failure_type_dist"] = dict(Counter(r.get("failure_type", "") for r in all_pool_rows))

    # Write pool_rows.jsonl
    with open(output_dir / "pool_rows.jsonl", "w", encoding="utf-8") as f:
        for row in all_pool_rows:
            f.write(json.dumps(row) + "\n")

    # Write manual_audit_batch.csv (only AUDIT_CSV_COLUMNS)
    with open(output_dir / "manual_audit_batch.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_pool_rows)

    write_pool_report(output_dir, stats, sources_used)

    print(f"\nTotal extracted:       {stats['total_extracted']}")
    print(f"After deduplication:   {stats['after_dedupe']}")
    print(f"Excluded (labeled):    {stats['excluded_labeled']}")
    print(f"Final pool size:       {stats['final_pool']}")
    print(f"Priority: {stats['priority_dist']}")
    print(f"Output dir: {output_dir}")
    print("✓ No gold answers in feature columns.")
    print("✓ Manual label columns are blank.")
    print("✓ No APIs called.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
