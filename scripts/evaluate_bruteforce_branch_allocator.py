#!/usr/bin/env python3
"""Evaluate trained branch-allocation models on brute-force label artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (
    LearningConfig,
    evaluate_models,
    load_label_artifacts,
    prepare_learning_tables,
    write_json,
    write_markdown_report,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate learned branch-allocation models")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--models-json", required=True)
    p.add_argument("--output", default="")
    p.add_argument("--near-tie-margin", type=float, default=0.05)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--val-ratio", type=float, default=0.1)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    models_payload = json.loads(Path(args.models_json).read_text(encoding="utf-8"))
    models = dict(models_payload.get("models", {}))
    run_id = str(models_payload.get("run_id", "eval_only"))

    cfg = LearningConfig(
        seed=int(args.seed),
        train_ratio=float(args.train_ratio),
        val_ratio=float(args.val_ratio),
        near_tie_margin=float(args.near_tie_margin),
    )

    artifacts = load_label_artifacts(Path(args.labels_dir))
    tables = prepare_learning_tables(artifacts, cfg)
    eval_summary = evaluate_models(models, tables, cfg)

    out_path = Path(args.output) if args.output else Path(args.models_json).with_name("evaluation_recomputed.json")
    write_json(out_path, {"run_id": run_id, "evaluation": eval_summary})

    report_path = out_path.with_suffix(".md")
    write_markdown_report(report_path, run_id=run_id, config=cfg, eval_summary=eval_summary)

    print(json.dumps({"output": str(out_path), "report": str(report_path)}, indent=2))


if __name__ == "__main__":
    main()
