"""Shared helpers for offline failure-analysis scripts."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from experiments.build_failure_feature_table import (
    CANONICAL_DEFAULT_INPUTS,
    METHOD_FRONTIER,
)

EXTERNAL_METHODS = (
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
)


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    out = Path(path)
    if out.exists():
        raise FileExistsError(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def write_json(path: str | Path, payload: Any) -> None:
    out = Path(path)
    if out.exists():
        raise FileExistsError(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=True)
        handle.write("\n")


def write_text(path: str | Path, text: str) -> None:
    out = Path(path)
    if out.exists():
        raise FileExistsError(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def write_csv(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    out = Path(path)
    if out.exists():
        raise FileExistsError(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def maybe_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def maybe_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return parsed
    return []


def load_feature_rows(path: str | Path) -> list[dict[str, Any]]:
    return load_jsonl(path)


def group_rows_by_source_seed(rows: list[dict[str, Any]]) -> dict[tuple[str, Any], list[dict[str, Any]]]:
    grouped: dict[tuple[str, Any], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("source_id")), row.get("seed"))].append(row)
    return dict(grouped)


def compute_group_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    return {
        "row_count": n,
        "fta_accuracy": (sum(bool(r.get("fta_correct")) for r in rows) / n) if n else None,
        "effective_fix2_action_count": sum(bool(r.get("effective_fix2_action")) for r in rows),
        "effective_fix4_action_count": sum(bool(r.get("effective_fix4_action")) for r in rows),
        "no_effective_gate_action_count": sum(bool(r.get("no_effective_gate_action")) for r in rows),
        "failure_class_counts": dict(Counter(str(r.get("failure_class_coarse")) for r in rows)),
    }


def load_canonical_raw_grouped(
    specs: list[dict[str, str]] | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    selected = specs or [dict(spec) for spec in CANONICAL_DEFAULT_INPUTS]
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for spec in selected:
        by_example: dict[str, dict[str, Any]] = defaultdict(dict)
        for row in load_jsonl(spec["path"]):
            by_example[str(row["example_id"])][str(row["method"])] = row
        grouped[spec["source_id"]] = dict(by_example)
    return grouped


def validate_canonical_summary(summary: dict[str, Any]) -> list[str]:
    gate_counts = summary.get("gate_counts") or {}
    failures: list[str] = []
    expected = {
        "rows_written": 720,
        "fta_correct_count": 581,
    }
    gate_expected = {
        "effective_fix2_action": 122,
        "effective_fix4_action": 5,
        "no_effective_gate_action": 593,
    }
    for key, want in expected.items():
        got = summary.get(key)
        if got != want:
            failures.append(f"{key}: expected {want}, got {got}")
    for key, want in gate_expected.items():
        got = gate_counts.get(key)
        if got != want:
            failures.append(f"gate_counts.{key}: expected {want}, got {got}")
    failure_counts = summary.get("failure_class_counts") or {}
    if failure_counts.get("fta_success") != 581:
        failures.append(
            "failure_class_counts.fta_success: "
            f"expected 581, got {failure_counts.get('fta_success')}"
        )
    return failures


def answer_group_signature(row: dict[str, Any]) -> str:
    sizes = row.get("answer_group_sizes") or {}
    if isinstance(sizes, str):
        try:
            sizes = json.loads(sizes)
        except json.JSONDecodeError:
            sizes = {}
    if not isinstance(sizes, dict):
        return "unknown"
    return "|".join(f"{k}:{v}" for k, v in sorted(sizes.items(), key=lambda item: (-item[1], item[0])))


def representative_example_rows(
    rows: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda r: (str(r.get("source_id")), int(r.get("seed") or 0), str(r.get("example_id"))),
    )
    return ordered[:limit]


def summarize_representatives(rows: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    reps = representative_example_rows(rows, limit=limit)
    summary = []
    for row in reps:
        summary.append(
            {
                "example_id": row.get("example_id"),
                "source_id": row.get("source_id"),
                "seed": row.get("seed"),
                "problem_text": row.get("problem_text"),
                "gold_answer_canonical": row.get("gold_answer_canonical"),
                "frontier_answer": row.get("frontier_answer"),
                "l1_answer": row.get("l1_answer"),
                "s1_answer": row.get("s1_answer"),
                "tale_answer": row.get("tale_answer"),
                "fta_selected_answer": row.get("fta_selected_answer"),
                "effective_policy_label": row.get("effective_policy_label"),
                "answer_group_signature": answer_group_signature(row),
            }
        )
    return summary


def frontier_row_from_group(method_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return method_rows[METHOD_FRONTIER]
