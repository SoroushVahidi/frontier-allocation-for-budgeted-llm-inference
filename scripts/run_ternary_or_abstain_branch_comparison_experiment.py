#!/usr/bin/env python3
"""Matched binary vs ternary vs selective-abstention branch-comparison experiment."""

from __future__ import annotations

import argparse
import itertools
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
    p.add_argument("--abstention-cost-correct-directional", type=float, default=0.0)
    p.add_argument("--abstention-cost-wrong-directional", type=float, default=1.0)
    p.add_argument("--abstention-cost-directional-to-unresolved", type=float, default=0.35)
    p.add_argument("--abstention-cost-unresolved-to-directional", type=float, default=0.70)
    p.add_argument("--abstention-cost-correct-unresolved", type=float, default=0.10)
    p.add_argument("--abstention-unresolved-class-upweight", type=float, default=1.35)
    p.add_argument("--calibration-enable-sweep", action="store_true")
    p.add_argument("--calibration-coverage-floor", type=float, default=0.40)
    p.add_argument("--calibration-grid-unresolved-upweight", default="1.00,1.20,1.35")
    p.add_argument("--calibration-grid-cost-directional-to-unresolved", default="0.35,0.45")
    p.add_argument("--calibration-grid-cost-unresolved-to-directional", default="0.70,0.55")
    p.add_argument("--calibration-grid-decision-margin", default="0.00,0.03")
    return p.parse_args()


def _mean(xs: list[float]) -> float:
    return sum(xs) / max(1, len(xs))


def _train_ternary_pair_model(rows: list[dict[str, Any]], seed: int, *, label_key: str = "ternary_label", weight_key: str = "pair_train_weight") -> dict[str, Any]:
    train = [r for r in rows if r.get("split") == "train"]
    if len(train) < 3:
        return {"status": "insufficient_train_rows"}
    x = [r["x_diff"] for r in train]
    y = [int(r.get(label_key, 1)) for r in train]
    if len(set(y)) < 2:
        return {"status": "single_class_train", "constant": int(y[0])}
    weights = [float(r.get(weight_key, r.get("pair_train_weight", 1.0))) for r in train]
    model = LogisticRegression(max_iter=600, random_state=seed)
    model.fit(x, y, sample_weight=weights)
    return {"status": "ok", "model": model}


