from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from paper_style import canonical_method_name, dataset_sort_key, method_sort_key

REPO_ROOT = Path(__file__).resolve().parents[2]
PLOT_DATA_DIR = REPO_ROOT / "outputs" / "paper_plot_data"
FIGURE_DIR = REPO_ROOT / "outputs" / "paper_figures"
TABLE_DIR = REPO_ROOT / "outputs" / "paper_tables"

STRICT_PHASED_DEFAULT_DOC = REPO_ROOT / "docs" / "FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md"
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
    """Parse the strict-phased broader default comparison table from canonical doc."""
    ensure_file(STRICT_PHASED_DEFAULT_DOC)
    txt = STRICT_PHASED_DEFAULT_DOC.read_text(encoding="utf-8")
    out: list[dict[str, str]] = []
    in_table = False
    for line in txt.splitlines():
        if line.strip().startswith("| dataset | method | accuracy |"):
            in_table = True
            continue
        if in_table:
            if (not line.strip()) or (not line.strip().startswith("|")):
                break
            if line.strip().startswith("|---"):
                continue
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) < 10:
                continue
            dataset, method = parts[0], canonical_method_name(parts[1])
            out.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "budget": "0",
                    "accuracy": str(float(parts[2])),
                    "gap_to_oracle": "0.0",
                    "avg_actions": str(float(parts[8])),
                    "avg_expansions": str(float(parts[9])),
                    "avg_verifications": str(float(parts[10])),
                    "absent_from_tree": parts[3],
                    "present_not_selected": parts[4],
                    "repeated_same_family_present": parts[6],
                    "gold_in_tree": parts[7],
                }
            )
    if not out:
        raise MissingArtifactError(f"Could not parse strict-phased dataset table from {STRICT_PHASED_DEFAULT_DOC}")
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
    payload = json.loads((BUDGET_AWARE_DIR / "aggregate_summary.json").read_text(encoding="utf-8"))
    return list(payload.get("overall_table", []))


def load_budget_aware_per_budget() -> list[dict[str, Any]]:
    return json.loads((BUDGET_AWARE_DIR / "per_budget_summary.json").read_text(encoding="utf-8"))


def load_budget_aware_per_dataset() -> list[dict[str, Any]]:
    return json.loads((BUDGET_AWARE_DIR / "per_dataset_summary.json").read_text(encoding="utf-8"))


def load_canonical_hundred_aggregate() -> dict[str, Any]:
    return json.loads((CANONICAL_HUNDRED_DIR / "aggregate_failure_statistics.json").read_text(encoding="utf-8"))


def load_canonical_hundred_failure_table() -> list[dict[str, str]]:
    return read_csv(CANONICAL_HUNDRED_DIR / "failure_statistics_table.csv")
