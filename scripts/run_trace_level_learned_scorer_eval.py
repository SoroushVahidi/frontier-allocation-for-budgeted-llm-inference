#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
    p = argparse.ArgumentParser(description="Offline selection comparison on trace-level candidate pools.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--predictions", required=True)
    p.add_argument("--prefer-split", default="")
    p.add_argument("--prefer-model", default="")
    return p.parse_args()


def _pick_best(rows: list[dict[str, Any]], score_key: str) -> dict[str, Any] | None:
    if not rows:
        return None
    return max(rows, key=lambda r: float(r.get(score_key, 0.0)))


def _gold_present(cell: list[dict[str, Any]]) -> int:
    return int(any(as_int(r.get("label"), 0) == 1 for r in cell))


def _selector_rows_for_case(cell: list[dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    current = next((r for r in cell if as_int(r.get("was_selected_by_current_controller"), 0) == 1), None)
    if current is None:
        current = next((r for r in cell if str(r.get("method")) == "strict_f3"), None)
    support = _pick_best(cell, "answer_group_support")
    learned = _pick_best(cell, "score")

    # Optional learned answer-group aggregation by summing learned scores per normalized answer.
    ag_scores: dict[str, float] = defaultdict(float)
    for r in cell:
        ag_scores[str(r.get("candidate_answer_normalized", ""))] += float(r.get("score", 0.0))
    best_group = sorted(ag_scores.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if ag_scores else ""
    learned_ag = next((r for r in sorted(cell, key=lambda r: float(r.get("score", 0.0)), reverse=True) if str(r.get("candidate_answer_normalized", "")) == best_group), None)

    return {
        "current_controller_selection": current,
        "support_based_selection": support,
        "learned_candidate_scorer": learned,
        "learned_answer_group_aggregation": learned_ag,
    }


def _metrics(rows: list[dict[str, Any]], selector: str) -> dict[str, Any]:
    subset = [r for r in rows if str(r.get("selector")) == selector]
    n_cases = len(subset)
    gold_present_cases = sum(as_int(r.get("gold_present"), 0) for r in subset)
    selected_gold = sum(as_int(r.get("selected_gold"), 0) for r in subset)
    present_not_selected = sum(as_int(r.get("present_not_selected"), 0) for r in subset)
    return {
        "selector": selector,
        "n_cases": n_cases,
        "gold_present_cases": gold_present_cases,
        "selected_gold_rate": selected_gold / max(1, n_cases),
        "accuracy_gold_present": selected_gold / max(1, gold_present_cases),
        "present_not_selected_rate": present_not_selected / max(1, gold_present_cases),
    }


def main() -> None:
    args = parse_args()
    rows = read_csv(REPO_ROOT / args.predictions)
    if not rows:
        raise SystemExit("No prediction rows found.")

    if args.prefer_split:
        filtered = [r for r in rows if str(r.get("split")) == args.prefer_split]
        rows = filtered or rows
    if args.prefer_model:
        filtered = [r for r in rows if str(r.get("model")) == args.prefer_model]
        rows = filtered or rows

    if not args.prefer_model:
        # choose model with highest avg score range sanity; fallback to first model.
        models = sorted(set(str(r.get("model", "")) for r in rows))
        if models:
            rows = [r for r in rows if str(r.get("model")) == models[0]]

    grouped = group_by_case(rows)

    case_level_selection: list[dict[str, Any]] = []
    selector_comparison: list[dict[str, Any]] = []
    degradation_cases: list[dict[str, Any]] = []

    for case_key, cell in grouped.items():
        selectors = _selector_rows_for_case(cell)
        gp = _gold_present(cell)
        for selector_name, pick in selectors.items():
            selected_gold = as_int(pick.get("label"), 0) if pick else 0
            present_not_selected = int(gp == 1 and selected_gold == 0)
            record = {
                "provider": case_key[0],
                "seed": case_key[1],
                "budget": case_key[2],
                "dataset": case_key[3],
                "example_id": case_key[4],
                "selector": selector_name,
                "selected_answer": pick.get("candidate_answer_normalized", "") if pick else "",
                "selected_method": pick.get("method", "") if pick else "",
                "selected_score": float(pick.get("score", 0.0)) if pick else 0.0,
                "gold_present": gp,
                "selected_gold": selected_gold,
                "present_not_selected": present_not_selected,
            }
            case_level_selection.append(record)
        current_gold = as_int(selectors["current_controller_selection"].get("label"), 0) if selectors["current_controller_selection"] else 0
        learned_gold = as_int(selectors["learned_candidate_scorer"].get("label"), 0) if selectors["learned_candidate_scorer"] else 0
        if gp == 1 and current_gold == 1 and learned_gold == 0:
            degradation_cases.append(
                {
                    "provider": case_key[0],
                    "seed": case_key[1],
                    "budget": case_key[2],
                    "dataset": case_key[3],
                    "example_id": case_key[4],
                    "current_selected_answer": selectors["current_controller_selection"].get("candidate_answer_normalized", "") if selectors["current_controller_selection"] else "",
                    "learned_selected_answer": selectors["learned_candidate_scorer"].get("candidate_answer_normalized", "") if selectors["learned_candidate_scorer"] else "",
                }
            )

    selector_names = [
        "current_controller_selection",
        "support_based_selection",
        "learned_candidate_scorer",
        "learned_answer_group_aggregation",
    ]
    summary = [_metrics(case_level_selection, selector=s) for s in selector_names]

    by_group = defaultdict(list)
    for r in case_level_selection:
        key = (str(r.get("selector")), as_int(r.get("seed"), -1), as_int(r.get("budget"), -1), str(r.get("dataset", "")))
        by_group[key].append(r)
    for (selector, seed, budget, dataset), rows_group in by_group.items():
        m = _metrics(rows_group, selector=selector)
        m.update({"seed": seed, "budget": budget, "dataset": dataset})
        selector_comparison.append(m)

    # top-k learned recall from ranked learned scores
    topk_rows = []
    for case_key, cell in grouped.items():
        ranked = sorted(cell, key=lambda r: float(r.get("score", 0.0)), reverse=True)
        gp = _gold_present(cell)
        topk_rows.append(
            {
                "provider": case_key[0],
                "seed": case_key[1],
                "budget": case_key[2],
                "dataset": case_key[3],
                "example_id": case_key[4],
                "gold_present": gp,
                "top1_gold": int(any(as_int(r.get("label"), 0) == 1 for r in ranked[:1])) if gp else 0,
                "top2_gold": int(any(as_int(r.get("label"), 0) == 1 for r in ranked[:2])) if gp else 0,
                "top3_gold": int(any(as_int(r.get("label"), 0) == 1 for r in ranked[:3])) if gp else 0,
            }
        )

    gp_subset = [r for r in case_level_selection if as_int(r.get("gold_present"), 0) == 1]
    gold_present_subset_metrics = [_metrics(gp_subset, selector=s) for s in selector_names]

    out_dir = REPO_ROOT / "outputs" / f"trace_level_learned_scorer_eval_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "summary.csv", summary)
    write_csv(out_dir / "case_level_selection.csv", case_level_selection)
    write_csv(out_dir / "selector_comparison.csv", selector_comparison)
    write_csv(out_dir / "degradation_cases.csv", degradation_cases)
    write_csv(out_dir / "gold_present_subset_metrics.csv", gold_present_subset_metrics)
    write_csv(out_dir / "topk_learned_recall.csv", topk_rows)

    readme = "\n".join(
        [
            f"# Trace-level learned scorer eval ({args.timestamp})",
            "",
            "Compares selectors on a shared candidate pool:",
            "1) current controller selection",
            "2) support-based answer-group selection",
            "3) learned candidate scorer",
            "4) learned answer-group aggregation",
        ]
    )
    (out_dir / "README.md").write_text(readme + "\n", encoding="utf-8")

    print(f"Wrote: {out_dir}")


if __name__ == "__main__":
    main()
