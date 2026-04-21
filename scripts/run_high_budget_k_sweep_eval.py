#!/usr/bin/env python3
"""High-budget fixed-K sweep for strict_gate1 hard same-family cap tuning."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
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


BN = _load_module(REPO_ROOT / "scripts/build_new_hundred_newest_vs_best_failure_statistics.py", "bn_high_budget_k")
TW = BN.TW

BASE = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
METHOD_TEMPLATE = (
    BASE
    + "_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k{cap}_v1"
    + "__deterministic_output_layer_repair_v1"
)


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _method_for_cap(cap: int) -> str:
    if cap < 1 or cap > 14:
        raise ValueError(f"cap must be in [1,14], got {cap}")
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


def _evaluate_cap_rows(rows: list[dict[str, Any]], cap: int) -> dict[str, Any]:
    key = f"k{cap}"
    out: dict[str, Any] = {
        "cap_k": int(cap),
        "n_cases": len(rows),
        "accuracy": _mean([1.0 if r[f"{key}_correct"] else 0.0 for r in rows]),
        "absent_from_tree": sum(1 for r in rows if r[f"{key}_failure_type"] == "absent_from_tree"),
        "present_not_selected": sum(1 for r in rows if r[f"{key}_failure_type"] == "present_not_selected"),
        "repeated_same_family_present": sum(1 for r in rows if bool(r[f"{key}_repeated_same_family_present"])),
        "avg_longest_same_family_run": _mean([float(r[f"{key}_longest_same_family_run"]) for r in rows]),
        "avg_max_family_share": _mean([float(r[f"{key}_max_family_share"]) for r in rows]),
        "avg_actions": _mean([float(r[f"{key}_actions"]) for r in rows]),
        "avg_expansions": _mean([float(r[f"{key}_expansions"]) for r in rows]),
        "avg_verifications": _mean([float(r[f"{key}_verifications"]) for r in rows]),
        "improved_vs_k6": sum(1 for r in rows if (not r["k6_correct"]) and r[f"{key}_correct"]),
        "worsened_vs_k6": sum(1 for r in rows if r["k6_correct"] and (not r[f"{key}_correct"])),
        "unchanged_vs_k6": sum(1 for r in rows if bool(r["k6_correct"]) == bool(r[f"{key}_correct"])),
    }
    return out


def _best_cap(summary_rows: list[dict[str, Any]]) -> int:
    ranked = sorted(
        summary_rows,
        key=lambda r: (
            float(r["accuracy"]),
            -int(r["absent_from_tree"]),
            -float(r["avg_max_family_share"]),
            -float(r["avg_actions"]),
            -int(r["cap_k"]),
        ),
        reverse=True,
    )
    return int(ranked[0]["cap_k"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,olympiadbench")
    ap.add_argument("--subset-size", type=int, default=8)
    ap.add_argument("--seeds", default="13,37,101")
    ap.add_argument("--budgets", default="12,14,16,18,20")
    ap.add_argument("--k-values", default="4,6,8,10,12")
    args = ap.parse_args()

    datasets = [x.strip() for x in args.datasets.split(",") if x.strip()]
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    budgets = [int(x.strip()) for x in args.budgets.split(",") if x.strip()]
    k_values = [int(x.strip()) for x in args.k_values.split(",") if x.strip()]
    if 6 not in k_values:
        raise ValueError("k-values must include control K=6")

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/high_budget_k_sweep_eval_{ts}"
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
        for cap in k_values:
            method = _method_for_cap(cap)
            key = f"k{cap}"
            raw = BN._run_observed_with_events(method, row, f"high_budget_k{cap}")
            failure, correct, gold_in_tree, answer = _classify(raw, row["ground_truth"], row["dataset"])
            meta = raw.get("metadata") or {}
            out_row[f"{key}_method"] = method
            out_row[f"{key}_answer"] = answer
            out_row[f"{key}_correct"] = bool(correct)
            out_row[f"{key}_failure_type"] = failure
            out_row[f"{key}_gold_in_tree"] = bool(gold_in_tree)
            out_row[f"{key}_repeated_same_family_present"] = bool(float(meta.get("repeated_same_family_expansion_rate", 0.0)) > 0.0)
            out_row[f"{key}_longest_same_family_run"] = int(meta.get("max_consecutive_same_family", 0))
            fam_counts = {str(k): int(v) for k, v in dict(meta.get("hard_max_family_expansion_counts") or {}).items()}
            denom = max(1, sum(fam_counts.values()))
            max_share = (max(fam_counts.values()) / denom) if fam_counts else 0.0
            out_row[f"{key}_max_family_share"] = float(max_share)
            out_row[f"{key}_actions"] = int(raw["actions"])
            out_row[f"{key}_expansions"] = int(raw["expansions"])
            out_row[f"{key}_verifications"] = int(raw["verifications"])
        per_case.append(out_row)

    overall_table = [_evaluate_cap_rows(per_case, cap) for cap in k_values]
    best_overall = _best_cap(overall_table)

    per_budget_table: list[dict[str, Any]] = []
    best_by_budget: dict[int, int] = {}
    for b in budgets:
        b_rows = [r for r in per_case if int(r["budget"]) == int(b)]
        rows = [_evaluate_cap_rows(b_rows, cap) for cap in k_values]
        for rec in rows:
            rec["budget"] = int(b)
            per_budget_table.append(rec)
        best_by_budget[int(b)] = _best_cap(rows)

    per_dataset_table: list[dict[str, Any]] = []
    for ds in datasets:
        ds_rows = [r for r in per_case if str(r["dataset"]) == ds]
        for cap in k_values:
            rec = _evaluate_cap_rows(ds_rows, cap)
            rec["dataset"] = ds
            per_dataset_table.append(rec)

    h2h = {}
    for cap in k_values:
        if cap == 6:
            continue
        key = f"k{cap}"
        h2h[f"k{cap}_vs_k6"] = {
            "improved": sum(1 for r in per_case if (not r["k6_correct"]) and r[f"{key}_correct"]),
            "worsened": sum(1 for r in per_case if r["k6_correct"] and (not r[f"{key}_correct"])),
            "unchanged": sum(1 for r in per_case if bool(r["k6_correct"]) == bool(r[f"{key}_correct"])),
        }

    summary = {
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "control_cap": 6,
        "n_cases": len(per_case),
        "datasets": datasets,
        "subset_size_per_dataset_seed": int(args.subset_size),
        "seeds": seeds,
        "budgets": budgets,
        "k_values": k_values,
        "overall_table": overall_table,
        "best_k_overall": best_overall,
        "best_k_by_budget": {str(k): int(v) for k, v in best_by_budget.items()},
        "head_to_head_vs_k6": h2h,
    }

    (out_dir / "per_case_results.json").write_text(json.dumps(per_case, indent=2), encoding="utf-8")
    (out_dir / "aggregate_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "per_budget_summary.json").write_text(json.dumps(per_budget_table, indent=2), encoding="utf-8")
    (out_dir / "per_dataset_summary.json").write_text(json.dumps(per_dataset_table, indent=2), encoding="utf-8")
    (out_dir / "head_to_head_vs_k6.json").write_text(json.dumps(h2h, indent=2), encoding="utf-8")
    (out_dir / "recommended_k_for_high_budget_regime.json").write_text(
        json.dumps(
            {
                "scope": "evaluated high-budget surface only",
                "recommended_k": int(best_overall),
                "best_k_by_budget": {str(k): int(v) for k, v in best_by_budget.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    with (out_dir / "overall_summary_table.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(overall_table[0].keys()))
        writer.writeheader()
        writer.writerows(overall_table)

    with (out_dir / "per_budget_summary_table.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_budget_table[0].keys()))
        writer.writeheader()
        writer.writerows(per_budget_table)

    report = REPO_ROOT / f"docs/HIGH_BUDGET_K_SWEEP_EVAL_{ts}.md"
    lines = [
        f"# High-budget fixed-K sweep evaluation ({ts})",
        "",
        "## Scope",
        "Focused sweep over fixed same-family hard caps under the strict-phased Gate-1 controller, targeting only higher budgets.",
        "Controller behavior is held constant; only the hard same-family cap K changes.",
        "",
        "## Control/default",
        "- control alias: `strict_gate1_cap_k6`",
        f"- control method: `{_method_for_cap(6)}`",
        "",
        "## Evaluation surface",
        f"- datasets: {datasets}",
        f"- subset size per dataset/seed: {args.subset_size}",
        f"- seeds: {seeds}",
        f"- budgets (high-only): {budgets}",
        f"- fixed K values: {k_values}",
        f"- total evaluated rows: {len(per_case)}",
        "",
        "## Overall comparison",
        "| K | accuracy | absent_from_tree | present_not_selected | repeated_same_family_present | avg_longest_same_family_run | avg_max_family_share | avg_actions | avg_expansions | avg_verifications | improved_vs_k6 | worsened_vs_k6 | unchanged_vs_k6 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rec in sorted(overall_table, key=lambda r: (float(r["accuracy"]), -int(r["cap_k"])), reverse=True):
        lines.append(
            f"| {rec['cap_k']} | {rec['accuracy']:.4f} | {rec['absent_from_tree']} | {rec['present_not_selected']} | {rec['repeated_same_family_present']} | {rec['avg_longest_same_family_run']:.3f} | {rec['avg_max_family_share']:.3f} | {rec['avg_actions']:.3f} | {rec['avg_expansions']:.3f} | {rec['avg_verifications']:.3f} | {rec['improved_vs_k6']} | {rec['worsened_vs_k6']} | {rec['unchanged_vs_k6']} |"
        )

    lines.extend(["", "## Best K by budget", "| budget | best_k |", "|---:|---:|"])
    for b in budgets:
        lines.append(f"| {b} | {best_by_budget[b]} |")

    lines.extend([
        "",
        "## Interpretation",
        f"- On this evaluated high-budget surface, overall best fixed cap is **K={best_overall}**.",
        f"- Winner sequence by budget: {[best_by_budget[b] for b in budgets]}",
        "- Plateau check: assess whether gains past K=6 are small/inconsistent across budgets using per-budget table.",
        "- Collapse check: use repeated_same_family_present, avg_longest_same_family_run, and avg_max_family_share to verify whether larger K reintroduces concentration.",
        "- Recommendation is scoped to this evaluated high-budget surface and current strict-phased repository phase.",
        "",
        "## Artifacts",
        f"- output directory: `outputs/high_budget_k_sweep_eval_{ts}`",
        "- machine-readable aggregate summary: `aggregate_summary.json`",
        "- per-budget summary: `per_budget_summary.json` and `per_budget_summary_table.csv`",
        "- per-dataset summary: `per_dataset_summary.json`",
        "- head-to-head summaries vs K=6: `head_to_head_vs_k6.json`",
        "- high-budget recommendation artifact: `recommended_k_for_high_budget_regime.json`",
    ])
    report.write_text("\n".join(lines), encoding="utf-8")

    print(f"output_dir={out_dir.relative_to(REPO_ROOT)}")
    print(f"report={report.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
