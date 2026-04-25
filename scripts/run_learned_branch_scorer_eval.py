#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.learned_branch_scorer_utils import as_int, group_by_case, read_csv, write_csv


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Offline reranking diagnostic evaluation for learned_branch_scorer_v1.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--predictions", required=True, help="Path to training predictions.csv")
    p.add_argument("--prefer-split", default="joint_holdout")
    p.add_argument("--prefer-model", default="")
    return p.parse_args()


def _pick_best(candidates: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    if not candidates:
        return None
    return max(candidates, key=lambda r: float(r.get(key, 0.0)))


def _method_pick(candidates: list[dict[str, Any]], method_name: str) -> dict[str, Any] | None:
    return next((r for r in candidates if str(r.get("method")) == method_name), None)


def _support_pick(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    return _pick_best(candidates, "answer_group_support_count")


def _metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    n = len(rows)
    if n == 0:
        return {
            "n_cases": 0.0,
            "accuracy": 0.0,
            "present_not_selected_rate": 0.0,
            "absent_from_tree_rate": 0.0,
            "gold_present_rate": 0.0,
            "top1_learned_selection_accuracy_gold_present": 0.0,
        }
    acc = sum(as_int(r.get("is_correct"), 0) for r in rows) / n
    pns = sum(as_int(r.get("present_not_selected"), 0) for r in rows) / n
    aft = sum(as_int(r.get("absent_from_tree"), 0) for r in rows) / n
    gpr = sum(as_int(r.get("gold_present"), 0) for r in rows) / n
    gp = [r for r in rows if as_int(r.get("gold_present"), 0) == 1]
    gp_acc = sum(as_int(r.get("is_correct"), 0) for r in gp) / max(1, len(gp))
    return {
        "n_cases": float(n),
        "accuracy": float(acc),
        "present_not_selected_rate": float(pns),
        "absent_from_tree_rate": float(aft),
        "gold_present_rate": float(gpr),
        "top1_learned_selection_accuracy_gold_present": float(gp_acc),
    }


def main() -> None:
    args = parse_args()
    rows = read_csv(REPO_ROOT / args.predictions)
    if not rows:
        raise SystemExit("No rows found in predictions.")

    split_filtered = [r for r in rows if str(r.get("split")) == args.prefer_split]
    rows = split_filtered or rows

    if args.prefer_model:
        model_filtered = [r for r in rows if str(r.get("model")) == args.prefer_model]
        rows = model_filtered or rows
    else:
        ranked = sorted(rows, key=lambda r: (str(r.get("split")), float(r.get("score", 0.0))), reverse=True)
        chosen_model = str(ranked[0].get("model", "")) if ranked else ""
        rows = [r for r in rows if str(r.get("model")) == chosen_model] or rows

    grouped = group_by_case(rows)

    eval_rows: list[dict[str, Any]] = []
    per_case_summary: list[dict[str, Any]] = []

    for key, cell in grouped.items():
        provider, seed, budget, dataset, example_id = key
        gold_present = int(any(as_int(r.get("label"), 0) == 1 for r in cell))

        strict = _method_pick(cell, "strict_f3")
        external = _method_pick(cell, "external_l1_max")
        direct_reserve = _method_pick(cell, "strict_f3_direct_reserve_gate_rerank_v1")
        support = _support_pick(cell)
        learned = _pick_best(cell, "score")

        # Learned-on-direct-reserve proxy: prioritize candidates already in direct-reserve blend when present.
        dr_pool = [
            r
            for r in cell
            if str(r.get("method")) in {"strict_f3_direct_reserve_gate_rerank_v1", "strict_f3", "external_l1_max"}
        ]
        learned_on_dr = _pick_best(dr_pool or cell, "score")

        selections = {
            "strict_f3": strict,
            "external_l1_max": external,
            "support_rerank_proxy": support,
            "learned_branch_scorer_v1": learned,
            "direct_reserve_gate_rerank_proxy": direct_reserve,
            "learned_on_direct_reserve_proxy": learned_on_dr,
        }

        for method_name, pick in selections.items():
            if pick is None:
                continue
            is_correct = as_int(pick.get("label"), 0)
            absent = int(gold_present == 0)
            present_not_selected = int(gold_present == 1 and is_correct == 0)
            eval_rows.append(
                {
                    "provider": provider,
                    "dataset": dataset,
                    "seed": seed,
                    "budget": budget,
                    "example_id": example_id,
                    "method": method_name,
                    "is_correct": is_correct,
                    "gold_present": gold_present,
                    "absent_from_tree": absent,
                    "present_not_selected": present_not_selected,
                    "selected_candidate_method": pick.get("method", ""),
                    "selected_score": float(pick.get("score", 0.0)),
                    "selected_support": as_int(pick.get("answer_group_support_count"), 0),
                }
            )

        per_case_summary.append(
            {
                "provider": provider,
                "dataset": dataset,
                "seed": seed,
                "budget": budget,
                "example_id": example_id,
                "gold_present": gold_present,
                "strict_f3_correct": as_int(strict.get("label"), 0) if strict else -1,
                "external_l1_max_correct": as_int(external.get("label"), 0) if external else -1,
                "learned_correct": as_int(learned.get("label"), 0) if learned else -1,
            }
        )

    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eval_rows:
        by_method[str(row["method"])].append(row)

    methods = [
        "strict_f3",
        "external_l1_max",
        "support_rerank_proxy",
        "learned_branch_scorer_v1",
        "direct_reserve_gate_rerank_proxy",
        "learned_on_direct_reserve_proxy",
    ]

    summary = []
    for method in methods:
        m = _metrics(by_method.get(method, []))
        m["method"] = method
        summary.append(m)

    per_budget_seed = []
    for budget in sorted({as_int(r.get("budget"), -1) for r in eval_rows}):
        for seed in sorted({as_int(r.get("seed"), -1) for r in eval_rows}):
            for method in methods:
                subset = [
                    r
                    for r in by_method.get(method, [])
                    if as_int(r.get("budget"), -1) == budget and as_int(r.get("seed"), -1) == seed
                ]
                m = _metrics(subset)
                m.update({"budget": budget, "seed": seed, "method": method})
                per_budget_seed.append(m)

    paired = []
    piv: dict[tuple[str, int, int, str], dict[str, int]] = defaultdict(dict)
    for row in eval_rows:
        key = (str(row.get("dataset")), as_int(row.get("seed"), -1), as_int(row.get("budget"), -1), str(row.get("example_id")))
        piv[key][str(row.get("method"))] = as_int(row.get("is_correct"), 0)
    for key, val in piv.items():
        if "learned_branch_scorer_v1" not in val:
            continue
        paired.append(
            {
                "dataset": key[0],
                "seed": key[1],
                "budget": key[2],
                "example_id": key[3],
                "delta_vs_strict_f3": val.get("learned_branch_scorer_v1", 0) - val.get("strict_f3", 0),
                "delta_vs_external_l1_max": val.get("learned_branch_scorer_v1", 0) - val.get("external_l1_max", 0),
            }
        )

    gold_present_subset = [r for r in eval_rows if as_int(r.get("gold_present"), 0) == 1]
    gp_summary = []
    for method in methods:
        subset = [r for r in gold_present_subset if str(r.get("method")) == method]
        m = _metrics(subset)
        m["method"] = method
        gp_summary.append(m)

    out_dir = REPO_ROOT / "outputs" / f"learned_branch_scorer_eval_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "predictions_with_scores.csv", eval_rows)
    write_csv(out_dir / "summary.csv", summary)
    write_csv(out_dir / "per_budget_seed_summary.csv", per_budget_seed)
    write_csv(out_dir / "paired_deltas.csv", paired)
    write_csv(out_dir / "gold_present_subset_metrics.csv", gp_summary)

    readme = {
        "diagnostic_only": True,
        "selected_split": args.prefer_split,
        "comparisons": methods,
        "note": "Learned scorer mainly targets present_not_selected when gold is already present.",
        "limitation": "Absent-from-tree failures are not directly solved by this reranking-only diagnostic pass.",
    }
    (out_dir / "README.md").write_text(json.dumps(readme, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote: {out_dir}")


if __name__ == "__main__":
    main()
