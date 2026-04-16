#!/usr/bin/env python3
"""Train/evaluate branch allocators across seeds and cross-dataset held-out slices."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (
    LearningConfig,
    evaluate_models,
    load_label_artifacts,
    prepare_learning_tables,
    train_models,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scaling experiment for brute-force branch allocators")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", required=True)
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--val-ratio", type=float, default=0.1)
    p.add_argument("--pairwise-near-tie-action", choices=["none", "filter", "downweight"], default="none")
    p.add_argument("--pairwise-near-tie-downweight", type=float, default=0.25)
    p.add_argument("--uncertainty-weighting", action="store_true")
    p.add_argument("--disable-lightgbm-ranker", action="store_true")
    p.add_argument("--disable-catboost-ranker", action="store_true")
    return p.parse_args()


def _dataset_for_pair_row(row: dict[str, Any], state_to_dataset: dict[str, str]) -> str:
    return str(row.get("source_dataset_name") or state_to_dataset.get(str(row.get("state_id")), "unknown"))


def _dataset_for_candidate_row(row: dict[str, Any], state_to_dataset: dict[str, str]) -> str:
    return str(row.get("source_dataset_name") or state_to_dataset.get(str(row.get("state_id")), "unknown"))


def _train_excluding_dataset(
    tables: dict[str, Any],
    cfg: LearningConfig,
    heldout_dataset: str,
    *,
    model_artifact_dir: Path,
) -> dict[str, Any]:
    t = copy.deepcopy(tables)
    for row in t["candidates"]:
        ds = _dataset_for_candidate_row(row, t["state_to_dataset"])
        if ds == heldout_dataset:
            row["split"] = "test"
    for row in t["pairwise"]:
        ds = _dataset_for_pair_row(row, t["state_to_dataset"])
        if ds == heldout_dataset:
            row["split"] = "test"
    models = train_models(t, cfg, model_artifact_dir=model_artifact_dir)
    eval_summary = evaluate_models(models, t, cfg)
    return {"models": models, "evaluation": eval_summary}


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts = load_label_artifacts(Path(args.labels_dir))
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]

    all_results: dict[str, Any] = {
        "run_id": args.run_id,
        "labels_dir": args.labels_dir,
        "seeds": seeds,
        "near_tie_margin": args.near_tie_margin,
        "full_corpus": {},
        "cross_dataset_leave_one_out": {},
    }

    for seed in seeds:
        cfg = LearningConfig(
            seed=seed,
            train_ratio=float(args.train_ratio),
            val_ratio=float(args.val_ratio),
            near_tie_margin=float(args.near_tie_margin),
            pairwise_near_tie_action=str(args.pairwise_near_tie_action),
            pairwise_near_tie_downweight=float(args.pairwise_near_tie_downweight),
            uncertainty_weighting=bool(args.uncertainty_weighting),
            train_lightgbm_ranker=not bool(args.disable_lightgbm_ranker),
            train_catboost_ranker=not bool(args.disable_catboost_ranker),
        )
        tables = prepare_learning_tables(artifacts, cfg)
        seed_out_dir = out_dir / f"seed_{seed}"
        models = train_models(tables, cfg, model_artifact_dir=seed_out_dir / "full_corpus_models")
        evaluation = evaluate_models(models, tables, cfg)
        all_results["full_corpus"][str(seed)] = {
            "config": {
                "seed": seed,
                "train_ratio": args.train_ratio,
                "val_ratio": args.val_ratio,
                "near_tie_margin": args.near_tie_margin,
                "pairwise_near_tie_action": args.pairwise_near_tie_action,
                "pairwise_near_tie_downweight": args.pairwise_near_tie_downweight,
                "uncertainty_weighting": bool(args.uncertainty_weighting),
                "train_lightgbm_ranker": not bool(args.disable_lightgbm_ranker),
                "train_catboost_ranker": not bool(args.disable_catboost_ranker),
            },
            "models": models,
            "evaluation": evaluation,
        }

        datasets = sorted(set(tables["state_to_dataset"].values()))
        all_results["cross_dataset_leave_one_out"][str(seed)] = {}
        for ds in datasets:
            res = _train_excluding_dataset(
                tables,
                cfg,
                ds,
                model_artifact_dir=seed_out_dir / f"leaveout_{ds}_models",
            )
            all_results["cross_dataset_leave_one_out"][str(seed)][ds] = res

    (out_dir / "scaling_experiment_results.json").write_text(json.dumps(all_results, indent=2), encoding="utf-8")

    # Lightweight aggregate summary for docs.
    summary_rows: list[dict[str, Any]] = []
    for seed in seeds:
        evals = all_results["full_corpus"][str(seed)]["evaluation"]
        for model_name, met in evals.items():
            summary_rows.append(
                {
                    "seed": seed,
                    "scope": "full_corpus",
                    "heldout_dataset": "",
                    "model": model_name,
                    "pairwise_accuracy_test": met.get("pairwise_accuracy_test", 0.0),
                    "top1_test": met.get("ranking_top1_accuracy_test", 0.0),
                    "near_tie_test": met.get("near_tie_pairwise_accuracy_test", 0.0),
                    "far_margin_test": met.get("far_margin_pairwise_accuracy_test", 0.0),
                }
            )
        for ds, block in all_results["cross_dataset_leave_one_out"][str(seed)].items():
            for model_name, met in block["evaluation"].items():
                summary_rows.append(
                    {
                        "seed": seed,
                        "scope": "leave_one_out",
                        "heldout_dataset": ds,
                        "model": model_name,
                        "pairwise_accuracy_test": met.get("pairwise_accuracy_test", 0.0),
                        "top1_test": met.get("ranking_top1_accuracy_test", 0.0),
                        "near_tie_test": met.get("near_tie_pairwise_accuracy_test", 0.0),
                        "far_margin_test": met.get("far_margin_pairwise_accuracy_test", 0.0),
                    }
                )

    (out_dir / "scaling_experiment_summary.json").write_text(json.dumps(summary_rows, indent=2), encoding="utf-8")

    lines = [
        "# Brute-force allocator scaling experiment",
        "",
        f"- labels_dir: `{args.labels_dir}`",
        f"- seeds: `{seeds}`",
        "",
        "## Full-corpus metrics",
        "",
    ]
    for seed in seeds:
        lines.append(f"### Seed {seed}")
        for model_name, met in all_results["full_corpus"][str(seed)]["evaluation"].items():
            lines.append(f"- {model_name}: pairwise={met.get('pairwise_accuracy_test',0.0):.3f}, top1={met.get('ranking_top1_accuracy_test',0.0):.3f}, near_tie={met.get('near_tie_pairwise_accuracy_test',0.0):.3f}")
        lines.append("")

    lines.extend(["## Leave-one-dataset-out metrics", ""])
    for seed in seeds:
        lines.append(f"### Seed {seed}")
        for ds, block in all_results["cross_dataset_leave_one_out"][str(seed)].items():
            compact = ", ".join(
                [
                    f"{model_name}: pairwise={met.get('pairwise_accuracy_test', 0.0):.3f}, top1={met.get('ranking_top1_accuracy_test', 0.0):.3f}"
                    for model_name, met in block["evaluation"].items()
                ]
            )
            lines.append(f"- hold out {ds}: {compact}")
        lines.append("")

    (out_dir / "scaling_experiment_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
