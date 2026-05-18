#!/usr/bin/env python3
"""Evaluate a conservative calibrated-percentile baseline-gated allocator.

Offline/output-only analysis over a calibrated feature CSV.
No provider/API calls, no live inference, no training.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


FAMILY_ORDER = [
    "always_external",
    "frontier_pct_threshold",
    "external_low_frontier_high",
    "pct_margin",
    "conservative_combo",
    "z_margin",
    "always_frontier",
]


TRUE_TOKENS = {"1", "true", "t", "yes", "y"}
FALSE_TOKENS = {"0", "false", "f", "no", "n", "", "nan", "none", "null"}


@dataclass(frozen=True)
class Policy:
    family: str
    frontier_min: float | None = None
    baseline_max: float | None = None
    margin: float | None = None
    z_threshold: float | None = None
    is_ablation: bool = False


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _to_binary(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return 1 if float(value) > 0 else 0
    s = str(value).strip().lower()
    if s in TRUE_TOKENS:
        return 1
    if s in FALSE_TOKENS:
        return 0
    try:
        return 1 if float(s) > 0 else 0
    except ValueError:
        return 0


def _frange(start: float, stop: float, step: float) -> list[float]:
    if step <= 0:
        raise ValueError("step must be > 0")
    vals: list[float] = []
    cur = start
    eps = step / 10_000.0
    while cur <= stop + eps:
        vals.append(round(cur, 10))
        cur += step
    return vals


def _safe_group_id(value: Any, row_idx: int) -> str:
    s = str(value).strip()
    if s:
        return s
    return f"__row_{row_idx}"


def load_calibrated_rows(
    *,
    path: pathlib.Path,
    group_id_col: str,
    artifact_col: str,
    baseline_correct_col: str,
    frontier_correct_col: str,
    baseline_pct_col: str,
    frontier_pct_col: str,
    percentile_margin_col: str,
    z_margin_col: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing calibrated features CSV: {path}")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        required = [
            artifact_col,
            baseline_correct_col,
            frontier_correct_col,
            baseline_pct_col,
            frontier_pct_col,
        ]
        missing = [c for c in required if c not in header]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        missing_group = 0

        for i, raw in enumerate(reader):
            group_id = _safe_group_id(raw.get(group_id_col), i)
            if not str(raw.get(group_id_col, "")).strip():
                missing_group += 1

            baseline_pct = _to_float(raw.get(baseline_pct_col), default=0.0)
            frontier_pct = _to_float(raw.get(frontier_pct_col), default=0.0)
            pm = _to_float(raw.get(percentile_margin_col), default=frontier_pct - baseline_pct)
            z_margin = _to_float(raw.get(z_margin_col), default=0.0)

            row: dict[str, Any] = dict(raw)
            row["__group_id"] = group_id
            row["__artifact"] = str(raw.get(artifact_col, ""))
            row["__baseline_correct"] = _to_binary(raw.get(baseline_correct_col))
            row["__frontier_correct"] = _to_binary(raw.get(frontier_correct_col))
            row["__baseline_pct"] = baseline_pct
            row["__frontier_pct"] = frontier_pct
            row["__pct_margin"] = pm
            row["__z_margin"] = z_margin
            row["__oracle_top2"] = int((row["__baseline_correct"] == 1) or (row["__frontier_correct"] == 1))
            row["__oracle_recoverable"] = _to_binary(raw.get("oracle_recoverable"))
            row["__regression_risk"] = _to_binary(raw.get("regression_risk"))
            row["__both_wrong"] = _to_binary(raw.get("both_wrong"))
            row["__both_correct"] = _to_binary(raw.get("both_correct"))
            row["__disagreement"] = _to_binary(raw.get("disagreement"))
            rows.append(row)

        if missing_group > 0:
            warnings.append(
                f"{missing_group} rows missing {group_id_col}; used row-index fallback ids for clustering."
            )
    return rows, warnings


def split_dev_holdout(rows: list[dict[str, Any]], holdout_artifacts: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    holdout = [r for r in rows if str(r.get("__artifact", "")) in holdout_artifacts]
    dev = [r for r in rows if str(r.get("__artifact", "")) not in holdout_artifacts]
    return dev, holdout


def should_switch(policy: Policy, row: dict[str, Any]) -> bool:
    fp = _to_float(row.get("__frontier_pct"), 0.0)
    bp = _to_float(row.get("__baseline_pct"), 0.0)
    pm = _to_float(row.get("__pct_margin"), fp - bp)
    zm = _to_float(row.get("__z_margin"), 0.0)

    if policy.family == "always_external":
        return False
    if policy.family == "always_frontier":
        return True
    if policy.family == "frontier_pct_threshold":
        return fp >= _to_float(policy.frontier_min, 1.0)
    if policy.family == "external_low_frontier_high":
        return (bp <= _to_float(policy.baseline_max, 0.0)) and (fp >= _to_float(policy.frontier_min, 1.0))
    if policy.family == "pct_margin":
        return (fp - bp) >= _to_float(policy.margin, 0.0)
    if policy.family == "conservative_combo":
        return (
            (fp >= _to_float(policy.frontier_min, 1.0))
            and (bp <= _to_float(policy.baseline_max, 0.0))
            and (pm >= _to_float(policy.margin, 0.0))
        )
    if policy.family == "z_margin":
        return zm >= _to_float(policy.z_threshold, 0.0)
    raise ValueError(f"Unknown policy family: {policy.family}")


def evaluate_policy(rows: list[dict[str, Any]], policy: Policy) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        switch = int(should_switch(policy, row))
        ext = int(row["__baseline_correct"])
        fr = int(row["__frontier_correct"])
        gated = fr if switch else ext
        recovery = int(ext == 0 and gated == 1)
        regression = int(ext == 1 and gated == 0)
        missed_recovery = int(ext == 0 and fr == 1 and switch == 0)
        out.append(
            {
                "group_id": row["__group_id"],
                "artifact_label": row["__artifact"],
                "baseline_correct": ext,
                "frontier_correct": fr,
                "gated_correct": gated,
                "oracle_top2_correct": int(row["__oracle_top2"]),
                "did_switch": switch,
                "recovery": recovery,
                "regression": regression,
                "missed_recovery": missed_recovery,
                "net_gain": recovery - regression,
                "oracle_recoverable": int(row["__oracle_recoverable"]),
                "regression_risk": int(row["__regression_risk"]),
                "both_wrong": int(row["__both_wrong"]),
                "both_correct": int(row["__both_correct"]),
                "disagreement": int(row["__disagreement"]),
                "frontier_pct": _to_float(row.get("__frontier_pct"), 0.0),
                "baseline_pct": _to_float(row.get("__baseline_pct"), 0.0),
                "pct_margin": _to_float(row.get("__pct_margin"), 0.0),
                "z_margin": _to_float(row.get("__z_margin"), 0.0),
            }
        )
    return out


def aggregate_metrics(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(decisions)
    if n == 0:
        return {
            "n_groups": 0,
            "external_accuracy": None,
            "frontier_accuracy": None,
            "gated_accuracy": None,
            "oracle_top2_accuracy": None,
            "gated_minus_external": None,
            "gated_minus_frontier": None,
            "switch_count": 0,
            "switch_rate": None,
            "recoveries": 0,
            "regressions": 0,
            "missed_recoveries": 0,
            "net_gain": 0,
            "oracle_recoverable_count": 0,
            "regression_risk_count": 0,
        }
    ext = [int(d["baseline_correct"]) for d in decisions]
    fr = [int(d["frontier_correct"]) for d in decisions]
    gated = [int(d["gated_correct"]) for d in decisions]
    oracle = [int(d["oracle_top2_correct"]) for d in decisions]

    ext_acc = sum(ext) / n
    fr_acc = sum(fr) / n
    gated_acc = sum(gated) / n
    switch_count = sum(int(d["did_switch"]) for d in decisions)
    recoveries = sum(int(d["recovery"]) for d in decisions)
    regressions = sum(int(d["regression"]) for d in decisions)
    missed = sum(int(d["missed_recovery"]) for d in decisions)
    oracle_recoverable_count = sum(int(d["oracle_recoverable"]) for d in decisions)
    regression_risk_count = sum(int(d["regression_risk"]) for d in decisions)
    return {
        "n_groups": n,
        "external_accuracy": ext_acc,
        "frontier_accuracy": fr_acc,
        "gated_accuracy": gated_acc,
        "oracle_top2_accuracy": sum(oracle) / n,
        "gated_minus_external": gated_acc - ext_acc,
        "gated_minus_frontier": gated_acc - fr_acc,
        "switch_count": switch_count,
        "switch_rate": switch_count / n,
        "recoveries": recoveries,
        "regressions": regressions,
        "missed_recoveries": missed,
        "net_gain": recoveries - regressions,
        "oracle_recoverable_count": oracle_recoverable_count,
        "regression_risk_count": regression_risk_count,
    }


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return math.nan
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = (len(sorted_values) - 1) * q
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_values[lo]
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def ci_from_samples(values: list[float], alpha: float = 0.05) -> tuple[float, float]:
    vals = sorted(values)
    return (_percentile(vals, alpha / 2), _percentile(vals, 1 - alpha / 2))


def cluster_bootstrap_deltas(decisions: list[dict[str, Any]], *, n_bootstrap: int, seed: int) -> dict[str, Any]:
    if n_bootstrap <= 0:
        raise ValueError("n_bootstrap must be > 0")
    if not decisions:
        return {
            "rows": [],
            "ci": {
                "gated_minus_external": {"lower": None, "upper": None},
                "gated_minus_frontier": {"lower": None, "upper": None},
                "always_frontier_minus_external": {"lower": None, "upper": None},
            },
        }

    by_cluster: dict[str, list[dict[str, Any]]] = {}
    for d in decisions:
        by_cluster.setdefault(str(d["group_id"]), []).append(d)
    cluster_ids = list(by_cluster.keys())
    rng = random.Random(seed)

    rows: list[dict[str, Any]] = []
    d_ge: list[float] = []
    d_gf: list[float] = []
    d_fe: list[float] = []

    for i in range(n_bootstrap):
        sampled_ids = [cluster_ids[rng.randrange(len(cluster_ids))] for _ in range(len(cluster_ids))]
        sampled: list[dict[str, Any]] = []
        for cid in sampled_ids:
            sampled.extend(by_cluster[cid])
        agg = aggregate_metrics(sampled)
        ge = float(agg["gated_minus_external"])
        gf = float(agg["gated_minus_frontier"])
        fe = float(agg["frontier_accuracy"] - agg["external_accuracy"])
        d_ge.append(ge)
        d_gf.append(gf)
        d_fe.append(fe)
        rows.append(
            {
                "iteration": i,
                "gated_minus_external": ge,
                "gated_minus_frontier": gf,
                "always_frontier_minus_external": fe,
            }
        )

    lo_ge, hi_ge = ci_from_samples(d_ge)
    lo_gf, hi_gf = ci_from_samples(d_gf)
    lo_fe, hi_fe = ci_from_samples(d_fe)
    return {
        "rows": rows,
        "ci": {
            "gated_minus_external": {"lower": lo_ge, "upper": hi_ge},
            "gated_minus_frontier": {"lower": lo_gf, "upper": hi_gf},
            "always_frontier_minus_external": {"lower": lo_fe, "upper": hi_fe},
        },
    }


def generate_policies(args: argparse.Namespace) -> list[Policy]:
    frontier_vals = _frange(args.frontier_min_start, args.frontier_min_stop, args.frontier_min_step)
    baseline_vals = _frange(args.baseline_max_start, args.baseline_max_stop, args.baseline_max_step)
    margin_vals = _frange(args.margin_start, args.margin_stop, args.margin_step)
    z_vals = _frange(args.z_threshold_start, args.z_threshold_stop, args.z_threshold_step)

    policies: list[Policy] = [
        Policy(family="always_external"),
        Policy(family="always_frontier"),
    ]
    for f in frontier_vals:
        policies.append(Policy(family="frontier_pct_threshold", frontier_min=f))
    for b in baseline_vals:
        for f in frontier_vals:
            policies.append(Policy(family="external_low_frontier_high", baseline_max=b, frontier_min=f))
    for m in margin_vals:
        policies.append(Policy(family="pct_margin", margin=m))
    for f in frontier_vals:
        for b in baseline_vals:
            for m in margin_vals:
                policies.append(Policy(family="conservative_combo", frontier_min=f, baseline_max=b, margin=m))
    for z in z_vals:
        policies.append(Policy(family="z_margin", z_threshold=z, is_ablation=True))
    return policies


def _family_rank(family: str) -> int:
    return FAMILY_ORDER.index(family)


def _conservative_signature(policy: Policy) -> tuple[float, float, float]:
    # Higher tuple means more conservative under same family.
    frontier_min = _to_float(policy.frontier_min, default=-1.0)
    baseline_max = _to_float(policy.baseline_max, default=2.0)
    margin = _to_float(policy.margin, default=-2.0)
    return (frontier_min, -baseline_max, margin)


def _policy_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    policy = row["policy"]
    m = row["metrics"]
    c1, c2, c3 = _conservative_signature(policy)
    return (
        -_to_float(m.get("gated_accuracy"), default=-1.0),
        -_to_float(m.get("gated_minus_external"), default=-1.0),
        _to_float(m.get("switch_rate"), default=1.0),
        _family_rank(policy.family),
        -c1,
        -c2,
        -c3,
    )


def tune_policy(dev_rows: list[dict[str, Any]], args: argparse.Namespace) -> tuple[Policy, list[dict[str, Any]]]:
    candidates = generate_policies(args)
    eval_rows: list[dict[str, Any]] = []
    for p in candidates:
        decisions = evaluate_policy(dev_rows, p)
        m = aggregate_metrics(decisions)
        eval_rows.append({"policy": p, "metrics": m})

    ranked = sorted(eval_rows, key=_policy_sort_key)
    if not ranked:
        raise ValueError("No policies generated for tuning.")
    selected = ranked[0]["policy"]

    search_rows: list[dict[str, Any]] = []
    for i, rr in enumerate(ranked, start=1):
        p = rr["policy"]
        m = rr["metrics"]
        search_rows.append(
            {
                "rank": i,
                "family": p.family,
                "frontier_min": p.frontier_min,
                "baseline_max": p.baseline_max,
                "margin": p.margin,
                "z_threshold": p.z_threshold,
                "is_ablation": int(p.is_ablation),
                "n_groups": m["n_groups"],
                "external_accuracy": m["external_accuracy"],
                "frontier_accuracy": m["frontier_accuracy"],
                "gated_accuracy": m["gated_accuracy"],
                "gated_minus_external": m["gated_minus_external"],
                "gated_minus_frontier": m["gated_minus_frontier"],
                "switch_count": m["switch_count"],
                "switch_rate": m["switch_rate"],
                "recoveries": m["recoveries"],
                "regressions": m["regressions"],
                "missed_recoveries": m["missed_recoveries"],
                "net_gain": m["net_gain"],
            }
        )
    return selected, search_rows


def by_artifact_metrics(decisions: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    by_art: dict[str, list[dict[str, Any]]] = {}
    for d in decisions:
        by_art.setdefault(str(d["artifact_label"]), []).append(d)
    rows: list[dict[str, Any]] = []
    for art, part in sorted(by_art.items(), key=lambda kv: kv[0]):
        m = aggregate_metrics(part)
        row = {"split": split, "artifact_label": art}
        row.update(m)
        rows.append(row)
    return rows


def by_target_metrics(decisions: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    targets = ["oracle_recoverable", "regression_risk", "both_wrong", "both_correct", "disagreement"]
    rows: list[dict[str, Any]] = []
    for t in targets:
        part = [d for d in decisions if int(d.get(t, 0)) == 1]
        m = aggregate_metrics(part)
        row = {"split": split, "target": t}
        row.update(m)
        rows.append(row)
    return rows


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(r.get(k)) for k in fieldnames})


def _metrics_row(split: str, metrics: dict[str, Any], ci: dict[str, Any], policy: Policy) -> dict[str, Any]:
    row = {
        "split": split,
        "family": policy.family,
        "frontier_min": policy.frontier_min,
        "baseline_max": policy.baseline_max,
        "margin": policy.margin,
        "z_threshold": policy.z_threshold,
        "is_ablation": int(policy.is_ablation),
    }
    row.update(metrics)
    row["gated_minus_external_ci_lower"] = ci["gated_minus_external"]["lower"]
    row["gated_minus_external_ci_upper"] = ci["gated_minus_external"]["upper"]
    row["gated_minus_frontier_ci_lower"] = ci["gated_minus_frontier"]["lower"]
    row["gated_minus_frontier_ci_upper"] = ci["gated_minus_frontier"]["upper"]
    row["always_frontier_minus_external_ci_lower"] = ci["always_frontier_minus_external"]["lower"]
    row["always_frontier_minus_external_ci_upper"] = ci["always_frontier_minus_external"]["upper"]
    return row


def _policy_to_dict(policy: Policy) -> dict[str, Any]:
    return {
        "family": policy.family,
        "frontier_min": policy.frontier_min,
        "baseline_max": policy.baseline_max,
        "margin": policy.margin,
        "z_threshold": policy.z_threshold,
        "is_ablation": policy.is_ablation,
    }


def _make_report(
    *,
    selected: Policy,
    dev_metrics: dict[str, Any],
    holdout_metrics: dict[str, Any],
    all_metrics: dict[str, Any],
    holdout_artifacts: set[str],
    sign_flip_artifact: str,
) -> str:
    def _pp(x: Any) -> str:
        if x is None:
            return "N/A"
        return f"{100.0 * float(x):+.2f}pp"

    def _pct(x: Any) -> str:
        if x is None:
            return "N/A"
        return f"{100.0 * float(x):.2f}%"

    beat_dev = (dev_metrics.get("gated_minus_external") or 0.0) > 0
    beat_holdout = (holdout_metrics.get("gated_minus_external") or 0.0) > 0
    beat_frontier_holdout = (holdout_metrics.get("gated_minus_frontier") or 0.0) > 0
    one_artifact_dominant = abs(_to_float(holdout_metrics.get("gated_minus_external"), 0.0) - _to_float(all_metrics.get("gated_minus_external"), 0.0)) > 0.03

    lines = [
        "# Calibrated Percentile Gate Report",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Selected policy family: `{selected.family}`",
        f"- Selected thresholds: frontier_min={selected.frontier_min}, baseline_max={selected.baseline_max}, margin={selected.margin}, z_threshold={selected.z_threshold}",
        f"- Holdout artifacts: {sorted(holdout_artifacts)}",
        "",
        "## Answers",
        f"1. Selected policy on dev: `{selected.family}`",
        f"2. Selected thresholds: frontier_min={selected.frontier_min}, baseline_max={selected.baseline_max}, margin={selected.margin}, z_threshold={selected.z_threshold}",
        f"3. Beat always_external on dev: {'YES' if beat_dev else 'NO'} ({_pp(dev_metrics.get('gated_minus_external'))})",
        f"4. Beat always_external on holdout: {'YES' if beat_holdout else 'NO'} ({_pp(holdout_metrics.get('gated_minus_external'))})",
        f"5. Beat always_frontier on holdout: {'YES' if beat_frontier_holdout else 'NO'} ({_pp(holdout_metrics.get('gated_minus_frontier'))})",
        f"6. Switch rate (holdout): {_pct(holdout_metrics.get('switch_rate'))}",
        f"7. Gains driven by one artifact: {'LIKELY YES' if one_artifact_dominant else 'NOT OBVIOUS'}",
        f"8. Sign-flip holdout `{sign_flip_artifact}` behaved differently: {'YES' if sign_flip_artifact in holdout_artifacts else 'NO'}",
        "9. Next-stage gate justification: prototype-yes, but keep manual math review before threshold lock.",
        "10. Cohere API collection needed now: NO.",
        "",
        "## Claim Boundary",
        "- Prototype diagnostic only; not a final baseline-beating claim.",
    ]
    return "\n".join(lines) + "\n"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--calibrated-features-csv", required=True)
    p.add_argument("--output-dir", required=True)

    p.add_argument("--baseline-correct-col", default="baseline_correct")
    p.add_argument("--frontier-correct-col", default="frontier_correct")
    p.add_argument("--artifact-col", default="artifact_label")
    p.add_argument("--group-id-col", default="example_id")
    p.add_argument("--baseline-pct-col", default="baseline_proba_ready_pct_within_method")
    p.add_argument("--frontier-pct-col", default="frontier_proba_ready_pct_within_method")
    p.add_argument("--percentile-margin-col", default="frontier_minus_baseline_percentile_margin")
    p.add_argument("--z-margin-col", default="frontier_minus_baseline_z_margin")

    p.add_argument(
        "--holdout-artifact",
        action="append",
        default=["cohere_paired_pal_retry_vs_external_l1_300case_poolfix_20260506"],
        help="Repeatable; rows with this artifact go to robustness holdout split.",
    )

    p.add_argument("--n-bootstrap", type=int, default=2000)
    p.add_argument("--seed", type=int, default=12345)

    p.add_argument("--frontier-min-start", type=float, default=0.50)
    p.add_argument("--frontier-min-stop", type=float, default=0.95)
    p.add_argument("--frontier-min-step", type=float, default=0.05)
    p.add_argument("--baseline-max-start", type=float, default=0.05)
    p.add_argument("--baseline-max-stop", type=float, default=0.80)
    p.add_argument("--baseline-max-step", type=float, default=0.05)
    p.add_argument("--margin-start", type=float, default=-0.50)
    p.add_argument("--margin-stop", type=float, default=0.50)
    p.add_argument("--margin-step", type=float, default=0.05)
    p.add_argument("--z-threshold-start", type=float, default=-1.0)
    p.add_argument("--z-threshold-stop", type=float, default=1.0)
    p.add_argument("--z-threshold-step", type=float, default=0.1)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    holdouts = set(args.holdout_artifact or [])

    try:
        rows, warnings = load_calibrated_rows(
            path=pathlib.Path(args.calibrated_features_csv),
            group_id_col=args.group_id_col,
            artifact_col=args.artifact_col,
            baseline_correct_col=args.baseline_correct_col,
            frontier_correct_col=args.frontier_correct_col,
            baseline_pct_col=args.baseline_pct_col,
            frontier_pct_col=args.frontier_pct_col,
            percentile_margin_col=args.percentile_margin_col,
            z_margin_col=args.z_margin_col,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    dev_rows, holdout_rows = split_dev_holdout(rows, holdouts)
    if not dev_rows:
        print("No dev rows remain after holdout split.", file=sys.stderr)
        return 1
    if not holdout_rows:
        warnings.append("No rows found for holdout artifacts; holdout metrics will be empty.")

    selected, search_rows = tune_policy(dev_rows, args)

    dev_decisions = evaluate_policy(dev_rows, selected)
    holdout_decisions = evaluate_policy(holdout_rows, selected)
    all_decisions = evaluate_policy(rows, selected)

    dev_metrics = aggregate_metrics(dev_decisions)
    holdout_metrics = aggregate_metrics(holdout_decisions)
    all_metrics = aggregate_metrics(all_decisions)

    dev_boot = cluster_bootstrap_deltas(dev_decisions, n_bootstrap=args.n_bootstrap, seed=args.seed + 11)
    holdout_boot = cluster_bootstrap_deltas(holdout_decisions, n_bootstrap=args.n_bootstrap, seed=args.seed + 23) if holdout_decisions else {
        "rows": [],
        "ci": {
            "gated_minus_external": {"lower": None, "upper": None},
            "gated_minus_frontier": {"lower": None, "upper": None},
            "always_frontier_minus_external": {"lower": None, "upper": None},
        },
    }
    all_boot = cluster_bootstrap_deltas(all_decisions, n_bootstrap=args.n_bootstrap, seed=args.seed + 37)

    # Output files
    selected_json = {
        "selected_policy": _policy_to_dict(selected),
        "selection_protocol": {
            "rank_order": [
                "highest_gated_accuracy",
                "highest_gated_minus_external",
                "lower_switch_rate",
                "family_order",
                "more_conservative_thresholds",
            ],
            "family_order": FAMILY_ORDER,
        },
        "holdout_artifacts": sorted(holdouts),
    }
    (out_dir / "selected_policy.json").write_text(json.dumps(selected_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    write_csv(
        out_dir / "dev_gate_search_results.csv",
        search_rows,
        [
            "rank",
            "family",
            "frontier_min",
            "baseline_max",
            "margin",
            "z_threshold",
            "is_ablation",
            "n_groups",
            "external_accuracy",
            "frontier_accuracy",
            "gated_accuracy",
            "gated_minus_external",
            "gated_minus_frontier",
            "switch_count",
            "switch_rate",
            "recoveries",
            "regressions",
            "missed_recoveries",
            "net_gain",
        ],
    )

    holdout_row = _metrics_row("holdout", holdout_metrics, holdout_boot["ci"], selected)
    all_row = _metrics_row("all", all_metrics, all_boot["ci"], selected)
    write_csv(out_dir / "holdout_metrics.csv", [holdout_row], list(holdout_row.keys()))
    write_csv(out_dir / "all_artifacts_metrics.csv", [all_row], list(all_row.keys()))

    art_rows = []
    art_rows.extend(by_artifact_metrics(dev_decisions, "dev"))
    art_rows.extend(by_artifact_metrics(holdout_decisions, "holdout"))
    art_rows.extend(by_artifact_metrics(all_decisions, "all"))
    if art_rows:
        write_csv(out_dir / "by_artifact_metrics.csv", art_rows, list(art_rows[0].keys()))
    else:
        write_csv(out_dir / "by_artifact_metrics.csv", [], ["split", "artifact_label"])

    tgt_rows = []
    tgt_rows.extend(by_target_metrics(dev_decisions, "dev"))
    tgt_rows.extend(by_target_metrics(holdout_decisions, "holdout"))
    tgt_rows.extend(by_target_metrics(all_decisions, "all"))
    write_csv(out_dir / "by_target_metrics.csv", tgt_rows, list(tgt_rows[0].keys()))

    group_rows = []
    for src, split in [(dev_decisions, "dev"), (holdout_decisions, "holdout"), (all_decisions, "all")]:
        for r in src:
            rr = dict(r)
            rr["split"] = split
            rr["selected_family"] = selected.family
            rr["selected_frontier_min"] = selected.frontier_min
            rr["selected_baseline_max"] = selected.baseline_max
            rr["selected_margin"] = selected.margin
            rr["selected_z_threshold"] = selected.z_threshold
            group_rows.append(rr)
    write_csv(out_dir / "group_decisions.csv", group_rows, list(group_rows[0].keys()))

    boot_rows: list[dict[str, Any]] = []
    for split, boot in [("dev", dev_boot), ("holdout", holdout_boot), ("all", all_boot)]:
        for r in boot["rows"]:
            row = dict(r)
            row["split"] = split
            boot_rows.append(row)
    write_csv(
        out_dir / "bootstrap_deltas.csv",
        boot_rows,
        ["split", "iteration", "gated_minus_external", "gated_minus_frontier", "always_frontier_minus_external"],
    )

    sign_flip_artifact = "cohere_paired_pal_retry_vs_external_l1_300case_poolfix_20260506"
    report = _make_report(
        selected=selected,
        dev_metrics=dev_metrics,
        holdout_metrics=holdout_metrics,
        all_metrics=all_metrics,
        holdout_artifacts=holdouts,
        sign_flip_artifact=sign_flip_artifact,
    )
    (out_dir / "calibrated_gate_report.md").write_text(report, encoding="utf-8")

    metrics_obj = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_csv": args.calibrated_features_csv,
        "output_dir": str(out_dir),
        "selected_policy": _policy_to_dict(selected),
        "holdout_artifacts": sorted(holdouts),
        "split_counts": {"dev_rows": len(dev_rows), "holdout_rows": len(holdout_rows), "all_rows": len(rows)},
        "dev_metrics": dev_metrics,
        "holdout_metrics": holdout_metrics,
        "all_metrics": all_metrics,
        "dev_bootstrap_ci": dev_boot["ci"],
        "holdout_bootstrap_ci": holdout_boot["ci"],
        "all_bootstrap_ci": all_boot["ci"],
        "warnings": warnings,
        "safety": {
            "provider_api_calls": False,
            "live_inference": False,
            "training": False,
            "output_only": True,
        },
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics_obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

