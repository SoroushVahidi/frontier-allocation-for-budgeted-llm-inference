#!/usr/bin/env python3
"""Run matched learning comparisons across target-construction regimes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (  # noqa: E402
    LearningConfig,
    evaluate_models,
    load_label_artifacts,
    prepare_learning_tables,
    train_models,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Matched target-fidelity regime experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", required=True)
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--pairwise-near-tie-action", choices=["none", "filter", "downweight"], default="none")
    p.add_argument("--pairwise-near-tie-downweight", type=float, default=0.25)
    p.add_argument("--uncertainty-weighting", action="store_true")
    return p.parse_args()


def _mean(xs: list[float]) -> float:
    return sum(xs) / max(1, len(xs))


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    regime_dirs = sorted([p for p in Path(args.targets_root).glob("regime_*") if p.is_dir()])

    payload: dict[str, Any] = {
        "run_id": args.run_id,
        "targets_root": args.targets_root,
        "seeds": seeds,
        "regimes": {},
    }

    flat_summary: list[dict[str, Any]] = []

    for regime_dir in regime_dirs:
        regime_name = regime_dir.name.replace("regime_", "")
        payload["regimes"][regime_name] = {}

        for seed in seeds:
            cfg = LearningConfig(
                seed=seed,
                near_tie_margin=float(args.near_tie_margin),
                pairwise_near_tie_action=str(args.pairwise_near_tie_action),
                pairwise_near_tie_downweight=float(args.pairwise_near_tie_downweight),
                uncertainty_weighting=bool(args.uncertainty_weighting),
            )
            artifacts = load_label_artifacts(regime_dir)
            tables = prepare_learning_tables(artifacts, cfg)
            models = train_models(tables, cfg, model_artifact_dir=out_dir / f"{regime_name}_seed_{seed}" / "models")
            evals = evaluate_models(models, tables, cfg)
            payload["regimes"][regime_name][str(seed)] = {
                "config": {
                    "near_tie_margin": cfg.near_tie_margin,
                    "pairwise_near_tie_action": cfg.pairwise_near_tie_action,
                    "pairwise_near_tie_downweight": cfg.pairwise_near_tie_downweight,
                    "uncertainty_weighting": cfg.uncertainty_weighting,
                },
                "evaluation": evals,
            }
            for model_name, met in evals.items():
                flat_summary.append(
                    {
                        "regime": regime_name,
                        "seed": seed,
                        "model": model_name,
                        "pairwise_accuracy_test": float(met.get("pairwise_accuracy_test", 0.0)),
                        "top1_test": float(met.get("ranking_top1_accuracy_test", 0.0)),
                        "near_tie_test": float(met.get("near_tie_pairwise_accuracy_test", 0.0)),
                        "far_margin_test": float(met.get("far_margin_pairwise_accuracy_test", 0.0)),
                        "exact_mode_test": float(met.get("pairwise_accuracy_by_mode", {}).get("exact", 0.0)),
                    }
                )

    (out_dir / "target_fidelity_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "target_fidelity_summary.json").write_text(json.dumps(flat_summary, indent=2), encoding="utf-8")

    md = ["# Target-fidelity matched regime experiment", "", f"- targets_root: `{args.targets_root}`", f"- seeds: `{seeds}`", ""]
    regimes = sorted(set(r["regime"] for r in flat_summary))
    models = sorted(set(r["model"] for r in flat_summary))
    for regime in regimes:
        md.append(f"## Regime `{regime}`")
        for model in models:
            rows = [r for r in flat_summary if r["regime"] == regime and r["model"] == model]
            if not rows:
                continue
            md.append(
                f"- {model}: pairwise={_mean([x['pairwise_accuracy_test'] for x in rows]):.4f}, "
                f"top1={_mean([x['top1_test'] for x in rows]):.4f}, "
                f"near_tie={_mean([x['near_tie_test'] for x in rows]):.4f}, "
                f"far_margin={_mean([x['far_margin_test'] for x in rows]):.4f}, "
                f"exact={_mean([x['exact_mode_test'] for x in rows]):.4f}"
            )
        md.append("")
    (out_dir / "target_fidelity_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "regimes": regimes}, indent=2))


if __name__ == "__main__":
    main()
