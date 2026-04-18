#!/usr/bin/env python3
"""Bounded validation pass for compute-response curve supervision on branch allocation."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from statistics import pstdev
from typing import Any

import numpy as np
from sklearn.linear_model import Ridge

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (  # noqa: E402
    LearningConfig,
    load_label_artifacts,
    prepare_learning_tables,
    scorer_from_model,
    train_models,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_int_csv(text: str) -> list[int]:
    vals = [int(x.strip()) for x in str(text).split(",") if x.strip()]
    if not vals:
        raise ValueError("Expected at least one seed")
    return vals


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _pair_pred_from_score(score_fn, row: dict[str, Any]) -> int:
    si = float(score_fn({"x": row["x_i"]}))
    sj = float(score_fn({"x": row["x_j"]}))
    return 1 if si >= sj else 0


def _slice_acc(rows: list[dict[str, Any]], pred_fn, *, mask) -> tuple[float, int]:
    subset = [r for r in rows if mask(r)]
    if not subset:
        return 0.0, 0
    return float(sum(int(pred_fn(r) == int(r.get("label", 0))) for r in subset) / len(subset)), len(subset)


def _pair_metrics(pair_rows: list[dict[str, Any]], pred_fn) -> dict[str, Any]:
    test = [r for r in pair_rows if str(r.get("split")) == "test"]
    if not test:
        return {"accepted_accuracy": 0.0, "near_tie_accepted_accuracy": 0.0, "adjacent_rank_accepted_accuracy": 0.0, "strict_slice_accepted_accuracy": 0.0, "test_n": 0}
    near_acc, near_n = _slice_acc(test, pred_fn, mask=lambda r: bool(r.get("near_tie_flag", False)))
    adj_acc, adj_n = _slice_acc(test, pred_fn, mask=lambda r: str(r.get("pair_type", "")) == "adjacent_rank")
    strict_acc, strict_n = _slice_acc(test, pred_fn, mask=lambda r: bool(r.get("near_tie_flag", False)) and str(r.get("pair_type", "")) == "adjacent_rank")
    acc, n = _slice_acc(test, pred_fn, mask=lambda _r: True)
    return {
        "accepted_accuracy": acc,
        "near_tie_accepted_accuracy": near_acc,
        "adjacent_rank_accepted_accuracy": adj_acc,
        "strict_slice_accepted_accuracy": strict_acc,
        "near_tie_n": near_n,
        "adjacent_rank_n": adj_n,
        "strict_slice_n": strict_n,
        "test_n": n,
        "coverage": 1.0,
        "defer_rate": 0.0,
    }


def _fit_curve_model(candidates: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return {"status": "insufficient_train_rows", "training_rows": len(train)}
    x = np.array([r["x"] for r in train], dtype=float)
    y = np.array([[float(r.get("compute_response_curve_h1", 0.0)), float(r.get("compute_response_curve_h2", 0.0)), float(r.get("compute_response_curve_h3", 0.0))] for r in train], dtype=float)
    if float(np.std(y)) <= 1e-12:
        return {"status": "degenerate_target", "training_rows": len(train)}
    model = Ridge(alpha=1.0, random_state=seed)
    model.fit(x, y)
    return {
        "status": "ok",
        "training_rows": len(train),
        "weights": np.asarray(model.coef_, dtype=float).tolist(),
        "intercept": np.asarray(model.intercept_, dtype=float).tolist(),
    }


def _predict_curve(model: dict[str, Any], x: list[float]) -> tuple[float, float, float]:
    w = np.array(model.get("weights", []), dtype=float)
    b = np.array(model.get("intercept", [0.0, 0.0, 0.0]), dtype=float)
    xv = np.array(x, dtype=float)
    yh = np.dot(w, xv) + b
    if yh.ndim == 0:
        return float(yh), float(yh), float(yh)
    vals = np.asarray(yh, dtype=float).reshape(-1)
    if vals.shape[0] < 3:
        v = float(vals[0]) if vals.size else 0.0
        return v, v, v
    return float(vals[0]), float(vals[1]), float(vals[2])


def _curve_decision_score(h1: float, h2: float, h3: float, *, w1: float, w2: float, w3: float) -> float:
    m1 = float(h1)
    m2 = float(h2 - h1)
    m3 = float(h3 - h2)
    return float(w1 * m1 + w2 * m2 + w3 * m3)


def _state_best_branch_map_from_target(candidates: list[dict[str, Any]], target_field: str) -> dict[str, str]:
    by_state: dict[str, list[dict[str, Any]]] = {}
    for r in candidates:
        if str(r.get("split")) == "test":
            by_state.setdefault(str(r.get("state_id", "")), []).append(r)
    out: dict[str, str] = {}
    for sid, rows in by_state.items():
        if len(rows) < 2:
            continue
        out[sid] = str(max(rows, key=lambda rr: float(rr.get(target_field, 0.0))).get("branch_id", ""))
    return out


def _mode_best_from_model(candidates: list[dict[str, Any]], model: dict[str, Any], *, w1: float, w2: float, w3: float) -> dict[str, str]:
    by_state: dict[str, list[dict[str, Any]]] = {}
    for r in candidates:
        if str(r.get("split")) == "test":
            by_state.setdefault(str(r.get("state_id", "")), []).append(r)
    out: dict[str, str] = {}
    for sid, rows in by_state.items():
        if len(rows) < 2:
            continue
        best_bid = ""
        best_score = -1e18
        for rr in rows:
            h1, h2, h3 = _predict_curve(model, rr["x"])
            sc = _curve_decision_score(h1, h2, h3, w1=w1, w2=w2, w3=w3)
            if sc > best_score:
                best_score = sc
                best_bid = str(rr.get("branch_id", ""))
        out[sid] = best_bid
    return out


def _state_near_tie_flags(pair_rows: list[dict[str, Any]]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for r in pair_rows:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        out[sid] = bool(out.get(sid, False) or bool(r.get("near_tie_flag", False)))
    return out


def _delayed_payoff_confusion(candidates: list[dict[str, Any]], mode_best: dict[str, str], oracle_best: dict[str, str], near_tie: dict[str, bool]) -> dict[str, Any]:
    lookup = {(str(r.get("state_id", "")), str(r.get("branch_id", ""))): r for r in candidates if str(r.get("split")) == "test"}
    rows = []
    for sid in sorted(set(mode_best) & set(oracle_best)):
        mb = mode_best[sid]
        ob = oracle_best[sid]
        chosen = lookup.get((sid, mb), {})
        oracle = lookup.get((sid, ob), {})
        fail = mb != ob
        delayed_overvalue = bool(
            fail
            and float(chosen.get("compute_response_curve_marginal_m1", 0.0)) < float(oracle.get("compute_response_curve_marginal_m1", 0.0))
            and (float(chosen.get("compute_response_curve_marginal_m2", 0.0)) > float(oracle.get("compute_response_curve_marginal_m2", 0.0)) or float(chosen.get("compute_response_curve_marginal_m3", 0.0)) > float(oracle.get("compute_response_curve_marginal_m3", 0.0)))
        )
        rows.append({
            "state_id": sid,
            "method_choice": mb,
            "oracle_choice": ob,
            "is_near_tie_state": bool(near_tie.get(sid, False)),
            "failure": bool(fail),
            "delayed_payoff_confusion": bool(delayed_overvalue),
        })
    failures = [r for r in rows if bool(r["failure"])]
    delayed = [r for r in failures if bool(r["delayed_payoff_confusion"])]
    return {
        "states": len(rows),
        "failure_states": len(failures),
        "delayed_payoff_confusion_failures": len(delayed),
        "delayed_payoff_confusion_rate_on_failures": float(len(delayed) / len(failures)) if failures else 0.0,
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded compute-response curve branch-allocation experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-root", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--feature-set", default="v3", choices=["v1", "v2", "v3"])
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--baseline-regime", default="all_pairs")
    p.add_argument("--current-multistep-regime", default="multistep_branch_utility_target_k3")
    p.add_argument("--curve-regime", default="compute_response_curve_target_h123")
    p.add_argument("--curve-score-w1", type=float, default=1.0)
    p.add_argument("--curve-score-w2", type=float, default=0.60)
    p.add_argument("--curve-score-w3", type=float, default=0.30)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_root) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    targets_root = Path(args.targets_root)
    seeds = _parse_int_csv(args.seeds)

    per_seed_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []

    for seed in seeds:
        baseline_raw = load_label_artifacts(targets_root / f"regime_{args.baseline_regime}")
        baseline_cfg = LearningConfig(
            seed=int(seed),
            near_tie_margin=float(args.near_tie_margin),
            feature_set=str(args.feature_set),
            train_pairwise=True,
            train_pointwise=True,
            train_outside_option=False,
            train_lightgbm_ranker=False,
            train_catboost_ranker=False,
            train_pairwise_svm=False,
        )
        baseline_tables = prepare_learning_tables(baseline_raw, baseline_cfg)
        eval_pairs = baseline_tables["pairwise"]
        near_tie = _state_near_tie_flags(eval_pairs)
        support_rows.append({"seed": int(seed), "test_pairs": len([r for r in eval_pairs if str(r.get("split")) == "test"])})

        # baseline pairwise model
        baseline_models = train_models(baseline_tables, baseline_cfg)
        baseline_pairwise = baseline_models.get("pairwise", {})
        if str(baseline_pairwise.get("status")) == "ok":
            b_score = scorer_from_model(baseline_pairwise)
            b_pred = lambda r: _pair_pred_from_score(b_score, r)
        else:
            b_const = int(baseline_pairwise.get("constant_label", 0))
            b_pred = lambda _r: b_const
        per_seed_rows.append({
            "seed": int(seed),
            "mode": "baseline_current_matched",
            "regime": str(args.baseline_regime),
            "metrics": _pair_metrics(eval_pairs, b_pred),
            "model_status": str(baseline_pairwise.get("status", "unknown")),
            "config": asdict(baseline_cfg),
        })

        # current multistep pointwise scalar target
        current_raw = load_label_artifacts(targets_root / f"regime_{args.current_multistep_regime}")
        current_cfg = LearningConfig(
            seed=int(seed),
            near_tie_margin=float(args.near_tie_margin),
            feature_set=str(args.feature_set),
            train_pairwise=False,
            train_pointwise=True,
            train_outside_option=False,
            train_lightgbm_ranker=False,
            train_catboost_ranker=False,
            train_pairwise_svm=False,
            pointwise_target_field="multistep_branch_utility_target",
        )
        current_tables = prepare_learning_tables(current_raw, current_cfg)
        current_model = Ridge(alpha=1.0, random_state=int(seed))
        cur_train = [r for r in current_tables["candidates"] if str(r.get("split")) == "train"]
        x_cur = np.array([r["x"] for r in cur_train], dtype=float)
        y_cur = np.array([float(r.get("multistep_branch_utility_target", 0.0)) for r in cur_train], dtype=float)
        current_model.fit(x_cur, y_cur)
        c_pred = lambda r: 1 if float(current_model.predict(np.array([r["x_i"]], dtype=float))[0]) >= float(current_model.predict(np.array([r["x_j"]], dtype=float))[0]) else 0
        per_seed_rows.append({
            "seed": int(seed),
            "mode": "multistep_k3_current",
            "regime": str(args.current_multistep_regime),
            "metrics": _pair_metrics(eval_pairs, c_pred),
            "model_status": "ok",
            "config": asdict(current_cfg),
        })

        # response-curve model
        curve_raw = load_label_artifacts(targets_root / f"regime_{args.curve_regime}")
        curve_cfg = LearningConfig(
            seed=int(seed),
            near_tie_margin=float(args.near_tie_margin),
            feature_set=str(args.feature_set),
            train_pairwise=False,
            train_pointwise=False,
            train_outside_option=False,
            train_lightgbm_ranker=False,
            train_catboost_ranker=False,
            train_pairwise_svm=False,
        )
        curve_tables = prepare_learning_tables(curve_raw, curve_cfg)
        curve_model = _fit_curve_model(curve_tables["candidates"], seed=int(seed))
        if str(curve_model.get("status")) == "ok":
            r_pred = lambda r: 1 if _curve_decision_score(*_predict_curve(curve_model, r["x_i"]), w1=float(args.curve_score_w1), w2=float(args.curve_score_w2), w3=float(args.curve_score_w3)) >= _curve_decision_score(*_predict_curve(curve_model, r["x_j"]), w1=float(args.curve_score_w1), w2=float(args.curve_score_w2), w3=float(args.curve_score_w3)) else 0
        else:
            r_pred = lambda r: 1 if float(r.get("pair_curve_scalar_i", 0.0)) >= float(r.get("pair_curve_scalar_j", 0.0)) else 0
        per_seed_rows.append({
            "seed": int(seed),
            "mode": "compute_response_curve_h123",
            "regime": str(args.curve_regime),
            "metrics": _pair_metrics(eval_pairs, r_pred),
            "model_status": str(curve_model.get("status", "unknown")),
            "config": {
                **asdict(curve_cfg),
                "curve_score_weights": [float(args.curve_score_w1), float(args.curve_score_w2), float(args.curve_score_w3)],
            },
        })

        oracle_best = _state_best_branch_map_from_target(curve_tables["candidates"], "estimated_value_if_allocate_next")
        current_best = _state_best_branch_map_from_target(current_tables["candidates"], "multistep_branch_utility_target")
        curve_best = _mode_best_from_model(curve_tables["candidates"], curve_model, w1=float(args.curve_score_w1), w2=float(args.curve_score_w2), w3=float(args.curve_score_w3)) if str(curve_model.get("status")) == "ok" else _state_best_branch_map_from_target(curve_tables["candidates"], "compute_response_curve_decision_scalar")
        failure_rows.append({"seed": int(seed), "mode": "multistep_k3_current", **_delayed_payoff_confusion(current_tables["candidates"], current_best, oracle_best, near_tie)})
        failure_rows.append({"seed": int(seed), "mode": "compute_response_curve_h123", **_delayed_payoff_confusion(curve_tables["candidates"], curve_best, oracle_best, near_tie)})

    modes = list(dict.fromkeys([str(r["mode"]) for r in per_seed_rows]))
    aggregate: dict[str, Any] = {}
    for mode in modes:
        rows = [r for r in per_seed_rows if str(r["mode"]) == mode]
        aggregate[mode] = {
            "seeds": len(rows),
            "accepted_accuracy_mean": _mean([float(r["metrics"].get("accepted_accuracy", 0.0)) for r in rows]),
            "accepted_accuracy_std": float(pstdev([float(r["metrics"].get("accepted_accuracy", 0.0)) for r in rows])) if len(rows) > 1 else 0.0,
            "near_tie_accepted_accuracy_mean": _mean([float(r["metrics"].get("near_tie_accepted_accuracy", 0.0)) for r in rows]),
            "adjacent_rank_accepted_accuracy_mean": _mean([float(r["metrics"].get("adjacent_rank_accepted_accuracy", 0.0)) for r in rows]),
            "strict_slice_accepted_accuracy_mean": _mean([float(r["metrics"].get("strict_slice_accepted_accuracy", 0.0)) for r in rows]),
        }

    baseline = aggregate.get("baseline_current_matched", {})
    current = aggregate.get("multistep_k3_current", {})
    curve = aggregate.get("compute_response_curve_h123", {})
    comparison = {
        "compute_response_curve_h123": {
            "delta_accepted_accuracy_vs_baseline": float(curve.get("accepted_accuracy_mean", 0.0) - baseline.get("accepted_accuracy_mean", 0.0)),
            "delta_accepted_accuracy_vs_current_multistep": float(curve.get("accepted_accuracy_mean", 0.0) - current.get("accepted_accuracy_mean", 0.0)),
            "delta_near_tie_accepted_accuracy_vs_baseline": float(curve.get("near_tie_accepted_accuracy_mean", 0.0) - baseline.get("near_tie_accepted_accuracy_mean", 0.0)),
            "delta_strict_slice_accepted_accuracy_vs_current_multistep": float(curve.get("strict_slice_accepted_accuracy_mean", 0.0) - current.get("strict_slice_accepted_accuracy_mean", 0.0)),
        }
    }

    failure_aggregate = {}
    for mode in ["multistep_k3_current", "compute_response_curve_h123"]:
        rows = [r for r in failure_rows if str(r["mode"]) == mode]
        failure_aggregate[mode] = {
            "seeds": len(rows),
            "failure_states_mean": _mean([float(r.get("failure_states", 0)) for r in rows]),
            "delayed_payoff_confusion_failures_mean": _mean([float(r.get("delayed_payoff_confusion_failures", 0)) for r in rows]),
            "delayed_payoff_confusion_rate_on_failures_mean": _mean([float(r.get("delayed_payoff_confusion_rate_on_failures", 0.0)) for r in rows]),
        }

    _write_json(
        out_dir / "config_manifest.json",
        {
            "run_id": str(args.run_id),
            "targets_root": str(targets_root),
            "seeds": seeds,
            "feature_set": str(args.feature_set),
            "near_tie_margin": float(args.near_tie_margin),
            "baseline_regime": str(args.baseline_regime),
            "current_multistep_regime": str(args.current_multistep_regime),
            "curve_regime": str(args.curve_regime),
            "curve_score_weights": [float(args.curve_score_w1), float(args.curve_score_w2), float(args.curve_score_w3)],
            "command": " ".join(sys.argv),
        },
    )
    _write_json(out_dir / "per_seed_summary.json", {"rows": per_seed_rows})
    _write_json(out_dir / "aggregate_comparison_summary.json", {"aggregate": aggregate, "comparison": comparison, "failure_aggregate": failure_aggregate})
    _write_json(out_dir / "per_seed_failure_taxonomy.json", {"rows": failure_rows})
    _write_json(out_dir / "support_diagnostics.json", {"rows": support_rows})

    print(json.dumps({"output_dir": str(out_dir), "modes": modes}, indent=2))


if __name__ == "__main__":
    main()
