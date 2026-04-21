#!/usr/bin/env python3
"""Budget-aware same-family cap evaluation for strict_gate1_cap_k6 successor testing."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import load_pilot_examples


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


BN = _load_module(REPO_ROOT / "scripts/build_new_hundred_newest_vs_best_failure_statistics.py", "bn_budget_cap")
TW = BN.TW

BASE = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
METHOD_TEMPLATE = (
    BASE
    + "_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k{cap}_v1"
    + "__deterministic_output_layer_repair_v1"
)

FORMULAS: dict[str, tuple[str, Any]] = {
    "fixed_k6": ("K(b)=6", lambda b: 6),
    "min6_half": ("K(b)=min(6,floor(b/2))", lambda b: min(6, b // 2)),
    "min6_third": ("K(b)=min(6,floor(b/3))", lambda b: min(6, b // 3)),
    "min6_quarter": ("K(b)=min(6,floor(b/4))", lambda b: min(6, b // 4)),
    "half": ("K(b)=max(1,floor(b/2))", lambda b: max(1, b // 2)),
    "third": ("K(b)=max(1,floor(b/3))", lambda b: max(1, b // 3)),
    "quarter": ("K(b)=max(1,floor(b/4))", lambda b: max(1, b // 4)),
}


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _formula_cap(formula: str, budget: int) -> int:
    return int(max(1, FORMULAS[formula][1](int(budget))))


def _method_for_cap(cap: int) -> str:
    if cap < 1 or cap > 10:
        raise ValueError(f"cap must be in [1,10], got {cap}")
    return METHOD_TEMPLATE.format(cap=cap)


def _classify(raw: dict[str, Any], gold_raw: str, dataset: str) -> tuple[str, bool, bool, str]:
    rep = TW.choose_repair_answer(
        final_nodes=list(raw["final_nodes"]),
        selected_group_hint=(raw.get("metadata") or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    ans = rep.get("surfaced_final_answer_raw")
    ans_can = TW.canonicalize_answer(ans, dataset=dataset)
    gold_can = TW.canonicalize_answer(gold_raw, dataset=dataset)
    correct = bool(ans_can == gold_can and ans_can is not None)
    gold_in_tree = bool(TW._node_ids_with_answer(raw["final_nodes"], gold_can))
    if not gold_in_tree:
        failure = "absent_from_tree"
    else:
        failure = "correct" if correct else "present_not_selected"
    return failure, correct, gold_in_tree, str(ans)


def _evaluate_formula_rows(rows: list[dict[str, Any]], formula: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "formula": formula,
        "formula_expr": FORMULAS[formula][0],
        "n_cases": len(rows),
        "accuracy": _mean([1.0 if r[f"{formula}_correct"] else 0.0 for r in rows]),
        "absent_from_tree": sum(1 for r in rows if r[f"{formula}_failure_type"] == "absent_from_tree"),
        "present_not_selected": sum(1 for r in rows if r[f"{formula}_failure_type"] == "present_not_selected"),
        "repeated_same_family_present": sum(1 for r in rows if bool(r[f"{formula}_repeated_same_family_present"])),
        "avg_longest_same_family_run": _mean([float(r[f"{formula}_longest_same_family_run"]) for r in rows]),
        "avg_max_family_share": _mean([float(r[f"{formula}_max_family_share"]) for r in rows]),
        "avg_actions": _mean([float(r[f"{formula}_actions"]) for r in rows]),
        "avg_expansions": _mean([float(r[f"{formula}_expansions"]) for r in rows]),
        "avg_verifications": _mean([float(r[f"{formula}_verifications"]) for r in rows]),
        "improved_vs_fixed_k6": sum(1 for r in rows if (not r["fixed_k6_correct"]) and r[f"{formula}_correct"]),
        "worsened_vs_fixed_k6": sum(1 for r in rows if r["fixed_k6_correct"] and (not r[f"{formula}_correct"])),
        "unchanged_vs_fixed_k6": sum(1 for r in rows if bool(r["fixed_k6_correct"]) == bool(r[f"{formula}_correct"])),
    }
    return out


def _best_formula(summary_rows: list[dict[str, Any]]) -> str:
    ranked = sorted(
        summary_rows,
        key=lambda r: (
            float(r["accuracy"]),
            -int(r["absent_from_tree"]),
            -float(r["avg_max_family_share"]),
            -float(r["avg_actions"]),
        ),
        reverse=True,
    )
    return str(ranked[0]["formula"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,olympiadbench")
    ap.add_argument("--subset-size", type=int, default=8)
    ap.add_argument("--seeds", default="13,37,101")
    ap.add_argument("--budgets", default="4,6,8,10,12,14,16")
    args = ap.parse_args()

    datasets = [x.strip() for x in args.datasets.split(",") if x.strip()]
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    budgets = [int(x.strip()) for x in args.budgets.split(",") if x.strip()]

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/budget_aware_family_cap_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    surface_rows: list[dict[str, Any]] = []
    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, int(args.subset_size), seed)
            for ex in examples:
                for budget in budgets:
                    surface_rows.append(
                        {
                            "dataset": dataset,
                            "example_id": str(ex.example_id),
                            "problem_text": str(ex.question),
                            "ground_truth": str(ex.answer),
                            "seed": int(seed),
                            "budget": int(budget),
                        }
                    )

    per_case: list[dict[str, Any]] = []
    for row in surface_rows:
        out_row: dict[str, Any] = {
            "dataset": row["dataset"],
            "example_id": row["example_id"],
            "seed": row["seed"],
            "budget": row["budget"],
            "gold_answer": row["ground_truth"],
        }
        for formula in FORMULAS:
            cap = _formula_cap(formula, int(row["budget"]))
            method = _method_for_cap(cap)
            raw = BN._run_observed_with_events(method, row, f"budget_cap_{formula}")
            failure, correct, gold_in_tree, answer = _classify(raw, row["ground_truth"], row["dataset"])
            meta = raw.get("metadata") or {}
            out_row[f"{formula}_cap"] = int(cap)
            out_row[f"{formula}_method"] = method
            out_row[f"{formula}_answer"] = answer
            out_row[f"{formula}_correct"] = bool(correct)
            out_row[f"{formula}_failure_type"] = failure
            out_row[f"{formula}_gold_in_tree"] = bool(gold_in_tree)
            out_row[f"{formula}_repeated_same_family_present"] = bool(float(meta.get("repeated_same_family_expansion_rate", 0.0)) > 0.0)
            out_row[f"{formula}_longest_same_family_run"] = int(meta.get("max_consecutive_same_family", 0))
            fam_counts = {str(k): int(v) for k, v in dict(meta.get("hard_max_family_expansion_counts") or {}).items()}
            denom = max(1, sum(fam_counts.values()))
            max_share = (max(fam_counts.values()) / denom) if fam_counts else 0.0
            out_row[f"{formula}_max_family_share"] = float(max_share)
            out_row[f"{formula}_actions"] = int(raw["actions"])
            out_row[f"{formula}_expansions"] = int(raw["expansions"])
            out_row[f"{formula}_verifications"] = int(raw["verifications"])
        per_case.append(out_row)

    overall_table = [_evaluate_formula_rows(per_case, f) for f in FORMULAS]
    overall_best = _best_formula(overall_table)

    per_budget_table: list[dict[str, Any]] = []
    best_by_budget: dict[int, str] = {}
    for b in budgets:
        b_rows = [r for r in per_case if int(r["budget"]) == int(b)]
        rows = [_evaluate_formula_rows(b_rows, f) for f in FORMULAS]
        for rec in rows:
            rec["budget"] = int(b)
            per_budget_table.append(rec)
        best_by_budget[int(b)] = _best_formula(rows)

    per_dataset_table: list[dict[str, Any]] = []
    for ds in datasets:
        ds_rows = [r for r in per_case if str(r["dataset"]) == ds]
        for f in FORMULAS:
            rec = _evaluate_formula_rows(ds_rows, f)
            rec["dataset"] = ds
            per_dataset_table.append(rec)

    h2h = {}
    for f in FORMULAS:
        if f == "fixed_k6":
            continue
        h2h[f"{f}_vs_fixed_k6"] = {
            "improved": sum(1 for r in per_case if (not r["fixed_k6_correct"]) and r[f"{f}_correct"]),
            "worsened": sum(1 for r in per_case if r["fixed_k6_correct"] and (not r[f"{f}_correct"])),
            "unchanged": sum(1 for r in per_case if bool(r["fixed_k6_correct"]) == bool(r[f"{f}_correct"])),
        }

    regimes = {
        "low": [b for b in budgets if b <= 6],
        "medium": [b for b in budgets if 8 <= b <= 10],
        "high": [b for b in budgets if b >= 12],
    }
    recommended_by_regime: dict[str, dict[str, Any]] = {}
    for regime, budget_list in regimes.items():
        reg_rows = [r for r in per_case if int(r["budget"]) in budget_list]
        if not reg_rows:
            continue
        rows = [_evaluate_formula_rows(reg_rows, f) for f in FORMULAS]
        winner = _best_formula(rows)
        recommended_by_regime[regime] = {
            "budgets": budget_list,
            "winner": winner,
            "winner_expr": FORMULAS[winner][0],
            "accuracy": next(float(r["accuracy"]) for r in rows if r["formula"] == winner),
        }

    summary = {
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "control_formula": "fixed_k6",
        "n_cases": len(per_case),
        "datasets": datasets,
        "subset_size_per_dataset_seed": int(args.subset_size),
        "seeds": seeds,
        "budgets": budgets,
        "formulas": {k: v[0] for k, v in FORMULAS.items()},
        "overall_table": overall_table,
        "overall_best_formula": overall_best,
        "best_formula_by_budget": {str(k): v for k, v in best_by_budget.items()},
        "head_to_head_vs_fixed_k6": h2h,
        "recommended_by_budget_regime": recommended_by_regime,
    }

    (out_dir / "per_case_results.json").write_text(json.dumps(per_case, indent=2), encoding="utf-8")
    (out_dir / "aggregate_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "per_budget_summary.json").write_text(json.dumps(per_budget_table, indent=2), encoding="utf-8")
    (out_dir / "per_dataset_summary.json").write_text(json.dumps(per_dataset_table, indent=2), encoding="utf-8")
    (out_dir / "head_to_head_vs_fixed_k6.json").write_text(json.dumps(h2h, indent=2), encoding="utf-8")
    (out_dir / "recommended_formula_by_budget_regime.json").write_text(
        json.dumps(recommended_by_regime, indent=2), encoding="utf-8"
    )

    with (out_dir / "overall_summary_table.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(overall_table[0].keys()))
        writer.writeheader()
        writer.writerows(overall_table)

    with (out_dir / "per_budget_summary_table.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_budget_table[0].keys()))
        writer.writeheader()
        writer.writerows(per_budget_table)

    report = REPO_ROOT / f"docs/BUDGET_AWARE_FAMILY_CAP_EVAL_{ts}.md"
    overall_by_formula = {r["formula"]: r for r in overall_table}

    lines = [
        f"# Budget-aware family cap evaluation ({ts})",
        "",
        "## Scope",
        "Evaluate whether strict_gate1 same-family hard cap should remain fixed at K=6 or switch to budget-aware K(b) formulas, while preserving strict-phased law and controller logic.",
        "",
        "## Candidate formulas",
    ]
    for k, (expr, _) in FORMULAS.items():
        lines.append(f"- `{k}`: `{expr}`")
    lines.extend([
        "",
        "## Evaluation surface",
        f"- datasets: {datasets}",
        f"- subset size per dataset/seed: {args.subset_size}",
        f"- seeds: {seeds}",
        f"- budgets: {budgets}",
        f"- total evaluated rows: {len(per_case)}",
        "",
        "## Overall comparison",
        "| formula | accuracy | absent_from_tree | present_not_selected | repeated_same_family_present | avg_longest_same_family_run | avg_max_family_share | avg_actions | avg_expansions | avg_verifications | improved_vs_fixed_k6 | worsened_vs_fixed_k6 | unchanged_vs_fixed_k6 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for rec in sorted(overall_table, key=lambda r: float(r["accuracy"]), reverse=True):
        lines.append(
            f"| {rec['formula']} | {rec['accuracy']:.4f} | {rec['absent_from_tree']} | {rec['present_not_selected']} | {rec['repeated_same_family_present']} | {rec['avg_longest_same_family_run']:.3f} | {rec['avg_max_family_share']:.3f} | {rec['avg_actions']:.3f} | {rec['avg_expansions']:.3f} | {rec['avg_verifications']:.3f} | {rec['improved_vs_fixed_k6']} | {rec['worsened_vs_fixed_k6']} | {rec['unchanged_vs_fixed_k6']} |"
        )

    lines.extend(["", "## Best formula by budget", "| budget | best_formula | formula_expr |", "|---:|---|---|"])
    for b in budgets:
        bf = best_by_budget[b]
        lines.append(f"| {b} | {bf} | {FORMULAS[bf][0]} |")

    lines.extend(["", "## Budget dependence assessment"])
    low_winners = [best_by_budget[b] for b in budgets if b <= 6]
    high_winners = [best_by_budget[b] for b in budgets if b >= 12]
    lines.append(f"- low-budget winners (<=6): {low_winners}")
    lines.append(f"- high-budget winners (>=12): {high_winners}")
    lines.append(
        f"- fixed_k6 winner-count across budgets: {sum(1 for b in budgets if best_by_budget[b] == 'fixed_k6')} / {len(budgets)}"
    )

    robust = [f for f in FORMULAS if sum(1 for b in budgets if best_by_budget[b] == f) >= max(1, len(budgets) // 2)]
    lines.append(f"- formulas winning at least half the budgets: {robust if robust else 'none'}")

    lines.extend(["", "## Recommended formula by budget regime"])
    for regime, rec in recommended_by_regime.items():
        lines.append(f"- {regime} budgets {rec['budgets']}: `{rec['winner']}` ({rec['winner_expr']}), accuracy={rec['accuracy']:.4f}")

    lines.extend([
        "",
        "## Final decision",
        f"- Overall winner on this evaluated surface: **{overall_best}** (`{FORMULAS[overall_best][0]}`).",
        "- Fixed K=6 should be retained only if it remains competitive across most budgets; otherwise replace with a budget-aware rule or piecewise regime policy.",
        "- Conclusion is scoped to this evaluated simulator surface and current strict-phased repository phase, not universal optimality.",
        "",
        "## Artifacts",
        f"- output directory: `outputs/budget_aware_family_cap_eval_{ts}`",
        "- machine-readable aggregate summary: `aggregate_summary.json`",
        "- per-budget summary: `per_budget_summary.json` and `per_budget_summary_table.csv`",
        "- per-dataset summary: `per_dataset_summary.json`",
        "- head-to-head summaries: `head_to_head_vs_fixed_k6.json`",
        "- recommended formula by budget regime: `recommended_formula_by_budget_regime.json`",
    ])
    report.write_text("\n".join(lines), encoding="utf-8")

    print(f"output_dir={out_dir.relative_to(REPO_ROOT)}")
    print(f"report={report.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
