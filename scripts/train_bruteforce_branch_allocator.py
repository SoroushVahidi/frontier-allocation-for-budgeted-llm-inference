#!/usr/bin/env python3
"""Train branch-allocation models from brute-force branch-comparison labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (
    LearningConfig,
    config_to_dict,
    evaluate_models,
    load_label_artifacts,
    prepare_learning_tables,
    train_models,
    write_json,
    write_markdown_report,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train branch-allocation models from brute-force labels")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", default="")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--near-tie-margin", type=float, default=0.05)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--val-ratio", type=float, default=0.1)
    p.add_argument("--pairwise-max-iter", type=int, default=500)
    p.add_argument("--outside-max-iter", type=int, default=500)
    p.add_argument("--pointwise-alpha", type=float, default=1.0)
    p.add_argument("--disable-lightgbm-ranker", action="store_true")
    p.add_argument("--disable-catboost-ranker", action="store_true")
    p.add_argument("--pairwise-near-tie-action", choices=["none", "filter", "downweight"], default="none")
    p.add_argument("--pairwise-near-tie-downweight", type=float, default=0.25)
    p.add_argument("--uncertainty-weighting", action="store_true")
    p.add_argument("--margin-weight-power", type=float, default=1.0)
    p.add_argument("--std-weight-scale", type=float, default=3.0)
    p.add_argument("--approx-mode-weight", type=float, default=0.9)
    p.add_argument("--exact-mode-weight", type=float, default=1.05)
    p.add_argument("--lightgbm-num-leaves", type=int, default=31)
    p.add_argument("--lightgbm-learning-rate", type=float, default=0.05)
    p.add_argument("--lightgbm-n-estimators", type=int, default=200)
    p.add_argument("--catboost-iterations", type=int, default=250)
    p.add_argument("--catboost-learning-rate", type=float, default=0.05)
    p.add_argument("--catboost-depth", type=int, default=6)
    p.add_argument("--disable-pairwise", action="store_true")
    p.add_argument("--disable-pointwise", action="store_true")
    p.add_argument("--disable-outside-option", action="store_true")
    p.add_argument("--resume", action="store_true")
    return p.parse_args()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _default_run_id() -> str:
    return f"learn_{time.strftime('%Y%m%d_%H%M%S', time.gmtime())}"


def main() -> None:
    args = parse_args()
    run_id = args.run_id.strip() or _default_run_id()
    out_dir = Path(args.output_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    models_path = out_dir / "models.json"
    eval_path = out_dir / "evaluation.json"
    manifest_path = out_dir / "manifest.json"
    report_path = out_dir / "report.md"
    progress_path = out_dir / "progress.json"

    if args.resume and models_path.exists() and eval_path.exists() and manifest_path.exists():
        payload = {
            "run_id": run_id,
            "status": "resume_noop_already_complete",
            "models": str(models_path),
            "evaluation": str(eval_path),
            "manifest": str(manifest_path),
        }
        print(json.dumps(payload, indent=2))
        return

    cfg = LearningConfig(
        seed=int(args.seed),
        train_ratio=float(args.train_ratio),
        val_ratio=float(args.val_ratio),
        near_tie_margin=float(args.near_tie_margin),
        pairwise_max_iter=int(args.pairwise_max_iter),
        outside_max_iter=int(args.outside_max_iter),
        pointwise_alpha=float(args.pointwise_alpha),
        train_pairwise=not bool(args.disable_pairwise),
        train_pointwise=not bool(args.disable_pointwise),
        train_outside_option=not bool(args.disable_outside_option),
        train_lightgbm_ranker=not bool(args.disable_lightgbm_ranker),
        train_catboost_ranker=not bool(args.disable_catboost_ranker),
        pairwise_near_tie_action=str(args.pairwise_near_tie_action),
        pairwise_near_tie_downweight=float(args.pairwise_near_tie_downweight),
        uncertainty_weighting=bool(args.uncertainty_weighting),
        margin_weight_power=float(args.margin_weight_power),
        std_weight_scale=float(args.std_weight_scale),
        approx_mode_weight=float(args.approx_mode_weight),
        exact_mode_weight=float(args.exact_mode_weight),
        lightgbm_num_leaves=int(args.lightgbm_num_leaves),
        lightgbm_learning_rate=float(args.lightgbm_learning_rate),
        lightgbm_n_estimators=int(args.lightgbm_n_estimators),
        catboost_iterations=int(args.catboost_iterations),
        catboost_learning_rate=float(args.catboost_learning_rate),
        catboost_depth=int(args.catboost_depth),
    )

    start = time.time()
    labels_dir = Path(args.labels_dir)
    artifacts = load_label_artifacts(labels_dir)
    tables = prepare_learning_tables(artifacts, cfg)

    write_json(
        progress_path,
        {
            "run_id": run_id,
            "phase": "loaded",
            "elapsed_sec": time.time() - start,
            "n_candidates": len(tables["candidates"]),
            "n_pairwise": len(tables["pairwise"]),
        },
    )

    models = train_models(tables, cfg, model_artifact_dir=out_dir / "model_artifacts")
    write_json(models_path, {"run_id": run_id, "config": config_to_dict(cfg), "models": models})

    eval_summary = evaluate_models(models, tables, cfg)
    write_json(eval_path, {"run_id": run_id, "evaluation": eval_summary})

    write_markdown_report(report_path, run_id=run_id, config=cfg, eval_summary=eval_summary)

    manifest = {
        "run_id": run_id,
        "generator": "bruteforce_branch_allocator_learning_v1",
        "started_at_epoch": start,
        "elapsed_sec": time.time() - start,
        "inputs": {
            "labels_dir": str(labels_dir),
            "labels_dir_files": {
                "candidate_labels": str(labels_dir / "candidate_labels.jsonl"),
                "pairwise_labels": str(labels_dir / "pairwise_labels.jsonl"),
                "state_summaries": str(labels_dir / "state_summaries.jsonl"),
            },
            "labels_sha256": {
                "candidate_labels": _sha256(labels_dir / "candidate_labels.jsonl"),
                "pairwise_labels": _sha256(labels_dir / "pairwise_labels.jsonl"),
                "state_summaries": _sha256(labels_dir / "state_summaries.jsonl"),
            },
        },
        "config": config_to_dict(cfg),
        "outputs": {
            "models": str(models_path),
            "evaluation": str(eval_path),
            "report": str(report_path),
            "progress": str(progress_path),
        },
        "output_sha256": {
            "models": _sha256(models_path),
            "evaluation": _sha256(eval_path),
            "report": _sha256(report_path),
        },
    }
    write_json(manifest_path, manifest)
    write_json(
        progress_path,
        {
            "run_id": run_id,
            "phase": "complete",
            "elapsed_sec": time.time() - start,
            "models": list(models.keys()),
        },
    )

    print(
        json.dumps(
            {
                "run_id": run_id,
                "output_dir": str(out_dir),
                "models": str(models_path),
                "evaluation": str(eval_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
