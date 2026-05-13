#!/usr/bin/env python3
"""Build a small, auditable RelationReady / relation-verifier seed dataset.

The builder is intentionally narrow: JSONL/CSV inputs only, no API calls, no
training logic, and no broad ingestion framework.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "relation_verifier_seed_dataset_v0"
ALLOWED_INPUT_SUFFIXES = {".jsonl", ".csv"}
TARGET_TYPE_KEYWORDS = {
    "percentage": ("percent", "percentage", "%"),
    "ratio": ("ratio",),
    "difference": ("difference", "left", "remaining", "less", "more", "how many more"),
    "total": ("total", "altogether", "in all", "combined", "sum"),
    "rate": (" per ", "/hour", "each", "rate"),
    "unit_conversion": ("convert", "conversion", "inch", "feet", "foot", "meter", "mile", "pound"),
}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _lower(value: Any) -> str:
    return _stringify(value).lower()


def _safe_bool(value: Any) -> bool:
    return _lower(value) in {"1", "true", "t", "yes", "y"}


def _normalize_case_id(value: Any) -> str:
    text = _stringify(value)
    if not text:
        return ""
    if text.startswith("openai_gsm8k_"):
        return "gsm8k_" + text.split("openai_gsm8k_", 1)[1]
    return text


def _stable_split_group(problem_id: str) -> str:
    if not problem_id:
        return "train"
    bucket = int(hashlib.sha256(problem_id.encode("utf-8")).hexdigest()[:8], 16) % 20
    if bucket < 14:
        return "train"
    if bucket < 17:
        return "val"
    return "test"


def _stable_row_id(problem_id: str, candidate_source: str, candidate_answer: str, candidate_equation: str, source_path: str, source_row_index: int) -> str:
    seed = "|".join(
        [
            problem_id,
            candidate_source,
            candidate_answer,
            candidate_equation,
            source_path,
            str(source_row_index),
        ]
    )
    return "rrseed_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_idx, line in enumerate(handle):
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception as exc:
                rows.append(
                    {
                        "__malformed__": True,
                        "__malformed_reason__": f"json_error:{type(exc).__name__}",
                        "__source_path__": str(path),
                        "__source_format__": "jsonl",
                        "__source_row_index__": line_idx,
                        "__raw_text__": raw,
                    }
                )
                continue
            if isinstance(payload, dict):
                payload["__source_path__"] = str(path)
                payload["__source_format__"] = "jsonl"
                payload["__source_row_index__"] = line_idx
                rows.append(payload)
            else:
                rows.append(
                    {
                        "__malformed__": True,
                        "__malformed_reason__": "non_dict_payload",
                        "__source_path__": str(path),
                        "__source_format__": "jsonl",
                        "__source_row_index__": line_idx,
                        "__raw_text__": raw,
                    }
                )
    return rows


def _load_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_idx, row in enumerate(reader):
            payload = dict(row)
            payload["__source_path__"] = str(path)
            payload["__source_format__"] = "csv"
            payload["__source_row_index__"] = row_idx
            rows.append(payload)
    return rows


def _load_source_rows(paths: Iterable[Path], *, source_format: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    excluded_files: list[dict[str, Any]] = []
    for path in paths:
        suffix = path.suffix.lower()
        if suffix not in ALLOWED_INPUT_SUFFIXES:
            excluded_files.append(
                {
                    "__unsupported__": True,
                    "row_id": _stable_row_id("", "unsupported", "", "", str(path), 0),
                    "problem_id": "",
                    "case_id": "",
                    "split_group_id": "train",
                    "dataset_name": path.stem or "unknown",
                    "question": "",
                    "candidate_source": "unsupported_source",
                    "candidate_trace": "",
                    "candidate_equation": "",
                    "candidate_answer": "",
                    "target_phrase": "",
                    "target_semantic_type": "unknown",
                    "source_facts": [],
                    "quantities": [],
                    "candidate_relations": [],
                    "formula_executable_ok": None,
                    "relation_ready_label": "unknown",
                    "first_error_axis": "unknown",
                    "exclusion_reason": "unsupported_source_format",
                    "label_source": "seed_builder_v0",
                    "provenance": {
                        "source_path": str(path),
                        "source_format": source_format,
                        "source_row_index": None,
                        "source_keys": [],
                    },
                }
            )
            continue
        if suffix == ".jsonl":
            rows.extend(_load_jsonl(path))
        else:
            rows.extend(_load_csv(path))
    return rows, excluded_files


def _first_nonempty(row: dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = _stringify(row.get(key))
        if value:
            return value
    return ""


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [f"{_stringify(k)}: {_stringify(v)}" for k, v in value.items()]
    text = _stringify(value)
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [f"{_stringify(k)}: {_stringify(v)}" for k, v in parsed.items()]
    if "\n" in text:
        return [part.strip() for part in text.splitlines() if part.strip()]
    if ";" in text:
        return [part.strip() for part in text.split(";") if part.strip()]
    return [text]


def _extract_question(row: dict[str, Any]) -> str:
    return _first_nonempty(
        row,
        [
            "question",
            "problem_statement",
            "prompt",
            "problem",
            "input_question",
            "query",
            "text",
        ],
    )


def _extract_candidate_trace(row: dict[str, Any]) -> str:
    trace = _first_nonempty(
        row,
        [
            "candidate_trace",
            "trace",
            "trace_text",
            "reasoning_trace",
            "candidate_reasoning",
        ],
    )
    if trace:
        return trace
    summary = row.get("action_trace_summary")
    if isinstance(summary, dict):
        excerpt = summary.get("trace_excerpt") or []
        if isinstance(excerpt, list):
            parts = []
            for item in excerpt:
                if not isinstance(item, dict):
                    continue
                text = _first_nonempty(item, ["reasoning_text", "extracted_answer", "text"])
                if text:
                    parts.append(text)
            if parts:
                return "\n".join(parts)
        return _first_nonempty(summary, ["short_diagnosis", "selection_reason", "failure_family", "likely_mismatch_subtype"])
    return ""


def _extract_candidate_equation(row: dict[str, Any]) -> str:
    return _first_nonempty(
        row,
        [
            "candidate_equation",
            "equation",
            "solution_formula",
            "formula",
            "candidate_formula",
        ],
    )


def _extract_candidate_answer(row: dict[str, Any]) -> str:
    return _first_nonempty(
        row,
        [
            "candidate_answer",
            "answer",
            "final_answer",
            "normalized_answer",
            "executable_final_answer",
            "fa",
            "model_final_prediction",
            "predicted",
        ],
    )


def _extract_target_phrase(row: dict[str, Any], question: str) -> str:
    explicit = _first_nonempty(row, ["target_phrase", "target_text", "target", "target_variable"])
    if explicit:
        return explicit
    q = question.lower()
    for prefix in ("how many ", "how much ", "what is the ", "what are the ", "what's the "):
        if prefix in q:
            tail = q.split(prefix, 1)[1]
            tail = re.split(r"[?.!;:]", tail, maxsplit=1)[0]
            return tail.strip(" ,")
    if "percentage" in q or "percent" in q or "%" in q:
        return "percentage"
    if "ratio" in q:
        return "ratio"
    return ""


def _extract_target_semantic_type(row: dict[str, Any], question: str, target_phrase: str) -> str:
    explicit = _first_nonempty(row, ["target_semantic_type", "semantic_type", "target_type"])
    if explicit:
        return explicit
    joined = f"{question} {target_phrase}".lower()
    for semantic_type, cues in TARGET_TYPE_KEYWORDS.items():
        if any(cue in joined for cue in cues):
            return semantic_type
    return "unknown"


def _extract_source_facts(row: dict[str, Any]) -> list[Any]:
    value = row.get("source_facts")
    if value is None:
        value = row.get("facts") or row.get("supporting_facts") or row.get("evidence_facts")
    return _coerce_list(value)


def _extract_quantities(row: dict[str, Any]) -> list[Any]:
    value = row.get("quantities")
    if value is None:
        value = row.get("numbers") or row.get("numerical_values") or row.get("candidate_variables")
    return _coerce_list(value)


def _extract_candidate_relations(row: dict[str, Any]) -> list[Any]:
    value = row.get("candidate_relations")
    if value is None:
        value = row.get("relations")
    return _coerce_list(value)


def _extract_formula_executable_ok(row: dict[str, Any]) -> bool | None:
    for key in ("formula_executable_ok", "formula_eval_ok", "equation_eval_ok"):
        if key in row:
            return _safe_bool(row.get(key))
    return None


def _looks_gold_inconsistent(row: dict[str, Any], source_path: str, dataset_name: str) -> bool:
    prompt_inconsistent = any(
        _safe_bool(row.get(key))
        for key in (
            "prompt_gold_inconsistent_flag",
            "prompt_gold_inconsistent",
            "gold_inconsistent",
            "gold_inconsistent_flag",
            "seed_prompt_gold_inconsistent",
        )
    )
    prompt_consistency = _lower(row.get("prompt_gold_consistency") or row.get("prompt_gold_consistency_flag"))
    if prompt_inconsistent or prompt_consistency == "inconsistent":
        return True
    blob = " ".join([source_path, dataset_name, _stringify(row.get("split")), _stringify(row.get("split_group_id"))]).lower()
    return any(marker in blob for marker in ("live_20cases", "gold_absent", "wrong_supported_consensus", "eval_holdout"))


def _detect_exclusion_reason(row: dict[str, Any], source_path: str, dataset_name: str) -> str | None:
    if row.get("__unsupported__"):
        return "unsupported_source_format"
    if row.get("__malformed__"):
        return "malformed_row"
    if not _extract_question(row):
        return "missing_question"
    if _looks_gold_inconsistent(row, source_path, dataset_name):
        return "gold_inconsistent_source"
    if not (_extract_candidate_trace(row) or _extract_candidate_equation(row)):
        return "missing_candidate_trace_and_equation"
    if not _extract_candidate_answer(row):
        return "empty_candidate_answer"
    return None


def _normalized_row(
    row: dict[str, Any],
    *,
    source_path: str,
    source_format: str,
    source_row_index: int | None,
    include_excluded: bool,
) -> dict[str, Any]:
    source_path_obj = Path(source_path)
    source_keys = sorted(k for k in row.keys() if not str(k).startswith("__"))
    question = _extract_question(row)
    case_id = _stringify(row.get("case_id") or row.get("problem_id") or row.get("example_id") or row.get("id"))
    problem_id = _normalize_case_id(case_id) or _normalize_case_id(row.get("problem_id") or row.get("example_id")) or f"{source_path_obj.stem}:{source_row_index if source_row_index is not None else 0}"
    dataset_name = _first_nonempty(row, ["dataset_name", "dataset", "source_dataset"]) or source_path_obj.stem or "unknown"
    candidate_source = _first_nonempty(row, ["candidate_source", "source_family", "source", "provenance_type", "provenance_source", "method"]) or source_path_obj.stem or "unknown"
    candidate_trace = _extract_candidate_trace(row)
    candidate_equation = _extract_candidate_equation(row)
    candidate_answer = _extract_candidate_answer(row)
    target_phrase = _extract_target_phrase(row, question)
    target_semantic_type = _extract_target_semantic_type(row, question, target_phrase)
    source_facts = _extract_source_facts(row)
    quantities = _extract_quantities(row)
    candidate_relations = _extract_candidate_relations(row)
    formula_executable_ok = _extract_formula_executable_ok(row)
    gold_answer = _first_nonempty(row, ["gold_answer", "gold", "correct_answer"])
    split_group_id = _stable_split_group(problem_id)
    label_source = _first_nonempty(row, ["label_source", "relation_ready_source"]) or "seed_builder_v0"
    exclusion_reason = _detect_exclusion_reason(row, source_path, dataset_name)
    row_id = _stable_row_id(problem_id, candidate_source, candidate_answer, candidate_equation, source_path, source_row_index or 0)

    normalized: dict[str, Any] = {
        "row_id": row_id,
        "problem_id": problem_id,
        "case_id": case_id,
        "split_group_id": split_group_id,
        "dataset_name": dataset_name,
        "question": question,
        "candidate_id": _first_nonempty(row, ["candidate_id", "id", "example_id"]),
        "candidate_source": candidate_source,
        "candidate_trace": candidate_trace,
        "candidate_equation": candidate_equation,
        "candidate_answer": candidate_answer,
        "target_phrase": target_phrase,
        "target_semantic_type": target_semantic_type,
        "source_facts": source_facts,
        "quantities": quantities,
        "candidate_relations": candidate_relations,
        "formula_executable_ok": formula_executable_ok,
        "relation_ready_label": "unknown",
        "first_error_axis": "unknown",
        "exclusion_reason": exclusion_reason or "",
        "label_source": label_source,
        "provenance": {
            "source_path": source_path,
            "source_format": source_format,
            "source_row_index": source_row_index,
            "source_keys": source_keys,
        },
    }
    if gold_answer:
        normalized["gold_answer"] = gold_answer
    return normalized


def build_seed_dataset(
    *,
    input_jsonl: list[Path],
    input_csv: list[Path],
    output_jsonl: Path,
    max_rows: int | None = None,
    include_excluded: bool = False,
) -> dict[str, Any]:
    source_rows: list[dict[str, Any]] = []
    jsonl_rows, jsonl_excluded = _load_source_rows(input_jsonl, source_format="jsonl")
    csv_rows, csv_excluded = _load_source_rows(input_csv, source_format="csv")
    source_rows.extend(jsonl_rows)
    source_rows.extend(csv_rows)
    source_rows.extend(jsonl_excluded)
    source_rows.extend(csv_excluded)

    emitted_rows: list[dict[str, Any]] = []
    included_count = 0
    written_included_count = 0
    excluded_count = 0
    reason_counts = Counter()
    candidate_source_counts = Counter()
    missing_field_counts = Counter()

    for row in source_rows:
        source_path = _stringify(row.get("__source_path__") or "")
        source_format = _stringify(row.get("__source_format__") or "")
        source_row_index = row.get("__source_row_index__")
        if row.get("__malformed__"):
            reason = "malformed_row"
            normalized = _normalized_row(
                row,
                source_path=source_path,
                source_format=source_format,
                source_row_index=source_row_index if isinstance(source_row_index, int) else None,
                include_excluded=True,
            )
            normalized["exclusion_reason"] = reason
            reason_counts[reason] += 1
            excluded_count += 1
            if include_excluded:
                emitted_rows.append(normalized)
            continue

        question = _extract_question(row)
        candidate_trace = _extract_candidate_trace(row)
        candidate_equation = _extract_candidate_equation(row)
        candidate_answer = _extract_candidate_answer(row)
        dataset_name = _first_nonempty(row, ["dataset_name", "dataset", "source_dataset"]) or Path(source_path).stem or "unknown"
        if not question:
            missing_field_counts["missing_question"] += 1
        if not candidate_trace:
            missing_field_counts["missing_candidate_trace"] += 1
        if not candidate_equation:
            missing_field_counts["missing_candidate_equation"] += 1
        if not candidate_answer:
            missing_field_counts["missing_candidate_answer"] += 1

        normalized = _normalized_row(
            row,
            source_path=source_path,
            source_format=source_format,
            source_row_index=source_row_index if isinstance(source_row_index, int) else None,
            include_excluded=include_excluded,
        )
        exclusion_reason = _stringify(normalized.get("exclusion_reason"))
        if exclusion_reason:
            excluded_count += 1
            reason_counts[exclusion_reason] += 1
        else:
            candidate_source_counts[_stringify(normalized.get("candidate_source"))] += 1
            included_count += 1

        if exclusion_reason:
            if include_excluded:
                emitted_rows.append(normalized)
            continue
        if max_rows is not None and written_included_count >= max_rows:
            continue
        emitted_rows.append(normalized)
        written_included_count += 1

    report_path = output_jsonl.with_name(output_jsonl.stem + ".report.md")
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8") as handle:
        for row in emitted_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "input_row_count": len(source_rows),
        "emitted_row_count": len(emitted_rows),
        "excluded_row_count": excluded_count,
        "truncated_emitted_count": max(0, included_count - written_included_count) if max_rows is not None else 0,
        "exclusion_reason_counts": dict(reason_counts),
        "candidate_source_counts": dict(candidate_source_counts),
        "missing_field_counts": dict(missing_field_counts),
        "included_examples": [row for row in emitted_rows if not _stringify(row.get("exclusion_reason"))][:5],
    }

    report_lines = [
        f"# {EXPERIMENT_ID} report",
        "",
        f"- input rows: `{summary['input_row_count']}`",
        f"- emitted rows: `{summary['emitted_row_count']}`",
        f"- excluded rows: `{summary['excluded_row_count']}`",
        f"- exclusion reason counts: `{summary['exclusion_reason_counts']}`",
        f"- candidate source counts: `{summary['candidate_source_counts']}`",
        f"- missing-field counts: `{summary['missing_field_counts']}`",
        "",
        "## Example emitted rows",
    ]
    included_examples = [row for row in emitted_rows if not _stringify(row.get("exclusion_reason"))]
    if included_examples:
        for row in included_examples[:5]:
            report_lines.append(
                f"- `{row['row_id']}` case=`{row['case_id']}` source=`{row['candidate_source']}` "
                f"split=`{row['split_group_id']}` exclusion=`{row['exclusion_reason'] or 'none'}`"
            )
    else:
        report_lines.append("- none")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", nargs="*", type=Path, default=[])
    parser.add_argument("--input-csv", nargs="*", type=Path, default=[])
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--include-excluded", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    return build_seed_dataset(
        input_jsonl=list(args.input_jsonl),
        input_csv=list(args.input_csv),
        output_jsonl=args.output_jsonl,
        max_rows=args.max_rows,
        include_excluded=args.include_excluded,
    )


if __name__ == "__main__":
    main()
