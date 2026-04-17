#!/usr/bin/env python3
"""Bounded matched experiment: pairwise logistic vs linear/nystroem SVM."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
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
    p = argparse.ArgumentParser(description="Run bounded pairwise SVM margin experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", default="")
    p.add_argument("--seeds", default="17,29,43")
    p.add_argument("--regimes", default="all_pairs_approx,promoted_exact_hard_region")
    p.add_argument("--feature-set", choices=["v1", "v2"], default="v2")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--svm-c", type=float, default=1.0)
    p.add_argument("--svm-nystroem-gamma", type=float, default=0.5)
    p.add_argument("--svm-max-train-rows-for-nystroem", type=int, default=8000)
    p.add_argument("--svm-nystroem-components", type=int, default=256)
    p.add_argument("--include-kernelized", action="store_true")
    return p.parse_args()


def _mean(vals: list[float]) -> float:
    return sum(vals) / max(1, len(vals))


def _model_keys(include_kernelized: bool) -> list[str]:
    keys = ["pairwise", "pairwise_svm_linear"]
    if include_kernelized:
        keys.append("pairwise_svm_nystroem")
    return keys


def _extract_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "pairwise_accuracy_test": float(metrics.get("pairwise_accuracy_test", 0.0)),
        "near_tie_pairwise_accuracy_test": float(metrics.get("near_tie_pairwise_accuracy_test", 0.0)),
        "far_margin_pairwise_accuracy_test": float(metrics.get("far_margin_pairwise_accuracy_test", 0.0)),
        "adjacent_rank_pairwise_accuracy_test": float(metrics.get("adjacent_rank_pairwise_accuracy_test", 0.0)),
        "exact_only_pairwise_accuracy_test": float(metrics.get("exact_only_pairwise_accuracy_test", 0.0)),
        "exact_promoted_pairwise_accuracy_test": float(metrics.get("exact_promoted_pairwise_accuracy_test", 0.0)),
        "exact_promoted_hard_region_pairwise_accuracy_test": float(
            metrics.get("exact_promoted_hard_region_pairwise_accuracy_test", 0.0)
        ),
        "ranking_top1_accuracy_test": metrics.get("ranking_top1_accuracy_test", None),
    }


def main() -> None:
    args = parse_args()
    run_id = args.run_id.strip() or f"pairwise_svm_margin_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir = Path(args.output_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = [int(s.strip()) for s in str(args.seeds).split(",") if s.strip()]
    regimes = [s.strip() for s in str(args.regimes).split(",") if s.strip()]
    records: list[dict[str, Any]] = []
    nested: dict[str, Any] = {
        "run_id": run_id,
        "targets_root": str(args.targets_root),
        "feature_set": args.feature_set,
        "near_tie_margin": float(args.near_tie_margin),
        "seeds": seeds,
        "regimes": regimes,
        "results": {},
    }

    for regime in regimes:
        labels_dir = Path(args.targets_root) / f"regime_{regime}"
        artifacts = load_label_artifacts(labels_dir)
        nested["results"][regime] = {}
        for seed in seeds:
            nested["results"][regime][str(seed)] = {}

            shared = dict(
                seed=seed,
                near_tie_margin=float(args.near_tie_margin),
                feature_set=str(args.feature_set),
                train_lightgbm_ranker=False,
                train_catboost_ranker=False,
                svm_c=float(args.svm_c),
                svm_use_sample_weight=True,
                svm_nystroem_gamma=float(args.svm_nystroem_gamma),
                svm_max_train_rows_for_nystroem=int(args.svm_max_train_rows_for_nystroem),
                svm_nystroem_components=int(args.svm_nystroem_components),
            )

            cfg_log = LearningConfig(train_pairwise=True, train_pairwise_svm=False, train_pairwise_svm_nystroem=False, **shared)
            tbl_log = prepare_learning_tables(artifacts, cfg_log)
            mdl_log = train_models(tbl_log, cfg_log, model_artifact_dir=out_dir / "artifacts" / regime / f"seed_{seed}" / "logistic")
            ev_log = evaluate_models(mdl_log, tbl_log, cfg_log).get("pairwise", {})

            cfg_lin = LearningConfig(train_pairwise=False, train_pairwise_svm=True, train_pairwise_svm_nystroem=False, **shared)
            tbl_lin = prepare_learning_tables(artifacts, cfg_lin)
            mdl_lin = train_models(tbl_lin, cfg_lin, model_artifact_dir=out_dir / "artifacts" / regime / f"seed_{seed}" / "svm_linear")
            ev_lin = evaluate_models(mdl_lin, tbl_lin, cfg_lin).get("pairwise_svm_linear", {})

            seed_result = {
                "pairwise": _extract_metrics(ev_log),
                "pairwise_svm_linear": _extract_metrics(ev_lin),
            }

            if args.include_kernelized:
                cfg_nys = LearningConfig(
                    train_pairwise=False,
                    train_pairwise_svm=True,
                    train_pairwise_svm_nystroem=True,
                    **shared,
                )
                tbl_nys = prepare_learning_tables(artifacts, cfg_nys)
                mdl_nys = train_models(
                    tbl_nys,
                    cfg_nys,
                    model_artifact_dir=out_dir / "artifacts" / regime / f"seed_{seed}" / "svm_nystroem",
                )
                ev_nys = evaluate_models(mdl_nys, tbl_nys, cfg_nys).get("pairwise_svm_nystroem", {})
                seed_result["pairwise_svm_nystroem"] = _extract_metrics(ev_nys)

            nested["results"][regime][str(seed)] = seed_result
            for model_name, met in seed_result.items():
                records.append({"regime": regime, "seed": seed, "model": model_name, **met})

    grouped: dict[str, Any] = {}
    for regime in regimes:
        grouped[regime] = {}
        for model_name in _model_keys(args.include_kernelized):
            rows = [r for r in records if r["regime"] == regime and r["model"] == model_name]
            if not rows:
                continue
            grouped[regime][model_name] = {
                k: _mean([float(rr[k]) for rr in rows])
                for k in [
                    "pairwise_accuracy_test",
                    "near_tie_pairwise_accuracy_test",
                    "far_margin_pairwise_accuracy_test",
                    "adjacent_rank_pairwise_accuracy_test",
                    "exact_only_pairwise_accuracy_test",
                    "exact_promoted_pairwise_accuracy_test",
                    "exact_promoted_hard_region_pairwise_accuracy_test",
                ]
            }

    summary_payload = {
        "run_id": run_id,
        "aggregate": grouped,
        "records": records,
        "safe_interpretation": (
            "SVM is a bounded margin-based baseline for hard-case diagnostics; model-class changes alone "
            "do not establish supervision-target bottlenecks as solved."
        ),
    }

    (out_dir / "pairwise_svm_margin_results.json").write_text(json.dumps(nested, indent=2), encoding="utf-8")
    (out_dir / "pairwise_svm_margin_summary.json").write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    md_lines = [
        "# Pairwise SVM margin experiment",
        "",
        f"- run_id: `{run_id}`",
        f"- targets_root: `{args.targets_root}`",
        f"- regimes: `{regimes}`",
        f"- seeds: `{seeds}`",
        f"- feature_set: `{args.feature_set}`",
        "",
        "## Safe interpretation",
        "",
        "SVM is a bounded margin-based baseline for ambiguous hard-case slices.",
        "This does not by itself establish that supervision-target bottlenecks are solved.",
        "",
    ]
    for regime in regimes:
        md_lines.append(f"## Regime `{regime}`")
        for model_name, agg in grouped.get(regime, {}).items():
            md_lines.append(f"### {model_name}")
            for metric_name, metric_val in agg.items():
                md_lines.append(f"- {metric_name}: `{metric_val:.6f}`")
            md_lines.append("")

    (out_dir / "pairwise_svm_margin_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "output_dir": str(out_dir), "rows": len(records)}, indent=2))


if __name__ == "__main__":
    main()
