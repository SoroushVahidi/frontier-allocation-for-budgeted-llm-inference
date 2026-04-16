#!/usr/bin/env python3
"""Matched comparison: old vs richer feature sets on fixed supervision regimes."""

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
    scorer_from_model,
    train_models,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run matched hard-case feature representation experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", required=True)
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--feature-sets", default="v1,v2")
    p.add_argument("--regimes", default="all_pairs_approx,promoted_exact_hard_region")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    return p.parse_args()


def _mean(xs: list[float]) -> float:
    return sum(xs) / max(1, len(xs))


def _pair_acc_subset(rows: list[dict[str, Any]], score_fn, pred) -> float:
    filt = [r for r in rows if r.get("split") == "test" and pred(r)]
    if not filt:
        return 0.0
    ok = 0
    for r in filt:
        si = score_fn({"x": r["x_i"]})
        sj = score_fn({"x": r["x_j"]})
        ok += int((1 if si >= sj else 0) == int(r["label"]))
    return ok / len(filt)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    feature_sets = [s.strip() for s in args.feature_sets.split(",") if s.strip()]
    regimes = [s.strip() for s in args.regimes.split(",") if s.strip()]

    flat: list[dict[str, Any]] = []
    nested: dict[str, Any] = {
        "run_id": args.run_id,
        "targets_root": args.targets_root,
        "seeds": seeds,
        "feature_sets": feature_sets,
        "regimes": regimes,
        "results": {},
    }

    for regime in regimes:
        regime_dir = Path(args.targets_root) / f"regime_{regime}"
        artifacts = load_label_artifacts(regime_dir)
        nested["results"][regime] = {}
        for feature_set in feature_sets:
            nested["results"][regime][feature_set] = {}
            for seed in seeds:
                cfg = LearningConfig(seed=seed, near_tie_margin=float(args.near_tie_margin), feature_set=feature_set)
                tables = prepare_learning_tables(artifacts, cfg)
                models = train_models(tables, cfg, model_artifact_dir=out_dir / f"{regime}_{feature_set}_seed_{seed}" / "models")
                evals = evaluate_models(models, tables, cfg)
                nested["results"][regime][feature_set][str(seed)] = evals

                for name, model in models.items():
                    score_fn = scorer_from_model(model)
                    adjacent = _pair_acc_subset(tables["pairwise"], score_fn, lambda r: str(r.get("pair_type", "")) == "adjacent_rank")
                    exact_promoted = _pair_acc_subset(tables["pairwise"], score_fn, lambda r: str(r.get("label_source", "")).startswith("exact"))
                    met = evals.get(name, {})
                    flat.append(
                        {
                            "regime": regime,
                            "feature_set": feature_set,
                            "seed": seed,
                            "model": name,
                            "pairwise_accuracy_test": float(met.get("pairwise_accuracy_test", 0.0)),
                            "top1_test": float(met.get("ranking_top1_accuracy_test", 0.0)),
                            "near_tie_test": float(met.get("near_tie_pairwise_accuracy_test", 0.0)),
                            "adjacent_rank_test": float(adjacent),
                            "exact_only_test": float(met.get("exact_only_pairwise_accuracy_test", 0.0)),
                            "exact_promoted_slice_test": float(exact_promoted),
                            "pairwise_accuracy_by_dataset": met.get("pairwise_accuracy_by_dataset", {}),
                            "pairwise_accuracy_by_budget": met.get("pairwise_accuracy_by_budget", {}),
                        }
                    )

    (out_dir / "hard_case_feature_representation_results.json").write_text(json.dumps(nested, indent=2), encoding="utf-8")
    (out_dir / "hard_case_feature_representation_summary.json").write_text(json.dumps(flat, indent=2), encoding="utf-8")

    md = [
        "# Hard-case feature representation matched experiment",
        "",
        f"- targets_root: `{args.targets_root}`",
        f"- seeds: `{seeds}`",
        f"- feature_sets: `{feature_sets}`",
        f"- regimes: `{regimes}`",
        "",
    ]
    for regime in regimes:
        md.append(f"## Regime `{regime}`")
        for model in sorted({r["model"] for r in flat if r["regime"] == regime}):
            md.append(f"### Model `{model}`")
            for fset in feature_sets:
                rows = [r for r in flat if r["regime"] == regime and r["model"] == model and r["feature_set"] == fset]
                if not rows:
                    continue
                md.append(
                    f"- {fset}: pairwise={_mean([r['pairwise_accuracy_test'] for r in rows]):.4f}, "
                    f"top1={_mean([r['top1_test'] for r in rows]):.4f}, "
                    f"near_tie={_mean([r['near_tie_test'] for r in rows]):.4f}, "
                    f"adjacent={_mean([r['adjacent_rank_test'] for r in rows]):.4f}, "
                    f"exact_only={_mean([r['exact_only_test'] for r in rows]):.4f}, "
                    f"exact_promoted={_mean([r['exact_promoted_slice_test'] for r in rows]):.4f}"
                )
            md.append("")
    (out_dir / "hard_case_feature_representation_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "rows": len(flat)}, indent=2))


if __name__ == "__main__":
    main()