def _train_soft_ternary_pair_model(rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    train = [r for r in rows if r.get("split") == "train"]
    if len(train) < 3:
        return {"status": "insufficient_train_rows"}
    x: list[list[float]] = []
    y: list[int] = []
    w: list[float] = []
    for r in train:
        p_i = float(r.get("soft_target_prob_i_wins", 0.0))
        p_t = float(r.get("soft_target_prob_tie", 0.0))
        p_j = float(r.get("soft_target_prob_j_wins", 0.0))
        total = p_i + p_t + p_j
        if total <= 1e-8:
            t = int(r.get("ternary_label", 1))
            p_j, p_t, p_i = (1.0, 0.0, 0.0) if t == 0 else ((0.0, 1.0, 0.0) if t == 1 else (0.0, 0.0, 1.0))
            total = 1.0
        p_i, p_t, p_j = p_i / total, p_t / total, p_j / total
        base_w = float(r.get("pair_train_weight", 1.0))
        for cls, p in [(0, p_j), (1, p_t), (2, p_i)]:
            if p > 1e-8:
                x.append(r["x_diff"])
                y.append(cls)
                w.append(base_w * p)
    if len(x) < 3 or len(set(y)) < 2:
        return {"status": "single_class_train_or_empty"}
    model = LogisticRegression(max_iter=800, random_state=seed)
    model.fit(x, y, sample_weight=w)
    return {"status": "ok", "model": model}
def _build_abstention_costs(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "labels": ["j_wins", "unresolved", "i_wins"],
        "pred_actions": ["predict_j_wins", "predict_unresolved", "predict_i_wins"],
        "matrix": {
            "j_wins": {
                "predict_j_wins": float(args.abstention_cost_correct_directional),
                "predict_unresolved": float(args.abstention_cost_directional_to_unresolved),
                "predict_i_wins": float(args.abstention_cost_wrong_directional),
            },
            "unresolved": {
                "predict_j_wins": float(args.abstention_cost_unresolved_to_directional),
                "predict_unresolved": float(args.abstention_cost_correct_unresolved),
                "predict_i_wins": float(args.abstention_cost_unresolved_to_directional),
            },
            "i_wins": {
                "predict_j_wins": float(args.abstention_cost_wrong_directional),
                "predict_unresolved": float(args.abstention_cost_directional_to_unresolved),
                "predict_i_wins": float(args.abstention_cost_correct_directional),
            },
        },
        "notes": "Conservative abstention utility: wrong confident directional > unresolved-on-directional > correct unresolved > correct directional.",
    }


def _parse_float_list(csv_text: str) -> list[float]:
    vals = [float(x.strip()) for x in str(csv_text).split(",") if x.strip()]
    return vals if vals else [0.0]


def _build_calibration_candidates(args: argparse.Namespace) -> list[dict[str, float]]:
    upweights = _parse_float_list(args.calibration_grid_unresolved_upweight)
    dir_to_unres = _parse_float_list(args.calibration_grid_cost_directional_to_unresolved)
    unres_to_dir = _parse_float_list(args.calibration_grid_cost_unresolved_to_directional)
    margins = _parse_float_list(args.calibration_grid_decision_margin)
    out: list[dict[str, float]] = []
    for uw, c_du, c_ud, dm in itertools.product(upweights, dir_to_unres, unres_to_dir, margins):
        out.append(
            {
                "abstention_unresolved_class_upweight": float(uw),
                "abstention_cost_directional_to_unresolved": float(c_du),
                "abstention_cost_unresolved_to_directional": float(c_ud),
                "abstention_decision_margin": float(dm),
            }
        )
    return out


def _cost_sensitive_partial_order_predictor(
    model: LogisticRegression,
    costs: dict[str, Any],
    *,
    decision_margin: float = 0.0,
) -> Callable[[dict[str, Any]], int | None]:
    class_order = [int(c) for c in model.classes_]

    def _predict(row: dict[str, Any]) -> int | None:
        probs = model.predict_proba([row["x_diff"]])[0]
        by_cls = {c: float(p) for c, p in zip(class_order, probs)}
        p_j = by_cls.get(0, 0.0)
        p_u = by_cls.get(1, 0.0)
        p_i = by_cls.get(2, 0.0)

        exp_cost_j = (
            p_j * float(costs["matrix"]["j_wins"]["predict_j_wins"])
            + p_u * float(costs["matrix"]["unresolved"]["predict_j_wins"])
            + p_i * float(costs["matrix"]["i_wins"]["predict_j_wins"])
        )
        exp_cost_u = (
            p_j * float(costs["matrix"]["j_wins"]["predict_unresolved"])
            + p_u * float(costs["matrix"]["unresolved"]["predict_unresolved"])
            + p_i * float(costs["matrix"]["i_wins"]["predict_unresolved"])
        )
        exp_cost_i = (
            p_j * float(costs["matrix"]["j_wins"]["predict_i_wins"])
            + p_u * float(costs["matrix"]["unresolved"]["predict_i_wins"])
            + p_i * float(costs["matrix"]["i_wins"]["predict_i_wins"])
        )

        action_costs = [
            ("predict_j_wins", exp_cost_j),
            ("predict_unresolved", exp_cost_u),
            ("predict_i_wins", exp_cost_i),
        ]
        action = min(action_costs, key=lambda x: x[1])[0]
        best_directional = min(exp_cost_j, exp_cost_i)
        if (exp_cost_u <= (best_directional + float(decision_margin))) and action != "predict_unresolved":
            action = "predict_unresolved"
        if action == "predict_unresolved":
            return None
        return 1 if action == "predict_i_wins" else 0

    return _predict




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
    ambiguity_truth_key: str = "ambiguous_target_flag",
    split: str = "test",
) -> dict[str, float]:
    subset = [r for r in rows if r.get("split") == split]
    accepted = [r for r in subset if pred_fn(r) is not None]
    truth_tie = [bool(r.get(ambiguity_truth_key, False)) for r in subset]
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
    deferred = [r for r in subset if pred_fn(r) is None]
    forced_on_deferred = _acc(deferred, lambda r: forced_pred_fn(r))
    accepted_value_gap = (
        sum(float(r.get("pair_value_gap", 0.0)) for r in accepted) / max(1, len(accepted))
    )
    deferred_value_gap = (
        sum(float(r.get("pair_value_gap", 0.0)) for r in deferred) / max(1, len(deferred))
    )

    return {
        "accepted_pair_accuracy": _acc(accepted, pred_fn),
        "coverage": len(accepted) / max(1, len(subset)),
        "abstention_rate": 1.0 - (len(accepted) / max(1, len(subset))),
        "unresolved_rate": 1.0 - (len(accepted) / max(1, len(subset))),
        "forced_pairwise_accuracy": _acc(subset, lambda r: forced_pred_fn(r)),
        "tie_detection_precision": prec,
        "tie_detection_recall": rec,
        "tie_detection_f1": f1,
        "ambiguity_detection_precision": prec,
        "ambiguity_detection_recall": rec,
        "ambiguity_detection_f1": f1,
        "near_tie_accepted_accuracy": _acc([r for r in near if pred_fn(r) is not None], pred_fn),
        "near_tie_forced_accuracy": _acc(near, lambda r: forced_pred_fn(r)),
        "adjacent_accepted_accuracy": _acc([r for r in adjacent if pred_fn(r) is not None], pred_fn),
        "adjacent_forced_accuracy": _acc(adjacent, lambda r: forced_pred_fn(r)),
        "fallback_on_deferred_accuracy": forced_on_deferred,
        "accepted_mean_pair_value_gap": accepted_value_gap,
        "deferred_mean_pair_value_gap": deferred_value_gap,
        "realized_spend_proxy_per_pair": len(accepted) / max(1, len(subset)),
        "test_pairs": float(len(subset)),
    }


