#!/usr/bin/env python3
"""Compute overlap/disjointness proof for exact-case Cohere validation planning.

This utility is intentionally offline-only and schema-robust across known JSONL artifacts.

Supported row schemas include:
- per_example_records.jsonl (top-level example_id/question)
- scored_candidates.jsonl (metadata.example_id, question in metadata or feature_text)
- exact case lists (example_id + question/problem_text)
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXAMPLE_ID_KEYS = (
    "example_id",
    "case_id",
    "problem_id",
    "gsm8k_id",
    "id",
)

QUESTION_KEYS = (
    "question",
    "problem_text",
    "problem_statement",
    "prompt",
)

FEATURE_QUESTION_RE = re.compile(
    r"(?:^|\|)\s*question\s*:\s*(.*?)\s*(?:\|\s*(?:candidate_answer|target_phrase|candidate_trace_short|candidate_source)\s*:|$)",
    flags=re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class SourceSummary:
    rows: int
    unique_example_ids: int
    unique_questions: int


def _norm_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _find_nested_key(obj: Any, target_keys: tuple[str, ...], *, max_depth: int = 5) -> Any:
    keys = set(target_keys)

    def walk(node: Any, depth: int) -> Any:
        if depth > max_depth:
            return None
        if isinstance(node, dict):
            for k, v in node.items():
                if str(k) in keys and v not in (None, ""):
                    return v
            for v in node.values():
                found = walk(v, depth + 1)
                if found not in (None, ""):
                    return found
        elif isinstance(node, list):
            for item in node:
                found = walk(item, depth + 1)
                if found not in (None, ""):
                    return found
        return None

    return walk(obj, 0)


def extract_example_id(row: dict[str, Any]) -> str:
    for k in EXAMPLE_ID_KEYS:
        v = row.get(k)
        if v not in (None, ""):
            out = str(v).strip()
            if out:
                return out

    md = row.get("metadata")
    if isinstance(md, dict):
        for k in EXAMPLE_ID_KEYS:
            v = md.get(k)
            if v not in (None, ""):
                out = str(v).strip()
                if out:
                    return out

    found = _find_nested_key(row, EXAMPLE_ID_KEYS)
    if found not in (None, ""):
        out = str(found).strip()
        if out:
            return out

    return ""


def extract_question(row: dict[str, Any]) -> str:
    for k in QUESTION_KEYS:
        v = row.get(k)
        q = _norm_text(v)
        if q:
            return q

    md = row.get("metadata")
    if isinstance(md, dict):
        for k in QUESTION_KEYS:
            v = md.get(k)
            q = _norm_text(v)
            if q:
                return q

    feature_text = str(row.get("feature_text") or "")
    if feature_text:
        m = FEATURE_QUESTION_RE.search(feature_text)
        if m:
            q = _norm_text(m.group(1))
            if q:
                return q

    found = _find_nested_key(row, QUESTION_KEYS)
    q = _norm_text(found)
    if q:
        return q

    return ""


def collect_ids_questions(path: Path) -> tuple[set[str], set[str], SourceSummary]:
    rows = _read_jsonl(path)
    ids: set[str] = set()
    questions: set[str] = set()
    for row in rows:
        eid = extract_example_id(row)
        if eid:
            ids.add(eid)
        q = extract_question(row)
        if q:
            questions.add(q)
    return ids, questions, SourceSummary(rows=len(rows), unique_example_ids=len(ids), unique_questions=len(questions))


def compute_disjointness(
    *,
    selected_cases_jsonl: Path,
    prior_jsonls: list[Path],
    source_labels: list[str] | None = None,
) -> dict[str, Any]:
    selected_ids, selected_questions, selected_summary = collect_ids_questions(selected_cases_jsonl)

    if source_labels is None:
        labels = [p.stem for p in prior_jsonls]
    else:
        if len(source_labels) != len(prior_jsonls):
            raise ValueError("source_labels length must match prior_jsonls length")
        labels = source_labels

    source_artifacts: dict[str, str] = {}
    source_counts: dict[str, dict[str, int]] = {}
    union_ids: set[str] = set()
    union_questions: set[str] = set()

    for label, path in zip(labels, prior_jsonls):
        ids, qs, summary = collect_ids_questions(path)
        source_artifacts[label] = str(path)
        source_counts[label] = {
            "rows": summary.rows,
            "unique_example_ids": summary.unique_example_ids,
            "unique_questions": summary.unique_questions,
        }
        union_ids |= ids
        union_questions |= qs

    overlap_ids = sorted(selected_ids & union_ids)
    overlap_questions = sorted(selected_questions & union_questions)

    selected_preview = sorted(selected_ids)[:10]
    selected_index_preview: list[int] = []
    selected_rows = _read_jsonl(selected_cases_jsonl)
    selected_pos = {extract_example_id(r): i for i, r in enumerate(selected_rows) if extract_example_id(r)}
    for eid in selected_preview:
        if eid in selected_pos:
            selected_index_preview.append(selected_pos[eid])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": source_artifacts,
        "source_counts": source_counts,
        "prior_unique_example_ids_union_count": len(union_ids),
        "prior_unique_questions_union_count": len(union_questions),
        "selected_count": len(selected_ids),
        "selected_example_id_preview": selected_preview,
        "selected_source_indices_preview": selected_index_preview,
        "selected_index_range": [0, max(len(selected_rows) - 1, 0)] if selected_rows else [0, 0],
        "overlap_example_ids_with_prior": len(overlap_ids),
        "overlap_example_ids_preview": overlap_ids[:25],
        "overlap_questions_with_prior": len(overlap_questions),
        "overlap_questions_preview": overlap_questions[:25],
        "selected_summary": {
            "rows": selected_summary.rows,
            "unique_example_ids": selected_summary.unique_example_ids,
            "unique_questions": selected_summary.unique_questions,
        },
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selected-cases-jsonl", required=True)
    p.add_argument("--prior-jsonl", action="append", required=True, help="Repeat for each prior artifact.")
    p.add_argument("--prior-label", action="append", default=[], help="Optional labels matching --prior-jsonl order.")
    p.add_argument("--output-json", required=True)
    p.add_argument("--fail-on-overlap", action="store_true")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    selected = Path(args.selected_cases_jsonl)
    priors = [Path(x) for x in args.prior_jsonl]
    labels = args.prior_label or None

    proof = compute_disjointness(selected_cases_jsonl=selected, prior_jsonls=priors, source_labels=labels)
    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(proof, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"wrote {out_path}")
    print(f"selected_unique_ids={proof['selected_count']} overlap_ids={proof['overlap_example_ids_with_prior']} overlap_questions={proof['overlap_questions_with_prior']}")

    if args.fail_on_overlap and proof["overlap_example_ids_with_prior"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
