"""Offline baseline-gated hybrid allocator comparison.

This script evaluates a minimal Stage-2 hybrid allocator that defaults to a
strong external baseline method and optionally switches to a frontier method
using a frozen gate rule.

No API/provider calls. Offline artifact analysis only.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


GATE_FAMILY_ORDER = [
    "always_external",
    "always_direct",
    "verifier_margin",
    "direct_threshold",
    "external_low_confidence",
    "margin_and_external_low",
]


@dataclass(frozen=True)
class GatePolicy:
    family: str
    margin: float | None = None
    threshold: float | None = None
    external_threshold: float | None = None


# ---------------------------------------------------------------------------
# Parsing / loading
# ---------------------------------------------------------------------------


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
    if s in {"1", "true", "t", "yes", "y"}:
        return 1
    if s in {"0", "false", "f", "no", "n", ""}:
        return 0
    try:
        return 1 if float(s) > 0 else 0
    except ValueError:
        return 0


def load_scored_candidates(
    path: pathlib.Path,
    *,
    score_field: str,
    correct_field: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            meta = raw.get("metadata", {}) or {}

            row: dict[str, Any] = {}
            row[score_field] = _to_float(raw.get(score_field), default=0.0)
            for k, v in meta.items():
                row[k] = v

            # Keep a normalized EM field value at top-level for easier downstream logic.
            row[correct_field] = _to_binary(row.get(correct_field, raw.get(correct_field)))
            row["_raw_score"] = raw.get(score_field)
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Group + top-candidate selection
# ---------------------------------------------------------------------------


def build_groups(rows: list[dict[str, Any]], group_id_field: str, budget_field: str) -> dict[tuple[Any, Any], list[dict[str, Any]]]:
    groups: dict[tuple[Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row.get(group_id_field), row.get(budget_field))
        groups[key].append(row)
    return dict(groups)


def select_verifier_top_candidate(cands: list[dict[str, Any]], score_field: str, seed_field: str) -> dict[str, Any]:
    if not cands:
        raise ValueError("Cannot select top candidate from empty list")

    def _key(c: dict[str, Any]) -> tuple[float, str]:
        score = _to_float(c.get(score_field), default=0.0)
        seed = c.get(seed_field)
        # max by score; deterministic tiebreak by seed string ascending
        return (score, str(seed) if seed is not None else "")

    # Use max(score), and for equal score prefer lexicographically later seed in max;
    # then enforce deterministic ascending seed tiebreak by doing two-step.
    max_score = max(_to_float(c.get(score_field), default=0.0) for c in cands)
    tied = [c for c in cands if _to_float(c.get(score_field), default=0.0) == max_score]
    tied_sorted = sorted(tied, key=lambda c: str(c.get(seed_field) if c.get(seed_field) is not None else ""))
    return tied_sorted[0]


def random_expected_accuracy(cands: list[dict[str, Any]], correct_field: str) -> float | None:
    if not cands:
        return None
    vals = [_to_binary(c.get(correct_field)) for c in cands]
    if not vals:
        return None
    return sum(vals) / len(vals)


# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------


def gate_should_switch(
    policy: GatePolicy,
    *,
    external_score: float,
    direct_score: float,
) -> bool:
    margin = _to_float(policy.margin, default=0.0)
    threshold = _to_float(policy.threshold, default=0.0)
    external_threshold = _to_float(policy.external_threshold, default=0.0)

    if policy.family == "always_external":
        return False
    if policy.family == "always_direct":
        return True
    if policy.family == "verifier_margin":
        return (direct_score - external_score) >= margin
    if policy.family == "direct_threshold":
        return direct_score >= threshold
    if policy.family == "external_low_confidence":
        return external_score <= threshold
    if policy.family == "margin_and_external_low":
        return ((direct_score - external_score) >= margin) and (external_score <= external_threshold)

    raise ValueError(f"Unknown gate family: {policy.family}")


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_gate_policy(
    rows: list[dict[str, Any]],
    *,
    baseline_method: str,
    frontier_method: str,
    score_field: str,
    correct_field: str,
    method_field: str,
    budget_field: str,
    seed_field: str,
    group_id_field: str,
    policy: GatePolicy,
) -> dict[str, Any]:
    groups = build_groups(rows, group_id_field=group_id_field, budget_field=budget_field)

    decisions: list[dict[str, Any]] = []
    skipped_missing_method: list[dict[str, Any]] = []

    for (group_id, budget), group_rows in groups.items():
        by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in group_rows:
            by_method[str(row.get(method_field, ""))].append(row)

        external_cands = by_method.get(baseline_method, [])
        direct_cands = by_method.get(frontier_method, [])

        if not external_cands or not direct_cands:
            skipped_missing_method.append(
                {
                    "group_id": group_id,
                    "budget": budget,
                    "missing_external": int(not external_cands),
                    "missing_direct": int(not direct_cands),
                }
            )
            continue

        external_top = select_verifier_top_candidate(external_cands, score_field=score_field, seed_field=seed_field)
        direct_top = select_verifier_top_candidate(direct_cands, score_field=score_field, seed_field=seed_field)

        external_score = _to_float(external_top.get(score_field), default=0.0)
        direct_score = _to_float(direct_top.get(score_field), default=0.0)

        external_correct = _to_binary(external_top.get(correct_field))
        direct_correct = _to_binary(direct_top.get(correct_field))

        did_switch = gate_should_switch(
            policy,
            external_score=external_score,
            direct_score=direct_score,
        )
        gated_correct = direct_correct if did_switch else external_correct
        selected_method = frontier_method if did_switch else baseline_method

        recovery = int(external_correct == 0 and gated_correct == 1)
        regression = int(external_correct == 1 and gated_correct == 0)

        decisions.append(
            {
                "group_id": group_id,
                "budget": budget,
                "external_top_score": external_score,
                "direct_top_score": direct_score,
                "score_margin_direct_minus_external": direct_score - external_score,
                "external_top_seed": external_top.get(seed_field),
                "direct_top_seed": direct_top.get(seed_field),
                "external_top_correct": external_correct,
                "direct_top_correct": direct_correct,
                "gated_correct": gated_correct,
                "selected_method": selected_method,
                "did_switch": int(did_switch),
                "random_expected_external": random_expected_accuracy(external_cands, correct_field),
                "random_expected_direct": random_expected_accuracy(direct_cands, correct_field),
                "oracle_top2_correct": int((external_correct == 1) or (direct_correct == 1)),
                "recovery": recovery,
                "regression": regression,
                "net_gain": recovery - regression,
            }
        )

    overall = aggregate_policy_metrics(decisions)

    by_budget: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in decisions:
        by_budget[row["budget"]].append(row)

    by_budget_metrics = {
        str(b): aggregate_policy_metrics(rows_for_budget)
        for b, rows_for_budget in sorted(by_budget.items(), key=lambda kv: str(kv[0]))
    }

    return {
        "decisions": decisions,
        "overall": overall,
        "by_budget": by_budget_metrics,
        "n_total_groups": len(groups),
        "n_skipped_missing_method": len(skipped_missing_method),
        "skipped_missing_method": skipped_missing_method,
    }


# ---------------------------------------------------------------------------
# Metrics + uncertainty
# ---------------------------------------------------------------------------


def aggregate_policy_metrics(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(decisions)
    if n == 0:
        return {
            "n_groups": 0,
            "external_top_accuracy": None,
            "direct_top_accuracy": None,
            "gated_accuracy": None,
            "gated_minus_external": None,
            "gated_minus_direct": None,
            "random_expected_external": None,
            "random_expected_direct": None,
            "oracle_top2_accuracy": None,
            "switch_count": 0,
            "switch_rate": None,
            "recoveries": 0,
            "regressions": 0,
            "net_gain": 0,
        }

    ext = [int(d["external_top_correct"]) for d in decisions]
    direct = [int(d["direct_top_correct"]) for d in decisions]
    gated = [int(d["gated_correct"]) for d in decisions]
    oracle = [int(d["oracle_top2_correct"]) for d in decisions]

    rnd_ext_vals = [d["random_expected_external"] for d in decisions if d["random_expected_external"] is not None]
    rnd_direct_vals = [d["random_expected_direct"] for d in decisions if d["random_expected_direct"] is not None]

    recoveries = sum(int(d["recovery"]) for d in decisions)
    regressions = sum(int(d["regression"]) for d in decisions)
    switch_count = sum(int(d["did_switch"]) for d in decisions)

    ext_acc = sum(ext) / n
    direct_acc = sum(direct) / n
    gated_acc = sum(gated) / n

    return {
        "n_groups": n,
        "external_top_accuracy": ext_acc,
        "direct_top_accuracy": direct_acc,
        "gated_accuracy": gated_acc,
        "gated_minus_external": gated_acc - ext_acc,
        "gated_minus_direct": gated_acc - direct_acc,
        "random_expected_external": (sum(rnd_ext_vals) / len(rnd_ext_vals)) if rnd_ext_vals else None,
        "random_expected_direct": (sum(rnd_direct_vals) / len(rnd_direct_vals)) if rnd_direct_vals else None,
        "oracle_top2_accuracy": sum(oracle) / n,
        "switch_count": switch_count,
        "switch_rate": switch_count / n,
        "recoveries": recoveries,
        "regressions": regressions,
        "net_gain": recoveries - regressions,
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
    sorted_vals = sorted(values)
    return (_percentile(sorted_vals, alpha / 2), _percentile(sorted_vals, 1 - alpha / 2))


def cluster_bootstrap_deltas(
    decisions: list[dict[str, Any]],
    *,
    n_bootstrap: int,
    seed: int,
) -> dict[str, Any]:
    if n_bootstrap <= 0:
        raise ValueError("n_bootstrap must be > 0")
    if not decisions:
        return {
            "rows": [],
            "ci": {
                "gated_minus_external": {"lower": None, "upper": None},
                "gated_minus_direct": {"lower": None, "upper": None},
            },
        }

    cluster_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in decisions:
        cluster_map[str(row["group_id"])].append(row)

    cluster_ids = list(cluster_map.keys())
    rng = random.Random(seed)

    boot_rows: list[dict[str, Any]] = []
    deltas_ext: list[float] = []
    deltas_direct: list[float] = []

    for i in range(n_bootstrap):
        sampled_ids = [cluster_ids[rng.randrange(len(cluster_ids))] for _ in range(len(cluster_ids))]
        sampled_rows: list[dict[str, Any]] = []
        for cid in sampled_ids:
            sampled_rows.extend(cluster_map[cid])

        agg = aggregate_policy_metrics(sampled_rows)
        d_ext = agg["gated_minus_external"]
        d_direct = agg["gated_minus_direct"]
        d_ext_f = float(d_ext) if d_ext is not None else math.nan
        d_direct_f = float(d_direct) if d_direct is not None else math.nan

        deltas_ext.append(d_ext_f)
        deltas_direct.append(d_direct_f)
        boot_rows.append(
            {
                "iteration": i,
                "gated_minus_external": d_ext_f,
                "gated_minus_direct": d_direct_f,
            }
        )

    lo_ext, hi_ext = ci_from_samples(deltas_ext)
    lo_direct, hi_direct = ci_from_samples(deltas_direct)

    return {
        "rows": boot_rows,
        "ci": {
            "gated_minus_external": {"lower": lo_ext, "upper": hi_ext},
            "gated_minus_direct": {"lower": lo_direct, "upper": hi_direct},
        },
    }


# ---------------------------------------------------------------------------
# Gate search / tuning
# ---------------------------------------------------------------------------


def _frange(start: float, stop: float, step: float) -> list[float]:
    if step <= 0:
        raise ValueError("step must be > 0")
    values: list[float] = []
    cur = start
    eps = step / 10_000
    while cur <= stop + eps:
        values.append(round(cur, 10))
        cur += step
    return values


def _candidate_families_from_arg(gate_family: str) -> list[str]:
    if gate_family in {"auto", "all"}:
        return list(GATE_FAMILY_ORDER)
    if gate_family not in GATE_FAMILY_ORDER:
        raise ValueError(f"Unknown gate family: {gate_family}")
    return [gate_family]


def enumerate_gate_candidates(args: argparse.Namespace) -> list[GatePolicy]:
    families = _candidate_families_from_arg(args.gate_family)

    margins = _frange(args.margin_min, args.margin_max, args.margin_step)
    thresholds = _frange(args.threshold_min, args.threshold_max, args.threshold_step)
    ext_thresholds = _frange(
        args.external_threshold_min,
        args.external_threshold_max,
        args.external_threshold_step,
    )

    policies: list[GatePolicy] = []
    for family in families:
        if family == "always_external":
            policies.append(GatePolicy(family=family))
        elif family == "always_direct":
            policies.append(GatePolicy(family=family))
        elif family == "verifier_margin":
            for margin in margins:
                policies.append(GatePolicy(family=family, margin=margin))
        elif family == "direct_threshold":
            for threshold in thresholds:
                policies.append(GatePolicy(family=family, threshold=threshold))
        elif family == "external_low_confidence":
            for threshold in thresholds:
                policies.append(GatePolicy(family=family, threshold=threshold))
        elif family == "margin_and_external_low":
            for margin in margins:
                for ext_t in ext_thresholds:
                    policies.append(
                        GatePolicy(
                            family=family,
                            margin=margin,
                            external_threshold=ext_t,
                        )
                    )

    return policies


def _family_rank(family: str) -> int:
    return GATE_FAMILY_ORDER.index(family)


def _conservative_signature(policy: GatePolicy) -> tuple[float, float, float]:
    # Higher values = more conservative.
    if policy.family == "verifier_margin":
        return (_to_float(policy.margin), 0.0, 0.0)
    if policy.family == "direct_threshold":
        return (_to_float(policy.threshold), 0.0, 0.0)
    if policy.family == "external_low_confidence":
        return (-_to_float(policy.threshold), 0.0, 0.0)
    if policy.family == "margin_and_external_low":
        return (_to_float(policy.margin), -_to_float(policy.external_threshold), 0.0)
    return (0.0, 0.0, 0.0)


def _policy_sort_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    acc = _to_float(candidate.get("dev_gated_accuracy"), default=-1.0)
    switch_count = int(candidate.get("dev_switch_count", 10**9))
    family = str(candidate.get("gate_family"))
    family_rank = _family_rank(family)

    policy = GatePolicy(
        family=family,
        margin=candidate.get("margin"),
        threshold=candidate.get("threshold"),
        external_threshold=candidate.get("external_threshold"),
    )
    c1, c2, c3 = _conservative_signature(policy)

    return (
        -acc,
        switch_count,
        family_rank,
        -c1,
        -c2,
        -c3,
        json.dumps(candidate, sort_keys=True),
    )


def tune_gate_on_dev(
    dev_rows: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
) -> dict[str, Any]:
    candidates = enumerate_gate_candidates(args)
    search_rows: list[dict[str, Any]] = []

    for policy in candidates:
        eval_obj = evaluate_gate_policy(
            dev_rows,
            baseline_method=args.baseline_method,
            frontier_method=args.frontier_method,
            score_field=args.score_field,
            correct_field=args.correct_field,
            method_field=args.method_field,
            budget_field=args.budget_field,
            seed_field=args.seed_field,
            group_id_field=args.group_id_field,
            policy=policy,
        )
        ov = eval_obj["overall"]
        search_rows.append(
            {
                "gate_family": policy.family,
                "margin": policy.margin,
                "threshold": policy.threshold,
                "external_threshold": policy.external_threshold,
                "dev_n_groups": ov["n_groups"],
                "dev_external_top_accuracy": ov["external_top_accuracy"],
                "dev_direct_top_accuracy": ov["direct_top_accuracy"],
                "dev_gated_accuracy": ov["gated_accuracy"],
                "dev_gated_minus_external": ov["gated_minus_external"],
                "dev_gated_minus_direct": ov["gated_minus_direct"],
                "dev_switch_count": ov["switch_count"],
                "dev_switch_rate": ov["switch_rate"],
                "dev_recoveries": ov["recoveries"],
                "dev_regressions": ov["regressions"],
                "dev_net_gain": ov["net_gain"],
            }
        )

    ranked = sorted(search_rows, key=_policy_sort_key)
    best = ranked[0] if ranked else None
    if best is None:
        raise ValueError("No gate candidates available for tuning")

    selected = GatePolicy(
        family=str(best["gate_family"]),
        margin=best.get("margin"),
        threshold=best.get("threshold"),
        external_threshold=best.get("external_threshold"),
    )

    return {
        "selected_policy": selected,
        "search_rows": ranked,
    }


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(row.get(k)) for k in fieldnames})


def write_outputs(
    *,
    out_dir: pathlib.Path,
    metrics_obj: dict[str, Any],
    overall_rows: list[dict[str, Any]],
    by_budget_rows: list[dict[str, Any]],
    decision_rows: list[dict[str, Any]],
    bootstrap_rows: list[dict[str, Any]],
    gate_search_rows: list[dict[str, Any]] | None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "metrics.json", "w") as f:
        json.dump(metrics_obj, f, indent=2, default=str)

    write_csv(
        out_dir / "policy_overall.csv",
        overall_rows,
        [
            "split",
            "n_groups",
            "external_top_accuracy",
            "direct_top_accuracy",
            "gated_accuracy",
            "gated_minus_external",
            "gated_minus_direct",
            "random_expected_external",
            "random_expected_direct",
            "oracle_top2_accuracy",
            "switch_count",
            "switch_rate",
            "recoveries",
            "regressions",
            "net_gain",
            "gated_minus_external_ci_lower",
            "gated_minus_external_ci_upper",
            "gated_minus_direct_ci_lower",
            "gated_minus_direct_ci_upper",
            "n_total_groups",
            "n_skipped_missing_method",
        ],
    )

    write_csv(
        out_dir / "policy_by_budget.csv",
        by_budget_rows,
        [
            "split",
            "budget",
            "n_groups",
            "external_top_accuracy",
            "direct_top_accuracy",
            "gated_accuracy",
            "gated_minus_external",
            "gated_minus_direct",
            "random_expected_external",
            "random_expected_direct",
            "oracle_top2_accuracy",
            "switch_count",
            "switch_rate",
            "recoveries",
            "regressions",
            "net_gain",
        ],
    )

    write_csv(
        out_dir / "group_decisions.csv",
        decision_rows,
        [
            "split",
            "group_id",
            "budget",
            "selected_method",
            "did_switch",
            "external_top_score",
            "direct_top_score",
            "score_margin_direct_minus_external",
            "external_top_seed",
            "direct_top_seed",
            "external_top_correct",
            "direct_top_correct",
            "gated_correct",
            "random_expected_external",
            "random_expected_direct",
            "oracle_top2_correct",
            "recovery",
            "regression",
            "net_gain",
        ],
    )

    write_csv(
        out_dir / "bootstrap_deltas.csv",
        bootstrap_rows,
        ["iteration", "gated_minus_external", "gated_minus_direct"],
    )

    if gate_search_rows is not None:
        write_csv(
            out_dir / "gate_search_results.csv",
            gate_search_rows,
            [
                "rank",
                "gate_family",
                "margin",
                "threshold",
                "external_threshold",
                "dev_n_groups",
                "dev_external_top_accuracy",
                "dev_direct_top_accuracy",
                "dev_gated_accuracy",
                "dev_gated_minus_external",
                "dev_gated_minus_direct",
                "dev_switch_count",
                "dev_switch_rate",
                "dev_recoveries",
                "dev_regressions",
                "dev_net_gain",
            ],
        )


def write_report(path: pathlib.Path, metrics_obj: dict[str, Any]) -> None:
    mode = metrics_obj["mode"]
    selected = metrics_obj["selected_policy"]
    now = datetime.now(timezone.utc).isoformat()

    def _pct(v: Any) -> str:
        if v is None:
            return "N/A"
        return f"{float(v):.4f} ({100.0*float(v):.2f}%)"

    def _pp(v: Any) -> str:
        if v is None:
            return "N/A"
        return f"{100.0*float(v):+.2f}pp"

    eval_split = "validation" if mode == "tune_dev_eval_validation" else "evaluation"
    eval_metrics = metrics_obj["eval_overall"]
    eval_ci = metrics_obj["eval_bootstrap_ci"]

    lines = [
        "# Baseline-Gated Hybrid Allocator Report",
        "",
        f"- Generated: {now}",
        f"- Mode: {mode}",
        f"- Baseline method: `{metrics_obj['baseline_method']}`",
        f"- Frontier method: `{metrics_obj['frontier_method']}`",
        f"- Selected gate: `{selected['family']}`",
        f"- Parameters: margin={selected.get('margin')}, threshold={selected.get('threshold')}, external_threshold={selected.get('external_threshold')}",
        "",
        f"## {eval_split.capitalize()} Summary",
        "",
        f"- n_groups: {eval_metrics['n_groups']} (skipped missing-method groups: {metrics_obj['eval_n_skipped_missing_method']})",
        f"- external_top_accuracy: {_pct(eval_metrics['external_top_accuracy'])}",
        f"- direct_top_accuracy: {_pct(eval_metrics['direct_top_accuracy'])}",
        f"- gated_accuracy: {_pct(eval_metrics['gated_accuracy'])}",
        f"- gated_minus_external: {_pp(eval_metrics['gated_minus_external'])} (95% cluster CI [{_pp(eval_ci['gated_minus_external']['lower'])}, {_pp(eval_ci['gated_minus_external']['upper'])}])",
        f"- gated_minus_direct: {_pp(eval_metrics['gated_minus_direct'])} (95% cluster CI [{_pp(eval_ci['gated_minus_direct']['lower'])}, {_pp(eval_ci['gated_minus_direct']['upper'])}])",
        f"- switch_count: {eval_metrics['switch_count']}",
        f"- switch_rate: {_pct(eval_metrics['switch_rate'])}",
        f"- recoveries/regressions/net_gain: {eval_metrics['recoveries']}/{eval_metrics['regressions']}/{eval_metrics['net_gain']}",
        "",
        "## Notes",
        "",
        "- Offline evaluation only; exact_match metadata used only for reporting.",
        "- No provider/API calls, no model training, no live inference.",
        "- This compares against the configured baseline method and does not claim all-baseline superiority.",
    ]

    if mode == "tune_dev_eval_validation":
        dev = metrics_obj["dev_overall"]
        lines.extend(
            [
                "",
                "## Dev Tuning Summary",
                "",
                f"- dev_n_groups: {dev['n_groups']} (skipped missing-method groups: {metrics_obj['dev_n_skipped_missing_method']})",
                f"- dev_external_top_accuracy: {_pct(dev['external_top_accuracy'])}",
                f"- dev_direct_top_accuracy: {_pct(dev['direct_top_accuracy'])}",
                f"- dev_gated_accuracy: {_pct(dev['gated_accuracy'])}",
                f"- dev_gated_minus_external: {_pp(dev['gated_minus_external'])}",
                f"- dev_switch_rate: {_pct(dev['switch_rate'])}",
            ]
        )

    path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)

    p.add_argument("--scored-jsonl")
    p.add_argument("--dev-scored-jsonl")
    p.add_argument("--validation-scored-jsonl")
    p.add_argument("--output-dir", required=True)

    p.add_argument("--baseline-method", default="external_l1_max")
    p.add_argument("--frontier-method", default="direct_reserve_semantic_frontier_v2")

    p.add_argument("--score-field", default="proba_ready")
    p.add_argument("--correct-field", default="exact_match_metadata")
    p.add_argument("--budget-field", default="budget")
    p.add_argument("--seed-field", default="seed")
    p.add_argument("--group-id-field", default="example_id")
    p.add_argument("--method-field", default="method")

    p.add_argument("--gate-family", default="auto")
    p.add_argument("--margin", type=float, default=0.0)
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--external-threshold", type=float, default=0.5)

    p.add_argument("--margin-min", type=float, default=-1.0)
    p.add_argument("--margin-max", type=float, default=1.0)
    p.add_argument("--margin-step", type=float, default=0.05)

    p.add_argument("--threshold-min", type=float, default=0.0)
    p.add_argument("--threshold-max", type=float, default=1.0)
    p.add_argument("--threshold-step", type=float, default=0.05)

    p.add_argument("--external-threshold-min", type=float, default=0.0)
    p.add_argument("--external-threshold-max", type=float, default=1.0)
    p.add_argument("--external-threshold-step", type=float, default=0.05)

    p.add_argument("--n-bootstrap", type=int, default=2000)
    p.add_argument("--seed", type=int, default=12345)

    return p.parse_args(argv)


def _policy_from_args(args: argparse.Namespace) -> GatePolicy:
    family = args.gate_family
    if family in {"auto", "all"}:
        family = "always_external"
    if family not in GATE_FAMILY_ORDER:
        raise ValueError(f"Unknown gate family: {family}")
    return GatePolicy(
        family=family,
        margin=args.margin,
        threshold=args.threshold,
        external_threshold=args.external_threshold,
    )


def _overall_row(
    split: str,
    eval_obj: dict[str, Any],
    ci_obj: dict[str, dict[str, float]],
) -> dict[str, Any]:
    ov = dict(eval_obj["overall"])
    ov["split"] = split
    ov["gated_minus_external_ci_lower"] = ci_obj["gated_minus_external"]["lower"]
    ov["gated_minus_external_ci_upper"] = ci_obj["gated_minus_external"]["upper"]
    ov["gated_minus_direct_ci_lower"] = ci_obj["gated_minus_direct"]["lower"]
    ov["gated_minus_direct_ci_upper"] = ci_obj["gated_minus_direct"]["upper"]
    ov["n_total_groups"] = eval_obj["n_total_groups"]
    ov["n_skipped_missing_method"] = eval_obj["n_skipped_missing_method"]
    return ov


def _by_budget_rows(split: str, eval_obj: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for budget, metrics in eval_obj["by_budget"].items():
        row = dict(metrics)
        row["split"] = split
        row["budget"] = budget
        rows.append(row)
    return rows


def _decision_rows(split: str, eval_obj: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in eval_obj["decisions"]:
        r = dict(row)
        r["split"] = split
        rows.append(r)
    return rows


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tune_mode = bool(args.dev_scored_jsonl and args.validation_scored_jsonl)
    if tune_mode and args.scored_jsonl:
        print("INFO: --scored-jsonl is ignored in tune mode (dev+validation).")

    if tune_mode:
        dev_path = pathlib.Path(args.dev_scored_jsonl)
        val_path = pathlib.Path(args.validation_scored_jsonl)
        if not dev_path.exists() or not val_path.exists():
            print("ERROR: dev/validation scored JSONL path missing", file=sys.stderr)
            return 1

        dev_rows = load_scored_candidates(
            dev_path,
            score_field=args.score_field,
            correct_field=args.correct_field,
        )
        val_rows = load_scored_candidates(
            val_path, score_field=args.score_field, correct_field=args.correct_field
        )

        tuned = tune_gate_on_dev(dev_rows, args=args)
        selected = tuned["selected_policy"]

        dev_eval = evaluate_gate_policy(
            dev_rows,
            baseline_method=args.baseline_method,
            frontier_method=args.frontier_method,
            score_field=args.score_field,
            correct_field=args.correct_field,
            method_field=args.method_field,
            budget_field=args.budget_field,
            seed_field=args.seed_field,
            group_id_field=args.group_id_field,
            policy=selected,
        )

        val_eval = evaluate_gate_policy(
            val_rows,
            baseline_method=args.baseline_method,
            frontier_method=args.frontier_method,
            score_field=args.score_field,
            correct_field=args.correct_field,
            method_field=args.method_field,
            budget_field=args.budget_field,
            seed_field=args.seed_field,
            group_id_field=args.group_id_field,
            policy=selected,
        )

        boot = cluster_bootstrap_deltas(
            val_eval["decisions"],
            n_bootstrap=args.n_bootstrap,
            seed=args.seed,
        )

        gate_search_rows = []
        for i, row in enumerate(tuned["search_rows"], start=1):
            rr = dict(row)
            rr["rank"] = i
            gate_search_rows.append(rr)

        metrics_obj = {
            "stamp": datetime.now(timezone.utc).isoformat(),
            "mode": "tune_dev_eval_validation",
            "baseline_method": args.baseline_method,
            "frontier_method": args.frontier_method,
            "selected_policy": {
                "family": selected.family,
                "margin": selected.margin,
                "threshold": selected.threshold,
                "external_threshold": selected.external_threshold,
            },
            "inputs": {
                "dev_scored_jsonl": str(dev_path),
                "validation_scored_jsonl": str(val_path),
            },
            "search_space": {
                "gate_family": args.gate_family,
                "margin_min": args.margin_min,
                "margin_max": args.margin_max,
                "margin_step": args.margin_step,
                "threshold_min": args.threshold_min,
                "threshold_max": args.threshold_max,
                "threshold_step": args.threshold_step,
                "external_threshold_min": args.external_threshold_min,
                "external_threshold_max": args.external_threshold_max,
                "external_threshold_step": args.external_threshold_step,
            },
            "dev_overall": dev_eval["overall"],
            "dev_n_total_groups": dev_eval["n_total_groups"],
            "dev_n_skipped_missing_method": dev_eval["n_skipped_missing_method"],
            "validation_overall": val_eval["overall"],
            "validation_n_total_groups": val_eval["n_total_groups"],
            "validation_n_skipped_missing_method": val_eval["n_skipped_missing_method"],
            "eval_overall": val_eval["overall"],
            "eval_n_total_groups": val_eval["n_total_groups"],
            "eval_n_skipped_missing_method": val_eval["n_skipped_missing_method"],
            "eval_bootstrap_ci": boot["ci"],
            "n_bootstrap": args.n_bootstrap,
            "seed": args.seed,
            "dev_skipped_groups": dev_eval["skipped_missing_method"],
            "validation_skipped_groups": val_eval["skipped_missing_method"],
        }

        overall_rows = [
            _overall_row("dev", dev_eval, {"gated_minus_external": {"lower": None, "upper": None}, "gated_minus_direct": {"lower": None, "upper": None}}),
            _overall_row("validation", val_eval, boot["ci"]),
        ]

        by_budget_rows = _by_budget_rows("dev", dev_eval) + _by_budget_rows("validation", val_eval)
        decision_rows = _decision_rows("dev", dev_eval) + _decision_rows("validation", val_eval)

        write_outputs(
            out_dir=out_dir,
            metrics_obj=metrics_obj,
            overall_rows=overall_rows,
            by_budget_rows=by_budget_rows,
            decision_rows=decision_rows,
            bootstrap_rows=boot["rows"],
            gate_search_rows=gate_search_rows,
        )
        write_report(out_dir / "hybrid_allocator_report.md", metrics_obj)

        return 0

    if not args.scored_jsonl:
        print(
            "ERROR: provide either --scored-jsonl for fixed evaluation, or both --dev-scored-jsonl and --validation-scored-jsonl for tuning mode",
            file=sys.stderr,
        )
        return 1

    scored_path = pathlib.Path(args.scored_jsonl)
    if not scored_path.exists():
        print(f"ERROR: scored JSONL not found: {scored_path}", file=sys.stderr)
        return 1

    rows = load_scored_candidates(scored_path, score_field=args.score_field, correct_field=args.correct_field)
    selected = _policy_from_args(args)

    eval_obj = evaluate_gate_policy(
        rows,
        baseline_method=args.baseline_method,
        frontier_method=args.frontier_method,
        score_field=args.score_field,
        correct_field=args.correct_field,
        method_field=args.method_field,
        budget_field=args.budget_field,
        seed_field=args.seed_field,
        group_id_field=args.group_id_field,
        policy=selected,
    )
    boot = cluster_bootstrap_deltas(
        eval_obj["decisions"],
        n_bootstrap=args.n_bootstrap,
        seed=args.seed,
    )

    metrics_obj = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "mode": "single_eval",
        "baseline_method": args.baseline_method,
        "frontier_method": args.frontier_method,
        "selected_policy": {
            "family": selected.family,
            "margin": selected.margin,
            "threshold": selected.threshold,
            "external_threshold": selected.external_threshold,
        },
        "inputs": {
            "scored_jsonl": str(scored_path),
        },
        "overall": eval_obj["overall"],
        "n_total_groups": eval_obj["n_total_groups"],
        "n_skipped_missing_method": eval_obj["n_skipped_missing_method"],
        "eval_overall": eval_obj["overall"],
        "eval_n_total_groups": eval_obj["n_total_groups"],
        "eval_n_skipped_missing_method": eval_obj["n_skipped_missing_method"],
        "eval_bootstrap_ci": boot["ci"],
        "n_bootstrap": args.n_bootstrap,
        "seed": args.seed,
        "skipped_groups": eval_obj["skipped_missing_method"],
    }

    write_outputs(
        out_dir=out_dir,
        metrics_obj=metrics_obj,
        overall_rows=[_overall_row("evaluation", eval_obj, boot["ci"])],
        by_budget_rows=_by_budget_rows("evaluation", eval_obj),
        decision_rows=_decision_rows("evaluation", eval_obj),
        bootstrap_rows=boot["rows"],
        gate_search_rows=None,
    )
    write_report(out_dir / "hybrid_allocator_report.md", metrics_obj)
    return 0


if __name__ == "__main__":
    sys.exit(main())
