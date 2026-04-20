#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict

from paper_data_sources import (
    CANONICAL_FULL_BUNDLE,
    CANONICAL_IMPORT_MULTI,
    TABLE_DIR,
    load_multidataset_frontier,
    load_multidataset_method_metrics,
    read_csv,
    to_float,
    to_int,
    write_csv,
    write_tex_table,
)


def table1_benchmark_method_summary() -> list[dict[str, object]]:
    summary = []
    summary.append(
        {
            "datasets": "openai/gsm8k; HuggingFaceH4/MATH-500; Idavidrein/gpqa",
            "controller_families": "adaptive frontier; fixed internal baselines; oracle frontier upper bound",
            "budgets": "8, 10",
            "metrics": "accuracy; avg_actions; gap_to_oracle; budget_exhaustion_rate",
            "canonical_bundle": "outputs/imported_methodology_frontier_eval/20260420T_multidataset_frontier_v1",
        }
    )
    return summary


def table2_main_frontier() -> list[dict[str, object]]:
    rows = load_multidataset_frontier()
    budgets = sorted({to_int(r["budget"]) for r in rows})
    tier_labels = {budgets[0]: "low", budgets[-1]: "high"} if budgets else {}
    out = []
    for budget in budgets:
        sub = [r for r in rows if to_int(r["budget"]) == budget and r["method"] != "Oracle Frontier Upper Bound"]
        # macro over dataset
        best_by_method: dict[str, list[float]] = defaultdict(list)
        for r in sub:
            best_by_method[r["method"]].append(to_float(r["accuracy"]))
        method_macro = {m: sum(v) / len(v) for m, v in best_by_method.items()}
        best_method = max(method_macro.items(), key=lambda kv: kv[1])[0]
        promoted = method_macro.get("Promoted (Strict-Coupled Tie-Aware, bridged)", -1.0)

        oracle_rows = [r for r in rows if to_int(r["budget"]) == budget and r["method"] == "Oracle Frontier Upper Bound"]
        oracle_macro = sum(to_float(r["accuracy"]) for r in oracle_rows) / max(1, len(oracle_rows))

        out.append(
            {
                "budget_tier": tier_labels.get(budget, f"tier_{budget}"),
                "budget": budget,
                "best_method": best_method,
                "best_accuracy_macro": method_macro[best_method],
                "promoted_method": "Promoted (Strict-Coupled Tie-Aware, bridged)",
                "promoted_accuracy_macro": promoted,
                "oracle_accuracy_macro": oracle_macro,
            }
        )
    return out


def table3_oracle_headroom() -> list[dict[str, object]]:
    rows = load_multidataset_frontier()
    out = []
    for budget in sorted({to_int(r["budget"]) for r in rows}):
        budget_rows = [r for r in rows if to_int(r["budget"]) == budget]
        by_method_gap: dict[str, list[float]] = defaultdict(list)
        for r in budget_rows:
            by_method_gap[r["method"]].append(to_float(r["gap_to_oracle"]))
        by_method_gap = {m: sum(v) / len(v) for m, v in by_method_gap.items()}

        fixed_candidates = {m: g for m, g in by_method_gap.items() if m in {"Reasoning Beam-2", "Self-Consistency-3", "Reasoning Greedy", "Verifier-Guided Search", "Program-of-Thought"}}
        best_fixed = min(fixed_candidates.items(), key=lambda kv: kv[1])[0]
        promoted_gap = by_method_gap.get("Promoted (Strict-Coupled Tie-Aware, bridged)", 1.0)

        out.append(
            {
                "budget": budget,
                "best_fixed_baseline": best_fixed,
                "best_fixed_gap": fixed_candidates[best_fixed],
                "promoted_method": "Promoted (Strict-Coupled Tie-Aware, bridged)",
                "promoted_gap": promoted_gap,
                "oracle_gap": 0.0,
                "promoted_to_oracle_ratio": 1.0 - promoted_gap,
            }
        )
    return out


