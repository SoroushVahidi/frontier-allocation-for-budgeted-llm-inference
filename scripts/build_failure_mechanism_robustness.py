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
    p = argparse.ArgumentParser(description="Build failure-mechanism robustness analysis across budgets.")
    p.add_argument("--run-id", default=_utc_run_id())
    p.add_argument("--surface-csv", type=Path, default=DEFAULT_SURFACE)
    p.add_argument("--strongest-json", type=Path, default=DEFAULT_STRONGEST_JSON)
    p.add_argument("--our-method", default="strict_f3")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--ambiguity-threshold", type=float, default=0.5)
    args = p.parse_args()

    datasets = _parse_csv(args.datasets)
    budgets = [int(x) for x in _parse_csv(args.budgets)]
    strongest = json.loads(args.strongest_json.read_text(encoding="utf-8")).get("strongest_external_baseline", "external_l1_max") if args.strongest_json.exists() else "external_l1_max"

    out_dir = REPO_ROOT / "outputs/failure_mechanism_robustness" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_df = pd.read_csv(args.surface_csv)
    available_datasets = sorted(raw_df["dataset"].dropna().unique().tolist())
    requested_missing_datasets = [d for d in datasets if d not in available_datasets]

    df = raw_df[
        raw_df["dataset"].isin(datasets)
        & raw_df["budget"].isin(budgets)
        & raw_df["method"].isin([args.our_method, strongest])
    ].copy()

    keys = ["dataset", "seed", "budget", "example_id"]
    our = df[df["method"] == args.our_method][keys + ["is_correct", "failure_type", "absent_from_tree", "present_not_selected", "repeated_same_family_present", "output_layer_mismatch"]].copy()
    ext = df[df["method"] == strongest][keys + ["is_correct"]].copy()
    merged = our.merge(ext, on=keys, suffixes=("_our", "_ext"))
    losses = merged[(merged["is_correct_our"] == 0) & (merged["is_correct_ext"] == 1)].copy()

    losses["absent_from_tree"] = losses["absent_from_tree"].astype(int)
    losses["present_not_selected"] = losses["present_not_selected"].astype(int)
    losses["repeated_same_family_present"] = losses["repeated_same_family_present"].astype(int)
    losses["output_layer_mismatch"] = losses["output_layer_mismatch"].astype(int)

    by_budget = (
        losses.groupby("budget", as_index=False)
        .agg(
            loss_count=("example_id", "size"),
            absent_from_tree_rate=("absent_from_tree", "mean"),
            present_not_selected_rate=("present_not_selected", "mean"),
            repeated_same_family_present_rate=("repeated_same_family_present", "mean"),
            output_layer_mismatch_rate=("output_layer_mismatch", "mean"),
        )
        .sort_values("budget")
    )
    by_budget.to_csv(out_dir / "failure_mechanism_by_budget.csv", index=False)

    by_dataset = (
        losses.groupby("dataset", as_index=False)
        .agg(
            loss_count=("example_id", "size"),
            absent_from_tree_rate=("absent_from_tree", "mean"),
            present_not_selected_rate=("present_not_selected", "mean"),
        )
        .sort_values("loss_count", ascending=False)
    )
    by_dataset.to_csv(out_dir / "failure_mechanism_by_dataset.csv", index=False)

    feature_summary = {
        "our_method": args.our_method,
        "strongest_fair_external_baseline": strongest,
        "loss_count": int(len(losses)),
        "dominant_mechanism_overall": (
            "absent_from_tree" if losses["absent_from_tree"].mean() >= losses["present_not_selected"].mean() else "present_not_selected"
        )
        if len(losses)
        else None,
        "overall_rates": {
            "absent_from_tree": float(losses["absent_from_tree"].mean()) if len(losses) else 0.0,
            "present_not_selected": float(losses["present_not_selected"].mean()) if len(losses) else 0.0,
            "repeated_same_family_present": float(losses["repeated_same_family_present"].mean()) if len(losses) else 0.0,
            "output_layer_mismatch": float(losses["output_layer_mismatch"].mean()) if len(losses) else 0.0,
        },
        "budget_slice_deltas": {
            "absent_from_tree_max_minus_min": float(by_budget["absent_from_tree_rate"].max() - by_budget["absent_from_tree_rate"].min()) if len(by_budget) else None,
            "present_not_selected_max_minus_min": float(by_budget["present_not_selected_rate"].max() - by_budget["present_not_selected_rate"].min()) if len(by_budget) else None,
        },
        "budget_slice_dominant_mechanism": [
            {
                "budget": int(row["budget"]),
                "dominant_mechanism": "absent_from_tree"
                if float(row["absent_from_tree_rate"]) >= float(row["present_not_selected_rate"])
                else "present_not_selected",
            }
            for _, row in by_budget.sort_values("budget").iterrows()
        ],
    }
    _write_json(out_dir / "feature_summary.json", feature_summary)

    summary = {
        "run_id": args.run_id,
        "datasets": datasets,
        "requested_missing_datasets": requested_missing_datasets,
        "budgets": budgets,
        "our_method": args.our_method,
        "strongest_fair_external_baseline": strongest,
        "loss_count": int(len(losses)),
        "dominant_mechanism_overall": feature_summary["dominant_mechanism_overall"],
    }
    _write_json(out_dir / "summary.json", summary)
    _write_json(out_dir / "status.json", {"status": "ok", **summary})
    _write_json(out_dir / "manifest.json", {"inputs": {"surface_csv": str(args.surface_csv.relative_to(REPO_ROOT)), "strongest_json": str(args.strongest_json.relative_to(REPO_ROOT)) if args.strongest_json.exists() else None}, "outputs": ["status.json", "summary.json", "summary.md", "manifest.json", "failure_mechanism_by_budget.csv", "failure_mechanism_by_dataset.csv", "feature_summary.json", "config_snapshot.json", "command_snapshot.txt"]})
    _write_json(out_dir / "config_snapshot.json", {"args": _jsonable_args(args), "resolved": {"datasets": datasets, "budgets": budgets, "strongest": strongest}})
    (out_dir / "command_snapshot.txt").write_text("python scripts/build_failure_mechanism_robustness.py " + " ".join(f"--{k.replace('_','-')} {v}" for k, v in vars(args).items() if k != "run_id") + f" --run-id {args.run_id}\n", encoding="utf-8")

    md = [
        f"# Failure-mechanism robustness ({args.run_id})",
        "",
        f"- Our method: `{args.our_method}`",
        f"- Strongest fair external baseline: `{strongest}`",
        f"- Requested datasets missing from canonical surface: `{requested_missing_datasets}`",
        f"- Loss count (our wrong, baseline correct): `{len(losses)}`",
        f"- Dominant mechanism overall: `{feature_summary['dominant_mechanism_overall']}`",
    ]
    (out_dir / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
