#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from paper_data_sources import REPO_ROOT, write_csv, write_tex_table

VARIANTS = [
    "anti_collapse_off",
    "anti_collapse_weak",
    "anti_collapse_default",
    "anti_collapse_strong",
    "anti_collapse_conditional",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build paper-facing anti-collapse calibration table.")
    p.add_argument("--input-csv", type=Path, default=None, help="Path to calibration_summary.csv. Defaults to latest sweep.")
    p.add_argument(
        "--output-csv",
        type=Path,
        default=REPO_ROOT / "outputs" / "paper_tables" / "table_anti_collapse_calibration.csv",
    )
    p.add_argument(
        "--output-tex",
        type=Path,
        default=REPO_ROOT / "outputs" / "paper_tables" / "table_anti_collapse_calibration.tex",
    )
    p.add_argument(
        "--output-plot-csv",
        type=Path,
        default=REPO_ROOT / "outputs" / "paper_plot_data" / "anti_collapse_calibration.csv",
    )
    return p.parse_args()


def _latest_input() -> Path:
    candidates = list((REPO_ROOT / "outputs").glob("anti_collapse_calibration_sweep_*/calibration_summary.csv"))
    if not candidates:
        raise FileNotFoundError("No anti-collapse calibration_summary.csv found under outputs/anti_collapse_calibration_sweep_*/")
    candidates.sort(key=lambda p: p.stat().st_mtime)
    return candidates[-1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _classification(rows: list[dict[str, Any]]) -> str:
    by_variant = {str(r["variant"]): r for r in rows}
    best = max(rows, key=lambda r: _to_float(r["mean_accuracy"]))
    best_name = str(best["variant"])
    if best_name == "anti_collapse_default":
        return "default best; earlier anti-collapse concern likely seed/surface fragile"
    if best_name in {"anti_collapse_weak", "anti_collapse_conditional"}:
        return (
            "default appears overactive/miscalibrated; weak anti-collapse is favored on this surface, "
            "off also beats default, strong is near-default, and conditional underperforms"
        )
    if best_name == "anti_collapse_off":
        return "off best; anti-collapse not validated as independent accuracy-improving component"
    default_acc = _to_float(by_variant.get("anti_collapse_default", {}).get("mean_accuracy"))
    off_acc = _to_float(by_variant.get("anti_collapse_off", {}).get("mean_accuracy"))
    if off_acc > default_acc:
        return "mixed; anti-collapse should be framed as surface-sensitive design axis"
    return "mixed; anti-collapse calibration remains surface-sensitive"


def main() -> None:
    args = parse_args()
    input_csv = (args.input_csv.resolve() if args.input_csv is not None else _latest_input().resolve())
    src_rows = _read_csv(input_csv)
    by_variant = {str(r.get("variant", "")).strip(): r for r in src_rows}

    missing = [v for v in VARIANTS if v not in by_variant]
    if missing:
        raise ValueError(f"Missing required anti-collapse variants in calibration summary: {missing}")

    section_classification = _classification(src_rows)
    out_rows = []
    for variant in VARIANTS:
        r = by_variant[variant]
        out_rows.append(
            {
                "variant": variant,
                "mean_accuracy": round(_to_float(r.get("mean_accuracy")), 4),
                "delta_accuracy_vs_default": round(_to_float(r.get("delta_accuracy_vs_default")), 4),
                "absent_from_tree_rate": round(_to_float(r.get("absent_from_tree_rate")), 4),
                "present_not_selected_rate": round(_to_float(r.get("present_not_selected_rate")), 4),
                "output_layer_mismatch_rate": round(_to_float(r.get("output_layer_mismatch_rate")), 4),
                "avg_actions": round(_to_float(r.get("avg_actions")), 4),
                "classification": section_classification,
                "safe_note": "surface-sensitive calibration tradeoff; anti-collapse is a design axis, not a universally validated gain",
            }
        )

    write_csv(args.output_csv, out_rows)
    write_tex_table(args.output_tex, out_rows)
    write_csv(args.output_plot_csv, out_rows)

    print(f"Built anti-collapse paper table from: {input_csv.relative_to(REPO_ROOT)}")
    print(f"- {args.output_csv.relative_to(REPO_ROOT)}")
    print(f"- {args.output_tex.relative_to(REPO_ROOT)}")
    print(f"- {args.output_plot_csv.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
