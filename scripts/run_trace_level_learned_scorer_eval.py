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
    p.add_argument("--output-prefix", default="trace_level_learned_scorer_eval")
    return p.parse_args()


def _pick_best(rows: list[dict[str, Any]], score_key: str) -> dict[str, Any] | None:
    return max(rows, key=lambda r: float(r.get(score_key, 0.0))) if rows else None


def _gold_present(cell: list[dict[str, Any]]) -> int:
    return int(any(as_int(r.get("label"), 0) == 1 for r in cell))


def _selector_rows_for_case(cell: list[dict[str, Any]], model_filter: str = "") -> dict[str, dict[str, Any] | None]:
    current = next((r for r in cell if as_int(r.get("was_selected_by_current_controller"), 0) == 1), None)
    if current is None:
        current = next((r for r in cell if str(r.get("method")) == "strict_f3"), None)
    support = _pick_best(cell, "answer_group_support")

    learned_pool = [r for r in cell if not model_filter or str(r.get("model", "")) == model_filter]
    learned = _pick_best(learned_pool, "score")

    ag_scores: dict[str, float] = defaultdict(float)
    for r in learned_pool:
        ag_scores[str(r.get("candidate_answer_normalized", ""))] += float(r.get("score", 0.0))
    best_group = sorted(ag_scores.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if ag_scores else ""
    learned_ag = next((r for r in sorted(learned_pool, key=lambda r: float(r.get("score", 0.0)), reverse=True) if str(r.get("candidate_answer_normalized", "")) == best_group), None)

    pairwise = _pick_best([r for r in cell if str(r.get("model", "")) == "pairwise_logistic"], "score")

    return {
        "current_controller_selector": current,
        "support_based_answer_group_selector": support,
        "learned_candidate_scorer": learned,
        "learned_answer_group_scorer": learned_ag,
        "pairwise_bt_selector": pairwise,
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
        rows = [r for r in rows if str(r.get("split")) == args.prefer_split] or rows

    model_for_learned = args.prefer_model
    if not model_for_learned:
        models = sorted(set(str(r.get("model", "")) for r in rows if str(r.get("model", "")) != "pairwise_logistic"))
        model_for_learned = models[0] if models else ""

    grouped = group_by_case(rows)
    case_level_selection: list[dict[str, Any]] = []
    degradation_cases: list[dict[str, Any]] = []

    for case_key, cell in grouped.items():
        selectors = _selector_rows_for_case(cell, model_filter=model_for_learned)
        gp = _gold_present(cell)
        for selector_name, pick in selectors.items():
            selected_gold = as_int(pick.get("label"), 0) if pick else 0
            present_not_selected = int(gp == 1 and selected_gold == 0)
            case_level_selection.append(
                {
                    "provider": case_key[0],
                    "seed": case_key[1],
                    "budget": case_key[2],
                    "dataset": case_key[3],
                    "example_id": case_key[4],
                    "stratum": str((pick or {}).get("stratum", "unknown")),
                    "selector": selector_name,
                    "selected_answer": pick.get("candidate_answer_normalized", "") if pick else "",
                    "selected_method": pick.get("method", "") if pick else "",
                    "selected_model": pick.get("model", "") if pick else "",
                    "selected_score": float(pick.get("score", 0.0)) if pick else 0.0,
                    "gold_present": gp,
                    "selected_gold": selected_gold,
                    "present_not_selected": present_not_selected,
                }
            )

        current_gold = as_int(selectors["current_controller_selector"].get("label"), 0) if selectors["current_controller_selector"] else 0
        learned_gold = as_int(selectors["learned_candidate_scorer"].get("label"), 0) if selectors["learned_candidate_scorer"] else 0
        if gp == 1 and current_gold == 1 and learned_gold == 0:
            degradation_cases.append(
                {
                    "provider": case_key[0],
                    "seed": case_key[1],
                    "budget": case_key[2],
                    "dataset": case_key[3],
                    "example_id": case_key[4],
                    "current_selected_answer": selectors["current_controller_selector"].get("candidate_answer_normalized", "") if selectors["current_controller_selector"] else "",
                    "learned_selected_answer": selectors["learned_candidate_scorer"].get("candidate_answer_normalized", "") if selectors["learned_candidate_scorer"] else "",
                }
            )

    selector_names = [
        "current_controller_selector",
        "support_based_answer_group_selector",
        "learned_candidate_scorer",
        "learned_answer_group_scorer",
        "pairwise_bt_selector",
    ]
    summary = [_metrics(case_level_selection, selector=s) for s in selector_names]

    by_group = defaultdict(list)
    for r in case_level_selection:
        key = (str(r.get("selector")), as_int(r.get("seed"), -1), as_int(r.get("budget"), -1), str(r.get("dataset", "")))
        by_group[key].append(r)
    selector_comparison = []
    for (selector, seed, budget, dataset), cell in by_group.items():
        m = _metrics(cell, selector=selector)
        m.update({"seed": seed, "budget": budget, "dataset": dataset})
        selector_comparison.append(m)

    gp_subset = [r for r in case_level_selection if as_int(r.get("gold_present"), 0) == 1]
    gold_present_subset_metrics = [_metrics(gp_subset, selector=s) for s in selector_names]

    coverage_vs_selection_breakdown = [
        {
            "n_cases": len(grouped),
            "gold_present_cases": sum(_gold_present(cell) for cell in grouped.values()),
            "gold_absent_cases": sum(1 - _gold_present(cell) for cell in grouped.values()),
            "current_present_not_selected": sum(as_int(r.get("present_not_selected"), 0) for r in case_level_selection if r.get("selector") == "current_controller_selector"),
            "learned_present_not_selected": sum(as_int(r.get("present_not_selected"), 0) for r in case_level_selection if r.get("selector") == "learned_candidate_scorer"),
        }
    ]

    per_stratum_summary = []
    for stratum in sorted(set(str(r.get("stratum", "unknown")) for r in case_level_selection)):
        for selector in selector_names:
            cell = [r for r in case_level_selection if str(r.get("stratum")) == stratum and str(r.get("selector")) == selector]
            if not cell:
                continue
            m = _metrics(cell, selector=selector)
            m["stratum"] = stratum
            per_stratum_summary.append(m)

    split_assignments = [
        {
            "split": str(r.get("split", "")),
            "example_id": str(r.get("example_id", "")),
            "model": str(r.get("model", "")),
        }
        for r in rows
    ]

    out_dir = REPO_ROOT / "outputs" / f"{args.output_prefix}_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "summary.csv", summary)
    write_csv(out_dir / "selector_comparison.csv", selector_comparison)
    write_csv(out_dir / "case_level_selection.csv", case_level_selection)
    write_csv(out_dir / "gold_present_subset_metrics.csv", gold_present_subset_metrics)
    write_csv(out_dir / "coverage_vs_selection_breakdown.csv", coverage_vs_selection_breakdown)
    write_csv(out_dir / "degradation_cases.csv", degradation_cases)
    write_csv(out_dir / "per_stratum_summary.csv", per_stratum_summary)
    write_csv(out_dir / "split_assignments.csv", split_assignments)

    readme = "\n".join(
        [
            f"# Trace-level learned scorer eval ({args.timestamp})",
            "",
            "Selectors compared:",
            "1) current controller selector",
            "2) support-based answer-group selector",
            "3) learned candidate scorer",
            "4) learned answer-group scorer",
            "5) pairwise/BT-style selector",
            "",
            f"Preferred learned model: `{model_for_learned}`",
        ]
    )
    (out_dir / "README.md").write_text(readme + "\n", encoding="utf-8")
    print(f"Wrote: {out_dir}")


if __name__ == "__main__":
    main()
