#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SURFACE = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv"
CANONICAL_RANKING = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/overall_ranking.csv"
OLDER_BUNDLE_METRICS = REPO_ROOT / "outputs/full_method_comparison_bundle/20260419T214335Z/per_method_metrics.csv"

OUT_FAMILY = "internal_method_final_decision_bundle"

FINALISTS = [
    "strict_f3",
    "strict_gate1_cap_k6",
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1",
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1",
    "reasoning_beam2",
    "reasoning_greedy",
    "self_consistency_3",
    "adaptive_min_expand_1",
    "verifier_guided_search",
]

FAMILY_MAP = {
    "strict_f3": "strict_phased_force_gate_cap",
    "strict_gate1_cap_k6": "strict_phased_force_gate_cap",
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1": "broad_diversity_anti_collapse",
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1": "integrated_full_or_repair",
    "reasoning_beam2": "internal_reasoning_baselines",
    "reasoning_greedy": "internal_reasoning_baselines",
    "self_consistency_3": "internal_reasoning_baselines",
    "adaptive_min_expand_1": "earlier_repo_line",
    "verifier_guided_search": "verifier_guided_internal_baseline",
}


def _ts() -> str:
    return pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")


def _head_to_head(df: pd.DataFrame, left: str, right: str) -> dict[str, int]:
    l = df[df["method"] == left].set_index(["dataset", "seed", "budget", "example_id"])["is_correct"]
    r = df[df["method"] == right].set_index(["dataset", "seed", "budget", "example_id"])["is_correct"]
    idx = l.index.intersection(r.index)
    li = l.loc[idx].astype(bool)
    ri = r.loc[idx].astype(bool)
    improved = int((li & ~ri).sum())
    worsened = int((~li & ri).sum())
    unchanged = int((li == ri).sum())
    return {"improved": improved, "worsened": worsened, "unchanged": unchanged}


