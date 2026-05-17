"""Bootstrap uncertainty analysis for within-method verifier reranking.

This script consumes a reranking group-details CSV where each row is a
(method-conditioned) group, typically keyed by (example_id, budget, method).
It computes point estimates and 95% percentile confidence intervals using:

1) Paired/group bootstrap over rows.
2) Cluster bootstrap over example_id (or configured cluster field), resampling
   all rows in a cluster together.

Usage:
    python3 scripts/analyze_within_method_reranking_uncertainty.py \
        --group-details-csv outputs/.../reranking_group_details.csv \
        --output-dir outputs/within_method_reranking_uncertainty_<STAMP>
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


METRIC_COLUMN_CANDIDATES = {
    "verifier_max": ["em_verifier_max", "verifier_max", "verifier_max_correct"],
    "random_expected": ["random_expected", "random_mean", "random_accuracy"],
    "anti_verifier": ["em_anti_verifier", "anti_verifier", "anti_verifier_correct"],
    "oracle": ["oracle_any_correct", "oracle", "oracle_correct"],
}

PRIMARY_METRICS = [
    "verifier_max",
    "random_expected",
    "anti_verifier",
    "oracle",
    "verifier_minus_random",
    "verifier_minus_anti",
    "oracle_minus_verifier",
]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--group-details-csv", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--n-bootstrap", type=int, default=10000)
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--cluster-field", default="example_id")
    p.add_argument("--method-field", default="method")
    p.add_argument("--budget-field", default="budget")
    return p.parse_args(argv)


def _as_float(value: Any) -> float:
    if value is None:
        raise ValueError("missing numeric value")
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        raise ValueError("empty numeric value")
    return float(s)


def _resolve_metric_columns(headers: list[str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    lower_to_original = {h.lower(): h for h in headers}

    for metric_name, candidates in METRIC_COLUMN_CANDIDATES.items():
        found = None
        for candidate in candidates:
            key = candidate.lower()
            if key in lower_to_original:
                found = lower_to_original[key]
                break
        if found is None:
            raise ValueError(
                f"Could not resolve required metric column '{metric_name}'. "
                f"Candidates: {candidates}; available headers: {headers}"
            )
        resolved[metric_name] = found

    return resolved


def load_group_details(
    path: pathlib.Path,
    *,
    cluster_field: str,
    method_field: str,
    budget_field: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        metric_cols = _resolve_metric_columns(headers)

        # Backward-compatible convenience: when the caller leaves the default
        # cluster field as `example_id`, but the CSV uses `problem_id`.
        resolved_cluster_field = cluster_field
        if resolved_cluster_field not in headers and cluster_field == "example_id" and "problem_id" in headers:
            resolved_cluster_field = "problem_id"

        missing_context = [
            field
            for field in [resolved_cluster_field, method_field, budget_field]
            if field not in headers
        ]
        if missing_context:
            raise ValueError(
                "Missing required context fields in CSV: "
                + ", ".join(missing_context)
            )

        rows: list[dict[str, Any]] = []
        for raw in reader:
            row = {
                "cluster": str(raw[resolved_cluster_field]),
                "method": str(raw[method_field]),
                "budget": str(raw[budget_field]),
            }
            row["verifier_max"] = _as_float(raw[metric_cols["verifier_max"]])
            row["random_expected"] = _as_float(raw[metric_cols["random_expected"]])
            row["anti_verifier"] = _as_float(raw[metric_cols["anti_verifier"]])
            row["oracle"] = _as_float(raw[metric_cols["oracle"]])
            rows.append(row)

    if not rows:
        raise ValueError(f"No rows found in {path}")

    metric_cols["resolved_cluster_field"] = resolved_cluster_field
    return rows, metric_cols


def compute_point_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    n = len(rows)
    verifier_mean = sum(r["verifier_max"] for r in rows) / n
    random_mean = sum(r["random_expected"] for r in rows) / n
    anti_mean = sum(r["anti_verifier"] for r in rows) / n
    oracle_mean = sum(r["oracle"] for r in rows) / n

    return {
        "verifier_max": verifier_mean,
        "random_expected": random_mean,
        "anti_verifier": anti_mean,
        "oracle": oracle_mean,
        "verifier_minus_random": verifier_mean - random_mean,
        "verifier_minus_anti": verifier_mean - anti_mean,
        "oracle_minus_verifier": oracle_mean - verifier_mean,
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
    sorted_values = sorted(values)
    low = _percentile(sorted_values, alpha / 2)
    high = _percentile(sorted_values, 1 - alpha / 2)
    return low, high


def _resample_rows_paired(rows: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    n = len(rows)
    return [rows[rng.randrange(n)] for _ in range(n)]


def _build_cluster_map(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    cluster_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cluster_map[str(row["cluster"])].append(row)
    return dict(cluster_map)


def _resample_rows_cluster(
    cluster_map: dict[str, list[dict[str, Any]]], rng: random.Random
) -> tuple[list[dict[str, Any]], list[str]]:
    clusters = list(cluster_map.keys())
    sampled_ids = [clusters[rng.randrange(len(clusters))] for _ in range(len(clusters))]
    sampled_rows: list[dict[str, Any]] = []
    for cid in sampled_ids:
        sampled_rows.extend(cluster_map[cid])
    return sampled_rows, sampled_ids


def bootstrap_distributions(
    rows: list[dict[str, Any]],
    *,
    n_bootstrap: int,
    seed: int,
) -> dict[str, dict[str, list[float]]]:
    if n_bootstrap <= 0:
        raise ValueError("n_bootstrap must be > 0")

    rng = random.Random(seed)
    cluster_map = _build_cluster_map(rows)

    paired = {m: [] for m in PRIMARY_METRICS}
    cluster = {m: [] for m in PRIMARY_METRICS}

    for _ in range(n_bootstrap):
        paired_rows = _resample_rows_paired(rows, rng)
        paired_metrics = compute_point_metrics(paired_rows)
        for metric_name in PRIMARY_METRICS:
            paired[metric_name].append(paired_metrics[metric_name])

        cluster_rows, _sampled_clusters = _resample_rows_cluster(cluster_map, rng)
        cluster_metrics = compute_point_metrics(cluster_rows)
        for metric_name in PRIMARY_METRICS:
            cluster[metric_name].append(cluster_metrics[metric_name])

    return {"paired": paired, "cluster": cluster}


def summarize_with_uncertainty(
    rows: list[dict[str, Any]],
    *,
    n_bootstrap: int,
    seed: int,
) -> dict[str, Any]:
    point = compute_point_metrics(rows)
    boot = bootstrap_distributions(rows, n_bootstrap=n_bootstrap, seed=seed)

    ci: dict[str, dict[str, dict[str, float]]] = {"paired": {}, "cluster": {}}
    for bootstrap_type in ["paired", "cluster"]:
        for metric_name in PRIMARY_METRICS:
            lo, hi = ci_from_samples(boot[bootstrap_type][metric_name])
            ci[bootstrap_type][metric_name] = {"lower": lo, "upper": hi}

    return {
        "n_groups": len(rows),
        "n_clusters": len({r["cluster"] for r in rows}),
        "point": point,
        "ci": ci,
        "bootstrap_distributions": boot,
    }


def compute_verifier_vs_anti_discordance(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "n_groups": len(rows),
        "both_correct": 0,
        "verifier_only_correct": 0,
        "anti_only_correct": 0,
        "both_wrong": 0,
    }
    for row in rows:
        v = int(row["verifier_max"])
        a = int(row["anti_verifier"])
        if v == 1 and a == 1:
            counts["both_correct"] += 1
        elif v == 1 and a == 0:
            counts["verifier_only_correct"] += 1
        elif v == 0 and a == 1:
            counts["anti_only_correct"] += 1
        else:
            counts["both_wrong"] += 1
    return counts


def _aggregate_subsets(rows: list[dict[str, Any]]) -> tuple[list[tuple[str, list[dict[str, Any]]]], list[tuple[tuple[str, str], list[dict[str, Any]]]]]:
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_method_budget: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        method = row["method"]
        budget = row["budget"]
        by_method[method].append(row)
        by_method_budget[(method, budget)].append(row)

    by_method_items = sorted(by_method.items(), key=lambda kv: kv[0])
    by_method_budget_items = sorted(by_method_budget.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    return by_method_items, by_method_budget_items


def _fmt_float(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _write_bootstrap_overall_csv(summary: dict[str, Any], out_path: pathlib.Path, n_bootstrap: int) -> None:
    cols = [
        "metric",
        "point_estimate",
        "paired_ci_lower",
        "paired_ci_upper",
        "cluster_ci_lower",
        "cluster_ci_upper",
        "n_groups",
        "n_clusters",
        "n_bootstrap",
    ]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for metric_name in PRIMARY_METRICS:
            w.writerow(
                {
                    "metric": metric_name,
                    "point_estimate": _fmt_float(summary["point"][metric_name]),
                    "paired_ci_lower": _fmt_float(summary["ci"]["paired"][metric_name]["lower"]),
                    "paired_ci_upper": _fmt_float(summary["ci"]["paired"][metric_name]["upper"]),
                    "cluster_ci_lower": _fmt_float(summary["ci"]["cluster"][metric_name]["lower"]),
                    "cluster_ci_upper": _fmt_float(summary["ci"]["cluster"][metric_name]["upper"]),
                    "n_groups": summary["n_groups"],
                    "n_clusters": summary["n_clusters"],
                    "n_bootstrap": n_bootstrap,
                }
            )


def _write_bootstrap_by_method_csv(
    summaries: dict[str, dict[str, Any]],
    out_path: pathlib.Path,
    n_bootstrap: int,
) -> None:
    cols = [
        "method",
        "metric",
        "point_estimate",
        "paired_ci_lower",
        "paired_ci_upper",
        "cluster_ci_lower",
        "cluster_ci_upper",
        "n_groups",
        "n_clusters",
        "n_bootstrap",
    ]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for method, summary in sorted(summaries.items()):
            for metric_name in PRIMARY_METRICS:
                w.writerow(
                    {
                        "method": method,
                        "metric": metric_name,
                        "point_estimate": _fmt_float(summary["point"][metric_name]),
                        "paired_ci_lower": _fmt_float(summary["ci"]["paired"][metric_name]["lower"]),
                        "paired_ci_upper": _fmt_float(summary["ci"]["paired"][metric_name]["upper"]),
                        "cluster_ci_lower": _fmt_float(summary["ci"]["cluster"][metric_name]["lower"]),
                        "cluster_ci_upper": _fmt_float(summary["ci"]["cluster"][metric_name]["upper"]),
                        "n_groups": summary["n_groups"],
                        "n_clusters": summary["n_clusters"],
                        "n_bootstrap": n_bootstrap,
                    }
                )


def _write_bootstrap_by_method_budget_csv(
    summaries: dict[tuple[str, str], dict[str, Any]],
    out_path: pathlib.Path,
    n_bootstrap: int,
) -> None:
    cols = [
        "method",
        "budget",
        "metric",
        "point_estimate",
        "paired_ci_lower",
        "paired_ci_upper",
        "cluster_ci_lower",
        "cluster_ci_upper",
        "n_groups",
        "n_clusters",
        "n_bootstrap",
    ]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for (method, budget), summary in sorted(summaries.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            for metric_name in PRIMARY_METRICS:
                w.writerow(
                    {
                        "method": method,
                        "budget": budget,
                        "metric": metric_name,
                        "point_estimate": _fmt_float(summary["point"][metric_name]),
                        "paired_ci_lower": _fmt_float(summary["ci"]["paired"][metric_name]["lower"]),
                        "paired_ci_upper": _fmt_float(summary["ci"]["paired"][metric_name]["upper"]),
                        "cluster_ci_lower": _fmt_float(summary["ci"]["cluster"][metric_name]["lower"]),
                        "cluster_ci_upper": _fmt_float(summary["ci"]["cluster"][metric_name]["upper"]),
                        "n_groups": summary["n_groups"],
                        "n_clusters": summary["n_clusters"],
                        "n_bootstrap": n_bootstrap,
                    }
                )


def _write_distribution_summary_csv(
    overall: dict[str, Any],
    by_method: dict[str, dict[str, Any]],
    by_method_budget: dict[tuple[str, str], dict[str, Any]],
    out_path: pathlib.Path,
) -> None:
    cols = ["scope", "method", "budget", "bootstrap_type", "metric", "mean", "stdev"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()

        def _emit(scope: str, method: str, budget: str, summary: dict[str, Any]) -> None:
            for bootstrap_type in ["paired", "cluster"]:
                for metric_name in PRIMARY_METRICS:
                    vals = summary["bootstrap_distributions"][bootstrap_type][metric_name]
                    row = {
                        "scope": scope,
                        "method": method,
                        "budget": budget,
                        "bootstrap_type": bootstrap_type,
                        "metric": metric_name,
                        "mean": _fmt_float(statistics.mean(vals)),
                        "stdev": _fmt_float(statistics.stdev(vals) if len(vals) > 1 else 0.0),
                    }
                    w.writerow(row)

        _emit("overall", "", "", overall)
        for method, summary in sorted(by_method.items()):
            _emit("by_method", method, "", summary)
        for (method, budget), summary in sorted(by_method_budget.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            _emit("by_method_budget", method, budget, summary)


def _pp(value: float) -> str:
    return f"{value * 100:+.2f}pp"


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _ci_fmt(ci_obj: dict[str, float]) -> str:
    return f"[{_pct(ci_obj['lower'])}, {_pct(ci_obj['upper'])}]"


def _write_report(
    *,
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    n_bootstrap: int,
    seed: int,
    cluster_field: str,
    overall: dict[str, Any],
    by_method: dict[str, dict[str, Any]],
    overall_discordance: dict[str, int],
    by_method_discordance: dict[str, dict[str, int]],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    lines: list[str] = []
    lines.append("# Within-Method Reranking Uncertainty (Independent Cohere Validation)")
    lines.append("")
    lines.append(f"- Generated (UTC): {now}")
    lines.append(f"- Input group-details CSV: `{input_path}`")
    lines.append("- Validation context: independent/disjoint Cohere multi-seed validation artifact.")
    lines.append(f"- Bootstrap draws: {n_bootstrap}")
    lines.append(f"- RNG seed: {seed}")
    lines.append(f"- Cluster field: `{cluster_field}`")
    lines.append("")
    lines.append("This report uses two uncertainty procedures:")
    lines.append("1. Paired/group bootstrap over method-conditioned rows (evaluation unit: group).")
    lines.append(f"2. Cluster bootstrap over `{cluster_field}`, resampling all rows in each example cluster together.")
    lines.append("Cluster bootstrap is the primary uncertainty readout because it preserves shared-example dependence.")
    lines.append("")
    lines.append("`random_expected` is treated as the deterministic expected accuracy over seeds per group, not a Monte Carlo sampled run.")
    lines.append("`oracle` is a diagnostic fixed-pool upper bound on this candidate set, not a deployable policy.")
    lines.append("")

    ov_point = overall["point"]
    ov_ci_p = overall["ci"]["paired"]
    ov_ci_c = overall["ci"]["cluster"]

    lines.append("## Overall")
    lines.append("")
    lines.append(f"- n_groups: {overall['n_groups']}")
    lines.append(f"- n_clusters: {overall['n_clusters']}")
    lines.append(f"- verifier_max: {_pct(ov_point['verifier_max'])} | paired 95% CI { _ci_fmt(ov_ci_p['verifier_max']) } | cluster 95% CI { _ci_fmt(ov_ci_c['verifier_max']) }")
    lines.append(f"- random_expected: {_pct(ov_point['random_expected'])} | paired 95% CI { _ci_fmt(ov_ci_p['random_expected']) } | cluster 95% CI { _ci_fmt(ov_ci_c['random_expected']) }")
    lines.append(f"- anti_verifier: {_pct(ov_point['anti_verifier'])} | paired 95% CI { _ci_fmt(ov_ci_p['anti_verifier']) } | cluster 95% CI { _ci_fmt(ov_ci_c['anti_verifier']) }")
    lines.append(f"- oracle: {_pct(ov_point['oracle'])} | paired 95% CI { _ci_fmt(ov_ci_p['oracle']) } | cluster 95% CI { _ci_fmt(ov_ci_c['oracle']) }")
    lines.append(f"- verifier_minus_random: {_pp(ov_point['verifier_minus_random'])} | paired 95% CI { _ci_fmt(ov_ci_p['verifier_minus_random']) } | cluster 95% CI { _ci_fmt(ov_ci_c['verifier_minus_random']) }")
    lines.append(f"- verifier_minus_anti: {_pp(ov_point['verifier_minus_anti'])} | paired 95% CI { _ci_fmt(ov_ci_p['verifier_minus_anti']) } | cluster 95% CI { _ci_fmt(ov_ci_c['verifier_minus_anti']) }")
    lines.append(f"- oracle_minus_verifier: {_pp(ov_point['oracle_minus_verifier'])} | paired 95% CI { _ci_fmt(ov_ci_p['oracle_minus_verifier']) } | cluster 95% CI { _ci_fmt(ov_ci_c['oracle_minus_verifier']) }")
    lines.append("")

    lines.append("## By Method")
    lines.append("")
    for method, summary in sorted(by_method.items()):
        point = summary["point"]
        ci_p = summary["ci"]["paired"]
        ci_c = summary["ci"]["cluster"]
        lines.append(f"### {method}")
        lines.append(f"- n_groups: {summary['n_groups']}")
        lines.append(f"- n_clusters: {summary['n_clusters']}")
        lines.append(f"- verifier_max: {_pct(point['verifier_max'])} | paired { _ci_fmt(ci_p['verifier_max']) } | cluster { _ci_fmt(ci_c['verifier_max']) }")
        lines.append(f"- random_expected: {_pct(point['random_expected'])} | paired { _ci_fmt(ci_p['random_expected']) } | cluster { _ci_fmt(ci_c['random_expected']) }")
        lines.append(f"- anti_verifier: {_pct(point['anti_verifier'])} | paired { _ci_fmt(ci_p['anti_verifier']) } | cluster { _ci_fmt(ci_c['anti_verifier']) }")
        lines.append(f"- oracle: {_pct(point['oracle'])} | paired { _ci_fmt(ci_p['oracle']) } | cluster { _ci_fmt(ci_c['oracle']) }")
        lines.append(f"- verifier_minus_random: {_pp(point['verifier_minus_random'])} | paired { _ci_fmt(ci_p['verifier_minus_random']) } | cluster { _ci_fmt(ci_c['verifier_minus_random']) }")
        lines.append(f"- verifier_minus_anti: {_pp(point['verifier_minus_anti'])} | paired { _ci_fmt(ci_p['verifier_minus_anti']) } | cluster { _ci_fmt(ci_c['verifier_minus_anti']) }")
        lines.append(f"- oracle_minus_verifier: {_pp(point['oracle_minus_verifier'])} | paired { _ci_fmt(ci_p['oracle_minus_verifier']) } | cluster { _ci_fmt(ci_c['oracle_minus_verifier']) }")
        lines.append("")

    conservative_lo = ov_ci_c["verifier_minus_random"]["lower"]
    if conservative_lo > 0:
        stability_line = (
            "Conservative interpretation: verifier gain over random appears statistically "
            "stable under cluster bootstrap (lower bound > 0)."
        )
    else:
        stability_line = (
            "Conservative interpretation: verifier gain over random remains uncertain "
            "under cluster bootstrap (lower bound <= 0)."
        )

    lines.append("## Conservative Caveat")
    lines.append("")
    lines.append(stability_line)
    lines.append("")

    lines.append("## Optional Binary Discordance (Verifier vs Anti-Verifier)")
    lines.append("")
    lines.append("These 2x2 counts compare realized binary outcomes only (`verifier_max` vs `anti_verifier`).")
    lines.append("No McNemar test is reported here; bootstrap CIs remain primary.")
    lines.append("")
    lines.append(
        f"- Overall: both_correct={overall_discordance['both_correct']}, "
        f"verifier_only={overall_discordance['verifier_only_correct']}, "
        f"anti_only={overall_discordance['anti_only_correct']}, "
        f"both_wrong={overall_discordance['both_wrong']} (n={overall_discordance['n_groups']})"
    )
    for method, d in sorted(by_method_discordance.items()):
        lines.append(
            f"- {method}: both_correct={d['both_correct']}, "
            f"verifier_only={d['verifier_only_correct']}, "
            f"anti_only={d['anti_only_correct']}, "
            f"both_wrong={d['both_wrong']} (n={d['n_groups']})"
        )
    lines.append("")

    output_path.write_text("\n".join(lines) + "\n")


def _strip_distributions(summary: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(summary)
    cleaned.pop("bootstrap_distributions", None)
    return cleaned


def run_analysis(
    *,
    group_details_csv: pathlib.Path,
    output_dir: pathlib.Path,
    n_bootstrap: int,
    seed: int,
    cluster_field: str,
    method_field: str,
    budget_field: str,
) -> dict[str, Any]:
    rows, resolved_columns = load_group_details(
        group_details_csv,
        cluster_field=cluster_field,
        method_field=method_field,
        budget_field=budget_field,
    )

    overall = summarize_with_uncertainty(rows, n_bootstrap=n_bootstrap, seed=seed)

    by_method_items, by_method_budget_items = _aggregate_subsets(rows)
    by_method = {
        method: summarize_with_uncertainty(
            subset,
            n_bootstrap=n_bootstrap,
            seed=seed + 1000 + i,
        )
        for i, (method, subset) in enumerate(by_method_items)
    }
    by_method_budget = {
        key: summarize_with_uncertainty(
            subset,
            n_bootstrap=n_bootstrap,
            seed=seed + 2000 + i,
        )
        for i, (key, subset) in enumerate(by_method_budget_items)
    }
    overall_discordance = compute_verifier_vs_anti_discordance(rows)
    by_method_discordance = {
        method: compute_verifier_vs_anti_discordance(subset)
        for method, subset in by_method_items
    }
    by_method_budget_discordance = {
        key: compute_verifier_vs_anti_discordance(subset)
        for key, subset in by_method_budget_items
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    _write_bootstrap_overall_csv(overall, output_dir / "bootstrap_overall.csv", n_bootstrap)
    _write_bootstrap_by_method_csv(by_method, output_dir / "bootstrap_by_method.csv", n_bootstrap)
    _write_bootstrap_by_method_budget_csv(
        by_method_budget,
        output_dir / "bootstrap_by_method_budget.csv",
        n_bootstrap,
    )
    _write_distribution_summary_csv(
        overall,
        by_method,
        by_method_budget,
        output_dir / "bootstrap_distribution_summary.csv",
    )
    _write_report(
        input_path=group_details_csv,
        output_path=output_dir / "uncertainty_report.md",
        n_bootstrap=n_bootstrap,
        seed=seed,
        cluster_field=cluster_field,
        overall=overall,
        by_method=by_method,
        overall_discordance=overall_discordance,
        by_method_discordance=by_method_discordance,
    )

    metrics_obj = {
        "input": {
            "group_details_csv": str(group_details_csv),
            "resolved_columns": resolved_columns,
            "cluster_field": cluster_field,
            "method_field": method_field,
            "budget_field": budget_field,
        },
        "bootstrap": {
            "n_bootstrap": n_bootstrap,
            "seed": seed,
            "types": ["paired", "cluster"],
        },
        "discordance_verifier_vs_anti": {
            "overall": overall_discordance,
            "by_method": by_method_discordance,
            "by_method_budget": {
                f"{k[0]}|{k[1]}": v for k, v in by_method_budget_discordance.items()
            },
        },
        "overall": _strip_distributions(overall),
        "by_method": {k: _strip_distributions(v) for k, v in by_method.items()},
        "by_method_budget": {
            f"{k[0]}|{k[1]}": _strip_distributions(v) for k, v in by_method_budget.items()
        },
    }

    with open(output_dir / "metrics.json", "w") as f:
        json.dump(metrics_obj, f, indent=2)

    return {
        "rows": rows,
        "resolved_columns": resolved_columns,
        "overall": overall,
        "by_method": by_method,
        "by_method_budget": by_method_budget,
        "discordance_overall": overall_discordance,
        "discordance_by_method": by_method_discordance,
        "discordance_by_method_budget": by_method_budget_discordance,
        "metrics_obj": metrics_obj,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    group_details_csv = pathlib.Path(args.group_details_csv)
    output_dir = pathlib.Path(args.output_dir)

    if not group_details_csv.exists():
        print(f"[error] Missing input CSV: {group_details_csv}")
        return 1

    result = run_analysis(
        group_details_csv=group_details_csv,
        output_dir=output_dir,
        n_bootstrap=args.n_bootstrap,
        seed=args.seed,
        cluster_field=args.cluster_field,
        method_field=args.method_field,
        budget_field=args.budget_field,
    )

    overall_point = result["overall"]["point"]
    print(f"[done] Wrote uncertainty outputs to: {output_dir}")
    print(
        "[summary] "
        f"n_groups={result['overall']['n_groups']} "
        f"verifier={overall_point['verifier_max']:.4f} "
        f"random={overall_point['random_expected']:.4f} "
        f"anti={overall_point['anti_verifier']:.4f} "
        f"oracle={overall_point['oracle']:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
