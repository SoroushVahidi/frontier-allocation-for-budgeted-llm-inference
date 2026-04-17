#!/usr/bin/env python3
"""Bounded structured-ambiguity experiment for branch allocation."""

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
    p = argparse.ArgumentParser(description="Run structured ambiguity matched experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", default="")
    p.add_argument("--seeds", default="17,29,43")
    p.add_argument("--regimes", default="all_pairs_approx,promoted_exact_hard_region")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    return p.parse_args()


def _mean(vals: list[float]) -> float:
    return sum(vals) / max(1, len(vals))


def _extract_pairwise(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "pairwise_accuracy_test": float(m.get("pairwise_accuracy_test", 0.0)),
        "near_tie_pairwise_accuracy_test": float(m.get("near_tie_pairwise_accuracy_test", 0.0)),
        "adjacent_rank_pairwise_accuracy_test": float(m.get("adjacent_rank_pairwise_accuracy_test", 0.0)),
        "exact_promoted_hard_region_pairwise_accuracy_test": float(m.get("exact_promoted_hard_region_pairwise_accuracy_test", 0.0)),
    }


def _extract_defer(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "accepted_only_accuracy_test": float(m.get("accepted_only_accuracy_test", 0.0)),
        "coverage_test": float(m.get("coverage_test", 0.0)),
        "defer_f1_test": float(m.get("defer_f1_test", 0.0)),
        "near_tie_accepted_accuracy_test": float(m.get("near_tie_accepted_accuracy_test", 0.0)),
        "adjacent_rank_accepted_accuracy_test": float(m.get("adjacent_rank_accepted_accuracy_test", 0.0)),
        "exact_promoted_hard_region_accepted_accuracy_test": float(m.get("exact_promoted_hard_region_accepted_accuracy_test", 0.0)),
    }