def _aggregate(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("method", as_index=False).agg(
        accuracy=("is_correct", "mean"),
        avg_actions=("actions", "mean"),
        avg_expansions=("expansions", "mean"),
        avg_verifications=("verifications", "mean"),
        absent_from_tree=("absent_from_tree", "sum"),
        present_not_selected=("present_not_selected", "sum"),
        output_layer_mismatch=("output_layer_mismatch", "sum"),
        repeated_same_family_present=("repeated_same_family_present", "sum"),
        gold_in_tree=("gold_in_tree", "sum"),
        n=("is_correct", "size"),
    )
    g["family"] = g["method"].map(FAMILY_MAP).fillna("other_internal")
    g["absent_rate"] = g["absent_from_tree"] / g["n"]
    g["present_not_selected_rate"] = g["present_not_selected"] / g["n"]
    g["repeated_same_family_rate"] = g["repeated_same_family_present"] / g["n"]
    g = g.sort_values(["accuracy", "absent_rate", "present_not_selected_rate", "avg_actions"], ascending=[False, True, True, True]).reset_index(drop=True)
    g.insert(0, "rank_by_rule", range(1, len(g) + 1))
    return g


def main() -> None:
    out_dir = REPO_ROOT / "outputs" / f"{OUT_FAMILY}_{_ts()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    surface = pd.read_csv(CANONICAL_SURFACE)
    unified = surface[surface["method"].isin(FINALISTS)].copy()

    datasets = sorted(unified["dataset"].unique().tolist())
    seeds = sorted(int(x) for x in unified["seed"].unique().tolist())
    budgets = sorted(int(x) for x in unified["budget"].unique().tolist())

    agg = _aggregate(unified)
    agg.to_csv(out_dir / "internal_unified_summary_table.csv", index=False)

    dataset_comp = unified.groupby(["dataset", "method"], as_index=False).agg(
        accuracy=("is_correct", "mean"),
        avg_actions=("actions", "mean"),
        absent_from_tree=("absent_from_tree", "sum"),
        present_not_selected=("present_not_selected", "sum"),
        repeated_same_family_present=("repeated_same_family_present", "sum"),
    )
    dataset_comp.to_csv(out_dir / "dataset_wise_comparison.csv", index=False)

    cost = agg[["rank_by_rule", "method", "avg_actions", "avg_expansions", "avg_verifications"]].copy()
    cost.to_csv(out_dir / "cost_table.csv", index=False)

    fail = agg[["rank_by_rule", "method", "absent_from_tree", "present_not_selected", "output_layer_mismatch", "gold_in_tree", "absent_rate", "present_not_selected_rate"]].copy()
    fail.to_csv(out_dir / "failure_decomposition.csv", index=False)

    anti = agg[["rank_by_rule", "method", "repeated_same_family_present", "repeated_same_family_rate"]].copy()
    anti.to_csv(out_dir / "anti_collapse_tree_shape_diagnostics.csv", index=False)

    h2h_rows: list[dict[str, Any]] = []
    for left in ["strict_f3", "strict_gate1_cap_k6", "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1", "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1", "reasoning_beam2"]:
        for right in ["strict_f3", "strict_gate1_cap_k6", "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1", "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1", "reasoning_beam2"]:
            if left >= right:
                continue
            d = _head_to_head(unified, left, right)
            h2h_rows.append({"left": left, "right": right, **d})
    h2h = pd.DataFrame(h2h_rows)
    h2h.to_csv(out_dir / "head_to_head_finalists.csv", index=False)

    winner = agg.iloc[0]
    runner_up = agg.iloc[1]

    inventory = pd.DataFrame([
        {"family": "broad_diversity_anti_collapse", "methods": "broad_diversity_aggregation_strong_v1; broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_v1; broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1; broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"},
        {"family": "strict_phased_force_gate_cap", "methods": "strict_f2; strict_f3; strict_gate1; strict_gate2; strict_gate1_cap_k6; strict_gate1_cap_k7; strict_gate1_cap_k8"},
        {"family": "internal_reasoning_baselines", "methods": "reasoning_beam2; reasoning_greedy; self_consistency_3"},
        {"family": "verifier_guided_internal_baseline", "methods": "verifier_guided_search"},
        {"family": "earlier_repo_line", "methods": "adaptive_min_expand_0; adaptive_min_expand_1; adaptive_min_expand_2"},
        {"family": "integrated_full_or_repair", "methods": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1; strict_f3 (integrated strict-phased+repair)"},
    ])
    inventory.to_csv(out_dir / "internal_method_inventory.csv", index=False)

    surfaces = [
        {
            "surface_id": "full_method_comparison_bundle_20260419T214335Z",
            "type": "broad_matched_bundle",
            "winner": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1",
            "limitations": "did not include final strict_gate1_cap_k6 cap family and predated strict-phased default finalization",
            "reused_or_rerun": "reused",
        },
        {
            "surface_id": "broader_strict_phased_default_decision_eval_20260421T023506Z",
            "type": "strict_phased_default_decision",
            "winner": "strict_f2",
            "limitations": "pre-cap final follow-up; superseded by explicit cap K=6/7/8 pass",
            "reused_or_rerun": "reused",
        },
        {
            "surface_id": "final_strict_phased_cap_k678_eval_20260421T043950Z",
            "type": "strict_phased_cap_refinement",
            "winner": "strict_gate1_cap_k6",
            "limitations": "strict-family-focused; not a full cross-family/internal-baseline leaderboard",
            "reused_or_rerun": "reused",
        },
        {
            "surface_id": "canonical_full_method_ranking_20260421T212948Z",
            "type": "manuscript_facing_matched",
            "winner": "strict_f3",
            "limitations": "bounded dataset/seed/budget surface; should not be treated as universal",
            "reused_or_rerun": "reused",
        },
    ]
    pd.DataFrame(surfaces).to_csv(out_dir / "comparison_surfaces_summary.csv", index=False)

    rec = {
        "decision_rule": {
            "primary": "maximize mean accuracy on unified manuscript-facing matched internal surface",
            "secondary": "minimize absent_from_tree and present_not_selected",
            "tertiary": "minimize average actions/expansions with stability checks",
        },
        "surface": {
            "id": "canonical_full_method_ranking_20260421T212948Z (internal-only slice)",
            "datasets": datasets,
            "seeds": seeds,
            "budgets": budgets,
            "rows": int(len(unified)),
            "methods": FINALISTS,
        },
        "recommendation": {
            "winner": str(winner["method"]),
            "runner_up": str(runner_up["method"]),
            "winner_accuracy": float(winner["accuracy"]),
            "runner_up_accuracy": float(runner_up["accuracy"]),
            "margin": float(winner["accuracy"] - runner_up["accuracy"]),
            "claim_boundary": "Best internal method on this canonical matched manuscript-facing surface; not claimed as universal across all budgets/datasets.",
        },
    }
    (out_dir / "final_recommendation.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")

    md = []
    md.append("# Internal method final decision package")
    md.append("")
    md.append("## Unified manuscript-facing internal surface")
    md.append(f"- source: `outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv`")
    md.append(f"- datasets: `{datasets}`")
    md.append(f"- seeds: `{seeds}`")
    md.append(f"- budgets: `{budgets}`")
    md.append(f"- matched rows (internal finalists + anchors): `{len(unified)}`")
    md.append("")
    md.append("## Finalists and anchors")
    for m in FINALISTS:
        md.append(f"- `{m}` ({FAMILY_MAP.get(m, 'other_internal')})")
    md.append("")
    md.append("## Winner by explicit rule")
    md.append(f"- winner: `{winner['method']}`")
    md.append(f"- runner-up: `{runner_up['method']}`")
    md.append(f"- accuracy margin: `{winner['accuracy'] - runner_up['accuracy']:.6f}`")
    md.append("")
    md.append("## Primary limitation")
    md.append("- This resolves the manuscript-facing internal decision on a bounded matched surface; broader external generalization remains open.")
    md.append("")
    md.append("## Artifact files")
    for fn in [
        "internal_unified_summary_table.csv",
        "dataset_wise_comparison.csv",
        "cost_table.csv",
        "failure_decomposition.csv",
        "anti_collapse_tree_shape_diagnostics.csv",
        "head_to_head_finalists.csv",
        "internal_method_inventory.csv",
        "comparison_surfaces_summary.csv",
        "final_recommendation.json",
    ]:
        md.append(f"- `{fn}`")
    (out_dir / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    manifest = {
        "artifact_family": OUT_FAMILY,
        "output_dir": f"outputs/{out_dir.name}",
        "inputs": {
            "canonical_surface": "outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv",
            "canonical_ranking": "outputs/canonical_full_method_ranking_20260421T212948Z/overall_ranking.csv",
            "older_bundle_metrics": "outputs/full_method_comparison_bundle/20260419T214335Z/per_method_metrics.csv",
        },
        "outputs": [
            "internal_unified_summary_table.csv",
            "dataset_wise_comparison.csv",
            "cost_table.csv",
            "failure_decomposition.csv",
            "anti_collapse_tree_shape_diagnostics.csv",
            "head_to_head_finalists.csv",
            "internal_method_inventory.csv",
            "comparison_surfaces_summary.csv",
            "final_recommendation.json",
            "report.md",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(out_dir)


if __name__ == "__main__":
    main()
