#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from common import CANONICAL_IMPORT_RUN, CANONICAL_NEAR_TIE_RUN, TABLE_DIR, canonical_method_name, read_csv, to_float, to_int, write_csv


def _to_tex_table(rows: list[dict[str, object]], path: Path) -> None:
    if not rows:
        raise ValueError(f"No rows for TeX table: {path}")
    cols = list(rows[0].keys())
    lines = ["\\begin{tabular}{" + "l" * len(cols) + "}", "\\hline", " & ".join(cols) + " \\\\", "\\hline"]
    for row in rows:
        vals = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.4f}")
            else:
                vals.append(str(v))
        lines.append(" & ".join(vals) + " \\\\")
    lines.extend(["\\hline", "\\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_table1_summary() -> tuple[Path, Path]:
    rows = [
        {
            "benchmark_surface": "openai/gsm8k (canonical frontier run)",
            "method_families": "fixed baselines; adaptive_budget_guarded; oracle_frontier_upper_bound",
            "budgets": "8, 10",
            "core_metrics": "accuracy; avg_actions; gap_to_oracle; budget_exhaustion_rate",
            "source": "outputs/imported_methodology_frontier_eval/20260417T000000Z",
        }
    ]
    csv_path = TABLE_DIR / "benchmark_method_summary.csv"
    tex_path = TABLE_DIR / "benchmark_method_summary.tex"
    write_csv(csv_path, rows)
    _to_tex_table(rows, tex_path)
    return csv_path, tex_path


def build_table2_frontier_comparison() -> tuple[Path, Path]:
    rows = read_csv(CANONICAL_IMPORT_RUN / "budget_frontier_summary.csv")
    by_budget: dict[int, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_budget[to_int(r, "budget")].append(r)

    out_rows = []
    tier_names = {0: "low", 1: "high"}
    for idx, budget in enumerate(sorted(by_budget.keys())):
        non_oracle = [r for r in by_budget[budget] if r["method"] != "oracle_frontier_upper_bound"]
        best = max(non_oracle, key=lambda r: to_float(r, "accuracy"))
        promoted = [r for r in non_oracle if r["method"] == "adaptive_budget_guarded"]
        promoted_row = promoted[0] if promoted else None
        oracle = [r for r in by_budget[budget] if r["method"] == "oracle_frontier_upper_bound"][0]
        out_rows.append(
            {
                "budget_tier": tier_names.get(idx, f"tier_{idx}"),
                "budget": budget,
                "best_non_oracle_method": canonical_method_name(best["method"]),
                "best_non_oracle_accuracy": to_float(best, "accuracy"),
                "promoted_method": "Adaptive Budget Guarded",
                "promoted_accuracy": to_float(promoted_row, "accuracy") if promoted_row else -1.0,
                "oracle_accuracy": to_float(oracle, "accuracy"),
            }
        )

    csv_path = TABLE_DIR / "main_frontier_comparison.csv"
    tex_path = TABLE_DIR / "main_frontier_comparison.tex"
    write_csv(csv_path, out_rows)
    _to_tex_table(out_rows, tex_path)
    return csv_path, tex_path


def build_table3_oracle_headroom() -> tuple[Path, Path]:
    rows = read_csv(CANONICAL_IMPORT_RUN / "oracle_gap_summary.csv")
    out_rows = []
    for budget in sorted({to_int(r, "budget") for r in rows}):
        budget_rows = [r for r in rows if to_int(r, "budget") == budget]
        baseline_candidates = [r for r in budget_rows if not r["method"].startswith("adaptive_")]
        best_baseline = min(baseline_candidates, key=lambda r: to_float(r, "gap_to_oracle"))
        promoted = [r for r in budget_rows if r["method"] == "adaptive_budget_guarded"][0]
        out_rows.append(
            {
                "budget": budget,
                "best_fixed_baseline": canonical_method_name(best_baseline["method"]),
                "best_fixed_baseline_gap": to_float(best_baseline, "gap_to_oracle"),
                "promoted_method": "Adaptive Budget Guarded",
                "promoted_gap": to_float(promoted, "gap_to_oracle"),
                "oracle_gap": 0.0,
                "promoted_to_oracle_ratio": 1.0 - to_float(promoted, "gap_to_oracle"),
            }
        )

    csv_path = TABLE_DIR / "oracle_headroom_summary.csv"
    tex_path = TABLE_DIR / "oracle_headroom_summary.tex"
    write_csv(csv_path, out_rows)
    _to_tex_table(out_rows, tex_path)
    return csv_path, tex_path


def build_table4_anti_collapse() -> tuple[Path, Path]:
    import_rows = read_csv(CANONICAL_IMPORT_RUN / "method_metrics.csv")
    tie_rows = read_csv(CANONICAL_NEAR_TIE_RUN / "required_matched_rows.csv")

    tie_target = [r for r in tie_rows if r["variant"] == "strict_coupled_tie_aware_posthoc_deferral_v1"]
    tie_cov = sum(to_float(r, "coverage") for r in tie_target) / max(1, len(tie_target))
    tie_defer = sum(to_float(r, "deferred_rate") for r in tie_target) / max(1, len(tie_target))

    out_rows = []
    for r in sorted(import_rows, key=lambda x: (to_int(x, "budget"), canonical_method_name(x["method"]))):
        avg_actions = to_float(r, "avg_actions")
        exp_share = to_float(r, "avg_expansions") / avg_actions if avg_actions > 0 else 0.0
        ver_share = to_float(r, "avg_verifications") / avg_actions if avg_actions > 0 else 0.0
        out_rows.append(
            {
                "budget": to_int(r, "budget"),
                "method": canonical_method_name(r["method"]),
                "accuracy": to_float(r, "accuracy"),
                "budget_exhaustion_rate": to_float(r, "budget_exhaustion_rate"),
                "max_action_family_share": max(exp_share, ver_share),
                "tie_aware_reference_coverage": tie_cov,
                "tie_aware_reference_deferred_rate": tie_defer,
            }
        )

    csv_path = TABLE_DIR / "anti_collapse_summary.csv"
    tex_path = TABLE_DIR / "anti_collapse_summary.tex"
    write_csv(csv_path, out_rows)
    _to_tex_table(out_rows, tex_path)
    return csv_path, tex_path


def build_table5_failure_decomposition() -> tuple[Path, Path]:
    rows = read_csv(CANONICAL_IMPORT_RUN / "signal_slice_summary.csv")
    out_rows = []
    for r in sorted(rows, key=lambda x: (to_int(x, "budget"), canonical_method_name(x["method"]))):
        hard_n = to_int(r, "hard_n")
        easy_n = to_int(r, "easy_n")
        total_n = max(1, hard_n + easy_n)
        tree_fail = hard_n * (1.0 - to_float(r, "hard_accuracy")) / total_n
        output_fail = easy_n * (1.0 - to_float(r, "easy_accuracy")) / total_n
        out_rows.append(
            {
                "budget": to_int(r, "budget"),
                "method": canonical_method_name(r["method"]),
                "absent_from_tree_failure_rate": tree_fail,
                "present_in_tree_output_layer_failure_rate": output_fail,
                "decomposition_basis": "hard_easy_proxy_from_signal_slice",
            }
        )

    csv_path = TABLE_DIR / "failure_decomposition.csv"
    tex_path = TABLE_DIR / "failure_decomposition.tex"
    write_csv(csv_path, out_rows)
    _to_tex_table(out_rows, tex_path)
    return csv_path, tex_path


def build_table6_robustness() -> tuple[Path, Path]:
    rows = [
        {
            "axis": "dataset_variation",
            "status": "limited",
            "evidence": "main canonical frontier bundle is single-dataset (openai/gsm8k)",
            "source": "outputs/imported_methodology_frontier_eval/20260417T000000Z",
        },
        {
            "axis": "budget_variation",
            "status": "supported",
            "evidence": "budgets 8 and 10 with full method sweep + oracle",
            "source": "outputs/imported_methodology_frontier_eval/20260417T000000Z/budget_frontier_summary.csv",
        },
        {
            "axis": "seed_variation",
            "status": "supported_internal_aux",
            "evidence": "branch-scorer v3 final eval includes heldout seeds [29,31,37,41,43]",
            "source": "outputs/branch_scorer_v3_final_eval/final_summary.json",
        },
        {
            "axis": "external_baseline_surface",
            "status": "incomplete",
            "evidence": "external baselines are mostly runnable-adjacent/import-validated rather than matched",
            "source": "docs/COMPARISON_BUNDLE_STATUS_2026_04_17.md",
        },
    ]

    csv_path = TABLE_DIR / "robustness_sensitivity.csv"
    tex_path = TABLE_DIR / "robustness_sensitivity.tex"
    write_csv(csv_path, rows)
    _to_tex_table(rows, tex_path)
    return csv_path, tex_path


def build_all_tables() -> list[Path]:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    built = []
    for fn in [
        build_table1_summary,
        build_table2_frontier_comparison,
        build_table3_oracle_headroom,
        build_table4_anti_collapse,
        build_table5_failure_decomposition,
        build_table6_robustness,
    ]:
        csv_path, tex_path = fn()
        built.extend([csv_path, tex_path])
    return built


if __name__ == "__main__":
    for p in build_all_tables():
        print(p)
