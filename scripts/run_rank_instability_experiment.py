#!/usr/bin/env python3
"""Bounded rank-instability supervision experiment for branch allocation."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from statistics import pstdev
from typing import Any, Callable

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge

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


def _fit_linear_pointwise(candidates: list[dict[str, Any]], target_field: str, seed: int) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return {"status": "insufficient_train_rows", "training_rows": len(train)}
    x = np.asarray([r["x"] for r in train], dtype=float)
    y = np.asarray([float(r.get(target_field, r.get("estimated_value_if_allocate_next", 0.0))) for r in train], dtype=float)
    if float(np.std(y)) <= 1e-12:
        return {"status": "degenerate_target", "training_rows": len(train)}
    model = Ridge(alpha=1.0, random_state=int(seed))
    model.fit(x, y)
    return {
        "status": "ok",
        "weights": np.asarray(model.coef_, dtype=float).tolist(),
        "intercept": float(model.intercept_),
        "training_rows": len(train),
    }


def _linear_scorer(model: dict[str, Any]) -> Callable[[list[float]], float]:
    w = np.asarray(model.get("weights", []), dtype=float)
    b = float(model.get("intercept", 0.0))
    return lambda x: float(np.dot(w, np.asarray(x, dtype=float)) + b)


def _state_near_tie_flags(pair_rows: list[dict[str, Any]]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for r in pair_rows:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        out[sid] = bool(out.get(sid, False) or bool(r.get("near_tie_flag", False)))
    return out


def _state_adjacent_flags(pair_rows: list[dict[str, Any]]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for r in pair_rows:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        out[sid] = bool(out.get(sid, False) or str(r.get("pair_type", "")) == "adjacent_rank")
    return out


def _fit_instability_head(pair_rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    train = [r for r in pair_rows if str(r.get("split")) == "train"]
    x_rows: list[list[float]] = []
    y_rows: list[int] = []
    for r in train:
        x_rows.append(
            [
                float(r.get("margin_abs", 0.0)),
                float(r.get("relative_margin", 0.0)),
                float(r.get("pair_uncertainty_std_mean", 0.0)),
                float(r.get("rank_instability_pair_disagreement_count", 0.0)),
                float(r.get("rank_instability_state_score", 0.0)),
                1.0 if bool(r.get("near_tie_flag", False)) else 0.0,
                1.0 if str(r.get("pair_type", "")) == "adjacent_rank" else 0.0,
            ]
        )
        y_rows.append(1 if bool(r.get("rank_instability_pair_label", False)) else 0)
    if len(x_rows) < 16 or len(set(y_rows)) < 2:
        return {"status": "insufficient_or_single_class", "training_rows": len(x_rows)}
    x = np.asarray(x_rows, dtype=float)
    y = np.asarray(y_rows, dtype=int)
    m = LogisticRegression(max_iter=500, random_state=int(seed), class_weight="balanced")
    m.fit(x, y)
    return {
        "status": "ok",
        "weights": np.asarray(m.coef_, dtype=float).reshape(-1).tolist(),
        "intercept": float(np.asarray(m.intercept_, dtype=float).reshape(-1)[0]),
        "training_rows": len(x_rows),
        "positive_rate": float(np.mean(y)),
    }


def _instability_prob(model: dict[str, Any], row: dict[str, Any]) -> float:
    w = np.asarray(model.get("weights", []), dtype=float)
    b = float(model.get("intercept", 0.0))
    x = np.asarray(
        [
            float(row.get("margin_abs", 0.0)),
            float(row.get("relative_margin", 0.0)),
            float(row.get("pair_uncertainty_std_mean", 0.0)),
            float(row.get("rank_instability_pair_disagreement_count", 0.0)),
            float(row.get("rank_instability_state_score", 0.0)),
            1.0 if bool(row.get("near_tie_flag", False)) else 0.0,
            1.0 if str(row.get("pair_type", "")) == "adjacent_rank" else 0.0,
        ],
        dtype=float,
    )
    z = float(np.dot(w, x) + b)
    return float(1.0 / (1.0 + np.exp(-z)))


def _build_state_tables(candidates: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    test_by_state: dict[str, list[dict[str, Any]]] = {}
    oracle_best: dict[str, str] = {}
    for r in candidates:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        test_by_state.setdefault(sid, []).append(r)
    for sid, rows in test_by_state.items():
        if not rows:
            continue
        best = max(rows, key=lambda rr: float(rr.get("estimated_value_if_allocate_next", 0.0)))
        oracle_best[sid] = str(best.get("branch_id", ""))
    return test_by_state, oracle_best


def _top2_pair_lookup(pair_rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in pair_rows:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        bi = str(r.get("branch_i", ""))
        bj = str(r.get("branch_j", ""))
        key = (sid, min(bi, bj), max(bi, bj))
        out[key] = r
    return out


def _choose_branches(
    *,
    mode: str,
    scorer: Callable[[list[float]], float],
    states: dict[str, list[dict[str, Any]]],
    pair_lookup: dict[tuple[str, str, str], dict[str, Any]],
    instability_model: dict[str, Any] | None,
    instability_threshold: float,
    decision_margin_threshold: float,
) -> tuple[list[dict[str, Any]], list[float]]:
    rows: list[dict[str, Any]] = []
    gaps: list[float] = []
    for sid, cands in states.items():
        scored = sorted(
            [
                {
                    "branch_id": str(r.get("branch_id", "")),
                    "score": float(scorer(r["x"])),
                    "outside_gap": float(r.get("branch_vs_outside_gap", 0.0)),
                    "multistep_delta": float(r.get("multistep_branch_utility_delta_vs_onestep", 0.0)),
                    "state_label": bool(r.get("rank_instability_state_label", False)),
                }
                for r in cands
            ],
            key=lambda rr: rr["score"],
            reverse=True,
        )
        if not scored:
            continue
        chosen = scored[0]["branch_id"]
        gap = float(scored[0]["score"] - (scored[1]["score"] if len(scored) > 1 else scored[0]["score"]))
        gaps.append(gap)
        pair_prob = 0.0
        if len(scored) > 1 and instability_model is not None and str(instability_model.get("status")) == "ok":
            key = (sid, min(scored[0]["branch_id"], scored[1]["branch_id"]), max(scored[0]["branch_id"], scored[1]["branch_id"]))
            prow = pair_lookup.get(key)
            if prow is not None:
                pair_prob = _instability_prob(instability_model, prow)
        state_label = bool(scored[0].get("state_label", False))
        defer = bool(
            mode == "rank_instability_aware"
            and (pair_prob >= instability_threshold or state_label)
            and gap <= (1.5 * decision_margin_threshold)
        )
        rows.append(
            {
                "state_id": sid,
                "choice": chosen,
                "score_gap_top2": gap,
                "instability_prob_top2": float(pair_prob),
                "instability_state_label": bool(state_label),
                "defer": defer,
                "top2": scored[:2],
            }
        )
    return rows, gaps


def _evaluate_state_choices(
    rows: list[dict[str, Any]],
    oracle_best: dict[str, str],
    near_tie: dict[str, bool],
    adjacent: dict[str, bool],
) -> dict[str, Any]:
    all_n = len(rows)
    accepted = [r for r in rows if not bool(r.get("defer", False))]
    forced_correct = sum(int(str(r.get("choice", "")) == str(oracle_best.get(str(r.get("state_id", "")), ""))) for r in rows)
    accepted_correct = sum(int(str(r.get("choice", "")) == str(oracle_best.get(str(r.get("state_id", "")), ""))) for r in accepted)

    def _slice_acc(slice_rows: list[dict[str, Any]]) -> float:
        if not slice_rows:
            return 0.0
        corr = sum(int(str(r.get("choice", "")) == str(oracle_best.get(str(r.get("state_id", "")), ""))) for r in slice_rows)
        return float(corr / len(slice_rows))

    near_slice = [r for r in accepted if bool(near_tie.get(str(r.get("state_id", "")), False))]
    adj_slice = [r for r in accepted if bool(adjacent.get(str(r.get("state_id", "")), False))]
    strict_slice = [r for r in accepted if bool(near_tie.get(str(r.get("state_id", "")), False)) and bool(adjacent.get(str(r.get("state_id", "")), False))]

    wrong = [r for r in accepted if str(r.get("choice", "")) != str(oracle_best.get(str(r.get("state_id", "")), ""))]
    overconfident_wrong = [r for r in wrong if float(r.get("score_gap_top2", 0.0)) >= 0.08 and float(r.get("instability_prob_top2", 0.0)) <= 0.35]

    delayed_fail = []
    for r in wrong:
        top2 = r.get("top2", [])
        chosen = top2[0] if top2 else {}
        oracle_branch = str(oracle_best.get(str(r.get("state_id", "")), ""))
        oracle_row = None
        for t in top2:
            if str(t.get("branch_id", "")) == oracle_branch:
                oracle_row = t
                break
        if oracle_row is None:
            continue
        if float(chosen.get("multistep_delta", 0.0)) > float(oracle_row.get("multistep_delta", 0.0)) and float(chosen.get("outside_gap", 0.0)) < 0.0 and float(oracle_row.get("outside_gap", 0.0)) > 0.0:
            delayed_fail.append(r)

    return {
        "forced_accuracy": float(forced_correct / all_n) if all_n else 0.0,
        "accepted_accuracy": float(accepted_correct / len(accepted)) if accepted else 0.0,
        "coverage": float(len(accepted) / all_n) if all_n else 0.0,
        "defer_rate": float(1.0 - (len(accepted) / all_n)) if all_n else 0.0,
        "states": all_n,
        "accepted_states": len(accepted),
        "near_tie_accepted_accuracy": _slice_acc(near_slice),
        "adjacent_rank_accepted_accuracy": _slice_acc(adj_slice),
        "strict_slice_accepted_accuracy": _slice_acc(strict_slice),
        "near_tie_accepted_n": len(near_slice),
        "adjacent_rank_accepted_n": len(adj_slice),
        "strict_slice_accepted_n": len(strict_slice),
        "failure_states": len(wrong),
        "delayed_payoff_overvaluation_failures": len(delayed_fail),
        "overconfident_wrong_states": len(overconfident_wrong),
        "overconfident_wrong_rate_on_failures": float(len(overconfident_wrong) / len(wrong)) if wrong else 0.0,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded rank-instability supervision experiment")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-root", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--feature-set", default="v3", choices=["v1", "v2", "v3"])
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--baseline-regime", default="all_pairs")
    p.add_argument("--multistep-regime", default="multistep_branch_utility_target_k3")
    p.add_argument("--discounted-regime", default="discounted_multistep_branch_utility_target_gamma080")
    p.add_argument("--curve-regime", default="compute_response_curve_target_h123")
    p.add_argument("--rank-instability-regime", default="rank_instability_target_v1")
    p.add_argument("--instability-threshold", type=float, default=0.60)
    p.add_argument("--decision-margin-threshold", type=float, default=0.06)
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
        rank_raw = load_label_artifacts(targets_root / f"regime_{args.rank_instability_regime}")
        rank_cfg = LearningConfig(
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
        rank_tables = prepare_learning_tables(rank_raw, rank_cfg)
        rank_candidates = rank_tables["candidates"]
        rank_pairs = rank_tables["pairwise"]
        states, oracle_best = _build_state_tables(rank_candidates)
        near_tie = _state_near_tie_flags(rank_pairs)
        adjacent = _state_adjacent_flags(rank_pairs)
        pair_lookup = _top2_pair_lookup(rank_pairs)

        support_rows.append(
            {
                "seed": int(seed),
                "test_states": len(states),
                "test_pairs": len([r for r in rank_pairs if str(r.get("split")) == "test"]),
                "near_tie_state_rate": float(sum(1 for v in near_tie.values() if bool(v)) / max(1, len(states))),
                "rank_instability_state_label_rate": float(sum(1 for rs in states.values() if rs and bool(rs[0].get("rank_instability_state_label", False))) / max(1, len(states))),
            }
        )

        modes: list[tuple[str, Callable[[list[float]], float], dict[str, Any], dict[str, Any] | None]] = []

        # all_pairs baseline
        base_raw = load_label_artifacts(targets_root / f"regime_{args.baseline_regime}")
        base_cfg = LearningConfig(
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
        base_models = train_models(prepare_learning_tables(base_raw, base_cfg), base_cfg)
        base_pair = base_models.get("pairwise", {})
        if str(base_pair.get("status")) == "ok":
            base_scorer_raw = scorer_from_model(base_pair)
            base_scorer = lambda x: float(base_scorer_raw({"x": x}))
        else:
            base_scorer = lambda _x: 0.0
        modes.append(("baseline_all_pairs", base_scorer, {"status": str(base_pair.get("status", "unknown")), "regime": str(args.baseline_regime)}, None))

        # current multistep k3
        ms_raw = load_label_artifacts(targets_root / f"regime_{args.multistep_regime}")
        ms_tables = prepare_learning_tables(ms_raw, base_cfg)
        ms_model = _fit_linear_pointwise(ms_tables["candidates"], target_field="multistep_branch_utility_target", seed=int(seed))
        ms_scorer = _linear_scorer(ms_model) if str(ms_model.get("status")) == "ok" else (lambda _x: 0.0)
        modes.append(("multistep_k3_current", ms_scorer, {"status": str(ms_model.get("status", "unknown")), "regime": str(args.multistep_regime)}, None))

        # optional discounted and curve anchors
        d_raw = load_label_artifacts(targets_root / f"regime_{args.discounted_regime}")
        d_tables = prepare_learning_tables(d_raw, base_cfg)
        d_model = _fit_linear_pointwise(d_tables["candidates"], target_field="multistep_branch_utility_target", seed=int(seed))
        d_scorer = _linear_scorer(d_model) if str(d_model.get("status")) == "ok" else (lambda _x: 0.0)
        modes.append(("discounted_gamma080_anchor", d_scorer, {"status": str(d_model.get("status", "unknown")), "regime": str(args.discounted_regime)}, None))

        c_raw = load_label_artifacts(targets_root / f"regime_{args.curve_regime}")
        c_tables = prepare_learning_tables(c_raw, base_cfg)
        c_model = _fit_linear_pointwise(c_tables["candidates"], target_field="compute_response_curve_decision_scalar", seed=int(seed))
        c_scorer = _linear_scorer(c_model) if str(c_model.get("status")) == "ok" else (lambda _x: 0.0)
        modes.append(("compute_response_curve_anchor", c_scorer, {"status": str(c_model.get("status", "unknown")), "regime": str(args.curve_regime)}, None))

        # rank-instability aware
        rank_models = train_models(rank_tables, rank_cfg)
        rank_pair = rank_models.get("pairwise", {})
        if str(rank_pair.get("status")) == "ok":
            rank_scorer_raw = scorer_from_model(rank_pair)
            rank_scorer = lambda x: float(rank_scorer_raw({"x": x}))
        else:
            rank_scorer = lambda _x: 0.0
        inst_model = _fit_instability_head(rank_pairs, seed=int(seed))
        modes.append(("rank_instability_aware", rank_scorer, {"status": str(rank_pair.get("status", "unknown")), "regime": str(args.rank_instability_regime), "instability_head": inst_model}, inst_model))

        for mode_name, scorer, model_meta, inst_meta in modes:
            chosen_rows, score_gaps = _choose_branches(
                mode=mode_name,
                scorer=scorer,
                states=states,
                pair_lookup=pair_lookup,
                instability_model=inst_meta,
                instability_threshold=float(args.instability_threshold),
                decision_margin_threshold=float(args.decision_margin_threshold),
            )
            metrics = _evaluate_state_choices(chosen_rows, oracle_best, near_tie, adjacent)
            per_seed_rows.append(
                {
                    "seed": int(seed),
                    "mode": mode_name,
                    "metrics": metrics,
                    "model": model_meta,
                    "score_gap_mean": float(np.mean(score_gaps)) if score_gaps else 0.0,
                    "score_gap_p75": float(np.percentile(np.asarray(score_gaps, dtype=float), 75)) if score_gaps else 0.0,
                    "instability_policy": {
                        "instability_threshold": float(args.instability_threshold),
                        "decision_margin_threshold": float(args.decision_margin_threshold),
                    },
                }
            )
            failure_rows.append({"seed": int(seed), "mode": mode_name, "rows": chosen_rows})

    modes = sorted(set(str(r["mode"]) for r in per_seed_rows))
    aggregate: dict[str, Any] = {}
    for mode in modes:
        rows = [r for r in per_seed_rows if str(r["mode"]) == mode]
        aggregate[mode] = {
            "seeds": len(rows),
            "accepted_accuracy_mean": _mean([float(r["metrics"].get("accepted_accuracy", 0.0)) for r in rows]),
            "accepted_accuracy_std": float(pstdev([float(r["metrics"].get("accepted_accuracy", 0.0)) for r in rows])) if len(rows) > 1 else 0.0,
            "forced_accuracy_mean": _mean([float(r["metrics"].get("forced_accuracy", 0.0)) for r in rows]),
            "coverage_mean": _mean([float(r["metrics"].get("coverage", 0.0)) for r in rows]),
            "defer_rate_mean": _mean([float(r["metrics"].get("defer_rate", 0.0)) for r in rows]),
            "near_tie_accepted_accuracy_mean": _mean([float(r["metrics"].get("near_tie_accepted_accuracy", 0.0)) for r in rows]),
            "adjacent_rank_accepted_accuracy_mean": _mean([float(r["metrics"].get("adjacent_rank_accepted_accuracy", 0.0)) for r in rows]),
            "strict_slice_accepted_accuracy_mean": _mean([float(r["metrics"].get("strict_slice_accepted_accuracy", 0.0)) for r in rows]),
            "delayed_payoff_overvaluation_failures_mean": _mean([float(r["metrics"].get("delayed_payoff_overvaluation_failures", 0.0)) for r in rows]),
            "overconfident_wrong_states_mean": _mean([float(r["metrics"].get("overconfident_wrong_states", 0.0)) for r in rows]),
            "overconfident_wrong_rate_on_failures_mean": _mean([float(r["metrics"].get("overconfident_wrong_rate_on_failures", 0.0)) for r in rows]),
        }

    base = aggregate.get("baseline_all_pairs", {})
    ms = aggregate.get("multistep_k3_current", {})
    comparison = {}
    for mode in modes:
        if mode == "baseline_all_pairs":
            continue
        vals = aggregate.get(mode, {})
        comparison[mode] = {
            "delta_accepted_accuracy_vs_all_pairs": float(vals.get("accepted_accuracy_mean", 0.0) - base.get("accepted_accuracy_mean", 0.0)),
            "delta_accepted_accuracy_vs_multistep_k3": float(vals.get("accepted_accuracy_mean", 0.0) - ms.get("accepted_accuracy_mean", 0.0)),
            "delta_near_tie_accepted_accuracy_vs_multistep_k3": float(vals.get("near_tie_accepted_accuracy_mean", 0.0) - ms.get("near_tie_accepted_accuracy_mean", 0.0)),
            "delta_strict_slice_accepted_accuracy_vs_multistep_k3": float(vals.get("strict_slice_accepted_accuracy_mean", 0.0) - ms.get("strict_slice_accepted_accuracy_mean", 0.0)),
            "delta_overconfident_wrong_rate_vs_multistep_k3": float(vals.get("overconfident_wrong_rate_on_failures_mean", 0.0) - ms.get("overconfident_wrong_rate_on_failures_mean", 0.0)),
        }

    _write_json(
        out_dir / "config_manifest.json",
        {
            "run_id": str(args.run_id),
            "targets_root": str(targets_root),
            "seeds": seeds,
            "feature_set": str(args.feature_set),
            "near_tie_margin": float(args.near_tie_margin),
            "regimes": {
                "baseline": str(args.baseline_regime),
                "multistep": str(args.multistep_regime),
                "discounted": str(args.discounted_regime),
                "curve": str(args.curve_regime),
                "rank_instability": str(args.rank_instability_regime),
            },
            "instability_policy": {
                "defer_if_instability_prob_ge": float(args.instability_threshold),
                "and_score_gap_le": float(args.decision_margin_threshold),
            },
            "command": " ".join(sys.argv),
        },
    )
    _write_json(out_dir / "per_seed_summary.json", {"rows": per_seed_rows})
    _write_json(out_dir / "aggregate_comparison_summary.json", {"aggregate": aggregate, "comparison": comparison})
    _write_json(out_dir / "failure_diagnostics.json", {"rows": failure_rows})
    _write_json(out_dir / "support_diagnostics.json", {"rows": support_rows})
    (out_dir / "commands_assumptions_caveats.md").write_text(
        "\n".join(
            [
                "# Commands / assumptions / caveats",
                "",
                f"- Command: `{' '.join(sys.argv)}`",
                "- Bounded policy: defer only when predicted top-2 pair instability is high and score gap is small.",
                "- Accepted metrics are computed on non-deferred states only.",
                "- Forced metrics keep a branch decision for every state (deferred states counted via default top-1 score choice).",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"output_dir": str(out_dir), "modes": modes}, indent=2))


if __name__ == "__main__":
    main()
