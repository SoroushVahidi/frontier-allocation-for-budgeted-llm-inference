#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from paper_data_sources import PLOT_DATA_DIR, REPO_ROOT, read_csv, write_csv


DECISION_DIR = (
    REPO_ROOT / "outputs" / "paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3" / "20260422T175142Z"
)
ABLATION_DIR = REPO_ROOT / "outputs" / "component_ablation_strict_f3_paper_surface" / "20260422T180445Z"
READINESS_MATRIX = REPO_ROOT / "docs" / "external_baseline_paper_readiness_decision_matrix.json"
READINESS_TO_METHOD = {
    "l1_length_control_rl": "external_l1_max",
    "tale_token_budget_aware_reasoning": "external_tale_prompt_budgeting",
    "s1_simple_test_time_scaling": "external_s1_budget_forcing",
}


def _pick_strongest_external() -> str:
    rows = read_csv(DECISION_DIR / "decision_table.csv")
    external_rows = [r for r in rows if r["method"].startswith("external_")]
    external_rows.sort(key=lambda r: float(r["mean_accuracy"]), reverse=True)
    return external_rows[0]["method"]


def _main_table_external_methods() -> list[str]:
    payload = json.loads(READINESS_MATRIX.read_text(encoding="utf-8"))
    rows = list(payload.get("rows", []))
    selected = [
        READINESS_TO_METHOD[r["baseline_key"]]
        for r in rows
        if r.get("readiness_decision") == "main_table_ready" and r.get("baseline_key") in READINESS_TO_METHOD
    ]
    return sorted(set(selected))


def _target_methods() -> list[str]:
    methods = ["strict_f3", "strict_gate1_cap_k6"]
    selected = _main_table_external_methods()
    if selected:
        methods.extend(selected)
    else:
        methods.append(_pick_strongest_external())
    return methods


def _appendix_oracle_gap_methods(main_methods: list[str]) -> list[str]:
    # Appendix A1 can include one additional fair near-direct baseline
    # for broader context while keeping the chart readable.
    methods = list(main_methods)
    if "external_l1_exact" not in methods:
        methods.append("external_l1_exact")
    return methods


def _build_main_frontier(methods: list[str]) -> None:
    rows = read_csv(DECISION_DIR / "budget_performance_frontier.csv")
    out = []
    for r in rows:
        if r["method"] not in methods:
            continue
        out.append(
            {
                "budget": int(r["budget"]),
                "method": r["method"],
                "method_class": r["method_class"],
                "accuracy": float(r["mean_accuracy"]),
                "avg_actions": float(r["avg_actions"]),
            }
        )
    write_csv(PLOT_DATA_DIR / "figure2_main_frontier.csv", out)


def _build_main_failure_decomposition(methods: list[str]) -> None:
    rows = read_csv(DECISION_DIR / "failure_decomposition_plot_data.csv")
    out = []
    for r in rows:
        if r["method"] not in methods:
            continue
        out.append(
            {
                "method": r["method"],
                "method_class": r["method_class"],
                "n_cases": int(r["n_cases"]),
                "absent_from_tree_rate": float(r["absent_from_tree_rate"]),
                "present_not_selected_rate": float(r["present_not_selected_rate"]),
                "output_layer_mismatch_rate": float(r["output_layer_mismatch_rate"]),
            }
        )
    write_csv(PLOT_DATA_DIR / "figure3_failure_decomposition.csv", out)


def _build_appendix_oracle_gap(methods: list[str]) -> None:
    rows = read_csv(DECISION_DIR / "oracle_gap_regret.csv")
    out = []
    for r in rows:
        if r["method"] not in methods:
            continue
        out.append(
            {
                "budget": int(r["budget"]),
                "method": r["method"],
                "method_class": r["method_class"],
                "oracle_accuracy": float(r["oracle_accuracy"]),
                "method_accuracy": float(r["method_accuracy"]),
                "mean_regret_vs_inhouse_oracle": float(r["mean_regret_vs_inhouse_oracle"]),
            }
        )
    write_csv(PLOT_DATA_DIR / "appendix_a1_oracle_gap_regret.csv", out)


def _build_appendix_anti_collapse(methods: list[str]) -> None:
    rows = read_csv(DECISION_DIR / "anti_collapse_plot_data.csv")
    out = []
    for r in rows:
        if r["method"] not in methods:
            continue
        out.append(
            {
                "method": r["method"],
                "method_class": r["method_class"],
                "repeated_same_family_case_rate": float(r["repeated_same_family_case_rate"]),
                "avg_actions": float(r["avg_actions"]),
                "avg_expansions": float(r["avg_expansions"]),
                "avg_verifications": float(r["avg_verifications"]),
            }
        )
    write_csv(PLOT_DATA_DIR / "appendix_a2_anti_collapse.csv", out)


def _build_appendix_allocation(methods: list[str]) -> None:
    rows = read_csv(DECISION_DIR / "anti_collapse_plot_data.csv")
    out = []
    for r in rows:
        if r["method"] not in methods:
            continue
        out.extend(
            [
                {"method": r["method"], "metric": "avg_actions", "value": float(r["avg_actions"])},
                {"method": r["method"], "metric": "avg_expansions", "value": float(r["avg_expansions"])},
                {"method": r["method"], "metric": "avg_verifications", "value": float(r["avg_verifications"])},
            ]
        )
    write_csv(PLOT_DATA_DIR / "appendix_a3_allocation_composition.csv", out)


def _build_appendix_component_ablation() -> None:
    rows = read_csv(ABLATION_DIR / "component_summary_table.csv")
    out = []
    for r in rows:
        out.append(
            {
                "variant": r["variant"],
                "accuracy": float(r["accuracy"]),
                "delta_accuracy_vs_full": float(r["delta_accuracy_vs_full"]),
                "absent_from_tree_rate": float(r["absent_from_tree_rate"]),
                "present_not_selected_rate": float(r["present_not_selected_rate"]),
                "output_layer_mismatch_rate": float(r["output_layer_mismatch_rate"]),
            }
        )
    write_csv(PLOT_DATA_DIR / "appendix_a4_component_ablation.csv", out)


def main() -> None:
    PLOT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    main_methods = _target_methods()
    appendix_methods = _appendix_oracle_gap_methods(main_methods)
    _build_main_frontier(main_methods)
    _build_main_failure_decomposition(main_methods)
    _build_appendix_oracle_gap(appendix_methods)
    _build_appendix_anti_collapse(main_methods)
    _build_appendix_allocation(main_methods)
    _build_appendix_component_ablation()


if __name__ == "__main__":
    main()
