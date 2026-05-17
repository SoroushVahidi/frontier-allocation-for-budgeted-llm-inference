"""Sweep tie-aware within-method reranking policies on verifier-scored candidates.

No API calls. Offline analysis only.

Default groups: (example_id, budget, method) where each group contains seed-level
alternatives for a single method. Baseline policy is verifier_top1 by max score.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

THRESHOLDS = [0.0, 0.001, 0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02]
TIE_MODES = ["epsilon", "spread"]
NON_ORACLE_POLICIES = ["lowest_seed", "highest_seed", "median_seed", "secondary_score"]
ORACLE_POLICY = "oracle_upper_bound_in_tie_set"


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _seed_val(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def load_scored(path: pathlib.Path, score_field: str) -> list[dict[str, Any]]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            meta = raw.get("metadata", {}) or {}
            row: dict[str, Any] = {
                score_field: _safe_float(raw.get(score_field), 0.0),
                "feature_text": raw.get("feature_text", ""),
                "predicted_label": _safe_int(raw.get("predicted_label"), 0),
            }
            for k, v in meta.items():
                row[k] = v
            rows.append(row)
    return rows


def build_groups(rows: list[dict[str, Any]], group_fields: list[str]) -> dict[tuple, list[dict[str, Any]]]:
    out: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        out[tuple(r.get(f) for f in group_fields)].append(r)
    return dict(out)


def detect_secondary_score_field(rows: list[dict[str, Any]]) -> str | None:
    candidates = [
        "original_score",
        "frontier_score",
        "frontier_candidate_score",
        "candidate_score",
        "source_score",
    ]
    for field in candidates:
        for r in rows:
            if field in r and r.get(field) is not None:
                try:
                    float(r.get(field))
                    return field
                except (TypeError, ValueError):
                    continue
    return None


def baseline_top1_index(cands: list[dict[str, Any]], score_field: str) -> int:
    return max(
        range(len(cands)),
        key=lambda i: (_safe_float(cands[i].get(score_field), 0.0), -_seed_val(cands[i].get("seed"))),
    )


def tie_set_indices(
    cands: list[dict[str, Any]],
    score_field: str,
    mode: str,
    threshold: float,
) -> tuple[list[int], float]:
    scores = [_safe_float(c.get(score_field), 0.0) for c in cands]
    max_score = max(scores) if scores else 0.0
    min_score = min(scores) if scores else 0.0
    spread = max_score - min_score
    if mode == "epsilon":
        keep = [i for i, s in enumerate(scores) if (max_score - s) <= (threshold + 1e-12)]
        return keep or [0], spread
    if mode == "spread":
        if spread < (threshold + 1e-12):
            return list(range(len(cands))), spread
        return [baseline_top1_index(cands, score_field)], spread
    raise ValueError(f"unknown mode: {mode}")


def choose_tie_breaker_index(
    cands: list[dict[str, Any]],
    tie_idxs: list[int],
    policy: str,
    secondary_score_field: str | None,
) -> int | None:
    if not tie_idxs:
        return None
    ordered = sorted(tie_idxs, key=lambda i: _seed_val(cands[i].get("seed")))
    if policy == "lowest_seed":
        return ordered[0]
    if policy == "highest_seed":
        return ordered[-1]
    if policy == "median_seed":
        return ordered[len(ordered) // 2]
    if policy == "secondary_score":
        if not secondary_score_field:
            return None
        return max(
            ordered,
            key=lambda i: (_safe_float(cands[i].get(secondary_score_field), float("-inf")), -_seed_val(cands[i].get("seed"))),
        )
    if policy == ORACLE_POLICY:
        return None
    raise ValueError(f"unknown policy: {policy}")


def aggregate_binary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    n = len(rows)
    n_correct = sum(_safe_int(r.get("policy_em"), 0) for r in rows)
    n_baseline = sum(_safe_int(r.get("baseline_em"), 0) for r in rows)
    affected = sum(_safe_int(r.get("tie_activated"), 0) for r in rows)
    changed = sum(_safe_int(r.get("changed_choice"), 0) for r in rows)
    recoveries = sum(_safe_int(r.get("recovery"), 0) for r in rows)
    regressions = sum(_safe_int(r.get("regression"), 0) for r in rows)
    missed_total = sum(_safe_int(r.get("missed_oracle_group"), 0) for r in rows)
    recover_missed = sum(_safe_int(r.get("recovery_on_missed_oracle"), 0) for r in rows)
    tie_sizes = [_safe_int(r.get("tie_set_size"), 0) for r in rows]
    return {
        "n_groups": n,
        "accuracy": n_correct / n,
        "baseline_accuracy": n_baseline / n,
        "lift_vs_baseline": (n_correct - n_baseline) / n,
        "affected_groups": affected,
        "affected_pct": affected / n,
        "changed_groups": changed,
        "changed_pct": changed / n,
        "recoveries": recoveries,
        "regressions": regressions,
        "net_gain": recoveries - regressions,
        "missed_oracle_groups": missed_total,
        "recoveries_on_missed_oracle": recover_missed,
        "mean_tie_set_size": statistics.mean(tie_sizes) if tie_sizes else 0.0,
    }


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(r.get(k)) for k in columns})


def summarize_spreads(groups: dict[tuple, list[dict[str, Any]]], score_field: str, method_idx: int, budget_idx: int) -> dict[str, Any]:
    by_method: dict[str, list[float]] = defaultdict(list)
    by_mb: dict[tuple[str, str], list[float]] = defaultdict(list)
    for key, cands in groups.items():
        scores = [_safe_float(c.get(score_field), 0.0) for c in cands]
        spread = max(scores) - min(scores)
        method = str(key[method_idx])
        budget = str(key[budget_idx])
        by_method[method].append(spread)
        by_mb[(method, budget)].append(spread)
    return {
        "by_method": {
            m: {
                "mean_spread": statistics.mean(v),
                "median_spread": statistics.median(v),
                "tiny_spread_rate_lt_0_01": sum(1 for x in v if x < 0.01) / len(v),
                "n_groups": len(v),
            }
            for m, v in sorted(by_method.items())
        },
        "by_method_budget": {
            f"{m}|{b}": {
                "mean_spread": statistics.mean(v),
                "median_spread": statistics.median(v),
                "tiny_spread_rate_lt_0_01": sum(1 for x in v if x < 0.01) / len(v),
                "n_groups": len(v),
            }
            for (m, b), v in sorted(by_mb.items(), key=lambda x: (x[0][0], x[0][1]))
        },
    }


def write_plot(
    best_non_oracle_by_method_budget: list[dict[str, Any]],
    out_path: pathlib.Path,
) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    methods = sorted({r["method"] for r in best_non_oracle_by_method_budget})
    fig, axes = plt.subplots(1, len(methods), figsize=(5 * len(methods), 4), sharey=True)
    if len(methods) == 1:
        axes = [axes]
    for ax, method in zip(axes, methods):
        rows = [r for r in best_non_oracle_by_method_budget if r["method"] == method]
        rows = sorted(rows, key=lambda r: str(r["budget"]))
        x = list(range(len(rows)))
        y_policy = [float(r["accuracy"]) for r in rows]
        y_base = [float(r["baseline_accuracy"]) for r in rows]
        labels = [str(r["budget"]) for r in rows]
        ax.plot(x, y_base, marker="o", label="verifier_top1")
        ax.plot(x, y_policy, marker="^", linestyle="--", label="best_tie_aware")
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.set_title(method[-40:], fontsize=8)
        ax.set_xlabel("Budget")
        ax.legend(fontsize=7)
    axes[0].set_ylabel("Accuracy")
    fig.suptitle("Best Non-Oracle Tie-Aware vs Baseline")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return True


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scored-jsonl", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--group-fields", default="example_id,budget,method")
    p.add_argument("--score-field", default="proba_ready")
    p.add_argument("--correct-field", default="exact_match_metadata")
    p.add_argument("--method-field", default="method")
    p.add_argument("--budget-field", default="budget")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    scored_path = pathlib.Path(args.scored_jsonl)
    if not scored_path.exists():
        print(f"ERROR: {scored_path} not found", file=sys.stderr)
        return 1

    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_scored(scored_path, args.score_field)
    group_fields = [x.strip() for x in args.group_fields.split(",")]
    groups = build_groups(rows, group_fields)
    keys = list(groups.keys())

    try:
        method_idx = group_fields.index(args.method_field)
    except ValueError:
        method_idx = 2
    try:
        budget_idx = group_fields.index(args.budget_field)
    except ValueError:
        budget_idx = 1

    secondary_score_field = detect_secondary_score_field(rows)

    baseline_by_key: dict[tuple, dict[str, Any]] = {}
    for key, cands in groups.items():
        b_idx = baseline_top1_index(cands, args.score_field)
        ems = [_safe_int(c.get(args.correct_field), 0) for c in cands if c.get(args.correct_field) is not None]
        baseline_by_key[key] = {
            "baseline_idx": b_idx,
            "baseline_seed": cands[b_idx].get("seed"),
            "baseline_score": _safe_float(cands[b_idx].get(args.score_field), 0.0),
            "baseline_em": _safe_int(cands[b_idx].get(args.correct_field), 0),
            "oracle_any_correct": int(any(e == 1 for e in ems)),
        }

    tie_info: dict[tuple[str, float], dict[tuple, dict[str, Any]]] = {}
    for mode in TIE_MODES:
        for thr in THRESHOLDS:
            per_group: dict[tuple, dict[str, Any]] = {}
            for key, cands in groups.items():
                tie_idxs, spread = tie_set_indices(cands, args.score_field, mode, thr)
                activated = int(len(tie_idxs) > 1) if mode == "epsilon" else int(spread < (thr + 1e-12))
                per_group[key] = {
                    "tie_idxs": tie_idxs,
                    "tie_set_size": len(tie_idxs),
                    "spread": spread,
                    "activated": activated,
                }
            tie_info[(mode, thr)] = per_group

    # Distribution of tie sizes by (mode, threshold)
    tie_dist_rows: list[dict[str, Any]] = []
    for (mode, thr), info in tie_info.items():
        counts = Counter(v["tie_set_size"] for v in info.values())
        total = len(info)
        for size, n in sorted(counts.items()):
            tie_dist_rows.append(
                {
                    "mode": mode,
                    "threshold": thr,
                    "tie_set_size": size,
                    "n_groups": n,
                    "pct_groups": n / total if total else 0.0,
                }
            )

    affected_rows: list[dict[str, Any]] = []
    overall_rows: list[dict[str, Any]] = []
    by_method_rows: list[dict[str, Any]] = []
    by_method_budget_rows: list[dict[str, Any]] = []

    policies = NON_ORACLE_POLICIES + [ORACLE_POLICY]
    skipped_secondary = 0
    for mode in TIE_MODES:
        for thr in THRESHOLDS:
            for policy in policies:
                is_oracle = int(policy == ORACLE_POLICY)
                if policy == "secondary_score" and secondary_score_field is None:
                    skipped_secondary += 1
                    continue

                rows_eval: list[dict[str, Any]] = []
                for key in keys:
                    cands = groups[key]
                    b = baseline_by_key[key]
                    t = tie_info[(mode, thr)][key]
                    tie_idxs = t["tie_idxs"]
                    if policy == ORACLE_POLICY:
                        policy_idx = None
                        policy_em = int(any(_safe_int(cands[i].get(args.correct_field), 0) == 1 for i in tie_idxs))
                        policy_seed = None
                        policy_score = None
                    else:
                        policy_idx = choose_tie_breaker_index(cands, tie_idxs, policy, secondary_score_field)
                        if policy_idx is None:
                            continue
                        policy_em = _safe_int(cands[policy_idx].get(args.correct_field), 0)
                        policy_seed = cands[policy_idx].get("seed")
                        policy_score = _safe_float(cands[policy_idx].get(args.score_field), 0.0)

                    changed = 0
                    if policy_idx is not None:
                        changed = int(policy_idx != b["baseline_idx"])
                    recovery = int(b["baseline_em"] == 0 and policy_em == 1)
                    regression = int(b["baseline_em"] == 1 and policy_em == 0)
                    missed_oracle_group = int(b["baseline_em"] == 0 and b["oracle_any_correct"] == 1)
                    recovery_on_missed = int(missed_oracle_group == 1 and policy_em == 1)

                    method = str(key[method_idx]) if method_idx < len(key) else "unknown"
                    budget = str(key[budget_idx]) if budget_idx < len(key) else "unknown"
                    row = {
                        "mode": mode,
                        "threshold": thr,
                        "policy": policy,
                        "is_oracle_diagnostic": is_oracle,
                        "example_id": key[0] if len(key) > 0 else None,
                        "budget": budget,
                        "method": method,
                        "baseline_seed": b["baseline_seed"],
                        "baseline_score": b["baseline_score"],
                        "baseline_em": b["baseline_em"],
                        "policy_seed": policy_seed,
                        "policy_score": policy_score,
                        "policy_em": policy_em,
                        "oracle_any_correct": b["oracle_any_correct"],
                        "tie_set_size": t["tie_set_size"],
                        "tie_activated": t["activated"],
                        "changed_choice": changed,
                        "recovery": recovery,
                        "regression": regression,
                        "net_gain": recovery - regression,
                        "missed_oracle_group": missed_oracle_group,
                        "recovery_on_missed_oracle": recovery_on_missed,
                        "score_spread": t["spread"],
                    }
                    rows_eval.append(row)
                    affected_rows.append(row)

                agg = aggregate_binary(rows_eval)
                overall_rows.append(
                    {
                        "mode": mode,
                        "threshold": thr,
                        "policy": policy,
                        "is_oracle_diagnostic": is_oracle,
                        **agg,
                    }
                )

                # by method
                by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
                by_mb: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
                for r in rows_eval:
                    by_method[r["method"]].append(r)
                    by_mb[(r["method"], r["budget"])].append(r)
                for method, mrows in sorted(by_method.items()):
                    by_method_rows.append(
                        {
                            "mode": mode,
                            "threshold": thr,
                            "policy": policy,
                            "is_oracle_diagnostic": is_oracle,
                            "method": method,
                            **aggregate_binary(mrows),
                        }
                    )
                for (method, budget), brows in sorted(by_mb.items(), key=lambda x: (x[0][0], x[0][1])):
                    by_method_budget_rows.append(
                        {
                            "mode": mode,
                            "threshold": thr,
                            "policy": policy,
                            "is_oracle_diagnostic": is_oracle,
                            "method": method,
                            "budget": budget,
                            **aggregate_binary(brows),
                        }
                    )

    # CSV outputs
    write_csv(
        out_dir / "sweep_overall.csv",
        overall_rows,
        [
            "mode",
            "threshold",
            "policy",
            "is_oracle_diagnostic",
            "n_groups",
            "accuracy",
            "baseline_accuracy",
            "lift_vs_baseline",
            "affected_groups",
            "affected_pct",
            "changed_groups",
            "changed_pct",
            "recoveries",
            "regressions",
            "net_gain",
            "missed_oracle_groups",
            "recoveries_on_missed_oracle",
            "mean_tie_set_size",
        ],
    )
    write_csv(
        out_dir / "sweep_by_method.csv",
        by_method_rows,
        [
            "mode",
            "threshold",
            "policy",
            "is_oracle_diagnostic",
            "method",
            "n_groups",
            "accuracy",
            "baseline_accuracy",
            "lift_vs_baseline",
            "affected_groups",
            "affected_pct",
            "changed_groups",
            "changed_pct",
            "recoveries",
            "regressions",
            "net_gain",
            "missed_oracle_groups",
            "recoveries_on_missed_oracle",
            "mean_tie_set_size",
        ],
    )
    write_csv(
        out_dir / "sweep_by_method_budget.csv",
        by_method_budget_rows,
        [
            "mode",
            "threshold",
            "policy",
            "is_oracle_diagnostic",
            "method",
            "budget",
            "n_groups",
            "accuracy",
            "baseline_accuracy",
            "lift_vs_baseline",
            "affected_groups",
            "affected_pct",
            "changed_groups",
            "changed_pct",
            "recoveries",
            "regressions",
            "net_gain",
            "missed_oracle_groups",
            "recoveries_on_missed_oracle",
            "mean_tie_set_size",
        ],
    )
    write_csv(
        out_dir / "tie_set_size_distribution.csv",
        tie_dist_rows,
        ["mode", "threshold", "tie_set_size", "n_groups", "pct_groups"],
    )
    write_csv(
        out_dir / "affected_groups.csv",
        affected_rows,
        [
            "mode",
            "threshold",
            "policy",
            "is_oracle_diagnostic",
            "example_id",
            "budget",
            "method",
            "baseline_seed",
            "baseline_score",
            "baseline_em",
            "policy_seed",
            "policy_score",
            "policy_em",
            "oracle_any_correct",
            "tie_set_size",
            "tie_activated",
            "changed_choice",
            "recovery",
            "regression",
            "net_gain",
            "missed_oracle_group",
            "recovery_on_missed_oracle",
            "score_spread",
        ],
    )

    # Selections for report
    non_oracle_overall = [r for r in overall_rows if not r["is_oracle_diagnostic"]]
    oracle_overall = [r for r in overall_rows if r["is_oracle_diagnostic"]]
    best_non_oracle_overall = max(non_oracle_overall, key=lambda r: (r.get("accuracy", 0.0), r.get("net_gain", 0)))
    best_oracle_overall = max(oracle_overall, key=lambda r: (r.get("accuracy", 0.0), r.get("net_gain", 0)))

    by_mb_best_non_oracle = []
    grouped_mb: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in by_method_budget_rows:
        if r["is_oracle_diagnostic"]:
            continue
        grouped_mb[(r["method"], r["budget"])].append(r)
    for (method, budget), rows_mb in sorted(grouped_mb.items(), key=lambda x: (x[0][0], x[0][1])):
        best = max(rows_mb, key=lambda x: (x.get("accuracy", 0.0), x.get("net_gain", 0)))
        by_mb_best_non_oracle.append(best)

    by_method_best_non_oracle = []
    grouped_m: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in by_method_rows:
        if r["is_oracle_diagnostic"]:
            continue
        grouped_m[r["method"]].append(r)
    for method, rows_m in sorted(grouped_m.items()):
        best = max(rows_m, key=lambda x: (x.get("accuracy", 0.0), x.get("net_gain", 0)))
        by_method_best_non_oracle.append(best)

    spread_summary = summarize_spreads(groups, args.score_field, method_idx, budget_idx)

    metrics = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "input": args.scored_jsonl,
        "n_rows": len(rows),
        "n_groups": len(groups),
        "secondary_score_field": secondary_score_field,
        "n_secondary_score_configs_skipped": skipped_secondary,
        "thresholds": THRESHOLDS,
        "best_non_oracle_overall": best_non_oracle_overall,
        "best_oracle_diagnostic_overall": best_oracle_overall,
        "best_non_oracle_by_method": by_method_best_non_oracle,
        "best_non_oracle_by_method_budget": by_mb_best_non_oracle,
        "spread_summary": spread_summary,
    }
    with open(out_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    # Markdown report
    lines = [
        "# Tie-Aware Within-Method Reranking Sweep",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Input: `{args.scored_jsonl}`",
        f"- Groups: `{', '.join(group_fields)}`",
        f"- Rows: {len(rows)}, Groups: {len(groups)}",
        "",
        "## Best Overall (Non-Oracle Policy)",
        "",
        f"- Mode: `{best_non_oracle_overall['mode']}`, threshold: `{best_non_oracle_overall['threshold']}`, policy: `{best_non_oracle_overall['policy']}`",
        f"- Accuracy: {best_non_oracle_overall['accuracy']:.4f} vs baseline {best_non_oracle_overall['baseline_accuracy']:.4f} (lift {best_non_oracle_overall['lift_vs_baseline']*100:+.2f}pp)",
        f"- Recoveries: {best_non_oracle_overall['recoveries']}, regressions: {best_non_oracle_overall['regressions']}, net: {best_non_oracle_overall['net_gain']}",
        f"- Affected groups: {best_non_oracle_overall['affected_groups']}/{best_non_oracle_overall['n_groups']} ({best_non_oracle_overall['affected_pct']*100:.1f}%)",
        "",
        "## Oracle Tie-Set Upper Bound (Diagnostic Only)",
        "",
        f"- Mode: `{best_oracle_overall['mode']}`, threshold: `{best_oracle_overall['threshold']}`, policy: `{ORACLE_POLICY}`",
        f"- Diagnostic accuracy upper bound inside tie set: {best_oracle_overall['accuracy']:.4f}",
        "- This is not a deployable policy; it only measures headroom when tie sets include a correct candidate.",
        "",
        "## Best by Method",
        "",
        "| Method | Mode | Threshold | Policy | Accuracy | Baseline | Lift(pp) | Net gain |",
        "|---|---|---:|---|---:|---:|---:|---:|",
    ]
    for r in by_method_best_non_oracle:
        lines.append(
            f"| {r['method']} | {r['mode']} | {r['threshold']:.4f} | {r['policy']} | {r['accuracy']:.4f} | "
            f"{r['baseline_accuracy']:.4f} | {r['lift_vs_baseline']*100:+.2f} | {r['net_gain']} |"
        )

    lines += [
        "",
        "## Best by Method and Budget",
        "",
        "| Method | Budget | Mode | Threshold | Policy | Accuracy | Baseline | Lift(pp) | Recoveries | Regressions | Net |",
        "|---|---:|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in by_mb_best_non_oracle:
        lines.append(
            f"| {r['method']} | {r['budget']} | {r['mode']} | {r['threshold']:.4f} | {r['policy']} | "
            f"{r['accuracy']:.4f} | {r['baseline_accuracy']:.4f} | {r['lift_vs_baseline']*100:+.2f} | "
            f"{r['recoveries']} | {r['regressions']} | {r['net_gain']} |"
        )

    # Highlight requested slices
    def _pick(rows_in: list[dict[str, Any]], method: str, budget: str | None = None) -> dict[str, Any] | None:
        out = [r for r in rows_in if r["method"] == method and (budget is None or str(r["budget"]) == str(budget))]
        if not out:
            return None
        return max(out, key=lambda x: (x.get("accuracy", 0.0), x.get("net_gain", 0)))

    dr_all = _pick(by_method_best_non_oracle, "direct_reserve_semantic_frontier_v2")
    ex_all = _pick(by_method_best_non_oracle, "external_l1_max")
    dr_b8 = _pick(by_mb_best_non_oracle, "direct_reserve_semantic_frontier_v2", "8")

    lines += [
        "",
        "## Requested Focus",
        "",
    ]
    if dr_all:
        lines.append(
            f"- direct_reserve (all budgets) best: `{dr_all['mode']}` / `{dr_all['policy']}` @ {dr_all['threshold']:.4f}, "
            f"acc {dr_all['accuracy']:.4f} vs {dr_all['baseline_accuracy']:.4f} ({dr_all['lift_vs_baseline']*100:+.2f}pp)."
        )
    if ex_all:
        lines.append(
            f"- external_l1_max (all budgets) best: `{ex_all['mode']}` / `{ex_all['policy']}` @ {ex_all['threshold']:.4f}, "
            f"acc {ex_all['accuracy']:.4f} vs {ex_all['baseline_accuracy']:.4f} ({ex_all['lift_vs_baseline']*100:+.2f}pp)."
        )
    if dr_b8:
        lines.append(
            f"- direct_reserve budget 8 best: `{dr_b8['mode']}` / `{dr_b8['policy']}` @ {dr_b8['threshold']:.4f}, "
            f"acc {dr_b8['accuracy']:.4f} vs {dr_b8['baseline_accuracy']:.4f} ({dr_b8['lift_vs_baseline']*100:+.2f}pp), "
            f"recoveries={dr_b8['recoveries']}, regressions={dr_b8['regressions']}, net={dr_b8['net_gain']}."
        )

    lines += [
        "",
        "## Spread Diagnostics",
        "",
        "| Method | Mean spread | Median spread | Tiny spread rate (<0.01) |",
        "|---|---:|---:|---:|",
    ]
    for method, d in spread_summary["by_method"].items():
        lines.append(
            f"| {method} | {d['mean_spread']:.6f} | {d['median_spread']:.6f} | {d['tiny_spread_rate_lt_0_01']*100:.1f}% |"
        )
    lines += [
        "",
        "Artifacts:",
        "- `sweep_overall.csv`",
        "- `sweep_by_method.csv`",
        "- `sweep_by_method_budget.csv`",
        "- `tie_set_size_distribution.csv`",
        "- `affected_groups.csv`",
    ]
    (out_dir / "tie_aware_sweep_report.md").write_text("\n".join(lines) + "\n")

    plot_ok = write_plot(by_mb_best_non_oracle, out_dir / "tie_aware_accuracy_by_budget.png")
    if plot_ok:
        print(out_dir / "tie_aware_accuracy_by_budget.png")

    print(f"Loaded rows: {len(rows)}")
    print(f"Groups: {len(groups)}")
    print(f"Best non-oracle: {best_non_oracle_overall['mode']} / {best_non_oracle_overall['policy']} / {best_non_oracle_overall['threshold']}")
    print(f"Outputs: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
