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
    p = argparse.ArgumentParser(description="Build repeated-run/seed stability summary from canonical matched outcomes.")
    p.add_argument("--run-id", default=_utc_run_id())
    p.add_argument("--surface-csv", type=Path, default=DEFAULT_SURFACE)
    p.add_argument("--methods", default="strict_f3,external_l1_max")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--seeds", default="11,23,37")
    args = p.parse_args()

    methods = _parse_csv(args.methods)
    datasets = _parse_csv(args.datasets)
    budgets = [int(x) for x in _parse_csv(args.budgets)]
    seeds = [int(x) for x in _parse_csv(args.seeds)]

    out_dir = REPO_ROOT / "outputs/multi_seed_stability" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_df = pd.read_csv(args.surface_csv)
    available_datasets = sorted(raw_df["dataset"].dropna().unique().tolist())
    available_seeds = sorted(int(x) for x in raw_df["seed"].dropna().unique().tolist())
    requested_missing_datasets = [d for d in datasets if d not in available_datasets]
    requested_missing_seeds = [s for s in seeds if s not in available_seeds]

    df = raw_df[
        raw_df["method"].isin(methods)
        & raw_df["dataset"].isin(datasets)
        & raw_df["budget"].isin(budgets)
        & raw_df["seed"].isin(seeds)
    ].copy()
    df["is_correct"] = df["is_correct"].astype(int)

    per_seed = (
        df.groupby(["method", "seed"], as_index=False)
        .agg(accuracy=("is_correct", "mean"), n=("is_correct", "size"))
        .sort_values(["method", "seed"])
    )

    stability = (
        per_seed.groupby("method", as_index=False)
        .agg(
            mean_accuracy=("accuracy", "mean"),
            std_accuracy=("accuracy", "std"),
            min_accuracy=("accuracy", "min"),
            max_accuracy=("accuracy", "max"),
            seed_count=("seed", "nunique"),
        )
        .sort_values("mean_accuracy", ascending=False)
    )
    stability["std_accuracy"] = stability["std_accuracy"].fillna(0.0)
    stability.to_csv(out_dir / "seed_stability_table.csv", index=False)

    by_dataset_seed = (
        df.groupby(["dataset", "method", "seed"], as_index=False)
        .agg(accuracy=("is_correct", "mean"), n=("is_correct", "size"))
        .sort_values(["dataset", "method", "seed"])
    )
    by_dataset = (
        by_dataset_seed.groupby(["dataset", "method"], as_index=False)
        .agg(mean_accuracy=("accuracy", "mean"), std_accuracy=("accuracy", "std"), min_accuracy=("accuracy", "min"), max_accuracy=("accuracy", "max"), seed_count=("seed", "nunique"))
        .sort_values(["dataset", "mean_accuracy"], ascending=[True, False])
    )
    by_dataset["std_accuracy"] = by_dataset["std_accuracy"].fillna(0.0)
    by_dataset.to_csv(out_dir / "seed_stability_by_dataset.csv", index=False)

    summary = {
        "run_id": args.run_id,
        "protocol_note": "Repeated stochastic evaluation over available canonical seeds; this is evaluation-seed stability, not training-seed variation.",
        "methods": methods,
        "datasets": datasets,
        "requested_missing_datasets": requested_missing_datasets,
        "budgets": budgets,
        "seeds": seeds,
        "requested_missing_seeds": requested_missing_seeds,
        "feasible_seed_count": int(df["seed"].nunique()) if not df.empty else 0,
        "seed_count_limit_note": "Fewer than 3 evaluation seeds are currently available on this canonical surface."
        if (int(df["seed"].nunique()) if not df.empty else 0) < 3
        else None,
        "best_method_by_mean": stability.iloc[0]["method"] if not stability.empty else None,
    }
    _write_json(out_dir / "summary.json", summary)
    _write_json(out_dir / "status.json", {"status": "ok", **summary})
    _write_json(out_dir / "manifest.json", {"inputs": {"surface_csv": str(args.surface_csv.relative_to(REPO_ROOT))}, "outputs": ["status.json", "summary.json", "summary.md", "manifest.json", "seed_stability_table.csv", "seed_stability_by_dataset.csv", "config_snapshot.json", "command_snapshot.txt"]})
    _write_json(out_dir / "config_snapshot.json", {"args": _jsonable_args(args), "resolved": {"methods": methods, "datasets": datasets, "budgets": budgets, "seeds": seeds}})
    (out_dir / "command_snapshot.txt").write_text("python scripts/run_multi_seed_stability_eval.py " + " ".join(f"--{k.replace('_','-')} {v}" for k, v in vars(args).items() if k != "run_id") + f" --run-id {args.run_id}\n", encoding="utf-8")

    md = [
        f"# Multi-seed stability ({args.run_id})",
        "",
        "This report summarizes repeated evaluation-seed stability (not training-seed variation).",
        f"- Methods: `{methods}`",
        f"- Datasets: `{datasets}`",
        f"- Requested datasets missing from canonical surface: `{requested_missing_datasets}`",
        f"- Budgets: `{budgets}`",
        f"- Seeds: `{seeds}`",
        f"- Requested seeds missing from canonical surface: `{requested_missing_seeds}`",
        f"- Feasible seed count on this surface: `{summary['feasible_seed_count']}`",
    ]
    (out_dir / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
