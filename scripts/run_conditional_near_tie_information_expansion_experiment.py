#!/usr/bin/env python3
"""Bounded conditional near-tie information-expansion experiment.

Canonical path is preserved:
- coarse decision remains branch-value + uncertainty compare/defer,
- extra information is only queried on near-tie/inconclusive deferred comparisons.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import LearningConfig, load_label_artifacts, prepare_learning_tables  # noqa: E402


MODES = [
    "baseline",
    "conditional_expand_then_decide",
    "conditional_expand_then_decide_oracleish",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Conditional near-tie information expansion (bounded)")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--regimes", default="all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer")
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--feature-set", default="v3", choices=["v1", "v2", "v3"])
    p.add_argument("--coverage-floor", type=float, default=0.55)
    p.add_argument("--threshold-grid-gap", default="0.00,0.01,0.02,0.03,0.05,0.08")
    p.add_argument("--threshold-grid-z", default="0.25,0.50,0.75,1.00,1.25,1.50")
    p.add_argument("--outside-gap-threshold", type=float, default=0.03)
    p.add_argument("--trigger-gap-multiplier", type=float, default=1.0)
    p.add_argument("--trigger-z-multiplier", type=float, default=1.0)
    p.add_argument("--trigger-use-near-tie-flag", action="store_true")
    p.add_argument("--tiebreak-confidence-threshold", type=float, default=0.58)
    p.add_argument("--tiebreak-confidence-threshold-oracleish", type=float, default=0.53)
    p.add_argument("--expansion-cost-units", type=float, default=1.0)
    p.add_argument("--expansion-cost-units-oracleish", type=float, default=1.5)
    return p.parse_args()


def _parse_csv_floats(text: str) -> list[float]:
    vals = [float(x.strip()) for x in str(text).split(",") if x.strip()]
    return vals if vals else [0.0]


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _fit_value(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return {"status": "insufficient", "training_rows": len(train)}
    x = np.array([r["x"] for r in train], dtype=float)
    y = np.array([float(r.get("estimated_value_if_allocate_next", 0.0)) for r in train], dtype=float)
    m = Ridge(alpha=1.0, random_state=0)
    m.fit(x, y)
    return {"status": "ok", "model": m, "training_rows": len(train)}


def _pred_value(model_obj: dict[str, Any], row: dict[str, Any]) -> float:
    if str(model_obj.get("status")) != "ok":
        return float(row.get("estimated_value_if_allocate_next", 0.0))
    m: Ridge = model_obj["model"]
    return float(m.predict(np.array([row["x"]], dtype=float))[0])


def _fit_risk(candidates: list[dict[str, Any]], value_model: dict[str, Any]) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return {"status": "insufficient", "training_rows": len(train)}
    x = np.array([r["x"] for r in train], dtype=float)
    yp = np.array([_pred_value(value_model, r) for r in train], dtype=float)
    yt = np.array([float(r.get("estimated_value_if_allocate_next", 0.0)) for r in train], dtype=float)
    raw = np.array([float(r.get("allocation_value_std", 0.0)) for r in train], dtype=float)
    y = np.maximum(np.abs(yt - yp), 0.2 * raw)
    m = Ridge(alpha=1.0, random_state=0)
    m.fit(x, y)
    return {"status": "ok", "model": m, "training_rows": len(train)}


def _pred_sigma(risk_model: dict[str, Any], row: dict[str, Any]) -> float:
    raw = float(row.get("allocation_value_std", 0.0))
    if str(risk_model.get("status")) != "ok":
        return max(1e-6, raw)
    m: Ridge = risk_model["model"]
    learned = max(0.0, float(m.predict(np.array([row["x"]], dtype=float))[0]))
    return max(1e-6, 0.5 * raw + 0.5 * learned)


def _base_predict(row: dict[str, Any], *, gap_threshold: float, z_threshold: float, outside_gap_threshold: float) -> dict[str, Any]:
    diff = float(row.get("pred_value_i", 0.0)) - float(row.get("pred_value_j", 0.0))
    abs_gap = abs(diff)
    raw_si = float(row.get("raw_sigma_i", 0.0))
    raw_sj = float(row.get("raw_sigma_j", 0.0))
    lr_si = float(row.get("learned_sigma_i", 0.0))
    lr_sj = float(row.get("learned_sigma_j", 0.0))
    pair_sigma = float(np.sqrt((0.5 * raw_si + 0.5 * lr_si) ** 2 + (0.5 * raw_sj + 0.5 * lr_sj) ** 2))
    z_gap = abs_gap / max(1e-6, pair_sigma)
    outside_gap = float(row.get("pair_best_vs_outside_gap", 0.0))
    defer = (abs_gap < gap_threshold) or (z_gap < z_threshold)
    if outside_gap <= outside_gap_threshold and z_gap <= z_threshold:
        defer = True
    return {
        "action": None if defer else (1 if diff >= 0.0 else 0),
        "defer": bool(defer),
        "diff": float(diff),
        "abs_gap": float(abs_gap),
        "z_gap": float(z_gap),
        "outside_gap": float(outside_gap),
    }


def _fit_tiebreaker(rows: list[dict[str, Any]], *, include_val: bool) -> dict[str, Any]:
    allowed = {"train", "val"} if include_val else {"train"}
    train = [r for r in rows if str(r.get("split")) in allowed]
    if len(train) < 12:
        return {"status": "insufficient", "training_rows": len(train)}
    x = np.array([r.get("x_pair_v3", r.get("x_diff", [])) for r in train], dtype=float)
    y = np.array([int(r.get("label", 0)) for r in train], dtype=int)
    if len(set(int(v) for v in y.tolist())) < 2:
        return {"status": "constant", "training_rows": len(train), "constant_label": int(y[0])}
    m = LogisticRegression(max_iter=350, random_state=0)
    m.fit(x, y)
    return {"status": "ok", "model": m, "training_rows": len(train), "include_val": include_val}


def _predict_tiebreaker(model_obj: dict[str, Any], row: dict[str, Any]) -> tuple[int, float]:
    if str(model_obj.get("status")) == "constant":
        lbl = int(model_obj.get("constant_label", 0))
        return lbl, 1.0
    if str(model_obj.get("status")) != "ok":
        diff = float(row.get("pred_value_i", 0.0)) - float(row.get("pred_value_j", 0.0))
        lbl = 1 if diff >= 0.0 else 0
        return lbl, 0.5
    m: LogisticRegression = model_obj["model"]
    x = np.array([row.get("x_pair_v3", row.get("x_diff", []))], dtype=float)
    p1 = float(m.predict_proba(x)[0][1])
    lbl = 1 if p1 >= 0.5 else 0
    conf = max(p1, 1.0 - p1)
    return lbl, conf


def _is_triggered(row: dict[str, Any], base: dict[str, Any], *, gap_threshold: float, z_threshold: float, use_near_tie_flag: bool) -> bool:
    if not bool(base.get("defer", False)):
        return False
    trigger = (float(base["abs_gap"]) <= gap_threshold) or (float(base["z_gap"]) <= z_threshold)
    if use_near_tie_flag:
        trigger = trigger or bool(row.get("near_tie_flag", False))
    return bool(trigger)


def _evaluate_mode(
    rows: list[dict[str, Any]],
    *,
    mode: str,
    gap_threshold: float,
    z_threshold: float,
    outside_gap_threshold: float,
    trigger_gap_threshold: float,
    trigger_z_threshold: float,
    trigger_use_near_tie_flag: bool,
    tiebreak_model: dict[str, Any],
    tiebreak_conf_threshold: float,
    expansion_cost_units: float,
    split: str,
) -> dict[str, Any]:
    subset = [r for r in rows if str(r.get("split")) == split]
    accepted: list[tuple[dict[str, Any], int]] = []
    deferred: list[dict[str, Any]] = []
    triggered: list[dict[str, Any]] = []
    triggered_accepted: list[tuple[dict[str, Any], int]] = []
    triggered_deferred: list[dict[str, Any]] = []

    for r in subset:
        base = _base_predict(r, gap_threshold=gap_threshold, z_threshold=z_threshold, outside_gap_threshold=outside_gap_threshold)
        action = base["action"]
        trig = False

        if mode != "baseline":
            trig = _is_triggered(
                r,
                base,
                gap_threshold=trigger_gap_threshold,
                z_threshold=trigger_z_threshold,
                use_near_tie_flag=trigger_use_near_tie_flag,
            )
            if trig:
                tie_pred, tie_conf = _predict_tiebreaker(tiebreak_model, r)
                if tie_conf >= tiebreak_conf_threshold:
                    action = tie_pred
                r["_tiebreak_pred"] = int(tie_pred)
                r["_tiebreak_conf"] = float(tie_conf)

        if action is None:
            deferred.append(r)
            if trig:
                triggered_deferred.append(r)
        else:
            accepted.append((r, int(action)))
            if trig:
                triggered_accepted.append((r, int(action)))

        if trig:
            triggered.append(r)

    def _acc(items: list[tuple[dict[str, Any], int]]) -> float:
        if not items:
            return 0.0
        return sum(int(pred == int(rr.get("label", 0))) for rr, pred in items) / len(items)

    near_accepted = [(r, a) for r, a in accepted if bool(r.get("near_tie_flag", False))]
    triggered_near = [r for r in triggered if bool(r.get("near_tie_flag", False))]
    triggered_non = [r for r in subset if r not in triggered]

    forced_triggered_acc = 0.0
    if triggered:
        forced_triggered_acc = (
            sum(int((1 if float(r.get("pred_value_i", 0.0)) >= float(r.get("pred_value_j", 0.0)) else 0) == int(r.get("label", 0))) for r in triggered)
            / len(triggered)
        )
    forced_non_triggered_acc = 0.0
    if triggered_non:
        forced_non_triggered_acc = (
            sum(int((1 if float(r.get("pred_value_i", 0.0)) >= float(r.get("pred_value_j", 0.0)) else 0) == int(r.get("label", 0))) for r in triggered_non)
            / len(triggered_non)
        )

    return {
        "accepted_pair_accuracy": _acc(accepted),
        "coverage": len(accepted) / max(1, len(subset)),
        "defer_rate": len(deferred) / max(1, len(subset)),
        "near_tie_accepted_pair_accuracy": _acc(near_accepted),
        "test_pairs": float(len(subset)),
        "trigger_rate": len(triggered) / max(1, len(subset)),
        "triggered_count": float(len(triggered)),
        "triggered_accepted_count": float(len(triggered_accepted)),
        "triggered_deferred_count": float(len(triggered_deferred)),
        "triggered_acceptance_rate": len(triggered_accepted) / max(1, len(triggered)),
        "accepted_accuracy_on_triggered_cases": _acc(triggered_accepted),
        "triggered_near_tie_share": len(triggered_near) / max(1, len(triggered)),
        "triggered_mean_oracle_defer_score": _mean([float(r.get("pair_oracle_defer_score", 0.0)) for r in triggered]),
        "non_triggered_mean_oracle_defer_score": _mean([float(r.get("pair_oracle_defer_score", 0.0)) for r in triggered_non]),
        "triggered_forced_accuracy_proxy": forced_triggered_acc,
        "non_triggered_forced_accuracy_proxy": forced_non_triggered_acc,
        "extra_compute_units_total": float(len(triggered) * expansion_cost_units),
        "extra_compute_units_per_pair": float((len(triggered) * expansion_cost_units) / max(1, len(subset))),
    }


def main() -> None:
    args = parse_args()
    run_dir = Path(args.output_dir) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    seeds = [int(x.strip()) for x in str(args.seeds).split(",") if x.strip()]
    regimes = [x.strip() for x in str(args.regimes).split(",") if x.strip()]
    gap_grid = _parse_csv_floats(args.threshold_grid_gap)
    z_grid = _parse_csv_floats(args.threshold_grid_z)

    config = {
        "run_id": args.run_id,
        "targets_root": args.targets_root,
        "regimes": regimes,
        "seeds": seeds,
        "feature_set": args.feature_set,
        "coverage_floor": args.coverage_floor,
        "threshold_grid_gap": gap_grid,
        "threshold_grid_z": z_grid,
        "outside_gap_threshold": args.outside_gap_threshold,
        "trigger_gap_multiplier": args.trigger_gap_multiplier,
        "trigger_z_multiplier": args.trigger_z_multiplier,
        "trigger_use_near_tie_flag": bool(args.trigger_use_near_tie_flag),
        "modes": MODES,
        "notes": [
            "Baseline remains full_method branch-value + uncertainty compare/defer.",
            "Extra information is a tiny pair-level tiebreaker called only on deferred near-tie triggers.",
            "Oracle-ish mode is bounded headroom only: same trigger, slightly stronger tiebreak setting.",
        ],
    }

    per_seed_mode_rows: list[dict[str, Any]] = []

    for regime in regimes:
        regime_dir = Path(args.targets_root) / f"regime_{regime}"
        if not regime_dir.exists():
            raise FileNotFoundError(f"Missing regime directory: {regime_dir}")

        for seed in seeds:
            cfg = LearningConfig(
                seed=seed,
                feature_set=args.feature_set,
                train_pairwise=True,
                train_pointwise=False,
                train_outside_option=False,
                train_lightgbm_ranker=False,
                train_catboost_ranker=False,
                train_pairwise_svm=False,
            )
            artifacts = load_label_artifacts(regime_dir)
            tables = prepare_learning_tables(artifacts, cfg)
            pair_rows = tables["pairwise"]
            candidates = tables["candidates"]

            value_model = _fit_value(candidates)
            risk_model = _fit_risk(candidates, value_model)
            tiebreak_train = _fit_tiebreaker(pair_rows, include_val=False)
            tiebreak_oracleish = _fit_tiebreaker(pair_rows, include_val=True)

            c_lookup = {(str(c["state_id"]), str(c["branch_id"])): c for c in candidates}
            for r in pair_rows:
                ci = c_lookup[(str(r["state_id"]), str(r["branch_i"]))]
                cj = c_lookup[(str(r["state_id"]), str(r["branch_j"]))]
                r["pred_value_i"] = _pred_value(value_model, ci)
                r["pred_value_j"] = _pred_value(value_model, cj)
                r["raw_sigma_i"] = float(ci.get("allocation_value_std", 0.0))
                r["raw_sigma_j"] = float(cj.get("allocation_value_std", 0.0))
                r["learned_sigma_i"] = _pred_sigma(risk_model, ci)
                r["learned_sigma_j"] = _pred_sigma(risk_model, cj)

            best_sel: dict[str, Any] | None = None
            for g in gap_grid:
                for z in z_grid:
                    val_base = _evaluate_mode(
                        pair_rows,
                        mode="baseline",
                        gap_threshold=float(g),
                        z_threshold=float(z),
                        outside_gap_threshold=float(args.outside_gap_threshold),
                        trigger_gap_threshold=float(g),
                        trigger_z_threshold=float(z),
                        trigger_use_near_tie_flag=bool(args.trigger_use_near_tie_flag),
                        tiebreak_model=tiebreak_train,
                        tiebreak_conf_threshold=float(args.tiebreak_confidence_threshold),
                        expansion_cost_units=float(args.expansion_cost_units),
                        split="val",
                    )
                    if val_base["coverage"] < float(args.coverage_floor):
                        continue
                    cand = {
                        "gap_threshold": float(g),
                        "z_threshold": float(z),
                        "score": float(val_base["accepted_pair_accuracy"]),
                        "metrics": val_base,
                    }
                    if best_sel is None or cand["score"] > float(best_sel["score"]):
                        best_sel = cand

            selected_gap = float(best_sel["gap_threshold"]) if best_sel else 0.0
            selected_z = float(best_sel["z_threshold"]) if best_sel else 0.0
            trigger_gap = float(selected_gap * float(args.trigger_gap_multiplier))
            trigger_z = float(selected_z * float(args.trigger_z_multiplier))

            mode_to_result = {
                "baseline": _evaluate_mode(
                    pair_rows,
                    mode="baseline",
                    gap_threshold=selected_gap,
                    z_threshold=selected_z,
                    outside_gap_threshold=float(args.outside_gap_threshold),
                    trigger_gap_threshold=trigger_gap,
                    trigger_z_threshold=trigger_z,
                    trigger_use_near_tie_flag=bool(args.trigger_use_near_tie_flag),
                    tiebreak_model=tiebreak_train,
                    tiebreak_conf_threshold=float(args.tiebreak_confidence_threshold),
                    expansion_cost_units=0.0,
                    split="test",
                ),
                "conditional_expand_then_decide": _evaluate_mode(
                    pair_rows,
                    mode="conditional_expand_then_decide",
                    gap_threshold=selected_gap,
                    z_threshold=selected_z,
                    outside_gap_threshold=float(args.outside_gap_threshold),
                    trigger_gap_threshold=trigger_gap,
                    trigger_z_threshold=trigger_z,
                    trigger_use_near_tie_flag=bool(args.trigger_use_near_tie_flag),
                    tiebreak_model=tiebreak_train,
                    tiebreak_conf_threshold=float(args.tiebreak_confidence_threshold),
                    expansion_cost_units=float(args.expansion_cost_units),
                    split="test",
                ),
                "conditional_expand_then_decide_oracleish": _evaluate_mode(
                    pair_rows,
                    mode="conditional_expand_then_decide_oracleish",
                    gap_threshold=selected_gap,
                    z_threshold=selected_z,
                    outside_gap_threshold=float(args.outside_gap_threshold),
                    trigger_gap_threshold=trigger_gap,
                    trigger_z_threshold=trigger_z,
                    trigger_use_near_tie_flag=bool(args.trigger_use_near_tie_flag),
                    tiebreak_model=tiebreak_oracleish,
                    tiebreak_conf_threshold=float(args.tiebreak_confidence_threshold_oracleish),
                    expansion_cost_units=float(args.expansion_cost_units_oracleish),
                    split="test",
                ),
            }

            for mode, metrics in mode_to_result.items():
                per_seed_mode_rows.append(
                    {
                        "regime": regime,
                        "seed": seed,
                        "mode": mode,
                        "selected_gap_threshold": selected_gap,
                        "selected_z_threshold": selected_z,
                        "trigger_gap_threshold": trigger_gap,
                        "trigger_z_threshold": trigger_z,
                        "metrics": metrics,
                        "tiebreaker": {
                            "base_status": tiebreak_train.get("status", "unknown"),
                            "oracleish_status": tiebreak_oracleish.get("status", "unknown"),
                            "base_train_rows": tiebreak_train.get("training_rows", 0),
                            "oracleish_train_rows": tiebreak_oracleish.get("training_rows", 0),
                        },
                    }
                )

    by_mode: dict[str, dict[str, Any]] = {}
    for mode in MODES:
        rows = [r for r in per_seed_mode_rows if str(r.get("mode")) == mode]
        by_mode[mode] = {
            "n_runs": len(rows),
            "accepted_pair_accuracy": _mean([float(r["metrics"].get("accepted_pair_accuracy", 0.0)) for r in rows]),
            "coverage": _mean([float(r["metrics"].get("coverage", 0.0)) for r in rows]),
            "defer_rate": _mean([float(r["metrics"].get("defer_rate", 0.0)) for r in rows]),
            "near_tie_accepted_pair_accuracy": _mean([float(r["metrics"].get("near_tie_accepted_pair_accuracy", 0.0)) for r in rows]),
            "trigger_rate": _mean([float(r["metrics"].get("trigger_rate", 0.0)) for r in rows]),
            "accepted_accuracy_on_triggered_cases": _mean([float(r["metrics"].get("accepted_accuracy_on_triggered_cases", 0.0)) for r in rows]),
            "triggered_mean_oracle_defer_score": _mean([float(r["metrics"].get("triggered_mean_oracle_defer_score", 0.0)) for r in rows]),
            "non_triggered_mean_oracle_defer_score": _mean([float(r["metrics"].get("non_triggered_mean_oracle_defer_score", 0.0)) for r in rows]),
            "extra_compute_units_total": _mean([float(r["metrics"].get("extra_compute_units_total", 0.0)) for r in rows]),
            "extra_compute_units_per_pair": _mean([float(r["metrics"].get("extra_compute_units_per_pair", 0.0)) for r in rows]),
        }

    baseline = by_mode.get("baseline", {})

    def _delta(mode: str, key: str) -> float:
        return float(by_mode.get(mode, {}).get(key, 0.0)) - float(baseline.get(key, 0.0))

    aggregate_comparison = {
        "baseline": by_mode.get("baseline", {}),
        "conditional_expand_then_decide": {
            "metrics": by_mode.get("conditional_expand_then_decide", {}),
            "delta_vs_baseline": {
                "accepted_pair_accuracy": _delta("conditional_expand_then_decide", "accepted_pair_accuracy"),
                "coverage": _delta("conditional_expand_then_decide", "coverage"),
                "defer_rate": _delta("conditional_expand_then_decide", "defer_rate"),
                "near_tie_accepted_pair_accuracy": _delta("conditional_expand_then_decide", "near_tie_accepted_pair_accuracy"),
            },
        },
        "conditional_expand_then_decide_oracleish": {
            "metrics": by_mode.get("conditional_expand_then_decide_oracleish", {}),
            "delta_vs_baseline": {
                "accepted_pair_accuracy": _delta("conditional_expand_then_decide_oracleish", "accepted_pair_accuracy"),
                "coverage": _delta("conditional_expand_then_decide_oracleish", "coverage"),
                "defer_rate": _delta("conditional_expand_then_decide_oracleish", "defer_rate"),
                "near_tie_accepted_pair_accuracy": _delta("conditional_expand_then_decide_oracleish", "near_tie_accepted_pair_accuracy"),
            },
        },
    }

    trigger_diag = {
        "problematic_case_check": {
            "conditional_triggered_oracle_defer_minus_non_triggered": float(by_mode.get("conditional_expand_then_decide", {}).get("triggered_mean_oracle_defer_score", 0.0))
            - float(by_mode.get("conditional_expand_then_decide", {}).get("non_triggered_mean_oracle_defer_score", 0.0)),
            "oracleish_triggered_oracle_defer_minus_non_triggered": float(by_mode.get("conditional_expand_then_decide_oracleish", {}).get("triggered_mean_oracle_defer_score", 0.0))
            - float(by_mode.get("conditional_expand_then_decide_oracleish", {}).get("non_triggered_mean_oracle_defer_score", 0.0)),
            "interpretation": "Positive values imply trigger selection skews toward higher apparent ambiguity/hardness.",
        }
    }

    (run_dir / "conditional_near_tie_info_expansion_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (run_dir / "conditional_near_tie_info_expansion_per_seed_mode.json").write_text(json.dumps({"rows": per_seed_mode_rows}, indent=2) + "\n", encoding="utf-8")
    (run_dir / "conditional_near_tie_info_expansion_matched_summary_by_mode.json").write_text(json.dumps(by_mode, indent=2) + "\n", encoding="utf-8")
    (run_dir / "conditional_near_tie_info_expansion_aggregate_comparison_summary.json").write_text(json.dumps(aggregate_comparison, indent=2) + "\n", encoding="utf-8")
    (run_dir / "conditional_near_tie_info_expansion_trigger_diagnostics.json").write_text(json.dumps(trigger_diag, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "run_id": args.run_id,
        "run_dir": str(run_dir),
        "artifacts": {
            "config": "conditional_near_tie_info_expansion_config.json",
            "per_seed_mode": "conditional_near_tie_info_expansion_per_seed_mode.json",
            "matched_summary_by_mode": "conditional_near_tie_info_expansion_matched_summary_by_mode.json",
            "aggregate_comparison": "conditional_near_tie_info_expansion_aggregate_comparison_summary.json",
            "trigger_diagnostics": "conditional_near_tie_info_expansion_trigger_diagnostics.json",
            "manifest": "conditional_near_tie_info_expansion_manifest.json",
        },
        "modes": MODES,
        "assumptions": [
            "Coarse path remains branch-value + uncertainty defer gating.",
            "Extra information is a small pair-level tiebreak model on existing x_pair_v3 features.",
            "Triggering is bounded to near-tie/deferred comparisons only.",
        ],
        "caveats": [
            "Oracle-ish mode is bounded headroom context, not production policy.",
            "This is a go/no-go pass; no broader architecture changes are included.",
        ],
    }
    (run_dir / "conditional_near_tie_info_expansion_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"run_id": args.run_id, "run_dir": str(run_dir), "aggregate": aggregate_comparison}, indent=2))


if __name__ == "__main__":
    main()
