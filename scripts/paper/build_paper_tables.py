#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict

from paper_data_sources import (
    BUDGET_AWARE_DIR,
    CANONICAL_HUNDRED_DIR,
    MANUSCRIPT_METHOD_DECISION_DOC,
    EXTERNAL_READINESS_DOC,
    STRICT_PHASED_DEFAULT_DOC,
    TABLE_DIR,
    load_budget_aware_overall_table,
    load_budget_aware_per_budget,
    load_canonical_hundred_aggregate,
    load_canonical_hundred_failure_table,
    load_multidataset_frontier,
    write_csv,
    write_tex_table,
)


def table1_benchmark_method_summary() -> list[dict[str, object]]:
    return [
        {
            "surface": "manuscript-facing canonical matched internal decision surface",
            "datasets": "openai/gsm8k; HuggingFaceH4/MATH-500; HuggingFaceH4/aime_2024; olympiadbench",
            "methods_compared": "strict_f3; strict_gate1_cap_k6; broad-family finalists; internal anchors",
            "manuscript_main_method": "strict_f3",
            "runner_up_anchor": "strict_gate1_cap_k6",
            "source_doc": str(MANUSCRIPT_METHOD_DECISION_DOC.relative_to(MANUSCRIPT_METHOD_DECISION_DOC.parents[2])),
        }
    ]


def table2_main_frontier() -> list[dict[str, object]]:
    rows = load_multidataset_frontier()
    budgets = sorted({int(float(r["budget"])) for r in rows})
    out = []
    for budget in budgets or [0]:
        sub = [r for r in rows if int(float(r["budget"])) == budget]
        best_by_method: dict[str, list[float]] = defaultdict(list)
        for r in sub:
            best_by_method[str(r["method"])].append(float(r["accuracy"]))
        method_macro = {m: sum(v) / len(v) for m, v in best_by_method.items()}
        best_method = max(method_macro.items(), key=lambda kv: kv[1])[0]
        main_method_acc = method_macro.get("strict_f3", -1.0)
        out.append(
            {
                "budget_tier": "full_surface",
                "budget": budget,
                "best_method": best_method,
                "best_accuracy_macro": method_macro[best_method],
                "main_method": "strict_f3",
                "main_method_accuracy_macro": main_method_acc,
            }
        )
    return out


def table3_oracle_headroom() -> list[dict[str, object]]:
    rows = load_budget_aware_overall_table()
    return [
        {
            "formula": str(r["formula"]),
            "formula_expr": str(r["formula_expr"]),
            "accuracy": float(r["accuracy"]),
            "absent_from_tree": int(r["absent_from_tree"]),
            "present_not_selected": int(r["present_not_selected"]),
            "repeated_same_family_present": int(r["repeated_same_family_present"]),
            "avg_actions": float(r["avg_actions"]),
            "improved_vs_fixed_k6": int(r["improved_vs_fixed_k6"]),
            "worsened_vs_fixed_k6": int(r["worsened_vs_fixed_k6"]),
        }
        for r in rows
    ]


def table4_anti_collapse() -> list[dict[str, object]]:
    agg = load_canonical_hundred_aggregate()
    dist = agg["distributions"]
    return [
        {
            "target_n": int(agg["target_n"]),
            "failure_absent_from_tree_pct": float(agg["failure_type_counts"]["absent_from_tree"]["pct"]),
            "failure_present_not_selected_pct": float(agg["failure_type_counts"]["present_not_selected"]["pct"]),
            "repeated_same_family_present_n": int(agg["repeated_same_family_present_n"]),
            "longest_same_family_run_mean": float(dist["longest_consecutive_family_run"]["mean"]),
            "max_family_share_mean": float(dist["max_family_share"]["mean"]),
            "actions_mean": float(dist["actions_ours"]["mean"]),
            "expansions_mean": float(dist["expansions_ours"]["mean"]),
            "verifications_mean": float(dist["verifications_ours"]["mean"]),
        }
    ]


def table5_failure_decomposition() -> list[dict[str, object]]:
    rows = load_canonical_hundred_failure_table()
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "absent": 0, "present": 0})
    for r in rows:
        ds = str(r["dataset"])
        grouped[ds]["n"] += 1
        if str(r["failure_type"]) == "absent_from_tree":
            grouped[ds]["absent"] += 1
        elif str(r["failure_type"]) == "present_not_selected":
            grouped[ds]["present"] += 1
    out = []
    for ds, vals in sorted(grouped.items()):
        n = max(1, vals["n"])
        out.append(
            {
                "dataset": ds,
                "n_cases": int(vals["n"]),
                "absent_from_tree_n": int(vals["absent"]),
                "present_not_selected_n": int(vals["present"]),
                "absent_from_tree_rate": vals["absent"] / n,
                "present_not_selected_rate": vals["present"] / n,
            }
        )
    return out


def table6_robustness() -> list[dict[str, object]]:
    per_budget = load_budget_aware_per_budget()
    budget_count = len({int(r["budget"]) for r in per_budget})
    out = [
        {
            "axis": "manuscript_method_status",
            "status": "supported",
            "evidence": "resolved internal manuscript-facing decision selects strict_f3; strict_gate1_cap_k6 retained as runner-up anchor",
            "source": str(MANUSCRIPT_METHOD_DECISION_DOC.relative_to(MANUSCRIPT_METHOD_DECISION_DOC.parents[2])),
        },
        {
            "axis": "broad_default_context",
            "status": "supported",
            "evidence": f"broader strict-phased default/cap evaluation remains available for operational-default context ({budget_count} budget points in cap sweep package)",
            "source": str(STRICT_PHASED_DEFAULT_DOC.relative_to(STRICT_PHASED_DEFAULT_DOC.parents[2])),
        },
        {
            "axis": "external_baseline_policy",
            "status": "supported",
            "evidence": "main-table vs appendix-only external readiness decisions are explicitly locked in canonical policy",
            "source": str(EXTERNAL_READINESS_DOC.relative_to(EXTERNAL_READINESS_DOC.parents[2])),
        },
        {
            "axis": "exact_failure_profile",
            "status": "supported",
            "evidence": "canonical failure-statistics artifacts remain available as targeted mechanism evidence",
            "source": str((CANONICAL_HUNDRED_DIR / 'aggregate_failure_statistics.json').relative_to(CANONICAL_HUNDRED_DIR.parents[1])),
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
