#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from paper_data_sources import REPO_ROOT, write_csv, write_tex_table


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _latest_dir() -> Path:
    candidates = sorted((REPO_ROOT / "outputs").glob("non_math_dataset_expansion_*/main_summary.csv"))
    if not candidates:
        raise FileNotFoundError("No non_math_dataset_expansion outputs found.")
    return candidates[-1].parent


def _to_float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def _interpret(pval: float, delta: float, ci_low: float, ci_high: float, pilot: bool) -> str:
    if pilot:
        return "pilot_evidence"
    decisive = pval < 0.05 and ((ci_low > 0) or (ci_high < 0))
    if decisive and delta > 0:
        return "supports_broader_than_math"
    if decisive and delta < 0:
        return "mixed_or_insufficient"
    return "mixed_or_insufficient"


def main() -> None:
    p = argparse.ArgumentParser(description="Build non-math dataset expansion paper table.")
    p.add_argument("--input-dir", type=Path, default=None)
    p.add_argument("--output-csv", type=Path, default=REPO_ROOT / "outputs" / "paper_tables" / "table_non_math_dataset_expansion.csv")
    p.add_argument("--output-tex", type=Path, default=REPO_ROOT / "outputs" / "paper_tables" / "table_non_math_dataset_expansion.tex")
    p.add_argument("--output-plot-csv", type=Path, default=REPO_ROOT / "outputs" / "paper_plot_data" / "non_math_dataset_expansion.csv")
    args = p.parse_args()

    in_dir = args.input_dir or _latest_dir()
    manifest = __import__("json").loads((in_dir / "manifest.json").read_text(encoding="utf-8"))
    pilot = bool(manifest.get("pilot_only", True))

    per_dataset = _read_csv(in_dir / "per_dataset_summary.csv")
    pairwise = _read_csv(in_dir / "pairwise_statistical_tests.csv")
    best_pair = pairwise[0] if pairwise else {}
    delta = _to_float(best_pair.get("mean_difference", 0.0))
    pval = _to_float(best_pair.get("permutation_p_value", 1.0))
    ci_low = _to_float(best_pair.get("bootstrap_ci_low", 0.0))
    ci_high = _to_float(best_pair.get("bootstrap_ci_high", 0.0))
    interp = _interpret(pval=pval, delta=delta, ci_low=ci_low, ci_high=ci_high, pilot=pilot)

    rows: list[dict[str, Any]] = []
    for r in sorted(per_dataset, key=lambda x: (str(x.get("dataset", "")), -_to_float(x.get("mean_accuracy", 0.0)))):
        rows.append(
            {
                "dataset": str(r.get("dataset", "")),
                "method": str(r.get("method", "")),
                "mean_accuracy": round(_to_float(r.get("mean_accuracy", 0.0)), 6),
                "ci": f"[{round(ci_low,6)}, {round(ci_high,6)}]" if best_pair else "",
                "mean_actions": round(_to_float(r.get("avg_actions", 0.0)), 6),
                "key_pairwise_interpretation": interp,
                "evidence_strength": interp,
            }
        )

    write_csv(args.output_csv, rows)
    write_tex_table(args.output_tex, rows)
    write_csv(args.output_plot_csv, rows)
    print(f"Built non-math dataset expansion table from {in_dir}")


if __name__ == "__main__":
    main()
