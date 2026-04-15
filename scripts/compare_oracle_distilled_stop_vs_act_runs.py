#!/usr/bin/env python3
"""Aggregate oracle-distilled student summaries with matched-control evaluation gates.

This is an evaluation-readiness scaffold. It does not generate oracle labels and does
not claim oracle wins; it only checks whether required comparison controls are present.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics
from typing import Any


ROLE_ANCHOR = "anchor_default"
ROLE_ACCEPTED_ONLY = "oracle_distilled_accepted_only"
ROLE_ACCEPTED_PLUS_BORDERLINE = "oracle_distilled_accepted_plus_borderline"
ROLE_RANDOM_MATCHED = "random_matched_coverage_baseline"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _get_nested(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _safe_float(x: Any) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    return None


def _infer_role(summary: dict[str, Any], path: str) -> str:
    settings = dict(summary.get("settings", {}))
    role = str(settings.get("filter_policy", "")).strip().lower()
    if role:
        return role

    run_name = str(summary.get("run_name", "")).lower()
    train_buckets = sorted(str(x).lower() for x in settings.get("train_buckets", []))
    if "random" in run_name:
        return ROLE_RANDOM_MATCHED
    if train_buckets == ["accepted"]:
        return ROLE_ACCEPTED_ONLY
    if train_buckets == ["accepted", "borderline"]:
        return ROLE_ACCEPTED_PLUS_BORDERLINE
    if "anchor" in run_name:
        return ROLE_ANCHOR
    return f"unknown:{Path(path).stem}"


def _extract_required_slice_keys(summary: dict[str, Any]) -> list[str]:
    req_slices = dict(_get_nested(summary, "evaluation", "required_slices", default={}) or {})
    return sorted(req_slices.keys())


def _flatten(summary: dict[str, Any], path: str) -> dict[str, Any]:
    settings = dict(summary.get("settings", {}))
    data = dict(summary.get("dataset_summary", {}))
    evaln = dict(summary.get("evaluation", {}))
    student = dict(evaln.get("student", {}))
    anchor = dict(evaln.get("anchor_gain_gap_baseline", {}))
    diff = dict(evaln.get("student_minus_anchor", {}))
    compute = dict(evaln.get("compute_reporting", {}))
    behavior = dict(evaln.get("controller_behavior", {}))

    return {
        "summary_path": path,
        "run_name": summary.get("run_name", Path(path).parent.name),
        "run_role": _infer_role(summary, path),
        "train_buckets": ",".join(settings.get("train_buckets", [])),
        "eval_buckets": ",".join(settings.get("eval_buckets", [])),
        "model_kind": settings.get("model_kind", ""),
        "train_selection_mode": settings.get("train_selection_mode", ""),
        "random_baseline_source": settings.get("random_baseline_source", ""),
        "non_claim_mode": bool(dict(summary.get("safety", {})).get("non_claim_mode", False)),
        "mock_rows_detected": int(data.get("mock_rows_detected", 0)),
        "train_rows": int(data.get("train_rows", 0)),
        "train_pool_rows": int(data.get("train_pool_rows", 0)),
        "retained_coverage_train_pool": float(data.get("retained_coverage_train_pool", 0.0)),
        "eval_rows": int(data.get("eval_rows", 0)),
        "student_accuracy": float(student.get("accuracy", 0.0)),
        "student_auc": float(student.get("roc_auc", 0.0)),
        "student_brier": float(student.get("brier", 0.0)),
        "anchor_accuracy": float(anchor.get("accuracy", 0.0)),
        "anchor_auc": float(anchor.get("roc_auc", 0.0)),
        "anchor_brier": float(anchor.get("brier", 0.0)),
        "delta_accuracy": float(diff.get("accuracy", 0.0)),
        "delta_auc": float(diff.get("roc_auc", 0.0)),
        "delta_brier": float(diff.get("brier", 0.0)),
        "predicted_act_rate": float(compute.get("predicted_act_rate", 0.0)),
        "observed_avg_actions": compute.get("observed_avg_actions", None),
        "behavior_metrics_available": bool(behavior.get("available", False)),
        "behavior_metric_reason": str(behavior.get("reason", "")),
        "behavior_eligible_rows": int(behavior.get("eligible_rows", 0) or 0),
        "bar": _safe_float(behavior.get("beneficial_act_rate_bar")),
        "har": _safe_float(behavior.get("harmful_act_rate_har")),
        "hpsr": _safe_float(behavior.get("harmful_premature_stop_rate_hpsr")),
        "bsr": _safe_float(behavior.get("beneficial_stop_rate_bsr")),
        "oracle_action_regret": _safe_float(behavior.get("oracle_action_regret")),
        "required_slice_keys": ",".join(_extract_required_slice_keys(summary)),
    }


def _best_random_match(rows: list[dict[str, Any]], target_row: dict[str, Any]) -> dict[str, Any] | None:
    random_rows = [r for r in rows if r["run_role"] == ROLE_RANDOM_MATCHED]
    if not random_rows:
        return None
    return min(
        random_rows,
        key=lambda r: abs(float(r["retained_coverage_train_pool"]) - float(target_row["retained_coverage_train_pool"])),
    )


def _role_regime_key(role: str) -> str:
    if role == ROLE_ACCEPTED_ONLY:
        return "accepted_only"
    if role == ROLE_ACCEPTED_PLUS_BORDERLINE:
        return "accepted_plus_borderline"
    return "unknown"


def _comparable_random_rows(rows: list[dict[str, Any]], target_row: dict[str, Any], coverage_tol: float) -> list[dict[str, Any]]:
    random_rows = [r for r in rows if r["run_role"] == ROLE_RANDOM_MATCHED]
    if not random_rows:
        return []

    target_cov = float(target_row["retained_coverage_train_pool"])
    cov_matched = [r for r in random_rows if abs(float(r["retained_coverage_train_pool"]) - target_cov) <= coverage_tol]

    regime = _role_regime_key(str(target_row["run_role"]))
    if cov_matched:
        tagged = [r for r in cov_matched if regime in str(r.get("random_baseline_source", "")).lower()]
        return tagged if tagged else cov_matched

    nearest = _best_random_match(rows, target_row)
    return [nearest] if nearest is not None else []


def _summary_stats(vals: list[float]) -> dict[str, float]:
    if not vals:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
    return {
        "mean": float(sum(vals) / len(vals)),
        "std": float(statistics.pstdev(vals)) if len(vals) > 1 else 0.0,
        "min": float(min(vals)),
        "max": float(max(vals)),
    }


def _collect_present(rows: list[dict[str, Any]], key: str) -> list[float]:
    out: list[float] = []
    for row in rows:
        val = _safe_float(row.get(key))
        if val is not None:
            out.append(float(val))
    return out


def _closest_threshold_point(summary: dict[str, Any], target_act_rate: float) -> dict[str, Any]:
    evaln = dict(summary.get("evaluation", {}))
    sweep = list(evaln.get("threshold_sweep", []) or [])
    if not sweep:
        return {"available": False, "reason": "missing_threshold_sweep"}

    target = float(target_act_rate)
    best = min(
        sweep,
        key=lambda x: (
            abs(float(x.get("predicted_act_rate", 0.0)) - target),
            abs(float(x.get("threshold", 0.5)) - 0.5),
        ),
    )
    pred_rate = float(best.get("predicted_act_rate", 0.0))
    student = dict(best.get("student", {}))
    behavior = dict(best.get("controller_behavior", {}))
    return {
        "available": True,
        "target_act_rate": target,
        "threshold": float(best.get("threshold", 0.5)),
        "predicted_act_rate": pred_rate,
        "abs_act_rate_residual": float(abs(pred_rate - target)),
        "student": {
            "accuracy": float(student.get("accuracy", 0.0)),
            "roc_auc": float(student.get("roc_auc", 0.0)),
            "brier": float(student.get("brier", 0.0)),
        },
        "controller_behavior": {
            "available": bool(behavior.get("available", False)),
            "bar": _safe_float(behavior.get("beneficial_act_rate_bar")),
            "har": _safe_float(behavior.get("harmful_act_rate_har")),
            "hpsr": _safe_float(behavior.get("harmful_premature_stop_rate_hpsr")),
            "bsr": _safe_float(behavior.get("beneficial_stop_rate_bsr")),
            "oracle_action_regret": _safe_float(behavior.get("oracle_action_regret")),
        },
    }


def _resolve_target_act_rate(rows_sorted: list[dict[str, Any]], user_target: float) -> tuple[float, str]:
    role_rows = {str(r["run_role"]): r for r in rows_sorted}
    if user_target >= 0.0:
        return float(user_target), "user_specified"
    if ROLE_ANCHOR in role_rows:
        return float(role_rows[ROLE_ANCHOR]["predicted_act_rate"]), "anchor_native"
    return float(sum(float(r["predicted_act_rate"]) for r in rows_sorted) / max(1, len(rows_sorted))), "mean_native_fallback"


def _auc(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    pairs = sorted(zip(xs, ys), key=lambda z: z[0])
    area = 0.0
    for i in range(len(pairs) - 1):
        x0, y0 = pairs[i]
        x1, y1 = pairs[i + 1]
        area += 0.5 * (y0 + y1) * (x1 - x0)
    return float(area)


def _parse_frontier_grid_arg(value: str) -> list[float]:
    if not value.strip():
        return []
    out: list[float] = []
    for tok in value.split(","):
        tok = tok.strip()
        if not tok:
            continue
        v = max(0.0, min(1.0, float(tok)))
        out.append(float(v))
    return sorted(set(out))


def _shared_act_rate_grid(
    rows_sorted: list[dict[str, Any]],
    summary_by_path: dict[str, dict[str, Any]],
    *,
    target_act_rate: float,
    user_grid: list[float],
    frontier_points: int,
) -> list[float]:
    if user_grid:
        return user_grid

    role_rows = {str(r["run_role"]): r for r in rows_sorted}
    anchor_row = role_rows.get(ROLE_ANCHOR)
    if anchor_row is None:
        return [float(target_act_rate)]

    summary = summary_by_path.get(str(anchor_row["summary_path"]), {})
    sweep = list(dict(summary.get("evaluation", {})).get("threshold_sweep", []) or [])
    rates = sorted(set(float(x.get("predicted_act_rate", 0.0)) for x in sweep))
    if not rates:
        return [float(target_act_rate)]

    n = max(2, int(frontier_points))
    if len(rates) <= n:
        return rates

    idxs = sorted(set(int(round(i * (len(rates) - 1) / (n - 1))) for i in range(n)))
    return [float(rates[i]) for i in idxs]


def _frontier_for_run(summary: dict[str, Any], rate_grid: list[float]) -> list[dict[str, Any]]:
    return [_closest_threshold_point(summary, rate) for rate in rate_grid]


def _frontier_deltas(selective_points: list[dict[str, Any]], random_points: list[dict[str, Any]], rate_grid: list[float]) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    for target, sel, rnd in zip(rate_grid, selective_points, random_points):
        point: dict[str, Any] = {
            "target_act_rate": float(target),
            "selective": sel,
            "matched_random": rnd,
        }
        if bool(sel.get("available", False)) and bool(rnd.get("available", False)):
            delta = {
                "student_accuracy": float(sel["student"]["accuracy"] - rnd["student"]["accuracy"]),
                "student_auc": float(sel["student"]["roc_auc"] - rnd["student"]["roc_auc"]),
                "student_brier": float(sel["student"]["brier"] - rnd["student"]["brier"]),
                "bar": None if _safe_float(sel["controller_behavior"].get("bar")) is None or _safe_float(rnd["controller_behavior"].get("bar")) is None else float(float(sel["controller_behavior"]["bar"]) - float(rnd["controller_behavior"]["bar"])),
                "har": None if _safe_float(sel["controller_behavior"].get("har")) is None or _safe_float(rnd["controller_behavior"].get("har")) is None else float(float(sel["controller_behavior"]["har"]) - float(rnd["controller_behavior"]["har"])),
                "hpsr": None if _safe_float(sel["controller_behavior"].get("hpsr")) is None or _safe_float(rnd["controller_behavior"].get("hpsr")) is None else float(float(sel["controller_behavior"]["hpsr"]) - float(rnd["controller_behavior"]["hpsr"])),
                "bsr": None if _safe_float(sel["controller_behavior"].get("bsr")) is None or _safe_float(rnd["controller_behavior"].get("bsr")) is None else float(float(sel["controller_behavior"]["bsr"]) - float(rnd["controller_behavior"]["bsr"])),
                "oracle_action_regret": None if _safe_float(sel["controller_behavior"].get("oracle_action_regret")) is None or _safe_float(rnd["controller_behavior"].get("oracle_action_regret")) is None else float(float(sel["controller_behavior"]["oracle_action_regret"]) - float(rnd["controller_behavior"]["oracle_action_regret"])),
            }
            point["delta"] = delta
            point["abs_pred_act_rate_gap"] = float(abs(float(sel.get("predicted_act_rate", 0.0)) - float(rnd.get("predicted_act_rate", 0.0))))
            point["available"] = True
        else:
            point["available"] = False
        points.append(point)

    avail = [p for p in points if p.get("available", False)]
    acc_d = [float(p["delta"]["student_accuracy"]) for p in avail]
    auc_d = [float(p["delta"]["student_auc"]) for p in avail]
    brier_d = [float(p["delta"]["student_brier"]) for p in avail]
    regret_d = [float(p["delta"]["oracle_action_regret"]) for p in avail if _safe_float(p["delta"].get("oracle_action_regret")) is not None]
    xs = [float(p["target_act_rate"]) for p in avail]
    return {
        "points": points,
        "summary": {
            "available_points": int(len(avail)),
            "total_points": int(len(points)),
            "mean_delta": {
                "student_accuracy": float(sum(acc_d) / len(acc_d)) if acc_d else None,
                "student_auc": float(sum(auc_d) / len(auc_d)) if auc_d else None,
                "student_brier": float(sum(brier_d) / len(brier_d)) if brier_d else None,
                "oracle_action_regret": float(sum(regret_d) / len(regret_d)) if regret_d else None,
            },
            "win_counts": {
                "student_accuracy": int(sum(1 for x in acc_d if x > 0.0)),
                "student_auc": int(sum(1 for x in auc_d if x > 0.0)),
                "student_brier_lower_is_better": int(sum(1 for x in brier_d if x < 0.0)),
                "oracle_action_regret_lower_is_better": int(sum(1 for x in regret_d if x < 0.0)),
            },
            "auc_delta": {
                "student_accuracy": _auc(xs, acc_d) if len(acc_d) == len(xs) else None,
                "student_auc": _auc(xs, auc_d) if len(auc_d) == len(xs) else None,
                "student_brier": _auc(xs, brier_d) if len(brier_d) == len(xs) else None,
                "oracle_action_regret": _auc(xs, regret_d) if len(regret_d) == len(xs) else None,
            },
            "mean_abs_pred_act_rate_gap": float(sum(float(p.get("abs_pred_act_rate_gap", 0.0)) for p in avail) / len(avail)) if avail else None,
        },
    }


def _pairwise_control_report(
    rows: list[dict[str, Any]],
    summary_by_path: dict[str, dict[str, Any]],
    *,
    coverage_tol: float,
    act_rate_tol: float,
    matched_act_rate_target: float,
    matched_act_rate_tol: float,
    compute_rate_tol: float,
    frontier_grid: list[float],
) -> dict[str, Any]:
    role_rows = {r["run_role"]: r for r in rows}
    checks: dict[str, Any] = {}

    for role in [ROLE_ACCEPTED_ONLY, ROLE_ACCEPTED_PLUS_BORDERLINE]:
        row = role_rows.get(role)
        if row is None:
            checks[role] = {"status": "missing_run"}
            continue

        rnd_rows = _comparable_random_rows(rows, row, coverage_tol=coverage_tol)
        if not rnd_rows:
            checks[role] = {"status": "missing_random_matched_baseline"}
            continue
        rnd = _best_random_match(rnd_rows, row)
        if rnd is None:
            checks[role] = {"status": "missing_random_matched_baseline"}
            continue

        cov_gap = float(row["retained_coverage_train_pool"] - rnd["retained_coverage_train_pool"])
        act_gap = float(row["predicted_act_rate"] - rnd["predicted_act_rate"])
        obs_row = _safe_float(row.get("observed_avg_actions"))
        obs_rnd = _safe_float(rnd.get("observed_avg_actions"))
        avg_actions_gap = None if (obs_row is None or obs_rnd is None) else float(obs_row - obs_rnd)

        checks[role] = {
            "status": "ok",
            "run_name": row["run_name"],
            "num_random_draws": len(rnd_rows),
            "random_draw_run_names": [str(r["run_name"]) for r in rnd_rows],
            "matched_random_run_name": rnd["run_name"],
            "coverage_gap": cov_gap,
            "coverage_match_pass": abs(cov_gap) <= coverage_tol,
            "predicted_act_rate_gap": act_gap,
            "predicted_act_rate_match_pass": abs(act_gap) <= act_rate_tol,
            "observed_avg_actions_gap": avg_actions_gap,
            "delta_accuracy_vs_matched_random": float(row["student_accuracy"] - rnd["student_accuracy"]),
            "delta_auc_vs_matched_random": float(row["student_auc"] - rnd["student_auc"]),
            "delta_brier_vs_matched_random": float(row["student_brier"] - rnd["student_brier"]),
            "random_draw_stats": {
                "student_accuracy": _summary_stats([float(r["student_accuracy"]) for r in rnd_rows]),
                "student_auc": _summary_stats([float(r["student_auc"]) for r in rnd_rows]),
                "student_brier": _summary_stats([float(r["student_brier"]) for r in rnd_rows]),
                "predicted_act_rate": _summary_stats([float(r["predicted_act_rate"]) for r in rnd_rows]),
                "bar": _summary_stats(_collect_present(rnd_rows, "bar")),
                "har": _summary_stats(_collect_present(rnd_rows, "har")),
                "hpsr": _summary_stats(_collect_present(rnd_rows, "hpsr")),
                "bsr": _summary_stats(_collect_present(rnd_rows, "bsr")),
                "oracle_action_regret": _summary_stats(_collect_present(rnd_rows, "oracle_action_regret")),
            },
            "behavior_metric_availability": {
                "selective_run_has_behavior_metrics": bool(row.get("behavior_metrics_available", False)),
                "random_draws_with_behavior_metrics": int(sum(1 for r in rnd_rows if bool(r.get("behavior_metrics_available", False)))),
            },
        }

        sel_summary = summary_by_path.get(str(row["summary_path"]), {})
        rnd_summary = summary_by_path.get(str(rnd["summary_path"]), {})
        sel_match = _closest_threshold_point(sel_summary, matched_act_rate_target)
        rnd_match = _closest_threshold_point(rnd_summary, matched_act_rate_target)
        matched_block: dict[str, Any] = {
            "target_predicted_act_rate": float(matched_act_rate_target),
            "selective": sel_match,
            "matched_random": rnd_match,
            "match_tolerance": float(matched_act_rate_tol),
        }
        if sel_match.get("available") and rnd_match.get("available"):
            sel_rate = float(sel_match.get("predicted_act_rate", 0.0))
            rnd_rate = float(rnd_match.get("predicted_act_rate", 0.0))
            matched_block.update(
                {
                    "selective_vs_random_abs_act_rate_gap": float(abs(sel_rate - rnd_rate)),
                    "selective_vs_random_abs_act_rate_gap_pass": bool(abs(sel_rate - rnd_rate) <= matched_act_rate_tol),
                    "deltas_at_matched_rate": {
                        "student_accuracy": float(sel_match["student"]["accuracy"] - rnd_match["student"]["accuracy"]),
                        "student_auc": float(sel_match["student"]["roc_auc"] - rnd_match["student"]["roc_auc"]),
                        "student_brier": float(sel_match["student"]["brier"] - rnd_match["student"]["brier"]),
                    },
                }
            )
        checks[role]["matched_act_rate_evaluation"] = matched_block

        if obs_row is None or obs_rnd is None:
            checks[role]["matched_compute_rate_evaluation"] = {"available": False, "reason": "missing_observed_avg_actions"}
        else:
            gap = float(obs_row - obs_rnd)
            checks[role]["matched_compute_rate_evaluation"] = {
                "available": True,
                "selective_observed_avg_actions": float(obs_row),
                "matched_random_observed_avg_actions": float(obs_rnd),
                "abs_gap": float(abs(gap)),
                "match_tolerance": float(compute_rate_tol),
                "match_pass": bool(abs(gap) <= compute_rate_tol),
            }

        sel_frontier = _frontier_for_run(sel_summary, frontier_grid)
        rnd_frontier = _frontier_for_run(rnd_summary, frontier_grid)
        checks[role]["matched_act_rate_frontier"] = {
            "rate_grid": [float(x) for x in frontier_grid],
            "match_tolerance": float(matched_act_rate_tol),
            "deltas": _frontier_deltas(sel_frontier, rnd_frontier, frontier_grid),
        }

    return checks


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare oracle-distilled stop-vs-act run summaries with control gates")
    p.add_argument("--summaries", nargs="+", required=True, help="One or more oracle_distilled_student_summary.json paths")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--anchor-summary", default="", help="Optional current-default anchor summary for reference metadata")
    p.add_argument("--coverage-match-tol", type=float, default=0.01)
    p.add_argument("--act-rate-match-tol", type=float, default=0.02)
    p.add_argument(
        "--matched-act-rate-target",
        type=float,
        default=-1.0,
        help="If >=0, use this target predicted ACT-rate for matched-threshold evaluation. If <0, use anchor native ACT-rate.",
    )
    p.add_argument("--matched-act-rate-tol", type=float, default=0.01)
    p.add_argument("--compute-rate-match-tol", type=float, default=0.05)
    p.add_argument(
        "--frontier-act-rate-grid",
        default="",
        help="Optional comma-separated ACT-rate targets for frontier evaluation. If empty, derive from anchor sweep.",
    )
    p.add_argument("--frontier-points", type=int, default=5, help="Number of ACT-rate points when building automatic frontier grid.")
    p.add_argument("--min-random-draws-per-regime", type=int, default=1)
    p.add_argument(
        "--required-roles",
        default="anchor_default,oracle_distilled_accepted_only,oracle_distilled_accepted_plus_borderline,random_matched_coverage_baseline",
        help="Comma-separated required run roles for readiness gating.",
    )
    p.add_argument(
        "--required-slice-keys",
        default="uncertainty_bins,oracle_margin_bins,disagreement_bins,remaining_budget_bins",
        help="Comma-separated required slice keys expected in each run summary.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_by_path = {str(path): _load_json(Path(path)) for path in args.summaries}
    rows = [_flatten(summary_by_path[str(path)], path) for path in args.summaries]
    rows_sorted = sorted(rows, key=lambda r: (r["non_claim_mode"], -r["student_accuracy"], -r["student_auc"]))

    csv_path = out_dir / "oracle_distilled_student_comparison.csv"
    fields = [
        "run_name",
        "run_role",
        "summary_path",
        "train_buckets",
        "eval_buckets",
        "model_kind",
        "train_selection_mode",
        "random_baseline_source",
        "non_claim_mode",
        "mock_rows_detected",
        "train_rows",
        "train_pool_rows",
        "retained_coverage_train_pool",
        "eval_rows",
        "predicted_act_rate",
        "observed_avg_actions",
        "behavior_metrics_available",
        "behavior_metric_reason",
        "behavior_eligible_rows",
        "bar",
        "har",
        "hpsr",
        "bsr",
        "oracle_action_regret",
        "required_slice_keys",
        "student_accuracy",
        "anchor_accuracy",
        "delta_accuracy",
        "student_auc",
        "anchor_auc",
        "delta_auc",
        "student_brier",
        "anchor_brier",
        "delta_brier",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows_sorted:
            writer.writerow(row)

    required_slice_keys = [x.strip() for x in args.required_slice_keys.split(",") if x.strip()]
    required_roles = [x.strip() for x in args.required_roles.split(",") if x.strip()]
    present_roles = sorted({str(r["run_role"]) for r in rows_sorted})
    missing_roles = [r for r in required_roles if r not in present_roles]

    slice_coverage = {}
    for r in rows_sorted:
        keys = {k.strip() for k in str(r.get("required_slice_keys", "")).split(",") if k.strip()}
        missing = [k for k in required_slice_keys if k not in keys]
        slice_coverage[r["run_name"]] = {"run_role": r["run_role"], "missing_slice_keys": missing}

    behavior_metric_coverage = {
        r["run_name"]: {
            "run_role": r["run_role"],
            "available": bool(r.get("behavior_metrics_available", False)),
            "reason": str(r.get("behavior_metric_reason", "")),
            "eligible_rows": int(r.get("behavior_eligible_rows", 0)),
        }
        for r in rows_sorted
    }

    target_act_rate, target_source = _resolve_target_act_rate(rows_sorted, args.matched_act_rate_target)
    user_grid = _parse_frontier_grid_arg(args.frontier_act_rate_grid)
    frontier_grid = _shared_act_rate_grid(
        rows_sorted,
        summary_by_path,
        target_act_rate=target_act_rate,
        user_grid=user_grid,
        frontier_points=args.frontier_points,
    )

    matched_point_by_run = {
        r["run_name"]: _closest_threshold_point(summary_by_path[str(r["summary_path"])], target_act_rate) for r in rows_sorted
    }
    frontier_points_by_run = {
        r["run_name"]: _frontier_for_run(summary_by_path[str(r["summary_path"])], frontier_grid) for r in rows_sorted
    }

    pairwise_controls = _pairwise_control_report(
        rows_sorted,
        summary_by_path,
        coverage_tol=args.coverage_match_tol,
        act_rate_tol=args.act_rate_match_tol,
        matched_act_rate_target=target_act_rate,
        matched_act_rate_tol=args.matched_act_rate_tol,
        compute_rate_tol=args.compute_rate_match_tol,
        frontier_grid=frontier_grid,
    )

    repeated_random_aggregate = {
        role: {
            "num_random_draws": int(dict(detail).get("num_random_draws", 0)),
            "random_draw_stats": dict(detail).get("random_draw_stats", {}),
        }
        for role, detail in pairwise_controls.items()
        if dict(detail).get("status") == "ok"
    }

    selective_roles_to_check = [role for role in [ROLE_ACCEPTED_ONLY, ROLE_ACCEPTED_PLUS_BORDERLINE] if role in required_roles]
    pairwise_pass = True
    for role in selective_roles_to_check:
        detail = dict(pairwise_controls.get(role, {}))
        if detail.get("status") != "ok":
            pairwise_pass = False
            continue
        if not bool(detail.get("coverage_match_pass", False)):
            pairwise_pass = False
        if int(detail.get("num_random_draws", 0)) < int(args.min_random_draws_per_regime):
            pairwise_pass = False
        matched_block = dict(detail.get("matched_act_rate_evaluation", {}))
        if bool(matched_block.get("selective", {}).get("available", False)) and bool(matched_block.get("matched_random", {}).get("available", False)):
            if not bool(matched_block.get("selective_vs_random_abs_act_rate_gap_pass", False)):
                pairwise_pass = False

    readiness = {
        "required_roles_present": len(missing_roles) == 0,
        "missing_roles": missing_roles,
        "all_runs_have_required_slices": all(not v["missing_slice_keys"] for v in slice_coverage.values()),
        "behavior_metrics_present_in_any_run": any(v["available"] for v in behavior_metric_coverage.values()),
        "matched_act_rate_target": float(target_act_rate),
        "matched_act_rate_target_source": target_source,
        "frontier_rate_grid": [float(x) for x in frontier_grid],
        "pairwise_controls": pairwise_controls,
        "pairwise_coverage_controls_pass": pairwise_pass,
    }
    readiness["ready_for_oracle_phase_comparisons"] = bool(
        readiness["required_roles_present"] and readiness["all_runs_have_required_slices"] and readiness["pairwise_coverage_controls_pass"]
    )

    best = rows_sorted[0] if rows_sorted else {}
    payload = {
        "status": "ok",
        "rows": rows_sorted,
        "num_runs": len(rows_sorted),
        "best_by_student_accuracy": {
            "run_name": best.get("run_name", ""),
            "run_role": best.get("run_role", ""),
            "student_accuracy": best.get("student_accuracy", 0.0),
            "non_claim_mode": best.get("non_claim_mode", True),
        },
        "comparison_protocol": {
            "required_roles": required_roles,
            "required_slice_keys": required_slice_keys,
            "coverage_match_tolerance": args.coverage_match_tol,
            "act_rate_match_tolerance": args.act_rate_match_tol,
            "matched_act_rate_target": float(target_act_rate),
            "matched_act_rate_target_source": target_source,
            "matched_act_rate_tolerance": args.matched_act_rate_tol,
            "compute_rate_match_tolerance": args.compute_rate_match_tol,
            "frontier_rate_grid": [float(x) for x in frontier_grid],
            "frontier_points": int(args.frontier_points),
            "min_random_draws_per_regime": int(args.min_random_draws_per_regime),
            "naive_filtered_vs_unfiltered_allowed": False,
        },
        "readiness_checks": readiness,
        "repeated_random_aggregate": repeated_random_aggregate,
        "matched_point_by_run": matched_point_by_run,
        "frontier_points_by_run": frontier_points_by_run,
        "slice_coverage": slice_coverage,
        "behavior_metric_coverage": behavior_metric_coverage,
        "anchor_summary_path": args.anchor_summary,
        "non_claim_warning": "Any run with non_claim_mode=true is diagnostic only and not evidence of real oracle-distilled gains.",
    }

    (out_dir / "oracle_distilled_student_comparison_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_lines = [
        "# Oracle-distilled stop-vs-act comparison (matched-control scaffold)",
        "",
        f"- Runs compared: {len(rows_sorted)}",
        f"- CSV: `{csv_path}`",
        f"- Matched ACT-rate target: `{target_act_rate:.4f}` ({target_source})",
        f"- Frontier ACT-rate grid: `{', '.join(f'{x:.4f}' for x in frontier_grid)}`",
        "",
        "| run_name | run_role | retained_coverage | pred_act_rate | BAR | HAR | HPSR | BSR | regret | student_acc | student_auc | non_claim_mode |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def _fmt_opt(x: Any) -> str:
        v = _safe_float(x)
        return "n/a" if v is None else f"{v:.4f}"

    for row in rows_sorted:
        md_lines.append(
            f"| {row['run_name']} | {row['run_role']} | {row['retained_coverage_train_pool']:.4f} | "
            f"{row['predicted_act_rate']:.4f} | {_fmt_opt(row.get('bar'))} | {_fmt_opt(row.get('har'))} | "
            f"{_fmt_opt(row.get('hpsr'))} | {_fmt_opt(row.get('bsr'))} | {_fmt_opt(row.get('oracle_action_regret'))} | "
            f"{row['student_accuracy']:.4f} | {row['student_auc']:.4f} | {row['non_claim_mode']} |"
        )

    md_lines += [
        "",
        "## Readiness checks",
        f"- Required roles present: **{readiness['required_roles_present']}**",
        f"- Missing roles: `{', '.join(readiness['missing_roles']) if readiness['missing_roles'] else '(none)'}`",
        f"- All runs have required slices: **{readiness['all_runs_have_required_slices']}**",
        "",
        "## Pairwise matched-control checks",
    ]

    for role, detail in pairwise_controls.items():
        md_lines.append(f"- {role}: `{json.dumps(detail, sort_keys=True)}`")

    md_lines += [
        "",
        "## Interpretation guardrails",
        "- Naive filtered-vs-unfiltered claims are disallowed in this protocol.",
        "- Future oracle claims require real validated pilot labels and non-claim mode off.",
        "- Matched-coverage random controls and rate/slice/frontier checks are mandatory gates.",
    ]
    (out_dir / "oracle_distilled_student_comparison.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
