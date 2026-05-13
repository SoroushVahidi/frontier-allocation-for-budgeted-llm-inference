#!/usr/bin/env python3
"""Deterministic QA checks for RelationReady synthetic corruption pools."""
from __future__ import annotations

import argparse
import ast
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "relationready_corruption_pool_qa"
REQUIRED_FIELDS = [
    "case_id",
    "normalized_case_id",
    "parent_candidate_id",
    "candidate_id",
    "candidate_source",
    "corruption_operator",
    "corruption_status",
    "synthetic_negative",
    "relation_ready_label",
    "first_error_axis",
    "label_source",
    "label_confidence",
    "original_formula",
    "corrupted_formula",
    "qa_trivial_flag",
    "qa_broken_formula_flag",
    "qa_notes",
]
FORBIDDEN_GOLD_KEYS = {
    "gold",
    "gold_answer",
    "correct_answer",
    "gold_value",
    "gold_value_posthoc",
}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _safe_bool(value: Any) -> bool:
    return _stringify(value).lower() in {"1", "true", "t", "yes", "y"}


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


def _parses_formula(formula: str) -> bool:
    if not formula:
        return False
    try:
        ast.parse(formula, mode="eval")
        return True
    except SyntaxError:
        return False


def _required_field_issues(row: dict[str, Any]) -> list[str]:
    issues = [field for field in REQUIRED_FIELDS if _stringify(row.get(field)) == "" and field != "qa_notes"]
    return issues


def _gold_field_issues(row: dict[str, Any]) -> list[str]:
    issues = []
    for key in row:
        if key in FORBIDDEN_GOLD_KEYS and _stringify(row.get(key)):
            issues.append(key)
    return issues


def qa_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out: list[dict[str, Any]] = []
    trivial = 0
    broken = 0
    missing = 0
    prompt_gold_not_for_training = 0
    gold_field_violations = 0

    for row in rows:
        checked = dict(row)
        issues: list[str] = []
        required_issues = _required_field_issues(checked)
        if required_issues:
            issues.append(f"missing_required:{','.join(sorted(required_issues))}")
            missing += 1

        gold_issues = _gold_field_issues(checked)
        if gold_issues:
            issues.append(f"gold_fields_present:{','.join(sorted(gold_issues))}")
            gold_field_violations += 1

        original = _stringify(checked.get("original_formula"))
        corrupted = _stringify(checked.get("corrupted_formula"))
        if original and corrupted and original == corrupted:
            issues.append("formula_unchanged")
            trivial += 1
            checked["qa_trivial_flag"] = True

        if corrupted and not _parses_formula(corrupted):
            issues.append("broken_formula")
            broken += 1
            checked["qa_broken_formula_flag"] = True

        if _safe_bool(checked.get("seed_prompt_gold_inconsistent_flag")) or _safe_bool(
            checked.get("prompt_gold_inconsistent_flag")
        ):
            checked["training_eligibility"] = "not_for_training"
            prompt_gold_not_for_training += 1
            issues.append("prompt_gold_inconsistent_not_for_training")
        elif issues:
            checked["training_eligibility"] = "not_for_training"
        else:
            checked["training_eligibility"] = _stringify(checked.get("training_eligibility") or "eligible")

        checked["qa_pass"] = not issues
        checked["qa_issues"] = issues
        checked["qa_notes"] = "; ".join(issues)
        out.append(checked)

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "row_count": len(rows),
        "pass_count": sum(1 for row in out if row["qa_pass"]),
        "fail_count": sum(1 for row in out if not row["qa_pass"]),
        "missing_required_count": missing,
        "trivial_formula_count": trivial,
        "broken_formula_count": broken,
        "prompt_gold_inconsistent_not_for_training_count": prompt_gold_not_for_training,
        "gold_field_violation_count": gold_field_violations,
        "training_eligibility_counts": dict(Counter(row["training_eligibility"] for row in out)),
    }
    return out, summary


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        f"# {EXPERIMENT_ID} report",
        "",
        f"- rows: `{summary['row_count']}`",
        f"- pass: `{summary['pass_count']}`",
        f"- fail: `{summary['fail_count']}`",
        f"- missing required: `{summary['missing_required_count']}`",
        f"- trivial formulas: `{summary['trivial_formula_count']}`",
        f"- broken formulas: `{summary['broken_formula_count']}`",
        f"- prompt/gold inconsistent not-for-training: `{summary['prompt_gold_inconsistent_not_for_training_count']}`",
        f"- gold field violations: `{summary['gold_field_violation_count']}`",
        "",
        "## Preview",
    ]
    for row in rows[:5]:
        lines.append(
            f"- `{row['candidate_id']}` pass=`{row['qa_pass']}` "
            f"eligible=`{row['training_eligibility']}` notes=`{row['qa_notes']}`"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _default_out_dir() -> Path:
    return Path.cwd() / "outputs" / f"{EXPERIMENT_ID}"


def build_qa(args: argparse.Namespace) -> dict[str, Any]:
    rows = load_rows(args.input)
    qaed_rows, summary = qa_rows(rows)
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "qa_rows.jsonl", qaed_rows)
    _write_json(out_dir / "qa_summary.json", summary)
    _write_report(out_dir / "qa_report.md", summary, qaed_rows)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=_default_out_dir())
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    return build_qa(args)


if __name__ == "__main__":
    main()
