#!/usr/bin/env python3
"""Matched binary vs ternary vs selective-abstention branch-comparison experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable

from sklearn.linear_model import LogisticRegression

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (  # noqa: E402
    LearningConfig,
    _sigmoid,
    load_label_artifacts,
    prepare_learning_tables,
    scorer_from_model,
    train_models,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Binary vs ternary vs abstain branch-comparison experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", required=True)
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--regimes", default="all_pairs_approx,promoted_exact_hard_region")
    p.add_argument("--feature-set", choices=["v1", "v2"], default="v2")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--tie-abs-margin-threshold", type=float, default=0.03)
    p.add_argument("--tie-relative-margin-threshold", type=float, default=0.15)
    p.add_argument("--tie-std-threshold", type=float, default=0.08)
    p.add_argument("--tie-use-near-tie-flag", action="store_true")
    p.add_argument("--tie-include-approx", action="store_true")
    p.add_argument("--tie-require-exact-or-mixed", action="store_true")
    p.add_argument("--abstain-confidence-threshold", type=float, default=0.20)
    p.add_argument("--fallback-policy", choices=["pointwise_value", "heuristic_margin", "unresolved"], default="pointwise_value")
    return p.parse_args()


def _mean(xs: list[float]) -> float:
    return sum(xs) / max(1, len(xs))


def _train_ternary_pair_model(rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    train = [r for r in rows if r.get("split") == "train"]
    if len(train) < 3:
        return {"status": "insufficient_train_rows"}
    x = [r["x_diff"] for r in train]
    y = [int(r.get("ternary_label", 1)) for r in train]
    if len(set(y)) < 2:
        return {"status": "single_class_train", "constant": int(y[0])}
    model = LogisticRegression(max_iter=600, random_state=seed)
    model.fit(x, y)
    return {"status": "ok", "model": model}


def _top1_from_pairwise_rows(
    pair_rows: list[dict[str, Any]],
    state_to_candidates: dict[str, list[dict[str, Any]]],
    decision_fn: Callable[[dict[str, Any]], int | None],
    fallback_pair_fn: Callable[[dict[str, Any]], int],
) -> float:
    by_state: dict[str, list[dict[str, Any]]] = {}
    for r in pair_rows:
        by_state.setdefault(str(r["state_id"]), []).append(r)
    ok = 0
    total = 0
    for sid, cands in state_to_candidates.items():
        test_cands = [c for c in cands if c.get("split") == "test"]
        if len(test_cands) < 2:
            continue
        bids = [str(c["branch_id"]) for c in test_cands]
        wins = {b: 0 for b in bids}
        for r in by_state.get(sid, []):
            if r.get("split") != "test":
                continue
            bi = str(r["branch_i"])
            bj = str(r["branch_j"])
            if bi not in wins or bj not in wins:
                continue
            pref = decision_fn(r)
            if pref is None:
                pref = fallback_pair_fn(r)
            if pref == 1:
                wins[bi] += 1
            else:
                wins[bj] += 1
        pred = max(wins.items(), key=lambda kv: (kv[1], kv[0]))[0]
        truth = max(test_cands, key=lambda c: float(c.get("estimated_value_if_allocate_next", 0.0)))["branch_id"]
        ok += int(str(pred) == str(truth))
        total += 1
    return ok / max(1, total)


def _metrics_for_predictions(
    rows: list[dict[str, Any]],
    *,
    pred_fn: Callable[[dict[str, Any]], int | None],
    forced_pred_fn: Callable[[dict[str, Any]], int],
) -> dict[str, float]:
    subset = [r for r in rows if r.get("split") == "test"]
    accepted = [r for r in subset if pred_fn(r) is not None]
    truth_tie = [bool(r.get("ambiguous_target_flag", False)) for r in subset]
    pred_tie = [pred_fn(r) is None for r in subset]

    def _acc(items: list[dict[str, Any]], fn: Callable[[dict[str, Any]], int | None]) -> float:
        if not items:
            return 0.0
        return sum(int((fn(r) if fn(r) is not None else 0) == int(r.get("label", 0))) for r in items) / len(items)

    tp = sum(int(t and p) for t, p in zip(truth_tie, pred_tie))
    fp = sum(int((not t) and p) for t, p in zip(truth_tie, pred_tie))
    fn = sum(int(t and (not p)) for t, p in zip(truth_tie, pred_tie))
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    f1 = 0.0 if (prec + rec) <= 1e-12 else (2.0 * prec * rec / (prec + rec))

    near = [r for r in subset if bool(r.get("near_tie_flag", False))]
    adjacent = [r for r in subset if str(r.get("pair_type", "")) == "adjacent_rank"]

    return {
        "accepted_pair_accuracy": _acc(accepted, pred_fn),
        "coverage": len(accepted) / max(1, len(subset)),
        "abstention_rate": 1.0 - (len(accepted) / max(1, len(subset))),
        "forced_pairwise_accuracy": _acc(subset, lambda r: forced_pred_fn(r)),
        "tie_detection_precision": prec,
        "tie_detection_recall": rec,
        "tie_detection_f1": f1,
        "near_tie_accepted_accuracy": _acc([r for r in near if pred_fn(r) is not None], pred_fn),
        "near_tie_forced_accuracy": _acc(near, lambda r: forced_pred_fn(r)),
        "adjacent_accepted_accuracy": _acc([r for r in adjacent if pred_fn(r) is not None], pred_fn),
        "adjacent_forced_accuracy": _acc(adjacent, lambda r: forced_pred_fn(r)),
        "test_pairs": float(len(subset)),
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = [int(s.strip()) for s in str(args.seeds).split(",") if s.strip()]
    regimes = [r.strip() for r in str(args.regimes).split(",") if r.strip()]

    flat: list[dict[str, Any]] = []
    detailed: dict[str, Any] = {"run_id": args.run_id, "seeds": seeds, "regimes": {}}

    for regime in regimes:
        regime_dir = Path(args.targets_root) / f"regime_{regime}"
        if not regime_dir.exists():
            continue
        detailed["regimes"][regime] = {}
        for seed in seeds:
            cfg = LearningConfig(
                seed=seed,
                near_tie_margin=float(args.near_tie_margin),
                feature_set=str(args.feature_set),
                tie_abs_margin_threshold=float(args.tie_abs_margin_threshold),
                tie_relative_margin_threshold=float(args.tie_relative_margin_threshold),
                tie_std_threshold=float(args.tie_std_threshold),
                tie_use_near_tie_flag=bool(args.tie_use_near_tie_flag),
                tie_include_approx=bool(args.tie_include_approx),
                tie_require_exact_or_mixed=bool(args.tie_require_exact_or_mixed),
            )
            artifacts = load_label_artifacts(regime_dir)
            tables = prepare_learning_tables(artifacts, cfg)
            models = train_models(tables, cfg, model_artifact_dir=out_dir / f"{regime}_seed_{seed}" / "models")

            pair_model = models.get("pairwise", {})
            point_model = models.get("pointwise", {})
            pair_score = scorer_from_model(pair_model)
            point_score = scorer_from_model(point_model)

            def binary_pred(row: dict[str, Any]) -> int:
                si = pair_score({"x": row["x_i"]})
                sj = pair_score({"x": row["x_j"]})
                return 1 if si >= sj else 0

            def binary_fallback(row: dict[str, Any]) -> int:
                return binary_pred(row)

            binary_metrics = _metrics_for_predictions(
                tables["pairwise"],
                pred_fn=lambda r: binary_pred(r),
                forced_pred_fn=lambda r: binary_fallback(r),
            )
            binary_top1 = _top1_from_pairwise_rows(tables["pairwise"], tables["state_to_candidates"], lambda r: binary_pred(r), binary_fallback)

            ternary = _train_ternary_pair_model(tables["pairwise"], seed)

            def pointwise_fallback(row: dict[str, Any]) -> int:
                if str(args.fallback_policy) == "heuristic_margin":
                    return 1 if float(row.get("margin", 0.0)) >= 0.0 else 0
                if str(args.fallback_policy) == "unresolved":
                    return 0
                si = point_score({"x": row["x_i"]})
                sj = point_score({"x": row["x_j"]})
                return 1 if si >= sj else 0

            if ternary.get("status") == "ok":
                tm = ternary["model"]

                def ternary_pred(row: dict[str, Any]) -> int | None:
                    pred = int(tm.predict([row["x_diff"]])[0])
                    if pred == 1:
                        return None
                    return 1 if pred == 2 else 0

                ternary_metrics = _metrics_for_predictions(
                    tables["pairwise"],
                    pred_fn=ternary_pred,
                    forced_pred_fn=lambda r: pointwise_fallback(r) if ternary_pred(r) is None else int(ternary_pred(r) or 0),
                )
                ternary_top1 = _top1_from_pairwise_rows(
                    tables["pairwise"],
                    tables["state_to_candidates"],
                    ternary_pred,
                    pointwise_fallback,
                )
            else:
                ternary_metrics = {k: 0.0 for k in [
                    "accepted_pair_accuracy", "coverage", "abstention_rate", "forced_pairwise_accuracy", "tie_detection_precision",
                    "tie_detection_recall", "tie_detection_f1", "near_tie_accepted_accuracy", "near_tie_forced_accuracy",
                    "adjacent_accepted_accuracy", "adjacent_forced_accuracy", "test_pairs",
                ]}
                ternary_top1 = 0.0

            def abstain_pred(row: dict[str, Any]) -> int | None:
                si = pair_score({"x": row["x_i"]})
                sj = pair_score({"x": row["x_j"]})
                prob = _sigmoid(si - sj)
                confidence = abs(prob - 0.5) * 2.0
                if confidence < float(args.abstain_confidence_threshold):
                    return None
                return 1 if prob >= 0.5 else 0

            abstain_metrics = _metrics_for_predictions(
                tables["pairwise"],
                pred_fn=abstain_pred,
                forced_pred_fn=lambda r: pointwise_fallback(r) if abstain_pred(r) is None else int(abstain_pred(r) or 0),
            )
            abstain_top1 = _top1_from_pairwise_rows(
                tables["pairwise"],
                tables["state_to_candidates"],
                abstain_pred,
                pointwise_fallback,
            )

            seed_rows = [
                {"formulation": "binary_forced", "top1_test": binary_top1, **binary_metrics},
                {"formulation": "ternary_tie", "top1_test": ternary_top1, **ternary_metrics},
                {"formulation": "selective_abstain", "top1_test": abstain_top1, **abstain_metrics},
            ]
            detailed["regimes"][regime][str(seed)] = {
                "config": {
                    "feature_set": args.feature_set,
                    "near_tie_margin": args.near_tie_margin,
                    "tie_abs_margin_threshold": args.tie_abs_margin_threshold,
                    "tie_relative_margin_threshold": args.tie_relative_margin_threshold,
                    "tie_std_threshold": args.tie_std_threshold,
                    "tie_use_near_tie_flag": bool(args.tie_use_near_tie_flag),
                    "tie_include_approx": bool(args.tie_include_approx),
                    "tie_require_exact_or_mixed": bool(args.tie_require_exact_or_mixed),
                    "abstain_confidence_threshold": args.abstain_confidence_threshold,
                    "fallback_policy": args.fallback_policy,
                    "ternary_train_status": ternary.get("status", "unknown"),
                },
                "rows": seed_rows,
            }
            for r in seed_rows:
                flat.append({"regime": regime, "seed": seed, **r})

    (out_dir / "ternary_or_abstain_results.json").write_text(json.dumps(detailed, indent=2), encoding="utf-8")
    (out_dir / "ternary_or_abstain_summary.json").write_text(json.dumps(flat, indent=2), encoding="utf-8")

    md = [
        "# Binary vs ternary vs selective-abstention branch comparison",
        "",
        f"- targets_root: `{args.targets_root}`",
        f"- regimes: `{regimes}`",
        f"- seeds: `{seeds}`",
        f"- feature_set: `{args.feature_set}`",
        f"- fallback_policy: `{args.fallback_policy}`",
        f"- abstain_confidence_threshold: `{args.abstain_confidence_threshold}`",
        "",
    ]
    for regime in sorted(set(r["regime"] for r in flat)):
        md.append(f"## Regime `{regime}`")
        for formulation in ["binary_forced", "ternary_tie", "selective_abstain"]:
            rows = [r for r in flat if r["regime"] == regime and r["formulation"] == formulation]
            if not rows:
                continue
            md.append(
                f"- {formulation}: accepted_acc={_mean([x['accepted_pair_accuracy'] for x in rows]):.4f}, "
                f"coverage={_mean([x['coverage'] for x in rows]):.4f}, "
                f"forced_acc={_mean([x['forced_pairwise_accuracy'] for x in rows]):.4f}, "
                f"tie_f1={_mean([x['tie_detection_f1'] for x in rows]):.4f}, "
                f"near_tie_forced={_mean([x['near_tie_forced_accuracy'] for x in rows]):.4f}, "
                f"adjacent_forced={_mean([x['adjacent_forced_accuracy'] for x in rows]):.4f}, "
                f"top1={_mean([x['top1_test'] for x in rows]):.4f}"
            )
        md.append("")
    (out_dir / "ternary_or_abstain_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "rows": len(flat)}, indent=2))


if __name__ == "__main__":
    main()
