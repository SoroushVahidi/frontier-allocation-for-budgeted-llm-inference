#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SURFACE = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv"
DEFAULT_STRONGEST_JSON = REPO_ROOT / "outputs/full_our_method_vs_external_baselines_comparison/20260422T230000Z/strongest_external_baseline.json"


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _jsonable_args(args: argparse.Namespace) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in vars(args).items():
        out[k] = str(v) if isinstance(v, Path) else v
    return out


def _parse_csv(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def main() -> None:
    p = argparse.ArgumentParser(description="Build budget sweep robustness artifacts from canonical matched surface.")
    p.add_argument("--run-id", default=_utc_run_id())
    p.add_argument("--surface-csv", type=Path, default=DEFAULT_SURFACE)
    p.add_argument("--strongest-json", type=Path, default=DEFAULT_STRONGEST_JSON)
    p.add_argument("--our-method", default="strict_f3")
    p.add_argument("--methods", default="strict_f3,external_l1_max,external_s1_budget_forcing")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024")
    p.add_argument("--budgets", default="4,6,8")
    args = p.parse_args()

    methods = _parse_csv(args.methods)
    datasets = _parse_csv(args.datasets)
    budgets = [int(x) for x in _parse_csv(args.budgets)]

    out_dir = REPO_ROOT / "outputs/budget_sweep_robustness" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_df = pd.read_csv(args.surface_csv)
    available_datasets = sorted(raw_df["dataset"].dropna().unique().tolist())
    requested_missing_datasets = [d for d in datasets if d not in available_datasets]

    df = raw_df[raw_df["method"].isin(methods) & raw_df["dataset"].isin(datasets) & raw_df["budget"].isin(budgets)].copy()
    df["is_correct"] = df["is_correct"].astype(int)

    curve = (
        df.groupby(["method", "budget"], as_index=False)
        .agg(
            accuracy=("is_correct", "mean"),
            mean_actions=("actions", "mean"),
            mean_expansions=("expansions", "mean"),
            mean_verifications=("verifications", "mean"),
            n=("is_correct", "size"),
        )
        .sort_values(["method", "budget"])
    )
    curve.to_csv(out_dir / "budget_curve_table.csv", index=False)

    curve_ds = (
        df.groupby(["dataset", "method", "budget"], as_index=False)
        .agg(
            accuracy=("is_correct", "mean"),
            mean_actions=("actions", "mean"),
            n=("is_correct", "size"),
        )
        .sort_values(["dataset", "method", "budget"])
    )
    curve_ds.to_csv(out_dir / "budget_curve_by_dataset.csv", index=False)

    our = args.our_method
    strongest = "external_l1_max"
    if args.strongest_json.exists():
        strongest = json.loads(args.strongest_json.read_text(encoding="utf-8")).get("strongest_external_baseline", strongest)

    h2h = curve[curve["method"].isin([our, strongest])][["method", "budget", "accuracy"]].pivot(index="budget", columns="method", values="accuracy").reset_index()
    if our in h2h.columns and strongest in h2h.columns:
        h2h["delta_our_minus_strongest"] = h2h[our] - h2h[strongest]
    h2h.to_csv(out_dir / "head_to_head_budget_table.csv", index=False)

    deltas = h2h.get("delta_our_minus_strongest", pd.Series(dtype=float))
    strictly_ahead = bool(len(deltas) > 0 and (deltas > 0).all())

    per_budget_delta = []
    if "budget" in h2h.columns and "delta_our_minus_strongest" in h2h.columns:
        per_budget_delta = [
            {"budget": int(row["budget"]), "delta_our_minus_strongest": float(row["delta_our_minus_strongest"])}
            for _, row in h2h.sort_values("budget").iterrows()
        ]

    summary = {
        "run_id": args.run_id,
        "surface_csv": str(args.surface_csv.relative_to(REPO_ROOT)),
        "methods": methods,
        "datasets": datasets,
        "requested_missing_datasets": requested_missing_datasets,
        "budgets": budgets,
        "our_method": our,
        "strongest_fair_external_baseline": strongest,
        "strict_f3_ahead_all_budgets": strictly_ahead,
        "mean_delta_our_minus_strongest": float(deltas.mean()) if len(deltas) else None,
        "per_budget_delta_our_minus_strongest": per_budget_delta,
    }
    _write_json(out_dir / "summary.json", summary)
    _write_json(out_dir / "status.json", {"status": "ok", **summary})
    _write_json(
        out_dir / "manifest.json",
        {
            "inputs": {
                "surface_csv": str(args.surface_csv.relative_to(REPO_ROOT)),
                "strongest_json": str(args.strongest_json.relative_to(REPO_ROOT)) if args.strongest_json.exists() else None,
            },
            "outputs": [
                "status.json",
                "summary.json",
                "summary.md",
                "manifest.json",
                "budget_curve_table.csv",
                "budget_curve_by_dataset.csv",
                "head_to_head_budget_table.csv",
                "config_snapshot.json",
                "command_snapshot.txt",
            ],
        },
    )
    _write_json(out_dir / "config_snapshot.json", {"args": _jsonable_args(args), "resolved": {"methods": methods, "datasets": datasets, "budgets": budgets}})
    (out_dir / "command_snapshot.txt").write_text("python scripts/run_budget_sweep_robustness.py " + " ".join(f"--{k.replace('_','-')} {v}" for k, v in vars(args).items() if k != "run_id") + f" --run-id {args.run_id}\n", encoding="utf-8")

    lines = [
        f"# Budget sweep robustness ({args.run_id})",
        "",
        f"- Our method: `{our}`",
        f"- Strongest fair external baseline: `{strongest}`",
        f"- Methods: `{methods}`",
        f"- Datasets: `{datasets}`",
        f"- Requested datasets missing from canonical surface: `{requested_missing_datasets}`",
        f"- Budgets: `{budgets}`",
        f"- strict_f3 ahead at every budget: `{strictly_ahead}`",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
