#!/usr/bin/env python3
"""Extract clean positive RelationReady seed rows for synthetic corruption."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "relationready_seed_pool"
DEFAULT_ALLOWED_SPLITS = ["train", "val", "test"]
FORMULA_KEYS = ["candidate_formula", "solution_formula", "formula_text", "equation", "formula"]
POSITIVE_LABEL_KEYS = ["relation_ready_label", "accept", "is_positive"]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _safe_bool(value: Any) -> bool:
    return _stringify(value).lower() in {"1", "true", "t", "yes", "y"}


def _normalize_case_id(value: Any) -> str:
    text = _stringify(value)
    if not text:
        return ""
    if text.startswith("openai_gsm8k_"):
        return "gsm8k_" + text.split("openai_gsm8k_", 1)[1]
    return text


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _load_jsonl(path)
    if suffix == ".csv":
        return _load_csv(path)
    raise ValueError(f"unsupported input format: {path.suffix}")


def _row_formula(row: dict[str, Any]) -> str:
    for key in FORMULA_KEYS:
        value = _stringify(row.get(key))
        if value:
            return value
    return ""


def _row_split(row: dict[str, Any]) -> str:
    for key in ("split", "suggested_split", "dataset_split", "holdout_split"):
        value = _stringify(row.get(key))
        if value:
            return value
    return ""


def _is_positive_row(row: dict[str, Any]) -> bool:
    for key in POSITIVE_LABEL_KEYS:
        if _safe_bool(row.get(key)):
            return True
    return False


def _is_prompt_gold_inconsistent(row: dict[str, Any]) -> bool:
    return any(
        _safe_bool(row.get(key))
        for key in ("prompt_gold_inconsistent_flag", "prompt_gold_inconsistent", "seed_prompt_gold_inconsistent")
    )


def _allowed_split(row: dict[str, Any], allowed_splits: set[str]) -> bool:
    split = _row_split(row)
    if not split:
        return True
    return split in allowed_splits


def _read_exclusion_file(path: Path) -> set[str]:
    excluded: set[str] = set()
    if not path.exists():
        return excluded
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        for row in _load_jsonl(path):
            value = _normalize_case_id(row.get("case_id"))
            if value:
                excluded.add(value)
    elif suffix == ".csv":
        for row in _load_csv(path):
            value = _normalize_case_id(row.get("case_id"))
            if value:
                excluded.add(value)
    else:
        for line in path.read_text(encoding="utf-8").splitlines():
            value = _normalize_case_id(line)
            if value:
                excluded.add(value)
    return excluded


def _selection_reason(row: dict[str, Any]) -> str:
    if _is_prompt_gold_inconsistent(row):
        return "prompt_gold_inconsistent"
    if not _is_positive_row(row):
        return "not_positive"
    if not _row_formula(row):
        return "missing_formula"
    return "clean_positive"


def extract_seed_rows(
    rows: list[dict[str, Any]],
    *,
    allowed_splits: list[str],
    excluded_case_ids: set[str],
    max_per_case: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    allowed = set(allowed_splits)
    ranked: dict[str, list[dict[str, Any]]] = {}
    skipped_reasons = Counter()

    for row in rows:
        case_id = _normalize_case_id(row.get("case_id"))
        if not case_id:
            skipped_reasons["missing_case_id"] += 1
            continue
        if case_id in excluded_case_ids:
            skipped_reasons["excluded_case_id"] += 1
            continue
        if not _allowed_split(row, allowed):
            skipped_reasons["disallowed_split"] += 1
            continue
        reason = _selection_reason(row)
        if reason != "clean_positive":
            skipped_reasons[reason] += 1
            continue
        candidate_formula = _row_formula(row)
        if not candidate_formula:
            skipped_reasons["missing_formula"] += 1
            continue
        normalized_case_id = _normalize_case_id(row.get("normalized_case_id") or case_id)
        candidate_id = _stringify(row.get("candidate_id") or f"{case_id}:seed")
        selected = {
            "case_id": case_id,
            "normalized_case_id": normalized_case_id,
            "candidate_id": candidate_id,
            "candidate_source": _stringify(row.get("candidate_source")),
            "candidate_formula": candidate_formula,
            "candidate_text": _stringify(row.get("candidate_text") or row.get("question") or ""),
            "relation_ready_label": True,
            "relation_ready_source": _stringify(row.get("relation_ready_source") or "clean_positive_seed"),
            "relation_ready_confidence": _stringify(row.get("label_confidence") or "high"),
            "prompt_gold_inconsistent_flag": False,
            "split": _row_split(row) or "train",
            "seed_status": "selected_clean_positive",
            "seed_reason": "clean_positive",
            "seed_origin_split": _row_split(row) or "",
        }
        ranked.setdefault(case_id, []).append(selected)

    rows_out: list[dict[str, Any]] = []
    for case_id in sorted(ranked):
        case_rows = sorted(
            ranked[case_id],
            key=lambda row: (
                _stringify(row.get("candidate_source")),
                _stringify(row.get("candidate_id")),
                _stringify(row.get("candidate_formula")),
            ),
        )
        rows_out.extend(case_rows[:max_per_case])

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "input_row_count": len(rows),
        "selected_row_count": len(rows_out),
        "selected_case_count": len({row["normalized_case_id"] for row in rows_out}),
        "selected_candidate_source_counts": dict(Counter(_stringify(row.get("candidate_source")) for row in rows_out)),
        "selected_split_counts": dict(Counter(_stringify(row.get("split")) for row in rows_out)),
        "skipped_reason_counts": dict(skipped_reasons),
        "allowed_splits": allowed_splits,
        "excluded_case_id_count": len(excluded_case_ids),
    }
    return rows_out, summary


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_id",
        "normalized_case_id",
        "candidate_id",
        "candidate_source",
        "candidate_formula",
        "candidate_text",
        "relation_ready_label",
        "relation_ready_source",
        "relation_ready_confidence",
        "prompt_gold_inconsistent_flag",
        "split",
        "seed_status",
        "seed_reason",
        "seed_origin_split",
    ]
    extras = sorted({key for row in rows for key in row.keys() if key not in fieldnames})
    fieldnames.extend(extras)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _write_report(path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        f"# {EXPERIMENT_ID} report",
        "",
        f"- input rows: `{summary['input_row_count']}`",
        f"- selected rows: `{summary['selected_row_count']}`",
        f"- selected cases: `{summary['selected_case_count']}`",
        f"- selected sources: `{summary['selected_candidate_source_counts']}`",
        f"- selected splits: `{summary['selected_split_counts']}`",
        f"- skipped reasons: `{summary['skipped_reason_counts']}`",
        "",
        "## Preview",
    ]
    for row in rows[:5]:
        lines.append(
            f"- `{row['candidate_id']}` case=`{row['case_id']}` formula=`{row['candidate_formula']}` "
            f"split=`{row['split']}`"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _default_out_dir() -> Path:
    return Path.cwd() / "outputs" / f"{EXPERIMENT_ID}"


def build_seed_pool(args: argparse.Namespace) -> dict[str, Any]:
    rows = load_rows(args.input)
    excluded_case_ids = set(_normalize_case_id(item) for item in args.exclude_case_ids)
    for path in args.exclude_case_ids_file:
        excluded_case_ids.update(_read_exclusion_file(path))
    selected_rows, summary = extract_seed_rows(
        rows,
        allowed_splits=args.allowed_splits,
        excluded_case_ids=excluded_case_ids,
        max_per_case=args.max_per_case,
    )
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "seed_rows.jsonl", selected_rows)
    _write_csv(out_dir / "seed_rows.csv", selected_rows)
    _write_json(out_dir / "seed_summary.json", summary)
    _write_report(out_dir / "seed_report.md", summary, selected_rows)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=_default_out_dir())
    parser.add_argument("--allowed-splits", type=str, default=",".join(DEFAULT_ALLOWED_SPLITS))
    parser.add_argument("--exclude-case-ids", type=str, default="", help="Comma-separated case IDs to exclude")
    parser.add_argument(
        "--exclude-case-ids-file",
        type=Path,
        action="append",
        default=[],
        help="Path to newline/CSV/JSONL file containing case_id values to exclude",
    )
    parser.add_argument("--max-per-case", type=int, default=1)
    args = parser.parse_args(argv)
    args.allowed_splits = [item.strip() for item in args.allowed_splits.split(",") if item.strip()]
    args.exclude_case_ids = [item.strip() for item in args.exclude_case_ids.split(",") if item.strip()]
    return args


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    return build_seed_pool(args)


if __name__ == "__main__":
    main()
