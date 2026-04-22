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

STRICT_PHASED_DEFAULT_DOC = REPO_ROOT / "docs" / "FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md"
MANUSCRIPT_METHOD_DECISION_DOC = REPO_ROOT / "docs" / "INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md"
EXTERNAL_READINESS_DOC = REPO_ROOT / "docs" / "CANONICAL_EXTERNAL_BASELINE_PAPER_READINESS_DECISION_2026_04_22.md"
STRICT_PHASED_FRONTIER_CSV = PLOT_DATA_DIR / "sources" / "strict_phased_multidataset_frontier.csv"
CANONICAL_HUNDRED_DIR = (
    REPO_ROOT / "outputs" / "canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z"
)
BUDGET_AWARE_DIR = REPO_ROOT / "outputs" / "budget_aware_family_cap_eval_20260421T162842Z"
OUTPUT_LAYER_REPAIR_DIR = REPO_ROOT / "outputs" / "current_failure_output_layer_repair_20260420"


class MissingArtifactError(RuntimeError):
    pass


def ensure_file(path: Path) -> None:
    if not path.exists():
        raise MissingArtifactError(f"Required canonical input missing: {path}")


def read_json(path: Path) -> Any:
    ensure_file(path)
    return json.loads(path.read_text(encoding="utf-8"))


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

    def _tex_escape(value: str) -> str:
        return (
            value.replace("\\", "\\textbackslash{}")
            .replace("_", "\\_")
            .replace("%", "\\%")
            .replace("&", "\\&")
        )

    columns = list(rows[0].keys())
    lines = [
        "\\begin{tabular}{" + "l" * len(columns) + "}",
        "\\hline",
        " & ".join(_tex_escape(c) for c in columns) + " \\\\",
        "\\hline",
    ]
    for row in rows:
        vals = []
        for col in columns:
            val = row[col]
            if isinstance(val, float):
                vals.append(f"{val:.4f}")
            else:
                vals.append(_tex_escape(str(val)))
        lines.append(" & ".join(vals) + " \\\\")
    lines.extend(["\\hline", "\\end{tabular}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def to_float(v: str) -> float:
    return float(v)


def to_int(v: str) -> int:
    return int(float(v))


def load_multidataset_frontier() -> list[dict[str, str]]:
    """Load strict-phased broader default comparison rows from canonical structured CSV."""
    rows = read_csv(STRICT_PHASED_FRONTIER_CSV)
    out: list[dict[str, str]] = []
    required = {
        "dataset",
        "method",
        "budget",
        "accuracy",
        "gap_to_oracle",
        "avg_actions",
        "avg_expansions",
        "avg_verifications",
        "absent_from_tree",
        "present_not_selected",
        "repeated_same_family_present",
        "gold_in_tree",
    }
    for r in rows:
        missing = required.difference(r.keys())
        if missing:
            raise MissingArtifactError(
                f"Structured frontier CSV missing required columns {sorted(missing)}: {STRICT_PHASED_FRONTIER_CSV}"
            )
        out.append(
            {
                "dataset": str(r["dataset"]),
                "method": canonical_method_name(str(r["method"])),
                "budget": str(r["budget"]),
                "accuracy": str(r["accuracy"]),
                "gap_to_oracle": str(r["gap_to_oracle"]),
                "avg_actions": str(r["avg_actions"]),
                "avg_expansions": str(r["avg_expansions"]),
                "avg_verifications": str(r["avg_verifications"]),
                "absent_from_tree": str(r["absent_from_tree"]),
                "present_not_selected": str(r["present_not_selected"]),
                "repeated_same_family_present": str(r["repeated_same_family_present"]),
                "gold_in_tree": str(r["gold_in_tree"]),
            }
        )
    return sorted(out, key=lambda r: (dataset_sort_key(r["dataset"]), method_sort_key(r["method"])))


def load_multidataset_method_metrics() -> list[dict[str, str]]:
    # Reuse parsed strict-phased table metrics.
    return load_multidataset_frontier()


def aggregate_frontier_macro(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        grouped[(r["method"], to_int(r.get("budget", "0")))].append(r)

    out: list[dict[str, Any]] = []
    for (method, budget), vals in grouped.items():
        accs = [to_float(v["accuracy"]) for v in vals]
        gaps = [to_float(v.get("gap_to_oracle", "0.0")) for v in vals]
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


def load_budget_aware_overall_table() -> list[dict[str, Any]]:
    payload = read_json(BUDGET_AWARE_DIR / "aggregate_summary.json")
    return list(payload.get("overall_table", []))


def load_budget_aware_per_budget() -> list[dict[str, Any]]:
    return read_json(BUDGET_AWARE_DIR / "per_budget_summary.json")


def load_budget_aware_per_dataset() -> list[dict[str, Any]]:
    return read_json(BUDGET_AWARE_DIR / "per_dataset_summary.json")


def load_canonical_hundred_aggregate() -> dict[str, Any]:
    return read_json(CANONICAL_HUNDRED_DIR / "aggregate_failure_statistics.json")


def load_canonical_hundred_failure_table() -> list[dict[str, str]]:
    return read_csv(CANONICAL_HUNDRED_DIR / "failure_statistics_table.csv")
