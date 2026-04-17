#!/usr/bin/env python3
"""Matched learner comparison for baseline vs CL-cleaned hard-pair regime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import LearningConfig, evaluate_models, load_label_artifacts, prepare_learning_tables, train_models


KEY_METRICS = [
    "pairwise_accuracy_test",
    "ranking_top1_accuracy_test",
    "near_tie_pairwise_accuracy_test",
    "adjacent_rank_pairwise_accuracy_test",
    "exact_promoted_pairwise_accuracy_test",
    "exact_promoted_hard_region_pairwise_accuracy_test",
    "pairwise_margin_brier_test",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded matched CL hard-pair cleanup experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--feature-set", choices=["v1", "v2"], default="v2")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    return p.parse_args()


def _mean(vals: list[float]) -> float:
    return sum(vals) / max(1, len(vals))


def _summarize(rows: list[dict[str, Any]], key: str) -> float:
    return _mean([float(r.get(key, 0.0)) for r in rows])


def main() -> None:
    args = parse_args()
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]

    target_root = Path(args.targets_root)
    regimes = [p for p in sorted(target_root.glob("regime_*")) if p.is_dir()]
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "run_id": args.run_id,
        "targets_root": str(target_root),
        "seeds": seeds,
        "feature_set": str(args.feature_set),
        "regimes": {},
    }

    flat: list[dict[str, Any]] = []

    for regime_dir in regimes:
        regime_name = regime_dir.name.replace("regime_", "")
        payload["regimes"][regime_name] = {}
        for seed in seeds:
            cfg = LearningConfig(
                seed=seed,
                near_tie_margin=float(args.near_tie_margin),
                feature_set=str(args.feature_set),
            )
            artifacts = load_label_artifacts(regime_dir)
            tables = prepare_learning_tables(artifacts, cfg)
            models = train_models(tables, cfg, model_artifact_dir=out_dir / f"{regime_name}_seed_{seed}" / "model_artifacts")
            evals = evaluate_models(models, tables, cfg)

            payload["regimes"][regime_name][str(seed)] = {
                "config": {"near_tie_margin": cfg.near_tie_margin, "feature_set": cfg.feature_set},
                "evaluation": evals,
            }

            for model_name, m in evals.items():
                row = {"regime": regime_name, "seed": seed, "model": model_name}
                for k in KEY_METRICS:
                    row[k] = float(m.get(k, 0.0))
                flat.append(row)

    # focus summary on pairwise logistic anchor
    anchor = "pairwise"
    anchor_rows = [r for r in flat if r["model"] == anchor]
    summary: dict[str, Any] = {"anchor_model": anchor, "regimes": {}}
    for regime_name in sorted(set(r["regime"] for r in anchor_rows)):
        rows = [r for r in anchor_rows if r["regime"] == regime_name]
        summary["regimes"][regime_name] = {k: _summarize(rows, k) for k in KEY_METRICS}

    base = summary["regimes"].get("all_pairs_baseline", {})
    clean = summary["regimes"].get("cl_hardpair_excluded", {})
    summary["delta_clean_minus_baseline"] = {k: float(clean.get(k, 0.0) - base.get(k, 0.0)) for k in KEY_METRICS}

    (out_dir / "cl_hard_pair_matched_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "cl_hard_pair_matched_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = [
        "# CL hard-pair cleanup matched comparison",
        "",
        f"- targets_root: `{target_root}`",
        f"- seeds: `{seeds}`",
        f"- anchor_model: `{anchor}`",
        "",
    ]
    for regime_name, metrics in summary.get("regimes", {}).items():
        md.append(f"## {regime_name}")
        for k in KEY_METRICS:
            md.append(f"- {k}: `{float(metrics.get(k, 0.0)):.4f}`")
        md.append("")
    md.append("## Delta (clean - baseline)")
    for k, v in summary.get("delta_clean_minus_baseline", {}).items():
        md.append(f"- {k}: `{float(v):+.4f}`")
    md.append("")
    (out_dir / "cl_hard_pair_matched_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "regimes": sorted(summary.get("regimes", {}).keys())}, indent=2))


if __name__ == "__main__":
    main()
