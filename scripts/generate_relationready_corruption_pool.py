#!/usr/bin/env python3
"""Generate a local-only synthetic RelationReady corruption pool."""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import synthetic_corruption_scaffold as scaffold  # noqa: E402

EXPERIMENT_ID = "relationready_corruption_pool"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

OPERATOR_ALIASES = {
    "var_rebind_swap": "var_rebind_swap",
    "unit_scale": "unit_scale_inversion",
    "arithmetic_perturb": "arithmetic_perturbation",
    "relation_delete": "relation_deletion",
    "final_op_omit": "final_after_process_omit",
}

FIRST_ERROR_AXIS = {
    "var_rebind_swap": "wrong_target_variable",
    "unit_scale": "unit_scale_error",
    "arithmetic_perturb": "arithmetic_error",
    "relation_delete": "wrong_relation",
    "final_op_omit": "wrong_process_state",
}

DEFAULT_OPERATORS = list(OPERATOR_ALIASES.keys())
REQUIRED_OUTPUT_FIELDS = [
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


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _safe_bool(value: Any) -> bool:
    text = _stringify(value).lower()
    return text in {"1", "true", "t", "yes", "y"}


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


def load_seed_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _load_jsonl(path)
    if suffix == ".csv":
        return _load_csv(path)
    raise ValueError(f"unsupported seed format: {path.suffix}")


def _seed_formula(row: dict[str, Any]) -> str:
    for key in ("candidate_formula", "solution_formula", "formula", "equation", "final_formula"):
        value = _stringify(row.get(key))
        if value:
            return value
    return ""


def _is_prompt_gold_inconsistent(row: dict[str, Any]) -> bool:
    return any(
        _safe_bool(row.get(key))
        for key in (
            "prompt_gold_inconsistent_flag",
            "prompt_gold_inconsistent",
            "seed_prompt_gold_inconsistent",
        )
    )


def _operator_catalog() -> dict[str, tuple[str, Any]]:
    return {name: (name, fn) for name, fn in scaffold.CORRUPTORS}


def _apply_operator(formula: str, operator: str, seed: int) -> tuple[str, str] | None:
    catalog = _operator_catalog()
    internal_name = OPERATOR_ALIASES.get(operator)
    if internal_name is None:
        raise ValueError(f"unknown operator: {operator}")
    if internal_name not in catalog:
        raise ValueError(f"operator not supported by scaffold: {operator}")
    _, fn = catalog[internal_name]
    expr_ast = scaffold._try_parse(formula)  # noqa: SLF001
    if expr_ast is None:
        return None
    rnd = random.Random(seed)
    new_ast = fn(deepcopy(expr_ast), rnd)
    if new_ast is None:
        return None
    corrupted = scaffold._ast_to_source(new_ast)  # noqa: SLF001
    if not corrupted:
        return None
    if scaffold._try_parse(corrupted) is None:  # noqa: SLF001
        return None
    return internal_name, corrupted


def _build_output_row(
    seed_row: dict[str, Any],
    *,
    operator: str,
    corrupted_formula: str,
    variant_index: int,
    parent_candidate_id: str,
    original_formula: str,
) -> dict[str, Any]:
    case_id = _stringify(seed_row.get("case_id"))
    normalized_case_id = _normalize_case_id(seed_row.get("normalized_case_id") or case_id)
    candidate_source = "synthetic_corrupt"
    candidate_id = f"{parent_candidate_id}:{operator}:{variant_index}"
    return {
        "case_id": case_id,
        "normalized_case_id": normalized_case_id,
        "parent_candidate_id": parent_candidate_id,
        "candidate_id": candidate_id,
        "candidate_source": candidate_source,
        "corruption_operator": operator,
        "corruption_status": "generated",
        "synthetic_negative": True,
        "relation_ready_label": "not_ready",
        "first_error_axis": FIRST_ERROR_AXIS[operator],
        "label_source": "synthetic_corruption",
        "label_confidence": "high",
        "original_formula": original_formula,
        "corrupted_formula": corrupted_formula,
        "qa_trivial_flag": False,
        "qa_broken_formula_flag": False,
        "qa_notes": "",
        "seed_prompt_gold_inconsistent_flag": _is_prompt_gold_inconsistent(seed_row),
        "training_eligibility": "eligible",
    }


def generate_corruption_pool_rows(
    seed_rows: list[dict[str, Any]],
    *,
    operators: list[str],
    max_per_row: int,
    seed: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skipped_prompt_gold_inconsistent: list[str] = []
    skipped_missing_formula: list[str] = []
    by_operator = Counter()

    for seed_index, seed_row in enumerate(seed_rows):
        case_id = _stringify(seed_row.get("case_id"))
        parent_candidate_id = _stringify(seed_row.get("candidate_id") or f"seed:{case_id}")
        original_formula = _seed_formula(seed_row)
        if _is_prompt_gold_inconsistent(seed_row):
            skipped_prompt_gold_inconsistent.append(case_id)
            continue
        if not original_formula:
            skipped_missing_formula.append(case_id)
            continue

        created = 0
        attempts = 0
        max_attempts = max(1, max_per_row * max(1, len(operators)))
        while created < max_per_row and attempts < max_attempts:
            operator = operators[attempts % len(operators)]
            operator_seed = seed + seed_index * 1000 + attempts
            applied = _apply_operator(original_formula, operator, operator_seed)
            attempts += 1
            if applied is None:
                continue
            _, corrupted_formula = applied
            row = _build_output_row(
                seed_row,
                operator=operator,
                corrupted_formula=corrupted_formula,
                variant_index=created,
                parent_candidate_id=parent_candidate_id,
                original_formula=original_formula,
            )
            rows.append(row)
            by_operator[operator] += 1
            created += 1

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "seed_row_count": len(seed_rows),
        "eligible_seed_row_count": len(seed_rows) - len(skipped_prompt_gold_inconsistent) - len(skipped_missing_formula),
        "skipped_prompt_gold_inconsistent_count": len(skipped_prompt_gold_inconsistent),
        "skipped_missing_formula_count": len(skipped_missing_formula),
        "row_count": len(rows),
        "operator_counts": dict(by_operator),
        "skipped_prompt_gold_inconsistent_case_ids": skipped_prompt_gold_inconsistent,
        "skipped_missing_formula_case_ids": skipped_missing_formula,
        "corruption_status_counts": dict(Counter(row["corruption_status"] for row in rows)),
        "training_eligibility_counts": dict(Counter(row["training_eligibility"] for row in rows)),
    }
    return rows, summary


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
    fieldnames = list(REQUIRED_OUTPUT_FIELDS)
    extras = sorted({key for row in rows for key in row.keys() if key not in fieldnames})
    fieldnames.extend(extras)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _write_report(path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    preview = rows[:5]
    lines = [
        f"# {EXPERIMENT_ID} report",
        "",
        f"- seed rows: `{summary['seed_row_count']}`",
        f"- generated rows: `{summary['row_count']}`",
        f"- skipped prompt/gold inconsistent: `{summary['skipped_prompt_gold_inconsistent_count']}`",
        f"- skipped missing formula: `{summary['skipped_missing_formula_count']}`",
        f"- operator counts: `{summary['operator_counts']}`",
        "",
        "## Preview",
    ]
    for row in preview:
        lines.append(
            f"- `{row['candidate_id']}` operator=`{row['corruption_operator']}` "
            f"axis=`{row['first_error_axis']}` formula=`{row['corrupted_formula']}`"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _default_out_dir() -> Path:
    return Path.cwd() / "outputs" / f"{EXPERIMENT_ID}_{_TS}"


def build_pool(args: argparse.Namespace) -> dict[str, Any]:
    seed_rows = load_seed_rows(args.input)
    rows, summary = generate_corruption_pool_rows(
        seed_rows,
        operators=args.operators,
        max_per_row=args.max_per_row,
        seed=args.seed,
    )
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "corruption_pool_rows.jsonl", rows)
    _write_csv(out_dir / "corruption_pool_rows.csv", rows)
    _write_json(out_dir / "corruption_pool_summary.json", summary)
    _write_report(out_dir / "corruption_pool_report.md", summary, rows)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=_default_out_dir())
    parser.add_argument(
        "--operators",
        type=str,
        default=",".join(DEFAULT_OPERATORS),
        help="Comma-separated list of operator aliases",
    )
    parser.add_argument("--max-per-row", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    args.operators = [item.strip() for item in args.operators.split(",") if item.strip()]
    unknown = [op for op in args.operators if op not in OPERATOR_ALIASES]
    if unknown:
        raise ValueError(f"unknown operators: {unknown}")
    return args


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    return build_pool(args)


if __name__ == "__main__":
    main()
