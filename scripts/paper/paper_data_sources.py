from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from paper_style import canonical_method_name, dataset_sort_key, method_sort_key

REPO_ROOT = Path(__file__).resolve().parents[2]
PLOT_DATA_DIR = REPO_ROOT / "outputs" / "paper_plot_data"
FIGURE_DIR = REPO_ROOT / "outputs" / "paper_figures"
TABLE_DIR = REPO_ROOT / "outputs" / "paper_tables"

CANONICAL_IMPORT_MULTI = REPO_ROOT / "outputs" / "imported_methodology_frontier_eval" / "20260420T_multidataset_frontier_v1"
CANONICAL_IMPORT_SINGLE = REPO_ROOT / "outputs" / "imported_methodology_frontier_eval" / "20260417T000000Z"
CANONICAL_FULL_BUNDLE = REPO_ROOT / "outputs" / "full_method_comparison_bundle" / "20260419T214335Z"
CANONICAL_NEAR_TIE = REPO_ROOT / "outputs" / "branch_label_bruteforce_learning" / "near_tie_two_stage_complementarity_audit_upgrade_20260417"


class MissingArtifactError(RuntimeError):
    pass


def ensure_file(path: Path) -> None:
    if not path.exists():
        raise MissingArtifactError(f"Required canonical input missing: {path}")


def read_csv(path: Path) -> list[dict[str, str]]:
    ensure_file(path)
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise MissingArtifactError(f"CSV exists but empty: {path}")
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_tex_table(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No rows for tex table {path}")
    columns = list(rows[0].keys())
    lines = ["\\begin{tabular}{" + "l" * len(columns) + "}", "\\hline", " & ".join(columns) + " \\\\", "\\hline"]
    for row in rows:
        vals = []
        for col in columns:
            val = row[col]
            if isinstance(val, float):
                vals.append(f"{val:.4f}")
            else:
                vals.append(str(val))
        lines.append(" & ".join(vals) + " \\\\")
    lines.extend(["\\hline", "\\end{tabular}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def to_float(v: str) -> float:
    return float(v)


def to_int(v: str) -> int:
    return int(float(v))


def load_multidataset_frontier() -> list[dict[str, str]]:
    rows = read_csv(CANONICAL_IMPORT_MULTI / "budget_frontier_summary.csv")
    out = []
    for r in rows:
        rr = dict(r)
        rr["method"] = canonical_method_name(r["method"])
        out.append(rr)
    return sorted(out, key=lambda r: (dataset_sort_key(r["dataset"]), method_sort_key(r["method"]), to_int(r["budget"])))


def load_multidataset_method_metrics() -> list[dict[str, str]]:
    rows = read_csv(CANONICAL_IMPORT_MULTI / "method_metrics.csv")
    out = []
    for r in rows:
        rr = dict(r)
        rr["method"] = canonical_method_name(r["method"])
        out.append(rr)
    return sorted(out, key=lambda r: (dataset_sort_key(r["dataset"]), method_sort_key(r["method"]), to_int(r["budget"])))


def aggregate_frontier_macro(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        grouped[(r["method"], to_int(r["budget"]))].append(r)

    out: list[dict[str, Any]] = []
    for (method, budget), vals in grouped.items():
        accs = [to_float(v["accuracy"]) for v in vals]
        gaps = [to_float(v["gap_to_oracle"]) for v in vals]
        acts = [to_float(v["avg_actions"]) for v in vals]
        out.append(
            {
                "method": method,
                "budget": budget,
                "macro_accuracy": sum(accs) / len(accs),
                "macro_gap_to_oracle": sum(gaps) / len(gaps),
                "macro_avg_actions": sum(acts) / len(acts),
                "n_datasets": len(vals),
            }
        )
    return sorted(out, key=lambda r: (method_sort_key(r["method"]), r["budget"]))
