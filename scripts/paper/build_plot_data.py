#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from common import (
    CANONICAL_BRANCH_SCORER_RUN,
    CANONICAL_IMPORT_RUN,
    CANONICAL_NEAR_TIE_RUN,
    CANONICAL_TERNARY_RUN,
    PLOT_DATA_DIR,
    canonical_method_name,
    read_csv,
    to_float,
    to_int,
    write_csv,
    write_json,
)


def build_figure1_schematic() -> Path:
    payload = {
        "figure_id": "figure1_problem_schematic",
        "title": "Fixed-Budget Adaptive Allocation Pipeline",
        "nodes": [
            {"id": "input", "label": "Input Questions", "type": "source"},
            {"id": "tree", "label": "Active Branch Tree", "type": "state"},
            {"id": "controllers", "label": "Controller Families", "type": "process"},
            {"id": "allocation", "label": "Budget Allocation Decisions", "type": "decision"},
            {"id": "groups", "label": "Answer-Group Aware Aggregation", "type": "process"},
            {"id": "commit", "label": "Commit / Final Selection", "type": "sink"},
        ],
        "edges": [
            ["input", "tree"],
            ["tree", "controllers"],
            ["controllers", "allocation"],
            ["allocation", "groups"],
            ["groups", "commit"],
        ],
        "annotations": [
            "Budget is fixed ex-ante and allocated across active branches.",
            "Controller design includes anti-collapse constraints and defer/commit control.",
            "Oracle headroom and failure decomposition are evaluated downstream.",
        ],
    }
    out = PLOT_DATA_DIR / "figure1_problem_schematic.json"
    write_json(out, payload)
    return out


def build_main_frontier() -> Path:
    rows = read_csv(CANONICAL_IMPORT_RUN / "budget_frontier_summary.csv")
    out_rows = []
    for row in sorted(rows, key=lambda r: (canonical_method_name(r["method"]), to_int(r, "budget"))):
        out_rows.append(
            {
                "dataset": "openai/gsm8k",
                "method": canonical_method_name(row["method"]),
                "budget": to_int(row, "budget"),
                "accuracy": to_float(row, "accuracy"),
                "avg_actions": to_float(row, "avg_actions"),
                "gap_to_oracle": to_float(row, "gap_to_oracle"),
                "metric": "accuracy",
                "budget_axis": "budget",
            }
        )
    out = PLOT_DATA_DIR / "main_frontier_curves.csv"
    write_csv(out, out_rows)
    return out


def build_oracle_gap() -> Path:
    rows = read_csv(CANONICAL_IMPORT_RUN / "budget_frontier_summary.csv")
    out_rows = []
    for row in sorted(rows, key=lambda r: (canonical_method_name(r["method"]), to_int(r, "budget"))):
        gap = to_float(row, "gap_to_oracle")
        out_rows.append(
            {
                "dataset": "openai/gsm8k",
                "method": canonical_method_name(row["method"]),
                "budget": to_int(row, "budget"),
                "oracle_gap": gap,
                "normalized_regret": gap,
            }
        )
    out = PLOT_DATA_DIR / "oracle_gap_curves.csv"
    write_csv(out, out_rows)
    return out


def build_allocation_and_anticollapse() -> tuple[Path, Path]:
    rows = read_csv(CANONICAL_IMPORT_RUN / "method_metrics.csv")
    out_comp = []
    out_diag = []
    for row in sorted(rows, key=lambda r: (to_int(r, "budget"), canonical_method_name(r["method"]))):
        budget = to_int(row, "budget")
        avg_exp = to_float(row, "avg_expansions")
        avg_ver = to_float(row, "avg_verifications")
        avg_actions = to_float(row, "avg_actions")
        exp_share = (avg_exp / avg_actions) if avg_actions > 0 else 0.0
        ver_share = (avg_ver / avg_actions) if avg_actions > 0 else 0.0
        out_comp.append(
            {
                "dataset": "openai/gsm8k",
                "method": canonical_method_name(row["method"]),
                "budget": budget,
                "family": "expansion",
                "avg_actions": avg_actions,
                "avg_component_actions": avg_exp,
                "component_share": exp_share,
            }
        )
        out_comp.append(
            {
                "dataset": "openai/gsm8k",
                "method": canonical_method_name(row["method"]),
                "budget": budget,
                "family": "verification",
                "avg_actions": avg_actions,
                "avg_component_actions": avg_ver,
                "component_share": ver_share,
            }
        )

        concentration = max(exp_share, ver_share)
        active_family_count = int((avg_exp > 0) + (avg_ver > 0))
        monopolization_rate = 1.0 if concentration >= 0.95 else 0.0
        out_diag.append(
            {
                "dataset": "openai/gsm8k",
                "method": canonical_method_name(row["method"]),
                "budget": budget,
                "budget_exhaustion_rate": to_float(row, "budget_exhaustion_rate"),
                "max_family_share": concentration,
                "active_family_count": active_family_count,
                "monopolization_rate": monopolization_rate,
            }
        )

    comp_out = PLOT_DATA_DIR / "allocation_composition.csv"
    diag_out = PLOT_DATA_DIR / "anti_collapse_diagnostics.csv"
    write_csv(comp_out, out_comp)
    write_csv(diag_out, out_diag)
    return comp_out, diag_out