def table4_anti_collapse() -> list[dict[str, object]]:
    rows = load_multidataset_method_metrics()
    out = []
    for r in rows:
        avg_actions = to_float(r["avg_actions"])
        avg_exp = to_float(r["avg_expansions"])
        avg_ver = to_float(r["avg_verifications"])
        p_exp = (avg_exp / avg_actions) if avg_actions > 0 else 0.0
        p_ver = (avg_ver / avg_actions) if avg_actions > 0 else 0.0
        max_share = max(p_exp, p_ver)
        active = int(avg_exp > 0) + int(avg_ver > 0)
        out.append(
            {
                "dataset": r["dataset"],
                "budget": to_int(r["budget"]),
                "method": r["method"],
                "accuracy": to_float(r["accuracy"]),
                "max_family_share": max_share,
                "active_family_count": active,
                "budget_exhaustion_rate": to_float(r["budget_exhaustion_rate"]),
            }
        )
    return out


def table5_failure_decomposition() -> list[dict[str, object]]:
    rows = read_csv(CANONICAL_FULL_BUNDLE / "defeat_case_registry.csv")
    tree_like = {"under_exploration_or_early_commit", "branch_allocation_gap", "inefficient_budget_spend"}
    output_like = {"selection_or_aggregation_gap"}

    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0.0, "tree": 0.0, "output": 0.0, "other": 0.0})
    for r in rows:
        k = r["dataset"]
        grouped[k]["n"] += 1.0
        subtype = r.get("failure_subtype", "")
        if subtype in tree_like:
            grouped[k]["tree"] += 1.0
        elif subtype in output_like:
            grouped[k]["output"] += 1.0
        else:
            grouped[k]["other"] += 1.0

    out = []
    for dataset, vals in sorted(grouped.items()):
        n = max(1.0, vals["n"])
        out.append(
            {
                "dataset": dataset,
                "absent_from_tree_rate": vals["tree"] / n,
                "present_in_tree_output_layer_rate": vals["output"] / n,
                "other_rate": vals["other"] / n,
                "n_defeat_cases": int(vals["n"]),
                "basis": "defeat_case_failure_subtype_proxy",
            }
        )
    return out


def table6_robustness() -> list[dict[str, object]]:
    run_manifest = (CANONICAL_IMPORT_MULTI / "summary.json").read_text(encoding="utf-8")
    _ = run_manifest  # keeps explicit provenance linkage

    out = [
        {
            "axis": "dataset_variation",
            "status": "supported",
            "evidence": "matched frontier bundle includes GSM8K, MATH-500, GPQA",
            "source": "outputs/imported_methodology_frontier_eval/20260420T_multidataset_frontier_v1/summary.json",
        },
        {
            "axis": "budget_variation",
            "status": "supported",
            "evidence": "budgets 8 and 10 in canonical multi-dataset frontier bundle",
            "source": "outputs/imported_methodology_frontier_eval/20260420T_multidataset_frontier_v1/budget_frontier_summary.csv",
        },
        {
            "axis": "seed_variation",
            "status": "limited",
            "evidence": "frontier bundle uses fixed single seed per dataset in this run",
            "source": "outputs/imported_methodology_frontier_eval/20260420T_multidataset_frontier_v1/summary.json",
        },
        {
            "axis": "comparison_surface",
            "status": "incomplete",
            "evidence": "strict-coupled tie-aware promoted line is alias-bridge in frontier schema, not native controller",
            "source": "outputs/imported_methodology_frontier_eval/20260420T_multidataset_frontier_v1/summary.json",
        },
    ]
    return out


def write_table(prefix: str, rows: list[dict[str, object]]) -> None:
    csv_path = TABLE_DIR / f"{prefix}.csv"
    tex_path = TABLE_DIR / f"{prefix}.tex"
    write_csv(csv_path, rows)
    write_tex_table(tex_path, rows)


def main() -> None:
    write_table("table1_benchmark_method_summary", table1_benchmark_method_summary())
    write_table("table2_main_frontier", table2_main_frontier())
    write_table("table3_oracle_headroom", table3_oracle_headroom())
    write_table("table4_anti_collapse", table4_anti_collapse())
    write_table("table5_failure_decomposition", table5_failure_decomposition())
    write_table("table6_robustness", table6_robustness())


if __name__ == "__main__":
    main()