def main() -> None:
    args = parse_args()
    run_id = args.run_id.strip() or f"structured_ambiguity_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir = Path(args.output_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = [int(s.strip()) for s in str(args.seeds).split(",") if s.strip()]
    regimes = [s.strip() for s in str(args.regimes).split(",") if s.strip()]

    rows: list[dict[str, Any]] = []
    influence_rows: list[dict[str, Any]] = []
    nested: dict[str, Any] = {"run_id": run_id, "regimes": regimes, "seeds": seeds, "results": {}}

    for regime in regimes:
        labels_dir = Path(args.targets_root) / f"regime_{regime}"
        artifacts = load_label_artifacts(labels_dir)
        nested["results"][regime] = {}
        for seed in seeds:
            shared = dict(
                seed=seed,
                near_tie_margin=float(args.near_tie_margin),
                train_lightgbm_ranker=False,
                train_catboost_ranker=False,
            )

            cfg_v2 = LearningConfig(feature_set="v2", train_pairwise=True, train_pairwise_defer_classifier=False, **shared)
            tbl_v2 = prepare_learning_tables(artifacts, cfg_v2)
            mdl_v2 = train_models(tbl_v2, cfg_v2, model_artifact_dir=out_dir / "artifacts" / regime / f"seed_{seed}" / "pair_v2")
            met_v2 = evaluate_models(mdl_v2, tbl_v2, cfg_v2).get("pairwise", {})

            cfg_v3 = LearningConfig(feature_set="v3", train_pairwise=True, train_pairwise_defer_classifier=False, **shared)
            tbl_v3 = prepare_learning_tables(artifacts, cfg_v3)
            mdl_v3 = train_models(tbl_v3, cfg_v3, model_artifact_dir=out_dir / "artifacts" / regime / f"seed_{seed}" / "pair_v3")
            met_v3 = evaluate_models(mdl_v3, tbl_v3, cfg_v3).get("pairwise", {})

            cfg_defer = LearningConfig(
                feature_set="v3",
                train_pairwise=False,
                train_pairwise_defer_classifier=True,
                defer_use_outside_option=True,
                defer_include_approx=True,
                **shared,
            )
            tbl_defer = prepare_learning_tables(artifacts, cfg_defer)
            mdl_defer = train_models(
                tbl_defer,
                cfg_defer,
                model_artifact_dir=out_dir / "artifacts" / regime / f"seed_{seed}" / "defer_v3",
            )
            met_defer = evaluate_models(mdl_defer, tbl_defer, cfg_defer).get("pairwise_defer_classifier", {})
            defer_model = mdl_defer.get("pairwise_defer_classifier", {})
            if str(defer_model.get("status", "")) == "ok":
                feature_names = [str(f) for f in defer_model.get("feature_names", [])]
                coef = defer_model.get("weights", [])
                abs_coef = [sum(abs(float(row[i])) for row in coef) for i in range(len(feature_names))] if coef and feature_names else []

                def group_for(name: str) -> str:
                    if name.startswith("frontier_"):
                        return "frontier_relative"
                    if name.startswith("pair_"):
                        return "relational_margin"
                    if "budget" in name:
                        return "budget_conditioned"
                    if "outside" in name or "defer" in name or "stop_" in name:
                        return "outside_defer"
                    if "instability" in name or "delta" in name or "stalled" in name:
                        return "trajectory_instability"
                    return "other"

                grouped: dict[str, float] = {}
                for name, val in zip(feature_names, abs_coef):
                    grouped[group_for(name)] = grouped.get(group_for(name), 0.0) + float(val)
                influence_rows.append({"regime": regime, "seed": seed, **grouped})

            nested["results"][regime][str(seed)] = {
                "pairwise_logreg_v2": _extract_pairwise(met_v2),
                "pairwise_logreg_v3": _extract_pairwise(met_v3),
                "pairwise_defer_v3": _extract_defer(met_defer),
            }
            rows.extend(
                [
                    {"regime": regime, "seed": seed, "model": "pairwise_logreg_v2", **_extract_pairwise(met_v2)},
                    {"regime": regime, "seed": seed, "model": "pairwise_logreg_v3", **_extract_pairwise(met_v3)},
                    {"regime": regime, "seed": seed, "model": "pairwise_defer_v3", **_extract_defer(met_defer)},
                ]
            )

    aggregate: dict[str, Any] = {}
    for regime in regimes:
        aggregate[regime] = {}
        for model_name in ["pairwise_logreg_v2", "pairwise_logreg_v3", "pairwise_defer_v3"]:
            subset = [r for r in rows if r["regime"] == regime and r["model"] == model_name]
            if not subset:
                continue
            keys = [k for k in subset[0].keys() if k not in {"regime", "seed", "model"}]
            aggregate[regime][model_name] = {k: _mean([float(s.get(k, 0.0)) for s in subset]) for k in keys}

    influence: dict[str, Any] = {}
    for regime in regimes:
        per_reg = [r for r in influence_rows if r.get("regime") == regime]
        keys = sorted({k for r in per_reg for k in r.keys() if k not in {"regime", "seed"}})
        influence[regime] = {k: _mean([float(r.get(k, 0.0)) for r in per_reg]) for k in keys} if per_reg else {}

    summary = {
        "run_id": run_id,
        "aggregate": aggregate,
        "rows": rows,
        "feature_group_influence_abscoef": influence,
        "safe_interpretation": (
            "Structured ambiguity results are diagnostic; improvements indicate better ambiguity representation, "
            "not a solved universal allocator."
        ),
    }

    (out_dir / "structured_ambiguity_results.json").write_text(json.dumps(nested, indent=2), encoding="utf-8")
    (out_dir / "structured_ambiguity_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = [
        "# Structured ambiguity experiment",
        "",
        f"- run_id: `{run_id}`",
        f"- regimes: `{regimes}`",
        f"- seeds: `{seeds}`",
        "",
    ]
    for regime in regimes:
        md.append(f"## Regime `{regime}`")
        for model_name, vals in aggregate.get(regime, {}).items():
            md.append(f"### {model_name}")
            for k, v in vals.items():
                md.append(f"- {k}: `{v:.6f}`")
            md.append("")
        if influence.get(regime):
            md.append("### Defer feature-group influence (abs-coef proxy)")
            for k, v in sorted(influence[regime].items(), key=lambda kv: kv[1], reverse=True):
                md.append(f"- {k}: `{v:.6f}`")
            md.append("")

    (out_dir / "structured_ambiguity_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "output_dir": str(out_dir), "rows": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
