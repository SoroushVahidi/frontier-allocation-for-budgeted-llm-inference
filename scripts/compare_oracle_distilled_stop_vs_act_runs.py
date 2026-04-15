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
        "required_slice_keys": ",".join(_extract_required_slice_keys(summary)),
    }


def _safe_float(x: Any) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    return None


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


def _pairwise_control_report(rows: list[dict[str, Any]], coverage_tol: float, act_rate_tol: float) -> dict[str, Any]:
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
            },
            "selective_minus_random_mean": {
                "student_accuracy": float(row["student_accuracy"] - _summary_stats([float(r["student_accuracy"]) for r in rnd_rows])["mean"]),
                "student_auc": float(row["student_auc"] - _summary_stats([float(r["student_auc"]) for r in rnd_rows])["mean"]),
                "student_brier": float(row["student_brier"] - _summary_stats([float(r["student_brier"]) for r in rnd_rows])["mean"]),
            },
            "wins_vs_random_draws": {
                "student_accuracy": int(sum(1 for r in rnd_rows if float(row["student_accuracy"]) > float(r["student_accuracy"]))),
                "student_auc": int(sum(1 for r in rnd_rows if float(row["student_auc"]) > float(r["student_auc"]))),
                "student_brier_lower_is_better": int(
                    sum(1 for r in rnd_rows if float(row["student_brier"]) < float(r["student_brier"]))
                ),
            },
        }

    return checks


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare oracle-distilled stop-vs-act run summaries with control gates")
    p.add_argument("--summaries", nargs="+", required=True, help="One or more oracle_distilled_student_summary.json paths")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--anchor-summary", default="", help="Optional current-default anchor summary for reference metadata")
    p.add_argument("--coverage-match-tol", type=float, default=0.01)
    p.add_argument("--act-rate-match-tol", type=float, default=0.02)
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

    rows = [_flatten(_load_json(Path(path)), path) for path in args.summaries]
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

    pairwise_controls = _pairwise_control_report(rows_sorted, args.coverage_match_tol, args.act_rate_match_tol)
    repeated_random_aggregate = {
        role: {
            "num_random_draws": int(dict(detail).get("num_random_draws", 0)),
            "random_draw_stats": dict(detail).get("random_draw_stats", {}),
            "selective_minus_random_mean": dict(detail).get("selective_minus_random_mean", {}),
            "wins_vs_random_draws": dict(detail).get("wins_vs_random_draws", {}),
        }
        for role, detail in pairwise_controls.items()
        if dict(detail).get("status") == "ok"
    }
    selective_roles_to_check = [
        role for role in [ROLE_ACCEPTED_ONLY, ROLE_ACCEPTED_PLUS_BORDERLINE] if role in required_roles
    ]
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

    readiness = {
        "required_roles_present": len(missing_roles) == 0,
        "missing_roles": missing_roles,
        "all_runs_have_required_slices": all(not v["missing_slice_keys"] for v in slice_coverage.values()),
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
            "min_random_draws_per_regime": int(args.min_random_draws_per_regime),
            "naive_filtered_vs_unfiltered_allowed": False,
        },
        "readiness_checks": readiness,
        "repeated_random_aggregate": repeated_random_aggregate,
        "slice_coverage": slice_coverage,
        "anchor_summary_path": args.anchor_summary,
        "non_claim_warning": "Any run with non_claim_mode=true is diagnostic only and not evidence of real oracle-distilled gains.",
    }

    (out_dir / "oracle_distilled_student_comparison_summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    md_lines = [
        "# Oracle-distilled stop-vs-act comparison (matched-control scaffold)",
        "",
        f"- Runs compared: {len(rows_sorted)}",
        f"- CSV: `{csv_path}`",
        "",
        "| run_name | run_role | retained_coverage | pred_act_rate | student_acc | student_auc | non_claim_mode |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows_sorted:
        md_lines.append(
            f"| {row['run_name']} | {row['run_role']} | {row['retained_coverage_train_pool']:.4f} | "
            f"{row['predicted_act_rate']:.4f} | {row['student_accuracy']:.4f} | {row['student_auc']:.4f} | {row['non_claim_mode']} |"
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
        "## Repeated-random aggregate view",
    ]
    for role, detail in repeated_random_aggregate.items():
        md_lines.append(f"- {role}: `{json.dumps(detail, sort_keys=True)}`")

    md_lines += [
        "",
        "## Interpretation guardrails",
        "- Naive filtered-vs-unfiltered claims are disallowed in this protocol.",
        "- Future oracle claims require real validated pilot labels and non-claim mode off.",
        "- Matched-coverage random controls and rate/slice checks are mandatory gates.",
    ]
    (out_dir / "oracle_distilled_student_comparison.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
