from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        fields: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row.keys():
                k = str(key)
                if k not in seen:
                    seen.add(k)
                    fields.append(k)
    else:
        fields = ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def parse_support_counts(value: Any) -> dict[str, int]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return {str(k): as_int(v) for k, v in value.items()}
    try:
        data = json.loads(str(value))
        if isinstance(data, dict):
            return {str(k): as_int(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def entropy_from_counts(counts: dict[str, int]) -> float:
    total = sum(max(0, int(v)) for v in counts.values())
    if total <= 0:
        return 0.0
    probs = [max(0, int(v)) / total for v in counts.values() if int(v) > 0]
    if len(probs) <= 1:
        return 0.0
    ent = -sum(p * math.log(max(1e-12, p)) for p in probs)
    return float(ent / math.log(len(probs)))


def group_by_case(rows: list[dict[str, Any]]) -> dict[tuple[str, int, int, str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, int, int, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("provider", "")),
            as_int(row.get("seed"), -1),
            as_int(row.get("budget"), -1),
            str(row.get("dataset", "")),
            str(row.get("example_id", "")),
        )
        grouped[key].append(row)
    return grouped
