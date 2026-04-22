#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def write_md_table(path: Path, df: pd.DataFrame, title: str, intro: str | None = None) -> None:
    lines = [f"# {title}", ""]
    if intro:
        lines += [intro, ""]
    if df.empty:
        lines += ["_No rows available._", ""]
    else:
        cols = [str(c) for c in df.columns]
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
        for row in df.fillna("").astype(str).itertuples(index=False):
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build final publication tables package.")
    p.add_argument("--run-id", default=utc_run_id())
    p.add_argument("--full-comparison-run", default="20260422T230000Z")
    p.add_argument("--loss-run", default="20260422T230000Z")
    p.add_argument("--paper-tables-run", default="20260422T231500Z")
    p.add_argument("--fairness-run", default="20260422T235900Z")
    p.add_argument("--scaling-run", default="20260422T235959Z")
    p.add_argument("--budget-run", default="20260422T045249Z")
    p.add_argument("--stability-run", default="20260422T045249Z")
    p.add_argument("--failure-run", default="20260422T045249Z")
    p.add_argument("--inhouse-run", default="20260422T001521Z")
    p.add_argument("--breadth-run", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = REPO_ROOT / "outputs/publication_tables_package" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    canonical_surface = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv"
    canonical_ranking = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/overall_ranking.csv"

    full_dir = REPO_ROOT / "outputs/full_our_method_vs_external_baselines_comparison" / args.full_comparison_run
    loss_dir = REPO_ROOT / "outputs/our_method_vs_strongest_external_loss_analysis" / args.loss_run
    paper_dir = REPO_ROOT / "outputs/paper_facing_baseline_tables" / args.paper_tables_run
    fair_dir = REPO_ROOT / "outputs/fairness_audit_direct_baselines" / args.fairness_run
    scaling_dir = REPO_ROOT / "outputs/simple_scaling_baseline_coverage_audit" / args.scaling_run
    budget_dir = REPO_ROOT / "outputs/budget_sweep_robustness" / args.budget_run
    stability_dir = REPO_ROOT / "outputs/multi_seed_stability" / args.stability_run
    failure_dir = REPO_ROOT / "outputs/failure_mechanism_robustness" / args.failure_run
    inhouse_dir = REPO_ROOT / "outputs/final_inhouse_method_decision_20260422T001521Z"
    breadth_dir = REPO_ROOT / "outputs/breadth_dataset_eval" / args.breadth_run if args.breadth_run else None

    near = pd.read_csv(paper_dir / "near_direct_ranking.csv")
    near_methods = [
        "strict_f3",
        "external_l1_max",
        "external_tale_prompt_budgeting",
        "external_s1_budget_forcing",
        "external_l1_exact",
    ]
    near = near[near["method_name"].isin(near_methods)].copy()
    near = near.rename(
        columns={
            "family": "role",
            "score_name": "primary_metric_name",
            "score_primary": "primary_metric_value",
        }
    )
    near["comparison_surface"] = "canonical_full_method_ranking_20260421T212948Z"
    near = near[["method_name", "display_name", "role", "class", "comparison_surface", "primary_metric_name", "primary_metric_value", "notes"]]
    near.to_csv(out_dir / "table1_main_near_direct_ranking.csv", index=False)
    write_md_table(out_dir / "table1_main_near_direct_ranking.md", near, "Table 1 — Main fair near-direct ranking")

    adj = pd.read_csv(paper_dir / "adjacent_published_baselines.csv")
    adj = adj[[
        "paper_title",
        "repo_short_name",
        "official_vs_unofficial",
        "current_repo_status",
        "runnable_strength",
        "safe_comparison_scope",
        "key_caveat",
    ]].rename(columns={"safe_comparison_scope": "safe_scope"})
    adj.to_csv(out_dir / "table2_published_adjacent_baselines.csv", index=False)
    write_md_table(out_dir / "table2_published_adjacent_baselines.md", adj, "Table 2 — Published adjacent baselines")

    h2h_inhouse = pd.read_csv(inhouse_dir / "head_to_head_top_candidates.csv")
    inhouse_rank = pd.read_csv(inhouse_dir / "inhouse_overall_ranking.csv")
    contenders = inhouse_rank.head(4)[["method", "mean_accuracy"]].rename(columns={"method": "method_name", "mean_accuracy": "primary_metric_value"})
    contenders["role"] = contenders["method_name"].map(lambda x: "our_method" if x == "strict_f3" else "inhouse_contender")
    contenders["evaluation_surface"] = "canonical_full_method_ranking_20260421T212948Z"
    contenders["selection_status"] = contenders["method_name"].map(lambda x: "selected" if x == "strict_f3" else "not_selected")
    reason_map = {"strict_f3": "Top in-house mean accuracy on canonical matched surface."}
    for _, r in h2h_inhouse.iterrows():
        reason_map[r["opponent"]] = f"Trailing strict_f3 by {float(r['net_margin']):.6f} mean accuracy."
    contenders["reason_selected_or_not"] = contenders["method_name"].map(lambda x: reason_map.get(x, "Lower-ranked than strict_f3 on canonical in-house ranking."))
    t3 = contenders[["method_name", "role", "evaluation_surface", "primary_metric_value", "selection_status", "reason_selected_or_not"]]
    t3.to_csv(out_dir / "table3_internal_ablation_why_strict_f3.csv", index=False)
    write_md_table(out_dir / "table3_internal_ablation_why_strict_f3.md", t3, "Table 3 — Internal ablation / why strict_f3")

    h2h_budget = pd.read_csv(budget_dir / "head_to_head_budget_table.csv")
    curve = pd.read_csv(budget_dir / "budget_curve_table.csv")
    opt_method = "external_s1_budget_forcing" if "external_s1_budget_forcing" in curve["method"].unique() else None
    if opt_method:
        extra = curve[curve["method"] == opt_method][["budget", "accuracy"]].rename(columns={"accuracy": f"{opt_method}_accuracy"})
        t4 = h2h_budget.merge(extra, on="budget", how="left")
    else:
        t4 = h2h_budget.copy()
    t4.to_csv(out_dir / "table4_budget_robustness.csv", index=False)
    write_md_table(out_dir / "table4_budget_robustness.md", t4, "Table 4 — Budget robustness")

    stab = pd.read_csv(stability_dir / "seed_stability_table.csv")
    stab["datasets"] = "openai/gsm8k|HuggingFaceH4/MATH-500|HuggingFaceH4/aime_2024"
    stab = stab.rename(columns={"method": "methods", "mean_accuracy": "mean", "std_accuracy": "spread"})
    stab["summary_note"] = "Repeated evaluation-seed variation (not training-seed variation)."
    t5 = stab[["datasets", "methods", "mean", "spread", "summary_note"]]
    t5.to_csv(out_dir / "table5_multi_run_stability.csv", index=False)
    write_md_table(out_dir / "table5_multi_run_stability.md", t5, "Table 5 — Stability summary")

    feat = json.loads((failure_dir / "feature_summary.json").read_text(encoding="utf-8"))
    ds_break = pd.read_csv(loss_dir / "dataset_breakdown.csv")
    budget_dom = "; ".join([f"b{int(x['budget'])}:{x['dominant_mechanism']}" for x in feat.get("budget_slice_dominant_mechanism", [])])
    t6 = pd.DataFrame([
        {
            "strict_loss_count": feat["loss_count"],
            "absent_from_tree": feat["overall_rates"]["absent_from_tree"],
            "present_not_selected": feat["overall_rates"]["present_not_selected"],
            "dataset_mix": "|".join(f"{r.dataset}:{int(r['count'])}" for _, r in ds_break.iterrows()),
            "budget_slice_dominance": budget_dom,
        }
    ])
    t6.to_csv(out_dir / "table6_failure_mechanism_summary.csv", index=False)
    write_md_table(out_dir / "table6_failure_mechanism_summary.md", t6, "Table 6 — Failure-mechanism summary")

    taxonomy = pd.read_csv(full_dir / "overall_external_baseline_ranking.csv")
    taxonomy.to_csv(out_dir / "appendix_a_full_baseline_taxonomy.csv", index=False)
    write_md_table(out_dir / "appendix_a_full_baseline_taxonomy.md", taxonomy, "Appendix A — Full baseline taxonomy")

    claim = pd.read_csv(fair_dir / "claim_safety_matrix.csv")
    claim.to_csv(out_dir / "appendix_b_claim_safety_matrix.csv", index=False)
    write_md_table(out_dir / "appendix_b_claim_safety_matrix.md", claim, "Appendix B — Claim-safety / comparability matrix")

    outcomes = pd.read_csv(canonical_surface)
    methods = near_methods
    app_c = outcomes[outcomes["method"].isin(methods)].groupby(["dataset", "method"], as_index=False)["is_correct"].mean().rename(columns={"is_correct": "mean_accuracy"})
    app_c = app_c.sort_values(["dataset", "mean_accuracy"], ascending=[True, False])
    app_c.to_csv(out_dir / "appendix_c_per_dataset_near_direct_results.csv", index=False)
    write_md_table(out_dir / "appendix_c_per_dataset_near_direct_results.md", app_c, "Appendix C — Per-dataset near-direct results")

    app_d = pd.read_csv(budget_dir / "budget_curve_by_dataset.csv")
    app_d.to_csv(out_dir / "appendix_d_extended_budget_robustness.csv", index=False)
    write_md_table(out_dir / "appendix_d_extended_budget_robustness.md", app_d, "Appendix D — Extended budget robustness")

    app_e = pd.read_csv(failure_dir / "failure_mechanism_by_dataset.csv")
    app_e.to_csv(out_dir / "appendix_e_extended_failure_slices.csv", index=False)
    write_md_table(out_dir / "appendix_e_extended_failure_slices.md", app_e, "Appendix E — Extended failure slices")

    # Dataset plans
    main_plan = pd.DataFrame([
        {"dataset": "openai/gsm8k", "placement": "main", "reason": "Canonical matched near-direct surface."},
        {"dataset": "HuggingFaceH4/MATH-500", "placement": "main", "reason": "Canonical matched near-direct surface."},
        {"dataset": "HuggingFaceH4/aime_2024", "placement": "main", "reason": "Canonical matched near-direct surface."},
        {"dataset": "allenai/drop", "placement": "not_headline", "reason": "High-value non-math expansion candidate; not in current canonical run."},
        {"dataset": "TAUR-Lab/MuSR", "placement": "not_headline", "reason": "High-value non-math expansion candidate; not in current canonical run."},
    ])
    main_plan.to_csv(out_dir / "main_paper_dataset_plan.csv", index=False)
    write_md_table(out_dir / "main_paper_dataset_plan.md", main_plan, "Main paper dataset plan")

    appendix_plan = pd.DataFrame([
        {"dataset": "openeval/BIG-Bench-Hard", "placement": "appendix_future", "reason": "Cross-domain breadth expansion after DROP/MuSR."},
        {"dataset": "deepmind/aqua_rat", "placement": "appendix_future", "reason": "MCQ reasoning expansion once canonical runs exist."},
        {"dataset": "Idavidrein/gpqa (gpqa_diamond)", "placement": "appendix_future", "reason": "Science anchor desired but absent from current canonical surface."},
    ])
    appendix_plan.to_csv(out_dir / "appendix_dataset_plan.csv", index=False)
    write_md_table(out_dir / "appendix_dataset_plan.md", appendix_plan, "Appendix dataset plan")

    main_index = pd.DataFrame([
        {"table_id": "Table 1", "file_csv": "table1_main_near_direct_ranking.csv", "file_md": "table1_main_near_direct_ranking.md"},
        {"table_id": "Table 2", "file_csv": "table2_published_adjacent_baselines.csv", "file_md": "table2_published_adjacent_baselines.md"},
        {"table_id": "Table 3", "file_csv": "table3_internal_ablation_why_strict_f3.csv", "file_md": "table3_internal_ablation_why_strict_f3.md"},
        {"table_id": "Table 4", "file_csv": "table4_budget_robustness.csv", "file_md": "table4_budget_robustness.md"},
        {"table_id": "Table 5", "file_csv": "table5_multi_run_stability.csv", "file_md": "table5_multi_run_stability.md"},
        {"table_id": "Table 6", "file_csv": "table6_failure_mechanism_summary.csv", "file_md": "table6_failure_mechanism_summary.md"},
    ])
    main_index.to_csv(out_dir / "main_paper_tables_index.csv", index=False)

    appendix_index = pd.DataFrame([
        {"table_id": "Appendix A", "file_csv": "appendix_a_full_baseline_taxonomy.csv", "file_md": "appendix_a_full_baseline_taxonomy.md"},
        {"table_id": "Appendix B", "file_csv": "appendix_b_claim_safety_matrix.csv", "file_md": "appendix_b_claim_safety_matrix.md"},
        {"table_id": "Appendix C", "file_csv": "appendix_c_per_dataset_near_direct_results.csv", "file_md": "appendix_c_per_dataset_near_direct_results.md"},
        {"table_id": "Appendix D", "file_csv": "appendix_d_extended_budget_robustness.csv", "file_md": "appendix_d_extended_budget_robustness.md"},
        {"table_id": "Appendix E", "file_csv": "appendix_e_extended_failure_slices.csv", "file_md": "appendix_e_extended_failure_slices.md"},
    ])
    breadth_added = False
    if breadth_dir is not None and (breadth_dir / "breadth_comparison_summary.csv").exists():
        breadth_df = pd.read_csv(breadth_dir / "breadth_comparison_summary.csv")
        breadth_df.to_csv(out_dir / "appendix_f_breadth_dataset_results.csv", index=False)
        write_md_table(
            out_dir / "appendix_f_breadth_dataset_results.md",
            breadth_df,
            "Appendix F — Breadth dataset results",
            intro=f"Source run: outputs/breadth_dataset_eval/{args.breadth_run}",
        )
        appendix_index = pd.concat(
            [
                appendix_index,
                pd.DataFrame([{"table_id": "Appendix F", "file_csv": "appendix_f_breadth_dataset_results.csv", "file_md": "appendix_f_breadth_dataset_results.md"}]),
            ],
            ignore_index=True,
        )
        breadth_added = True
    appendix_index.to_csv(out_dir / "appendix_tables_index.csv", index=False)

    breadth_gap = True
    critical_gap = False
    gap_note = "Current canonical reported results are math-heavy (gsm8k, MATH-500, aime_2024). This is important but not publication-blocking for the current method-comparison claim because scope is explicitly bounded; prioritize DROP then MuSR in next expansion pass."

    summary = {
        "run_id": args.run_id,
        "our_method": "strict_f3",
        "promoted_strict_phased_default": "strict_gate1_cap_k6",
        "strongest_fair_external_baseline": "external_l1_max",
        "new_experiments_run_in_this_pass": False,
        "publication_critical_gap_remaining": critical_gap,
        "dataset_breadth_gap_present": breadth_gap,
        "dataset_breadth_gap_note": gap_note,
        "breadth_dataset_eval_run": args.breadth_run,
        "breadth_appendix_table": "appendix_f_breadth_dataset_results.csv" if breadth_added else None,
        "main_tables": main_index.to_dict("records"),
        "appendix_tables": appendix_index.to_dict("records"),
    }
    write_json(out_dir / "summary.json", summary)
    write_json(out_dir / "status.json", {"status": "ok", **summary})

    notes = [
        "# Table generation notes",
        "",
        "- No new baseline families were added.",
        "- strict_f3 identity lock was preserved.",
        "- external_l1_max remained the strongest fair external baseline.",
        "- Dataset breadth remains math-heavy; captured as a non-blocking plan item with explicit next datasets (DROP, MuSR).",
    ]
    (out_dir / "table_generation_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    manifest = {
        "inputs": {
            "canonical_surface": str(canonical_surface.relative_to(REPO_ROOT)),
            "canonical_ranking": str(canonical_ranking.relative_to(REPO_ROOT)),
            "full_comparison": str(full_dir.relative_to(REPO_ROOT)),
            "loss_analysis": str(loss_dir.relative_to(REPO_ROOT)),
            "paper_tables": str(paper_dir.relative_to(REPO_ROOT)),
            "fairness": str(fair_dir.relative_to(REPO_ROOT)),
            "scaling": str(scaling_dir.relative_to(REPO_ROOT)),
            "budget": str(budget_dir.relative_to(REPO_ROOT)),
            "stability": str(stability_dir.relative_to(REPO_ROOT)),
            "failure": str(failure_dir.relative_to(REPO_ROOT)),
            "inhouse": str(inhouse_dir.relative_to(REPO_ROOT)),
        },
        "outputs": sorted([p.name for p in out_dir.iterdir() if p.is_file()]),
    }
    write_json(out_dir / "manifest.json", manifest)
    write_json(out_dir / "config_snapshot.json", vars(args))
    (out_dir / "command_snapshot.txt").write_text(
        "python scripts/build_publication_tables_package.py "
        + " ".join(f"--{k.replace('_','-')} {v}" for k, v in vars(args).items())
        + "\n",
        encoding="utf-8",
    )

    summary_md = [
        "# Publication tables package summary",
        "",
        f"- Run ID: `{args.run_id}`",
        "- Main-paper table files generated: 6",
        f"- Appendix table files generated: {len(appendix_index)}",
        f"- Publication-critical empirical gap remaining: `{critical_gap}`",
        f"- Dataset breadth note: {gap_note}",
    ]
    (out_dir / "summary.md").write_text("\n".join(summary_md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
