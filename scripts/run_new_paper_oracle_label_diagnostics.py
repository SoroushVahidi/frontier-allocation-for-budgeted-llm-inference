#!/usr/bin/env python3
"""Lightweight diagnostics for approximate bounded oracle-ish continuation labels."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _corr(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mx, my = mean(xs), mean(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 1e-12 or vy <= 1e-12:
        return 0.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(vx * vy)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Diagnose oracle-ish branch labels")
    p.add_argument("--branch-labels", required=True)
    p.add_argument("--pairwise", default=None)
    p.add_argument("--output-root", default="outputs/new_paper/oracle_label_diagnostics")
    p.add_argument("--run-id", default=None)
    p.add_argument("--tie-margin", type=float, default=0.02)
    p.add_argument("--compare-branch-labels", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_jsonl(Path(args.branch_labels))
    pair_rows = _load_jsonl(Path(args.pairwise)) if args.pairwise else []

    by_decision: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for r in rows:
        by_decision.setdefault((int(r["episode_id"]), int(r["decision_id"])), []).append(r)

    diagnostics_rows: list[dict[str, Any]] = []
    near_tie_decisions = 0
    one_feature_dominance = 0
    proxy_top_match = 0
    score_top_match = 0

    for key, group in by_decision.items():
        vals = [float(g["approx_oracle_continuation_value"]) for g in group]
        proxy_vals = [float(g.get("proxy_continuation_value", 0.0)) for g in group]
        score_vals = [float(g.get("score", 0.0)) for g in group]
        if len(vals) < 2:
            continue
        sorted_idx = sorted(range(len(group)), key=lambda i: vals[i], reverse=True)
        top, second = vals[sorted_idx[0]], vals[sorted_idx[1]]
        margin = top - second
        spread = max(vals) - min(vals)
        near_tie = int(margin <= 2.0 * float(args.tie_margin))
        near_tie_decisions += near_tie

        oracle_top = group[sorted_idx[0]]["branch_id"]
        proxy_top = group[max(range(len(group)), key=lambda i: proxy_vals[i])]["branch_id"]
        score_top = group[max(range(len(group)), key=lambda i: score_vals[i])]["branch_id"]
        proxy_top_match += int(oracle_top == proxy_top)
        score_top_match += int(oracle_top == score_top)

        max_abs_corr = max(
            abs(_corr(vals, score_vals)),
            abs(_corr(vals, proxy_vals)),
            abs(_corr(vals, [float(g.get("depth", 0.0)) for g in group])),
            abs(_corr(vals, [float(g.get("verify_count", 0.0)) for g in group])),
        )
        one_feature_dominance += int(max_abs_corr >= 0.9)

        diagnostics_rows.append(
            {
                "episode_id": key[0],
                "decision_id": key[1],
                "n_branches": len(group),
                "remaining_budget": int(group[0].get("remaining_budget", 0)),
                "depth_mean": sum(float(g.get("depth", 0.0)) for g in group) / len(group),
                "action_history_len_mean": sum(float(g.get("action_history_len", 0.0)) for g in group) / len(group),
                "oracle_top_margin": margin,
                "oracle_value_spread": spread,
                "near_tie": near_tie,
                "oracle_proxy_corr": _corr(vals, proxy_vals),
                "oracle_score_corr": _corr(vals, score_vals),
                "oracle_rollout_std_mean": sum(float(g.get("rollout_value_std", 0.0)) for g in group) / len(group),
            }
        )

    rerun_agreement = None
    if args.compare_branch_labels:
        other_rows = _load_jsonl(Path(args.compare_branch_labels))
        key_self = {(int(r["episode_id"]), int(r["decision_id"]), str(r["branch_id"])): float(r["approx_oracle_continuation_value"]) for r in rows}
        key_other = {(int(r["episode_id"]), int(r["decision_id"]), str(r["branch_id"])): float(r["approx_oracle_continuation_value"]) for r in other_rows}
        shared = sorted(set(key_self) & set(key_other))
        if shared:
            a = [key_self[k] for k in shared]
            b = [key_other[k] for k in shared]
            rerun_agreement = {
                "shared_rows": len(shared),
                "value_correlation": _corr(a, b),
                "mean_abs_delta": sum(abs(x - y) for x, y in zip(a, b)) / len(shared),
            }

    def _pair_tie_flag(r: dict[str, Any]) -> int:
        return int(r.get("tie", r.get("oracle_tie", 0)))

    def _pair_uncertain_flag(r: dict[str, Any]) -> int:
        return int(r.get("tie_or_uncertain", r.get("oracle_tie", 0)))

    tie_rate_pairs = sum(_pair_tie_flag(r) for r in pair_rows) / max(1, len(pair_rows)) if pair_rows else None
    uncertain_rate_pairs = sum(_pair_uncertain_flag(r) for r in pair_rows) / max(1, len(pair_rows)) if pair_rows else None

    summary = {
        "label_name": "approximate bounded oracle-ish continuation labels",
        "n_branch_rows": len(rows),
        "n_decisions": len(diagnostics_rows),
        "decision_near_tie_rate": near_tie_decisions / max(1, len(diagnostics_rows)),
        "decision_mean_top_margin": sum(r["oracle_top_margin"] for r in diagnostics_rows) / max(1, len(diagnostics_rows)),
        "decision_mean_value_spread": sum(r["oracle_value_spread"] for r in diagnostics_rows) / max(1, len(diagnostics_rows)),
        "pair_tie_rate": tie_rate_pairs,
        "pair_tie_or_uncertain_rate": uncertain_rate_pairs,
        "oracle_top_match_proxy_rate": proxy_top_match / max(1, len(diagnostics_rows)),
        "oracle_top_match_score_rate": score_top_match / max(1, len(diagnostics_rows)),
        "one_feature_dominance_rate": one_feature_dominance / max(1, len(diagnostics_rows)),
        "rerun_agreement": rerun_agreement,
    }

    with (out_dir / "oracle_label_diagnostics.csv").open("w", encoding="utf-8", newline="") as f:
        if diagnostics_rows:
            writer = csv.DictWriter(f, fieldnames=list(diagnostics_rows[0].keys()))
            writer.writeheader()
            writer.writerows(diagnostics_rows)
        else:
            f.write("")

    (out_dir / "oracle_label_diagnostic_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md = [
        f"# Oracle label diagnostics ({run_id})",
        "",
        "Diagnostics are for **approximate bounded oracle-ish continuation labels** (not exact global oracle truth).",
        f"- Branch rows: {summary['n_branch_rows']}",
        f"- Decisions with >=2 branches: {summary['n_decisions']}",
        f"- Decision near-tie rate: {summary['decision_near_tie_rate']:.4f}",
        f"- Mean top margin: {summary['decision_mean_top_margin']:.4f}",
        f"- Mean value spread: {summary['decision_mean_value_spread']:.4f}",
        f"- Pair tie rate: {summary['pair_tie_rate'] if summary['pair_tie_rate'] is not None else 'n/a'}",
        f"- Pair tie/uncertain rate: {summary['pair_tie_or_uncertain_rate'] if summary['pair_tie_or_uncertain_rate'] is not None else 'n/a'}",
        f"- Oracle top-branch match with proxy top: {summary['oracle_top_match_proxy_rate']:.4f}",
        f"- Oracle top-branch match with score top: {summary['oracle_top_match_score_rate']:.4f}",
        f"- One-feature dominance rate (|corr|>=0.9): {summary['one_feature_dominance_rate']:.4f}",
    ]
    if rerun_agreement:
        md.extend(
            [
                "",
                "## Cheap rerun stability",
                f"- Shared rows: {rerun_agreement['shared_rows']}",
                f"- Value correlation across rerun labels: {rerun_agreement['value_correlation']:.4f}",
                f"- Mean absolute value delta: {rerun_agreement['mean_abs_delta']:.4f}",
            ]
        )
    (out_dir / "oracle_label_diagnostic_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"run_id": run_id, "out_dir": str(out_dir), "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
