#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from paper_data_sources import REPO_ROOT, write_csv, write_tex_table


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _latest_dir() -> Path:
    candidates = sorted((REPO_ROOT / "outputs").glob("tot_matched_budget_baseline_*/main_summary.csv"))
    if not candidates:
        raise FileNotFoundError("No tot_matched_budget_baseline outputs found.")
    return candidates[-1].parent


def _to_float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def _interpret(delta: float, pval: float, ci_low: float, ci_high: float) -> str:
    decisive = pval < 0.05 and ((ci_low > 0) or (ci_high < 0))
    if decisive and delta > 0:
        return "frontier_advantage_supported"
    if decisive and delta < 0:
        return "tot_or_baseline_advantage_supported"
    return "mixed_or_inconclusive"


def main() -> None:
    p = argparse.ArgumentParser(description="Build ToT matched-budget baseline paper table.")
    p.add_argument("--input-dir", type=Path, default=None)
    p.add_argument("--output-csv", type=Path, default=REPO_ROOT / "outputs" / "paper_tables" / "table_tot_matched_budget_baseline.csv")
    p.add_argument("--output-tex", type=Path, default=REPO_ROOT / "outputs" / "paper_tables" / "table_tot_matched_budget_baseline.tex")
    p.add_argument("--output-plot-csv", type=Path, default=REPO_ROOT / "outputs" / "paper_plot_data" / "tot_matched_budget_baseline.csv")
    args = p.parse_args()

    in_dir = args.input_dir or _latest_dir()
    manifest = json.loads((in_dir / "manifest.json").read_text(encoding="utf-8"))
    per_dataset = _read_csv(in_dir / "per_dataset_summary.csv")
    per_budget = _read_csv(in_dir / "per_budget_summary.csv")
    pairwise = _read_csv(in_dir / "pairwise_statistical_tests.csv")

    best_frontier = str(manifest.get("best_frontier_variant", "strict_f3"))
    pair_index = {(r.get("method_a", ""), r.get("method_b", "")): r for r in pairwise}

    rows: list[dict[str, Any]] = []
    for ds_row in per_dataset:
        dataset = str(ds_row.get("dataset", ""))
        method = str(ds_row.get("method", ""))
        for bg_row in [r for r in per_budget if str(r.get("method", "")) == method]:
            budget = str(bg_row.get("budget", ""))
            pair = pair_index.get((best_frontier, method)) or pair_index.get((method, best_frontier)) or {}
            delta = _to_float(pair.get("mean_difference", 0.0))
            if pair.get("method_a") == method and pair.get("method_b") == best_frontier:
                delta = -delta
            ci_low = _to_float(pair.get("bootstrap_ci_low", 0.0))
            ci_high = _to_float(pair.get("bootstrap_ci_high", 0.0))
            pval = _to_float(pair.get("permutation_p_value", 1.0))
            rows.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "budget": budget,
                    "mean_accuracy": round(_to_float(ds_row.get("mean_accuracy", 0.0)), 6),
                    "confidence_interval": f"[{round(ci_low,6)}, {round(ci_high,6)}]" if pair else "",
                    "mean_actions": round(_to_float(bg_row.get("avg_actions", 0.0)), 6),
                    "key_pairwise_vs_best_frontier": f"{best_frontier} vs {method}" if pair else "",
                    "bootstrap_ci": f"[{round(ci_low,6)}, {round(ci_high,6)}]" if pair else "",
                    "permutation_p_value": round(pval, 6) if pair else "",
                    "interpretation": _interpret(delta, pval, ci_low, ci_high) if pair else "not_available",
                }
            )

    rows = sorted(rows, key=lambda r: (r["dataset"], r["method"], str(r["budget"])))
    write_csv(args.output_csv, rows)
    write_tex_table(args.output_tex, rows)
    write_csv(args.output_plot_csv, rows)
    print(f"Built ToT matched-budget baseline table from {in_dir}")


if __name__ == "__main__":
    main()
