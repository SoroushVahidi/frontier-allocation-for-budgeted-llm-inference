#!/usr/bin/env python3
"""Build paper-facing tables from `outputs/tot_matched_budget_baseline_<timestamp>/`."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from paper_data_sources import REPO_ROOT, write_csv, write_tex_table

FORBIDDEN_SUBSTRINGS = [
    "official tree of thoughts",
    "official tree-of-thoughts",
    "universal dominance",
    "universally dominates",
    "tot is solved",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _to_float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def _latest_run_dir() -> Path:
    candidates = sorted((REPO_ROOT / "outputs").glob("tot_matched_budget_baseline_*/manifest.json"))
    if not candidates:
        raise FileNotFoundError("No tot_matched_budget_baseline outputs found under outputs/.")
    return candidates[-1].parent


def _interpret_pairwise(pval: float, delta: float, ci_low: float, ci_high: float) -> str:
    if pval < 0.05 and ci_low > 0:
        return "strict_f3_anti_higher_matched_baseline_evidence"
    if pval < 0.05 and ci_high < 0:
        return "comparison_favors_other_method"
    return "mixed_or_not_decisive_at_alpha005"


def main() -> None:
    p = argparse.ArgumentParser(description="Build ToT matched-budget baseline paper tables.")
    p.add_argument("--input-dir", type=Path, default=None)
    p.add_argument("--output-csv", type=Path, default=REPO_ROOT / "outputs" / "paper_tables" / "table_tot_matched_budget_baseline.csv")
    p.add_argument("--output-tex", type=Path, default=REPO_ROOT / "outputs" / "paper_tables" / "table_tot_matched_budget_baseline.tex")
    p.add_argument("--output-plot-csv", type=Path, default=REPO_ROOT / "outputs" / "paper_plot_data" / "tot_matched_budget_baseline.csv")
    args = p.parse_args()

    in_dir = (args.input_dir or _latest_run_dir()).resolve()
    manifest = json.loads((in_dir / "manifest.json").read_text(encoding="utf-8"))
    summary_path = in_dir / "per_dataset_budget_summary.csv"
    if not summary_path.exists():
        summary_path = in_dir / "per_dataset_summary.csv"
    rows_in = _read_csv(summary_path)
    pairwise = _read_csv(in_dir / "pairwise_statistical_tests.csv") if (in_dir / "pairwise_statistical_tests.csv").exists() else []

    anti = "strict_f3_anti_collapse_weak_v1"
    pool: dict[str, dict[str, str]] = {}
    for pr in pairwise:
        if str(pr.get("method_a", "")) == anti:
            pool[str(pr.get("method_b", ""))] = pr

    out_rows: list[dict[str, Any]] = []
    for r in rows_in:
        method = str(r.get("method", ""))
        budget = r.get("budget", "")
        pr = pool.get(method, {})
        delta = _to_float(pr.get("mean_difference", ""), float("nan"))
        ci_l = _to_float(pr.get("bootstrap_ci_low", ""), float("nan"))
        ci_h = _to_float(pr.get("bootstrap_ci_high", ""), float("nan"))
        pval = _to_float(pr.get("permutation_p_value", ""), float("nan"))
        interp = _interpret_pairwise(pval, delta, ci_l, ci_h) if pr else "no_pooled_pairwise_row"
        row = {
            "dataset": str(r.get("dataset", "")),
            "budget": str(budget) if budget != "" else "all_budgets_pooled",
            "method": method,
            "mean_accuracy": round(_to_float(r.get("mean_accuracy", 0.0)), 6),
            "accuracy_ci_note": "pooled_across_seeds_bootstrap_in_pairwise_columns",
            "mean_actions": round(_to_float(r.get("avg_actions", 0.0)), 6),
            "n_cases": int(_to_float(r.get("n_cases", 0.0))),
            "delta_vs_strict_f3_anti_collapse_weak_v1": (round(delta, 6) if pr else ""),
            "delta_bootstrap_ci_low": (round(ci_l, 6) if pr else ""),
            "delta_bootstrap_ci_high": (round(ci_h, 6) if pr else ""),
            "permutation_p_value": (round(pval, 6) if pr else ""),
            "pairwise_interpretation": interp,
            "wording_guard": "matched_budget_tot_style_adapter_not_official_tot",
        }
        out_rows.append(row)

    text_blob = json.dumps(out_rows, indent=2).lower()
    for bad in FORBIDDEN_SUBSTRINGS:
        if bad in text_blob:
            raise ValueError(f"Forbidden wording detected in table payload: {bad!r}")

    write_csv(args.output_csv, out_rows)
    write_tex_table(args.output_tex, out_rows)
    write_csv(args.output_plot_csv, out_rows)
    def _rel(p: Path) -> str:
        try:
            return str(p.resolve().relative_to(REPO_ROOT.resolve()))
        except ValueError:
            return str(p.resolve())

    print(
        json.dumps(
            {
                "status": "ok",
                "input_dir": _rel(in_dir),
                "output_csv": _rel(args.output_csv),
                "manifest_datasets": manifest.get("datasets_ran", []),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