def build_failure_decomposition() -> Path:
    source = read_csv(CANONICAL_IMPORT_RUN / "signal_slice_summary.csv")
    rows = []
    for row in source:
        method = canonical_method_name(row["method"])
        budget = to_int(row, "budget")
        hard_n = to_int(row, "hard_n")
        easy_n = to_int(row, "easy_n")
        hard_acc = to_float(row, "hard_accuracy")
        easy_acc = to_float(row, "easy_accuracy")
        total = max(1, hard_n + easy_n)
        # Honest proxy decomposition: hard-slice errors treated as tree-generation failures,
        # easy-slice residual errors treated as output-layer failures.
        tree_fail_count = hard_n * (1.0 - hard_acc)
        output_fail_count = easy_n * (1.0 - easy_acc)
        rows.append(
            {
                "dataset": "openai/gsm8k",
                "method": method,
                "budget": budget,
                "absent_from_tree_failures": tree_fail_count / total,
                "present_in_tree_output_layer_failures": output_fail_count / total,
                "other_failures": max(0.0, 1.0 - (tree_fail_count + output_fail_count) / total - (hard_n * hard_acc + easy_n * easy_acc) / total),
                "decomposition_note": "proxy_from_signal_slice_hard_easy",
            }
        )

    out = PLOT_DATA_DIR / "failure_decomposition.csv"
    write_csv(out, rows)
    return out


def build_per_dataset_frontiers() -> Path:
    rows = read_csv(CANONICAL_IMPORT_RUN / "budget_frontier_summary.csv")
    out_rows = []
    for row in sorted(rows, key=lambda r: (canonical_method_name(r["method"]), to_int(r, "budget"))):
        out_rows.append(
            {
                "dataset": "openai/gsm8k",
                "method": canonical_method_name(row["method"]),
                "budget": to_int(row, "budget"),
                "accuracy": to_float(row, "accuracy"),
                "gap_to_oracle": to_float(row, "gap_to_oracle"),
            }
        )
    out = PLOT_DATA_DIR / "per_dataset_frontiers.csv"
    write_csv(out, out_rows)
    return out


def build_appendix_plot_data() -> list[Path]:
    out_paths: list[Path] = []

    # Appendix A: per-dataset frontier duplicate with explicit appendix naming.
    src = read_csv(PLOT_DATA_DIR / "per_dataset_frontiers.csv")
    out_a = PLOT_DATA_DIR / "appendix_per_dataset_frontiers.csv"
    write_csv(out_a, src)
    out_paths.append(out_a)

    # Appendix B: promoted method vs adversary on failure slices (from near-tie bundle).
    near_tie_rows = read_csv(CANONICAL_NEAR_TIE_RUN / "required_matched_rows.csv")
    keep_variants = {
        "strict_coupled_near_tie_specialized_pointwise_v1",
        "binary_forced_baseline",
        "strict_coupled_tie_aware_posthoc_deferral_v1",
    }
    out_b_rows = []
    for row in near_tie_rows:
        if row["variant"] not in keep_variants:
            continue
        out_b_rows.append(
            {
                "regime": row["regime"],
                "seed": to_int(row, "seed"),
                "method": canonical_method_name(row["variant"]),
                "forced_pairwise_accuracy": to_float(row, "forced_pairwise_accuracy"),
                "near_tie_forced_accuracy": to_float(row, "near_tie_forced_accuracy"),
                "adjacent_forced_accuracy": to_float(row, "adjacent_forced_accuracy"),
                "coverage": to_float(row, "coverage"),
                "deferred_rate": to_float(row, "deferred_rate"),
            }
        )
    out_b = PLOT_DATA_DIR / "appendix_promoted_vs_adversary_failure_slices.csv"
    write_csv(out_b, out_b_rows)
    out_paths.append(out_b)

    # Appendix C and D are not derivable from committed canonical artifacts.
    todo = PLOT_DATA_DIR / "appendix_missing_figures_todo.md"
    todo.write_text(
        "# Appendix figure TODOs\n\n"
        "- `appendix_old_vs_current_tree_comparison.csv`: omitted; no committed old-vs-current tree summary with aligned schema.\n"
        "- `appendix_output_layer_repair.csv`: now generated from `outputs/current_failure_output_layer_repair_20260420/` via `scripts/paper/plot_appendix_output_layer_repair.py`.\n",
        encoding="utf-8",
    )
    out_paths.append(todo)

    return out_paths


def build_all_plot_data() -> list[Path]:
    PLOT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    built = [
        build_figure1_schematic(),
        build_main_frontier(),
        build_oracle_gap(),
        build_failure_decomposition(),
        build_per_dataset_frontiers(),
    ]
    comp_path, diag_path = build_allocation_and_anticollapse()
    built.extend([comp_path, diag_path])
    built.extend(build_appendix_plot_data())

    # Optional provenance export for branch-scorer table support.
    if CANONICAL_BRANCH_SCORER_RUN.exists():
        branch_summary = CANONICAL_BRANCH_SCORER_RUN / "final_summary.json"
        if branch_summary.exists():
            write_json(PLOT_DATA_DIR / "appendix_branch_scorer_summary_pointer.json", {"source": str(branch_summary)})
            built.append(PLOT_DATA_DIR / "appendix_branch_scorer_summary_pointer.json")

    return built


if __name__ == "__main__":
    for p in build_all_plot_data():
        print(p)