def _calibration_objective(metrics: dict[str, float], coverage_floor: float) -> float:
    coverage = float(metrics.get("coverage", 0.0))
    if coverage < float(coverage_floor):
        return float("-inf")
    return float(metrics.get("accepted_pair_accuracy", 0.0))


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = [int(s.strip()) for s in str(args.seeds).split(",") if s.strip()]
    regimes = [r.strip() for r in str(args.regimes).split(",") if r.strip()]

    flat: list[dict[str, Any]] = []
    detailed: dict[str, Any] = {"run_id": args.run_id, "seeds": seeds, "regimes": {}}
    calibration_records: list[dict[str, Any]] = []

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

            ternary = _train_ternary_pair_model(tables["pairwise"], seed, label_key="ternary_label")

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

            soft_ternary = _train_soft_ternary_pair_model(tables["pairwise"], seed)
            if soft_ternary.get("status") == "ok":
                sm = soft_ternary["model"]

                def soft_ternary_pred(row: dict[str, Any]) -> int | None:
                    cls = [int(c) for c in sm.classes_]
                    probs = sm.predict_proba([row["x_diff"]])[0]
                    by_cls = {c: float(p) for c, p in zip(cls, probs)}
                    p_tie = by_cls.get(1, 0.0)
                    p_i = by_cls.get(2, 0.0)
                    p_j = by_cls.get(0, 0.0)
                    if p_tie >= max(p_i, p_j):
                        return None
                    return 1 if p_i >= p_j else 0

                soft_ternary_metrics = _metrics_for_predictions(
                    tables["pairwise"],
                    pred_fn=soft_ternary_pred,
                    forced_pred_fn=lambda r: pointwise_fallback(r) if soft_ternary_pred(r) is None else int(soft_ternary_pred(r) or 0),
                )
                soft_ternary_top1 = _top1_from_pairwise_rows(
                    tables["pairwise"],
                    tables["state_to_candidates"],
                    soft_ternary_pred,
                    pointwise_fallback,
                )
            else:
                soft_ternary_metrics = {k: 0.0 for k in [
                    "accepted_pair_accuracy", "coverage", "abstention_rate", "forced_pairwise_accuracy", "tie_detection_precision",
                    "tie_detection_recall", "tie_detection_f1", "near_tie_accepted_accuracy", "near_tie_forced_accuracy",
                    "adjacent_accepted_accuracy", "adjacent_forced_accuracy", "test_pairs",
                ]}
                soft_ternary_top1 = 0.0

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

            partial_rows = [dict(r) for r in tables["pairwise"]]
            for _r in partial_rows:
                base_w = float(_r.get("pair_train_weight", 1.0))
                if int(_r.get("partial_order_label", 1)) == 1:
                    _r["partial_order_train_weight"] = base_w * float(args.abstention_unresolved_class_upweight)
                else:
                    _r["partial_order_train_weight"] = base_w

            partial_order = _train_ternary_pair_model(partial_rows, seed, label_key="partial_order_label", weight_key="partial_order_train_weight")
            if partial_order.get("status") == "ok":
                pm = partial_order["model"]

                def partial_order_pred(row: dict[str, Any]) -> int | None:
                    pred = int(pm.predict([row["x_diff"]])[0])
                    if pred == 1:
                        return None
                    return 1 if pred == 2 else 0

                partial_order_metrics = _metrics_for_predictions(
                    tables["pairwise"],
                    pred_fn=partial_order_pred,
                    forced_pred_fn=lambda r: pointwise_fallback(r) if partial_order_pred(r) is None else int(partial_order_pred(r) or 0),
                    ambiguity_truth_key="partial_order_incomparable_target",
                )
                partial_order_top1 = _top1_from_pairwise_rows(
                    tables["pairwise"],
                    tables["state_to_candidates"],
                    partial_order_pred,
                    pointwise_fallback,
                )

                abstention_costs = _build_abstention_costs(args)
                cost_sensitive_prev_pred = _cost_sensitive_partial_order_predictor(pm, abstention_costs, decision_margin=0.0)
                partial_order_cost_metrics = _metrics_for_predictions(
                    tables["pairwise"],
                    pred_fn=cost_sensitive_prev_pred,
                    forced_pred_fn=lambda r: pointwise_fallback(r) if cost_sensitive_prev_pred(r) is None else int(cost_sensitive_prev_pred(r) or 0),
                    ambiguity_truth_key="partial_order_incomparable_target",
                )
                partial_order_cost_top1 = _top1_from_pairwise_rows(
                    tables["pairwise"],
                    tables["state_to_candidates"],
                    cost_sensitive_prev_pred,
                    pointwise_fallback,
                )

                selected_calibration: dict[str, Any] = {
                    "selected": {
                        "abstention_unresolved_class_upweight": float(args.abstention_unresolved_class_upweight),
                        "abstention_cost_directional_to_unresolved": float(args.abstention_cost_directional_to_unresolved),
                        "abstention_cost_unresolved_to_directional": float(args.abstention_cost_unresolved_to_directional),
                        "abstention_decision_margin": 0.0,
                    },
                    "selection_rule": {
                        "type": "max_accepted_accuracy_subject_to_coverage_floor",
                        "coverage_floor": float(args.calibration_coverage_floor),
                    },
                    "candidates_evaluated": [],
                }
                calibrated_metrics = dict(partial_order_cost_metrics)
                calibrated_top1 = float(partial_order_cost_top1)
                if bool(args.calibration_enable_sweep):
                    candidate_rows: list[dict[str, Any]] = []
                    best_obj = float("-inf")
                    best_pick: dict[str, Any] | None = None
                    candidates = _build_calibration_candidates(args)
                    for cand in candidates:
                        train_rows = [dict(r) for r in tables["pairwise"]]
                        for tr in train_rows:
                            base_w = float(tr.get("pair_train_weight", 1.0))
                            if int(tr.get("partial_order_label", 1)) == 1:
                                tr["partial_order_train_weight"] = base_w * float(cand["abstention_unresolved_class_upweight"])
                            else:
                                tr["partial_order_train_weight"] = base_w
                        cand_model = _train_ternary_pair_model(
                            train_rows,
                            seed,
                            label_key="partial_order_label",
                            weight_key="partial_order_train_weight",
                        )
                        if cand_model.get("status") != "ok":
                            candidate_rows.append({"candidate": cand, "status": str(cand_model.get("status", "unknown"))})
                            continue
                        cand_costs = _build_abstention_costs(args)
                        cand_costs["matrix"]["j_wins"]["predict_unresolved"] = float(cand["abstention_cost_directional_to_unresolved"])
                        cand_costs["matrix"]["i_wins"]["predict_unresolved"] = float(cand["abstention_cost_directional_to_unresolved"])
                        cand_costs["matrix"]["unresolved"]["predict_j_wins"] = float(cand["abstention_cost_unresolved_to_directional"])
                        cand_costs["matrix"]["unresolved"]["predict_i_wins"] = float(cand["abstention_cost_unresolved_to_directional"])
                        cand_pred = _cost_sensitive_partial_order_predictor(
                            cand_model["model"],
                            cand_costs,
                            decision_margin=float(cand["abstention_decision_margin"]),
                        )
                        val_metrics = _metrics_for_predictions(
                            tables["pairwise"],
                            pred_fn=cand_pred,
                            forced_pred_fn=lambda r: pointwise_fallback(r) if cand_pred(r) is None else int(cand_pred(r) or 0),
                            ambiguity_truth_key="partial_order_incomparable_target",
                            split="val",
                        )
                        obj = _calibration_objective(val_metrics, float(args.calibration_coverage_floor))
                        row = {"candidate": cand, "status": "ok", "val_metrics": val_metrics, "objective": obj}
                        candidate_rows.append(row)
                        if obj > best_obj:
                            best_obj = obj
                            best_pick = row
                    if best_pick is None:
                        feasible = [c for c in candidate_rows if c.get("status") == "ok"]
                        if feasible:
                            best_pick = max(
                                feasible,
                                key=lambda c: (
                                    float(c.get("val_metrics", {}).get("coverage", 0.0)),
                                    float(c.get("val_metrics", {}).get("accepted_pair_accuracy", 0.0)),
                                ),
                            )
                    if best_pick is not None and best_pick.get("status") == "ok":
                        pick = best_pick["candidate"]
                        selected_calibration["selected"] = dict(pick)
                        selected_calibration["selected"]["objective"] = float(best_pick.get("objective", float("-inf")))
                        selected_calibration["selected"]["selection_split"] = "val"
                        final_rows = [dict(r) for r in tables["pairwise"]]
                        for fr in final_rows:
                            base_w = float(fr.get("pair_train_weight", 1.0))
                            if int(fr.get("partial_order_label", 1)) == 1:
                                fr["partial_order_train_weight"] = base_w * float(pick["abstention_unresolved_class_upweight"])
                            else:
                                fr["partial_order_train_weight"] = base_w
                        final_model = _train_ternary_pair_model(
                            final_rows,
                            seed,
                            label_key="partial_order_label",
                            weight_key="partial_order_train_weight",
                        )
                        if final_model.get("status") == "ok":
                            final_costs = _build_abstention_costs(args)
                            final_costs["matrix"]["j_wins"]["predict_unresolved"] = float(pick["abstention_cost_directional_to_unresolved"])
                            final_costs["matrix"]["i_wins"]["predict_unresolved"] = float(pick["abstention_cost_directional_to_unresolved"])
                            final_costs["matrix"]["unresolved"]["predict_j_wins"] = float(pick["abstention_cost_unresolved_to_directional"])
                            final_costs["matrix"]["unresolved"]["predict_i_wins"] = float(pick["abstention_cost_unresolved_to_directional"])
                            calibrated_pred = _cost_sensitive_partial_order_predictor(
                                final_model["model"],
                                final_costs,
                                decision_margin=float(pick["abstention_decision_margin"]),
                            )
                            calibrated_metrics = _metrics_for_predictions(
                                tables["pairwise"],
                                pred_fn=calibrated_pred,
                                forced_pred_fn=lambda r: pointwise_fallback(r) if calibrated_pred(r) is None else int(calibrated_pred(r) or 0),
                                ambiguity_truth_key="partial_order_incomparable_target",
                            )
                            calibrated_top1 = _top1_from_pairwise_rows(
                                tables["pairwise"],
                                tables["state_to_candidates"],
                                calibrated_pred,
                                pointwise_fallback,
                            )
                    selected_calibration["candidates_evaluated"] = candidate_rows
                calibration_records.append(
                    {
                        "regime": regime,
                        "seed": seed,
                        **selected_calibration,
                    }
                )
            else:
                partial_order_metrics = {k: 0.0 for k in [
                    "accepted_pair_accuracy", "coverage", "abstention_rate", "unresolved_rate", "forced_pairwise_accuracy",
                    "tie_detection_precision", "tie_detection_recall", "tie_detection_f1", "ambiguity_detection_precision",
                    "ambiguity_detection_recall", "ambiguity_detection_f1", "near_tie_accepted_accuracy", "near_tie_forced_accuracy",
                    "adjacent_accepted_accuracy", "adjacent_forced_accuracy", "test_pairs",
                ]}
                partial_order_top1 = 0.0
                partial_order_cost_metrics = dict(partial_order_metrics)
                partial_order_cost_top1 = 0.0
                calibrated_metrics = dict(partial_order_metrics)
                calibrated_top1 = 0.0
                calibration_records.append(
                    {
                        "regime": regime,
                        "seed": seed,
                        "selected": None,
                        "selection_rule": {
                            "type": "max_accepted_accuracy_subject_to_coverage_floor",
                            "coverage_floor": float(args.calibration_coverage_floor),
                        },
                        "candidates_evaluated": [],
                        "status": "partial_order_train_not_ok",
                    }
                )

            penalized_defer = _train_ternary_pair_model(tables["pairwise"], seed, label_key="ternary_defer_label")
            if penalized_defer.get("status") == "ok":
                pdm = penalized_defer["model"]

                def penalized_defer_pred(row: dict[str, Any]) -> int | None:
                    pred = int(pdm.predict([row["x_diff"]])[0])
                    if pred == 1:
                        return None
                    return 1 if pred == 2 else 0

                penalized_defer_metrics = _metrics_for_predictions(
                    tables["pairwise"],
                    pred_fn=penalized_defer_pred,
                    forced_pred_fn=lambda r: pointwise_fallback(r) if penalized_defer_pred(r) is None else int(penalized_defer_pred(r) or 0),
                    ambiguity_truth_key="penalized_marginal_defer_target",
                )
                penalized_defer_top1 = _top1_from_pairwise_rows(
                    tables["pairwise"],
                    tables["state_to_candidates"],
                    penalized_defer_pred,
                    pointwise_fallback,
                )
            else:
                penalized_defer_metrics = {k: 0.0 for k in [
                    "accepted_pair_accuracy", "coverage", "abstention_rate", "unresolved_rate", "forced_pairwise_accuracy",
                    "tie_detection_precision", "tie_detection_recall", "tie_detection_f1", "ambiguity_detection_precision",
                    "ambiguity_detection_recall", "ambiguity_detection_f1", "near_tie_accepted_accuracy", "near_tie_forced_accuracy",
                    "adjacent_accepted_accuracy", "adjacent_forced_accuracy", "fallback_on_deferred_accuracy",
                    "accepted_mean_pair_value_gap", "deferred_mean_pair_value_gap", "realized_spend_proxy_per_pair", "test_pairs",
                ]}
                penalized_defer_top1 = 0.0

            seed_rows = [
                {"formulation": "binary_forced", "top1_test": binary_top1, **binary_metrics},
                {"formulation": "ternary_tie", "top1_test": ternary_top1, **ternary_metrics},
                {"formulation": "soft_ternary_tie", "top1_test": soft_ternary_top1, **soft_ternary_metrics},
                {"formulation": "selective_abstain", "top1_test": abstain_top1, **abstain_metrics},
                {"formulation": "partial_order_incomparable", "top1_test": partial_order_top1, **partial_order_metrics},
                {"formulation": "partial_order_cost_sensitive_abstain_previous", "top1_test": partial_order_cost_top1, **partial_order_cost_metrics},
                {"formulation": "partial_order_cost_sensitive_abstain_calibrated", "top1_test": calibrated_top1, **calibrated_metrics},
                {"formulation": "penalized_marginal_defer", "top1_test": penalized_defer_top1, **penalized_defer_metrics},
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
                    "soft_ternary_train_status": soft_ternary.get("status", "unknown"),
                    "partial_order_train_status": partial_order.get("status", "unknown"),
                    "penalized_marginal_defer_train_status": penalized_defer.get("status", "unknown"),
                    "abstention_unresolved_class_upweight": args.abstention_unresolved_class_upweight,
                    "abstention_costs": _build_abstention_costs(args),
                    "calibration_enable_sweep": bool(args.calibration_enable_sweep),
                    "calibration_coverage_floor": float(args.calibration_coverage_floor),
                },
                "rows": seed_rows,
            }
            for r in seed_rows:
                flat.append({"regime": regime, "seed": seed, **r})

    (out_dir / "ternary_or_abstain_results.json").write_text(json.dumps(detailed, indent=2), encoding="utf-8")
    (out_dir / "ternary_or_abstain_summary.json").write_text(json.dumps(flat, indent=2), encoding="utf-8")
    (out_dir / "abstention_cost_calibration_selection.json").write_text(
        json.dumps(
            {
                "run_id": args.run_id,
                "selection_rule": {
                    "type": "max_accepted_accuracy_subject_to_coverage_floor",
                    "coverage_floor": float(args.calibration_coverage_floor),
                },
                "calibration_enable_sweep": bool(args.calibration_enable_sweep),
                "records": calibration_records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    md = [
        "# Binary vs ternary vs selective-abstention branch comparison",
        "",
        f"- targets_root: `{args.targets_root}`",
        f"- regimes: `{regimes}`",
        f"- seeds: `{seeds}`",
        f"- feature_set: `{args.feature_set}`",
        f"- fallback_policy: `{args.fallback_policy}`",
        f"- abstain_confidence_threshold: `{args.abstain_confidence_threshold}`",
        f"- abstention_unresolved_class_upweight: `{args.abstention_unresolved_class_upweight}`",
        f"- calibration_enable_sweep: `{bool(args.calibration_enable_sweep)}`",
        f"- calibration_coverage_floor: `{float(args.calibration_coverage_floor):.3f}`",
        "",
    ]
    for regime in sorted(set(r["regime"] for r in flat)):
        md.append(f"## Regime `{regime}`")
        for formulation in [
            "binary_forced",
            "ternary_tie",
            "soft_ternary_tie",
            "selective_abstain",
            "partial_order_incomparable",
            "partial_order_cost_sensitive_abstain_previous",
            "partial_order_cost_sensitive_abstain_calibrated",
            "penalized_marginal_defer",
        ]:
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
    (out_dir / "abstention_cost_config.json").write_text(json.dumps(_build_abstention_costs(args), indent=2), encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "rows": len(flat)}, indent=2))


if __name__ == "__main__":
    main()
