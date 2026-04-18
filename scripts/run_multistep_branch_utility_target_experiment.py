#!/usr/bin/env python3
"""Bounded validation pass for multistep and discounted multistep branch-utility targets."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from statistics import pstdev
from typing import Any, Callable
import sys

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


def _pair_pred_from_score(score_fn: Callable[[dict[str, Any]], float], row: dict[str, Any]) -> int:
    si = float(score_fn({"x": row["x_i"]}))
    sj = float(score_fn({"x": row["x_j"]}))
    return 1 if si >= sj else 0


def _slice_acc(rows: list[dict[str, Any]], pred_fn: Callable[[dict[str, Any]], int], *, mask: Callable[[dict[str, Any]], bool]) -> tuple[float, int]:
    subset = [r for r in rows if mask(r)]
    if not subset:
        return 0.0, 0
    return float(sum(int(pred_fn(r) == int(r.get("label", 0))) for r in subset) / len(subset)), len(subset)


def _pair_metrics(pair_rows: list[dict[str, Any]], pred_fn: Callable[[dict[str, Any]], int]) -> dict[str, Any]:
    test = [r for r in pair_rows if str(r.get("split")) == "test"]
    if not test:
        return {
            "accepted_accuracy": 0.0,
            "coverage": 0.0,
            "defer_rate": 0.0,
            "accepted_n": 0,
            "test_n": 0,
            "near_tie_accepted_accuracy": 0.0,
            "near_tie_n": 0,
            "adjacent_rank_accepted_accuracy": 0.0,
            "adjacent_rank_n": 0,
            "strict_slice_accepted_accuracy": 0.0,
            "strict_slice_n": 0,
        }

    near_acc, near_n = _slice_acc(test, pred_fn, mask=lambda r: bool(r.get("near_tie_flag", False)))
    adj_acc, adj_n = _slice_acc(test, pred_fn, mask=lambda r: str(r.get("pair_type", "")) == "adjacent_rank")
    strict_acc, strict_n = _slice_acc(
        test,
        pred_fn,
        mask=lambda r: bool(r.get("near_tie_flag", False)) and str(r.get("pair_type", "")) == "adjacent_rank",
    )
    overall_acc, overall_n = _slice_acc(test, pred_fn, mask=lambda _r: True)
    return {
        "accepted_accuracy": overall_acc,
        "coverage": 1.0,
        "defer_rate": 0.0,
        "accepted_n": overall_n,
        "test_n": len(test),
        "near_tie_accepted_accuracy": near_acc,
        "near_tie_n": near_n,
        "adjacent_rank_accepted_accuracy": adj_acc,
        "adjacent_rank_n": adj_n,
        "strict_slice_accepted_accuracy": strict_acc,
        "strict_slice_n": strict_n,
    }


def _fit_pointwise_target(candidates: list[dict[str, Any]], target_field: str, seed: int) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return {"status": "insufficient_train_rows", "training_rows": len(train)}
    x = np.array([r["x"] for r in train], dtype=float)
    y = np.array([float(r.get(target_field, r.get("estimated_value_if_allocate_next", 0.0))) for r in train], dtype=float)
    if np.std(y) <= 1e-12:
        return {"status": "degenerate_target", "training_rows": len(train), "target_field": target_field}
    m = Ridge(alpha=1.0, random_state=seed)
    m.fit(x, y)
    return {
        "status": "ok",
        "target_field": target_field,
        "weights": [float(v) for v in m.coef_],
        "intercept": float(m.intercept_),
        "training_rows": len(train),
    }


def _scorer_from_linear(model: dict[str, Any]) -> Callable[[dict[str, Any]], float]:
    w = np.array(model.get("weights", []), dtype=float)
    b = float(model.get("intercept", 0.0))
    return lambda row: float(np.dot(w, np.array(row["x"], dtype=float)) + b)


def _target_distribution_diagnostics(candidates: list[dict[str, Any]], eval_pairs: list[dict[str, Any]], target_field: str) -> dict[str, Any]:
    vals = [float(r.get(target_field, r.get("estimated_value_if_allocate_next", 0.0))) for r in candidates]
    one_step_vals = [float(r.get("estimated_value_if_allocate_next", 0.0)) for r in candidates]

    sid_flags: dict[str, dict[str, bool]] = {}
    for p in eval_pairs:
        if str(p.get("split")) != "test":
            continue
        sid = str(p.get("state_id", ""))
        sid_flags.setdefault(sid, {"near": False})
        sid_flags[sid]["near"] = bool(sid_flags[sid]["near"] or bool(p.get("near_tie_flag", False)))

    near_vals: list[float] = []
    non_near_vals: list[float] = []
    near_ones: list[float] = []
    non_near_ones: list[float] = []
    for r in candidates:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        tv = float(r.get(target_field, r.get("estimated_value_if_allocate_next", 0.0)))
        ov = float(r.get("estimated_value_if_allocate_next", 0.0))
        if bool(sid_flags.get(sid, {}).get("near", False)):
            near_vals.append(tv)
            near_ones.append(ov)
        else:
            non_near_vals.append(tv)
            non_near_ones.append(ov)

    def _stats(xs: list[float]) -> dict[str, float]:
        if not xs:
            return {"mean": 0.0, "std": 0.0, "p10": 0.0, "p50": 0.0, "p90": 0.0, "n": 0.0}
        arr = np.array(xs, dtype=float)
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "p10": float(np.percentile(arr, 10)),
            "p50": float(np.percentile(arr, 50)),
            "p90": float(np.percentile(arr, 90)),
            "n": float(len(xs)),
        }

    return {
        "target_field": target_field,
        "target_stats_all": _stats(vals),
        "one_step_stats_all": _stats(one_step_vals),
        "target_stats_near_tie_state": _stats(near_vals),
        "target_stats_non_near_tie_state": _stats(non_near_vals),
        "one_step_stats_near_tie_state": _stats(near_ones),
        "one_step_stats_non_near_tie_state": _stats(non_near_ones),
    }


def _state_best_branch_map(candidates: list[dict[str, Any]], target_field: str) -> dict[str, str]:
    by_state: dict[str, list[dict[str, Any]]] = {}
    for r in candidates:
        if str(r.get("split")) == "test":
            by_state.setdefault(str(r.get("state_id", "")), []).append(r)
    out: dict[str, str] = {}
    for sid, rows in by_state.items():
        if len(rows) < 2:
            continue
        best = max(rows, key=lambda rr: float(rr.get(target_field, rr.get("estimated_value_if_allocate_next", 0.0))))
        out[sid] = str(best.get("branch_id", ""))
    return out


def _parse_gamma_from_regime(regime: str) -> float | None:
    prefix = "discounted_multistep_branch_utility_target_gamma"
    if str(regime).startswith(prefix):
        return float(int(str(regime)[len(prefix) :])) / 100.0
    return None


def _build_state_branch_table(candidates: list[dict[str, Any]], target_field: str) -> dict[str, dict[str, dict[str, float | str]]]:
    out: dict[str, dict[str, dict[str, float | str]]] = {}
    for r in candidates:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        bid = str(r.get("branch_id", ""))
        out.setdefault(sid, {})[bid] = {
            "target": float(r.get(target_field, r.get("estimated_value_if_allocate_next", 0.0))),
            "one_step": float(r.get("estimated_value_if_allocate_next", 0.0)),
            "outside_gap": float(r.get("branch_vs_outside_gap", 0.0)),
            "multistep_delta": float(r.get("multistep_branch_utility_delta_vs_onestep", 0.0)),
        }
    return out


def _disagreement_vs_reference(reference_best: dict[str, str], candidate_best: dict[str, str], taxonomy_rows: list[dict[str, Any]]) -> dict[str, Any]:
    tax_by_state = {str(r["state_id"]): r for r in taxonomy_rows}
    shared_states = sorted(set(reference_best) & set(candidate_best))
    changed = [sid for sid in shared_states if reference_best[sid] != candidate_best[sid]]
    dominant = [sid for sid in changed if str(tax_by_state.get(sid, {}).get("mistake_type", "")) == "delayed_payoff_overvaluation_with_outside_option_miss"]
    return {
        "states_shared": len(shared_states),
        "changed_states": len(changed),
        "changed_rate": float(len(changed) / len(shared_states)) if shared_states else 0.0,
        "changed_dominant_group_states": len(dominant),
        "changed_dominant_group_share": float(len(dominant) / len(changed)) if changed else 0.0,
        "changed_state_examples": changed[:100],
    }


def _taxonomy_assign(chosen: dict[str, float | str], oracle: dict[str, float | str], *, is_near_tie_state: bool, oracle_gap: float, pred_top2_margin: float) -> tuple[str, str]:
    delayed_payoff_signature = (
        float(chosen.get("multistep_delta", 0.0)) > 0.05
        and float(chosen.get("outside_gap", 0.0)) < 0.0
        and float(oracle.get("outside_gap", 0.0)) > 0.0
    )
    if delayed_payoff_signature:
        return (
            "delayed_payoff_overvaluation_with_outside_option_miss",
            "chosen branch has multistep uplift but negative outside-gap while oracle branch has positive outside-gap",
        )

    fragile_boundary_signature = bool(is_near_tie_state and oracle_gap <= 0.03 and pred_top2_margin >= 0.08)
    if fragile_boundary_signature:
        return (
            "fragile_boundary_overconfidence",
            "near-tie with tiny oracle gap but large predicted margin",
        )
    return ("other_score_ordering_error", "residual mismatch outside stronger signatures")


def _failure_diagnostics_for_mode(
    *,
    mode: str,
    seed: int,
    mode_best: dict[str, str],
    oracle_best: dict[str, str],
    branch_table: dict[str, dict[str, dict[str, float | str]]],
    state_near_tie: dict[str, bool],
) -> dict[str, Any]:
    rows = []
    for sid in sorted(set(mode_best) & set(oracle_best)):
        chosen_id = mode_best[sid]
        oracle_id = oracle_best[sid]
        branches = branch_table.get(sid, {})
        chosen = branches.get(chosen_id)
        oracle = branches.get(oracle_id)
        if not chosen or not oracle:
            continue
        pred_vals = sorted([float(v.get("target", 0.0)) for v in branches.values()], reverse=True)
        pred_margin = float(pred_vals[0] - pred_vals[1]) if len(pred_vals) >= 2 else 0.0
        oracle_gap = float(oracle.get("one_step", 0.0) - chosen.get("one_step", 0.0))
        is_failure = bool(chosen_id != oracle_id)
        if is_failure:
            mistake_type, rationale = _taxonomy_assign(
                chosen,
                oracle,
                is_near_tie_state=bool(state_near_tie.get(sid, False)),
                oracle_gap=oracle_gap,
                pred_top2_margin=pred_margin,
            )
        else:
            mistake_type, rationale = ("correct_or_control", "method branch matches oracle best")
        rows.append(
            {
                "seed": int(seed),
                "mode": mode,
                "state_id": sid,
                "method_choice": chosen_id,
                "oracle_best": oracle_id,
                "method_matches_oracle": bool(not is_failure),
                "is_near_tie_state": bool(state_near_tie.get(sid, False)),
                "oracle_gap_if_method": float(max(0.0, oracle_gap)),
                "chosen_multistep_delta": float(chosen.get("multistep_delta", 0.0)),
                "chosen_outside_gap": float(chosen.get("outside_gap", 0.0)),
                "oracle_outside_gap": float(oracle.get("outside_gap", 0.0)),
                "pred_margin_top2": float(pred_margin),
                "mistake_type": mistake_type,
                "mistake_rationale": rationale,
            }
        )

    failures = [r for r in rows if not bool(r["method_matches_oracle"])]
    counts: dict[str, int] = {}
    for r in failures:
        counts[str(r["mistake_type"])] = counts.get(str(r["mistake_type"]), 0) + 1
    dominant_n = int(counts.get("delayed_payoff_overvaluation_with_outside_option_miss", 0))
    return {
        "seed": int(seed),
        "mode": mode,
        "states": len(rows),
        "failure_states": len(failures),
        "dominant_group_failures": dominant_n,
        "dominant_group_failure_rate": float(dominant_n / len(rows)) if rows else 0.0,
        "taxonomy_counts_on_failures": counts,
        "rows": rows,
    }


def _build_state_near_tie_flags(eval_pairs: list[dict[str, Any]]) -> dict[str, bool]:
    flags: dict[str, bool] = {}
    for r in eval_pairs:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id", ""))
        flags[sid] = bool(flags.get(sid, False) or bool(r.get("near_tie_flag", False)) )
    return flags


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded discounted multi-step branch utility target validation")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-root", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--feature-set", default="v3", choices=["v1", "v2", "v3"])
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--baseline-regime", default="all_pairs")
    p.add_argument("--current-multistep-regime", default="multistep_branch_utility_target_k3")
    p.add_argument("--discounted-regimes", default="discounted_multistep_branch_utility_target_gamma100,discounted_multistep_branch_utility_target_gamma080,discounted_multistep_branch_utility_target_gamma060")
    p.add_argument("--multistep-target-field", default="multistep_branch_utility_target")
    p.add_argument("--strict-slice-name", default="near_tie_and_adjacent_rank")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_root) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = _parse_int_csv(args.seeds)
    targets_root = Path(args.targets_root)

    discounted_regimes = [s.strip() for s in str(args.discounted_regimes).split(",") if s.strip()]
    regime_to_mode = {
        str(args.baseline_regime): "baseline_current_matched",
        str(args.current_multistep_regime): "multistep_k3_current",
    }
    for regime in discounted_regimes:
        gamma = _parse_gamma_from_regime(regime)
        if gamma is None:
            raise ValueError(f"Expected discounted regime naming to include gamma suffix: {regime}")
        mode_name = f"discounted_gamma_{gamma:.2f}".replace(".", "_")
        regime_to_mode[regime] = mode_name

    per_seed_rows: list[dict[str, Any]] = []
    target_diag_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    per_seed_failure_rows: list[dict[str, Any]] = []
    per_seed_disagreement_rows: list[dict[str, Any]] = []

    for seed in seeds:
        baseline_regime_dir = targets_root / f"regime_{args.baseline_regime}"
        baseline_raw = load_label_artifacts(baseline_regime_dir)
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
        eval_pair_rows = baseline_tables["pairwise"]
        support_rows.append({"seed": int(seed), "test_pairs": len([r for r in eval_pair_rows if str(r.get("split")) == "test"])})
        state_near_tie = _build_state_near_tie_flags(eval_pair_rows)

        mode_to_best: dict[str, dict[str, str]] = {}
        mode_to_branch_table: dict[str, dict[str, dict[str, dict[str, float | str]]]] = {}
        oracle_by_state: dict[str, str] = {}

        for regime, mode in regime_to_mode.items():
            regime_dir = targets_root / f"regime_{regime}"
            raw = load_label_artifacts(regime_dir)
            cfg = LearningConfig(
                seed=int(seed),
                near_tie_margin=float(args.near_tie_margin),
                feature_set=str(args.feature_set),
                train_pairwise=True,
                train_pointwise=True,
                train_outside_option=False,
                train_lightgbm_ranker=False,
                train_catboost_ranker=False,
                train_pairwise_svm=False,
                pointwise_target_field=(str(args.multistep_target_field) if mode != "baseline_current_matched" else "estimated_value_if_allocate_next"),
            )
            tables = prepare_learning_tables(raw, cfg)
            candidates = tables["candidates"]

            if mode == "baseline_current_matched":
                models = train_models(tables, cfg)
                pmodel = models.get("pairwise", {})
                if str(pmodel.get("status")) == "ok":
                    score_fn = scorer_from_model(pmodel)
                    pred = lambda r: _pair_pred_from_score(score_fn, r)
                else:
                    const_label = int(pmodel.get("constant_label", 0))
                    pred = lambda _r: const_label
                model_status = str(pmodel.get("status", "unknown"))
            else:
                target_field = str(args.multistep_target_field)
                fitted = _fit_pointwise_target(candidates, target_field=target_field, seed=int(seed))
                if str(fitted.get("status")) == "ok":
                    score_fn = _scorer_from_linear(fitted)
                    pred = lambda r: _pair_pred_from_score(score_fn, r)
                else:
                    pred = lambda r: 1 if float(r.get("pair_value_i", 0.0)) >= float(r.get("pair_value_j", 0.0)) else 0
                model_status = str(fitted.get("status", "unknown"))

                gamma = _parse_gamma_from_regime(regime)
                target_diag_rows.append(
                    {
                        "seed": int(seed),
                        "mode": mode,
                        "regime": regime,
                        "discount_gamma": gamma,
                        "discount_weights": {
                            "h1": 1.0,
                            "h2": float(gamma if gamma is not None else 1.0),
                            "h3": float((gamma**2) if gamma is not None else 1.0),
                        },
                        **_target_distribution_diagnostics(candidates, eval_pair_rows, target_field=target_field),
                    }
                )

                mode_to_best[mode] = _state_best_branch_map(candidates, target_field=target_field)
                mode_to_branch_table[mode] = _build_state_branch_table(candidates, target_field=target_field)
                if not oracle_by_state:
                    oracle_by_state = _state_best_branch_map(candidates, target_field="estimated_value_if_allocate_next")

            metrics = _pair_metrics(eval_pair_rows, pred)
            per_seed_rows.append(
                {
                    "seed": int(seed),
                    "mode": mode,
                    "regime": regime,
                    "metrics": metrics,
                    "model_status": model_status,
                    "config": asdict(cfg),
                }
            )

        for mode, best_map in mode_to_best.items():
            tax = _failure_diagnostics_for_mode(
                mode=mode,
                seed=int(seed),
                mode_best=best_map,
                oracle_best=oracle_by_state,
                branch_table=mode_to_branch_table.get(mode, {}),
                state_near_tie=state_near_tie,
            )
            per_seed_failure_rows.append(tax)

        current_mode = "multistep_k3_current"
        current_tax_rows = []
        for rr in per_seed_failure_rows:
            if int(rr["seed"]) == int(seed) and str(rr["mode"]) == current_mode:
                current_tax_rows = rr["rows"]
                break
        if current_mode in mode_to_best:
            for regime, mode in regime_to_mode.items():
                if mode == current_mode or (not mode.startswith("discounted_gamma_")):
                    continue
                per_seed_disagreement_rows.append(
                    {
                        "seed": int(seed),
                        "comparison": f"{current_mode}_vs_{mode}",
                        "reference_mode": current_mode,
                        "candidate_mode": mode,
                        "discount_gamma": _parse_gamma_from_regime(regime),
                        **_disagreement_vs_reference(mode_to_best[current_mode], mode_to_best.get(mode, {}), current_tax_rows),
                    }
                )

    modes = list(dict.fromkeys(regime_to_mode.values()))
    aggregate: dict[str, Any] = {}
    for mode in modes:
        rows = [r for r in per_seed_rows if r["mode"] == mode]
        aggregate[mode] = {
            "seeds": len(rows),
            "accepted_accuracy_mean": _mean([float(r["metrics"].get("accepted_accuracy", 0.0)) for r in rows]),
            "accepted_accuracy_std": float(pstdev([float(r["metrics"].get("accepted_accuracy", 0.0)) for r in rows])) if len(rows) > 1 else 0.0,
            "coverage_mean": _mean([float(r["metrics"].get("coverage", 0.0)) for r in rows]),
            "defer_rate_mean": _mean([float(r["metrics"].get("defer_rate", 0.0)) for r in rows]),
            "near_tie_accepted_accuracy_mean": _mean([float(r["metrics"].get("near_tie_accepted_accuracy", 0.0)) for r in rows]),
            "adjacent_rank_accepted_accuracy_mean": _mean([float(r["metrics"].get("adjacent_rank_accepted_accuracy", 0.0)) for r in rows]),
            "strict_slice_accepted_accuracy_mean": _mean([float(r["metrics"].get("strict_slice_accepted_accuracy", 0.0)) for r in rows]),
        }

    baseline = aggregate.get("baseline_current_matched", {})
    current = aggregate.get("multistep_k3_current", {})
    comparison: dict[str, Any] = {}
    for mode in modes:
        if mode == "baseline_current_matched":
            continue
        vals = aggregate.get(mode, {})
        comparison[mode] = {
            "delta_accepted_accuracy_vs_baseline": float(vals.get("accepted_accuracy_mean", 0.0) - baseline.get("accepted_accuracy_mean", 0.0)),
            "delta_accepted_accuracy_vs_current_multistep": float(vals.get("accepted_accuracy_mean", 0.0) - current.get("accepted_accuracy_mean", 0.0)),
            "delta_near_tie_accepted_accuracy_vs_baseline": float(vals.get("near_tie_accepted_accuracy_mean", 0.0) - baseline.get("near_tie_accepted_accuracy_mean", 0.0)),
            "delta_adjacent_rank_accepted_accuracy_vs_baseline": float(vals.get("adjacent_rank_accepted_accuracy_mean", 0.0) - baseline.get("adjacent_rank_accepted_accuracy_mean", 0.0)),
            "delta_strict_slice_accepted_accuracy_vs_baseline": float(vals.get("strict_slice_accepted_accuracy_mean", 0.0) - baseline.get("strict_slice_accepted_accuracy_mean", 0.0)),
        }

    failure_aggregate: dict[str, Any] = {}
    for mode in [m for m in modes if m != "baseline_current_matched"]:
        rows = [r for r in per_seed_failure_rows if str(r["mode"]) == mode]
        failure_aggregate[mode] = {
            "seeds": len(rows),
            "states_mean": _mean([float(r.get("states", 0)) for r in rows]),
            "failure_states_mean": _mean([float(r.get("failure_states", 0)) for r in rows]),
            "dominant_group_failures_mean": _mean([float(r.get("dominant_group_failures", 0)) for r in rows]),
            "dominant_group_failure_rate_mean": _mean([float(r.get("dominant_group_failure_rate", 0.0)) for r in rows]),
        }

    dominant_comparison_rows = []
    for seed in seeds:
        seed_rows = [r for r in per_seed_failure_rows if int(r["seed"]) == int(seed)]
        by_mode = {str(r["mode"]): r for r in seed_rows}
        current_row = by_mode.get("multistep_k3_current")
        if not current_row:
            continue
        for mode, row in by_mode.items():
            if not str(mode).startswith("discounted_gamma_"):
                continue
            dominant_comparison_rows.append(
                {
                    "seed": int(seed),
                    "mode": mode,
                    "dominant_failures_current": int(current_row.get("dominant_group_failures", 0)),
                    "dominant_failures_discounted": int(row.get("dominant_group_failures", 0)),
                    "delta_dominant_failures": int(row.get("dominant_group_failures", 0) - current_row.get("dominant_group_failures", 0)),
                    "failure_states_current": int(current_row.get("failure_states", 0)),
                    "failure_states_discounted": int(row.get("failure_states", 0)),
                    "delta_failure_states": int(row.get("failure_states", 0) - current_row.get("failure_states", 0)),
                }
            )

    _write_json(out_dir / "config_manifest.json", {
        "run_id": str(args.run_id),
        "targets_root": str(targets_root),
        "seeds": seeds,
        "feature_set": str(args.feature_set),
        "near_tie_margin": float(args.near_tie_margin),
        "regime_to_mode": regime_to_mode,
        "multistep_target_field": str(args.multistep_target_field),
        "strict_slice_name": str(args.strict_slice_name),
        "command": " ".join(sys.argv),
    })
    _write_json(out_dir / "per_seed_summary.json", {"rows": per_seed_rows})
    _write_json(out_dir / "matched_summary_by_mode_gamma.json", {"aggregate": aggregate, "comparison": comparison})
    _write_json(out_dir / "aggregate_comparison_summary.json", {"aggregate": aggregate, "comparison": comparison, "failure_aggregate": failure_aggregate})
    _write_json(out_dir / "per_seed_failure_taxonomy.json", {"rows": per_seed_failure_rows})
    _write_json(out_dir / "dominant_failure_group_comparison_summary.json", {"rows": dominant_comparison_rows, "aggregate": failure_aggregate})
    _write_json(out_dir / "target_diagnostics_by_gamma.json", {"rows": target_diag_rows})
    _write_json(out_dir / "disagreement_diagnostics.json", {"rows": per_seed_disagreement_rows})
    _write_json(out_dir / "support_diagnostics.json", {"rows": support_rows})

    print(json.dumps({"output_dir": str(out_dir), "modes": modes}, indent=2))


if __name__ == "__main__":
    main()
