#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
OUR_METHOD = "strict_f3"
CANONICAL_SURFACE = "outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv"
CANONICAL_RANKING = "outputs/canonical_full_method_ranking_20260421T212948Z/overall_ranking.csv"
BASELINE_MATRIX = "outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.csv"
EXTERNAL_REGISTRY = "configs/external_baselines_registry.json"

NEAR_DIRECT_METHOD_MAP = {
    "external_s1_budget_forcing": "s1_mode_a",
    "external_tale_prompt_budgeting": "tale_mode_a",
    "external_l1_exact": "l1_mode_a",
    "external_l1_max": "l1_mode_a",
}
ADJACENT_ARTIFACTS = {
    "best_route_microsoft": "outputs/best_route_adjacent_integration/20260422T004457Z/comparison_ready_rows.csv",
    "rest_mcts": "outputs/rest_mcts_adjacent_integration/20260422T022200Z/comparison_ready_rows.csv",
    "lets_verify_step_by_step": "outputs/lets_verify_step_by_step_adjacent_integration/20260422T181500Z/comparison_ready_rows.csv",
    "tree_plv": "outputs/tree_plv_adjacent_integration/20260422T200500Z/comparison_ready_rows.csv",
    "qstar_style_adapter": "outputs/qstar_style_adapter/20260422T160500Z/comparison_summary.csv",
}

def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=_utc_run_id())
    parser.add_argument("--loss-target", type=int, default=100)
    args = parser.parse_args()

    run_id = args.run_id
    cmp_out = REPO_ROOT / "outputs/full_our_method_vs_external_baselines_comparison" / run_id
    loss_out = REPO_ROOT / "outputs/our_method_vs_strongest_external_loss_analysis" / run_id
    cmp_out.mkdir(parents=True, exist_ok=True)
    loss_out.mkdir(parents=True, exist_ok=True)

    ranking_df = pd.read_csv(REPO_ROOT / CANONICAL_RANKING)
    outcomes_df = pd.read_csv(REPO_ROOT / CANONICAL_SURFACE)
    matrix_df = pd.read_csv(REPO_ROOT / BASELINE_MATRIX)
    registry = json.loads((REPO_ROOT / EXTERNAL_REGISTRY).read_text(encoding="utf-8"))

    external_rows = []
    for _, row in ranking_df.iterrows():
        method = str(row["method"])
        if method in NEAR_DIRECT_METHOD_MAP:
            baseline_id = NEAR_DIRECT_METHOD_MAP[method]
            matrix = matrix_df[matrix_df["baseline_id"] == baseline_id].iloc[0].to_dict()
            external_rows.append({
                "baseline": method,
                "baseline_registry_id": baseline_id,
                "taxonomy_label": "near_direct",
                "comparability_scope": "full matched surface",
                "status": matrix["status"],
                "control_equivalence": matrix["control_equivalence"],
                "mean_accuracy": float(row["mean_accuracy"]),
                "source": "canonical_full_method_ranking_20260421T212948Z",
            })

    for baseline_id, artifact in ADJACENT_ARTIFACTS.items():
        p = REPO_ROOT / artifact
        if not p.exists():
            external_rows.append({
                "baseline": baseline_id,
                "baseline_registry_id": baseline_id,
                "taxonomy_label": "adjacent",
                "comparability_scope": "excluded",
                "status": "missing_artifact",
                "control_equivalence": "adjacent",
                "mean_accuracy": None,
                "source": "missing",
            })
            continue
        adf = pd.read_csv(p)
        avg_acc = float(adf["accuracy"].mean()) if "accuracy" in adf.columns else None
        taxonomy = "unofficial_caveated" if baseline_id == "qstar_style_adapter" else "adjacent"
        external_rows.append({
            "baseline": baseline_id,
            "baseline_registry_id": baseline_id,
            "taxonomy_label": taxonomy,
            "comparability_scope": "partial runnable adjacent",
            "status": "partial_runnable_adjacent",
            "control_equivalence": "adjacent",
            "mean_accuracy": avg_acc,
            "source": artifact,
        })

    for baseline_id, cfg in registry.get("baselines", {}).items():
        if any(r["baseline_registry_id"] == baseline_id for r in external_rows):
            continue
        integration = cfg.get("integration", "unknown")
        if integration in {"discuss_only", "blocked"}:
            external_rows.append({
                "baseline": baseline_id,
                "baseline_registry_id": baseline_id,
                "taxonomy_label": "discuss_only",
                "comparability_scope": "excluded",
                "status": integration,
                "control_equivalence": cfg.get("baseline_class", "adjacent"),
                "mean_accuracy": None,
                "source": "configs/external_baselines_registry.json",
            })

    ext_df = pd.DataFrame(external_rows)
    ext_df["rank_score"] = ext_df["mean_accuracy"].fillna(-1.0)
    overall_rank = ext_df.sort_values(["rank_score", "baseline"], ascending=[False, True]).copy()
    overall_rank["overall_rank"] = range(1, len(overall_rank) + 1)
    overall_rank.to_csv(cmp_out / "overall_external_baseline_ranking.csv", index=False)

    class_rank = overall_rank.sort_values(["taxonomy_label", "rank_score", "baseline"], ascending=[True, False, True]).copy()
    class_rank["class_rank"] = class_rank.groupby("taxonomy_label").cumcount() + 1
    class_rank.to_csv(cmp_out / "class_aware_external_baseline_ranking.csv", index=False)

    excluded = class_rank[class_rank["comparability_scope"] == "excluded"].copy()
    excluded["exclusion_reason"] = excluded["status"]
    excluded.to_csv(cmp_out / "excluded_external_baselines.csv", index=False)

    comparable = class_rank[class_rank["comparability_scope"] == "full matched surface"]
    strongest = comparable.sort_values(["mean_accuracy", "baseline"], ascending=[False, True]).iloc[0].to_dict()

    keys = ["dataset", "seed", "budget", "example_id"]
    our = outcomes_df[outcomes_df["method"] == OUR_METHOD][keys + ["is_correct", "actions", "expansions", "verifications", "failure_type", "absent_from_tree", "present_not_selected", "output_layer_mismatch", "gold_in_tree", "repeated_same_family_present"]].copy()
    ext = outcomes_df[outcomes_df["method"] == strongest["baseline"]][keys + ["is_correct", "actions", "expansions", "verifications", "failure_type", "absent_from_tree", "present_not_selected", "output_layer_mismatch", "gold_in_tree", "repeated_same_family_present"]].copy()
    h2h = our.merge(ext, on=keys, suffixes=("_our", "_ext"))
    h2h["outcome"] = h2h.apply(lambda r: "our_win" if r["is_correct_our"] and not r["is_correct_ext"] else ("ext_win" if (not r["is_correct_our"] and r["is_correct_ext"]) else ("both_correct" if r["is_correct_our"] and r["is_correct_ext"] else "both_wrong")), axis=1)
    h2h.to_csv(cmp_out / "head_to_head_vs_our_method.csv", index=False)

    our_acc = float(ranking_df[ranking_df["method"] == OUR_METHOD]["mean_accuracy"].iloc[0])
    strongest_json = {
        "our_method": OUR_METHOD,
        "strongest_external_baseline": strongest["baseline"],
        "why": "Highest mean accuracy among external baselines on the full canonical matched surface.",
        "surface": "canonical_full_method_ranking_20260421T212948Z",
        "metric": "mean_accuracy",
        "taxonomy_label": strongest["taxonomy_label"],
        "comparability_scope": strongest["comparability_scope"],
        "mean_accuracy": strongest["mean_accuracy"],
        "our_mean_accuracy": our_acc,
        "gap_vs_our": float(our_acc - strongest["mean_accuracy"]),
    }
    _write_json(cmp_out / "strongest_external_baseline.json", strongest_json)
    (cmp_out / "strongest_external_baseline.md").write_text(
        "\n".join([
            "# Strongest external baseline",
            f"- baseline: `{strongest_json['strongest_external_baseline']}`",
            f"- reason: {strongest_json['why']}",
            f"- surface: {strongest_json['surface']}",
            f"- metric: {strongest_json['metric']}",
            f"- taxonomy_label: {strongest_json['taxonomy_label']}",
            f"- comparability_scope: {strongest_json['comparability_scope']}",
        ]),
        encoding="utf-8",
    )

    loss_df = h2h[h2h["outcome"] == "ext_win"].copy()
    loss_df["diagnostic_richness"] = (
        loss_df["absent_from_tree_our"].astype(int)
        + loss_df["present_not_selected_our"].astype(int)
        + loss_df["output_layer_mismatch_our"].astype(int)
        + loss_df["repeated_same_family_present_our"].astype(int)
    )
    loss_df["case_id"] = loss_df["dataset"].str.replace("/", "__") + "__" + loss_df["example_id"]

    legacy_path = REPO_ROOT / "outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/failure_statistics_table.csv"
    if legacy_path.exists() and not loss_df.empty:
        legacy = pd.read_csv(legacy_path)[["dataset", "example_id", "problem_regime_label", "error_geometry", "best_method_advantage_type", "selected_support_count", "num_answer_groups", "dominant_answer_group_share"]].drop_duplicates(["dataset", "example_id"])
        loss_df = loss_df.merge(legacy, on=["dataset", "example_id"], how="left")

    by_ds = {k: v.sort_values(["diagnostic_richness", "budget"], ascending=[False, False]).to_dict("records") for k, v in loss_df.groupby("dataset")}
    ordered = []
    while True:
        moved = False
        for ds in sorted(by_ds):
            if by_ds[ds]:
                ordered.append(by_ds[ds].pop(0))
                moved = True
        if not moved:
            break
    selected = pd.DataFrame(ordered[: args.loss_target])

    selected.to_csv(loss_out / "loss_analysis_100.csv", index=False)
    _write_json(loss_out / "loss_analysis_100.json", selected.to_dict("records"))

    mech = selected["failure_type_our"].fillna("unknown").value_counts().rename_axis("loss_mechanism").reset_index(name="count") if not selected.empty else pd.DataFrame(columns=["loss_mechanism", "count"])
    mech.to_csv(loss_out / "loss_mechanism_summary.csv", index=False)
    ds = selected["dataset"].value_counts().rename_axis("dataset").reset_index(name="count") if not selected.empty else pd.DataFrame(columns=["dataset", "count"])
    ds.to_csv(loss_out / "dataset_breakdown.csv", index=False)
    _write_json(loss_out / "feature_summary.json", {
        "selection_target": args.loss_target,
        "selected_cases": int(len(selected)),
        "available_loss_candidates": int(len(loss_df)),
        "shortfall_reason": "canonical full matched surface has fewer than requested strict_f3-loss / strongest-external-win rows" if len(loss_df) < args.loss_target else None,
        "our_absent_from_tree_rate": float(selected["absent_from_tree_our"].mean()) if len(selected) else 0.0,
        "our_present_not_selected_rate": float(selected["present_not_selected_our"].mean()) if len(selected) else 0.0,
        "our_output_layer_mismatch_rate": float(selected["output_layer_mismatch_our"].mean()) if len(selected) else 0.0,
    })

    (loss_out / "loss_analysis_100.md").write_text(
        "\n".join([
            f"# Loss analysis: {OUR_METHOD} vs {strongest_json['strongest_external_baseline']}",
            "",
            f"Requested target: {args.loss_target}",
            f"Available strict losses on canonical matched surface: {len(loss_df)}",
            f"Selected: {len(selected)}",
            "",
            "## Selection rule",
            "1. strict_f3 wrong and strongest external correct",
            "2. prefer richer observability flags (absent/present-not-selected/output-mismatch/repeated-family)",
            "3. round-robin by dataset for coverage",
            "4. prefer higher-budget rows within each dataset",
        ]),
        encoding="utf-8",
    )

    summary = {
        "run_id": run_id,
        "our_method": OUR_METHOD,
        "strongest_external_baseline": strongest_json["strongest_external_baseline"],
        "canonical_surface": "canonical_full_method_ranking_20260421T212948Z",
        "overall_rank_rows": int(len(overall_rank)),
        "loss_bundle_selected": int(len(selected)),
        "loss_bundle_candidates": int(len(loss_df)),
    }
    _write_json(cmp_out / "summary.json", summary)
    _write_json(cmp_out / "status.json", {"status": "ok", **summary})
    _write_json(cmp_out / "manifest.json", {
        "selection_rule": "Ranking and loss analysis are both anchored to canonical full matched surface outputs.",
        "loss_selection_rule": [
            "strict_f3 wrong + strongest external correct",
            "diagnostic richness",
            "dataset round-robin coverage",
            "higher budget tie-break",
        ],
        "required_inputs": [CANONICAL_RANKING, CANONICAL_SURFACE, BASELINE_MATRIX, EXTERNAL_REGISTRY],
    })
    (cmp_out / "config_snapshot.json").write_text(json.dumps({"our_method": OUR_METHOD, "near_direct_map": NEAR_DIRECT_METHOD_MAP, "adjacent_artifacts": ADJACENT_ARTIFACTS}, indent=2), encoding="utf-8")
    (cmp_out / "command_snapshot.txt").write_text(f"python scripts/run_full_our_method_vs_external_baselines_comparison.py --run-id {run_id}\n", encoding="utf-8")
    (cmp_out / "summary.md").write_text(
        "\n".join([
            f"# Full our-method vs external baselines comparison ({run_id})",
            "",
            f"Our method: `{OUR_METHOD}`",
            f"Strongest external baseline on canonical full matched surface: `{strongest_json['strongest_external_baseline']}` (mean_accuracy={strongest_json['mean_accuracy']:.6f}).",
            f"Gap vs our method: {strongest_json['gap_vs_our']:.6f}.",
            f"Loss analysis selected {len(selected)} / requested {args.loss_target} cases (available strict losses={len(loss_df)}).",
        ]),
        encoding="utf-8",
    )

    report = REPO_ROOT / "docs" / f"FULL_OUR_METHOD_VS_EXTERNAL_BASELINES_COMPARISON_{run_id}.md"
    report.write_text(
        "\n".join([
            f"# Full our-method vs external baselines comparison ({run_id})",
            "",
            f"- Canonical our method: `{OUR_METHOD}`.",
            f"- Strongest external baseline on full matched surface: `{strongest_json['strongest_external_baseline']}`.",
            f"- Our mean accuracy: {strongest_json['our_mean_accuracy']:.6f}.",
            f"- Strongest external mean accuracy: {strongest_json['mean_accuracy']:.6f}.",
            f"- Gap (our - strongest external): {strongest_json['gap_vs_our']:.6f}.",
            "",
            "## Baseline taxonomy and comparability",
            "- near_direct rows are ranked on canonical matched surface.",
            "- adjacent rows are preserved separately and not merged into direct claim space.",
            "- discuss_only rows are explicitly excluded with reasons.",
            "- unofficial caveated adapters remain in their own trust bucket.",
            "",
            "## Loss-analysis note",
            f"- Requested 100 strict losses, but canonical matched surface provides {len(loss_df)} strict losses.",
            f"- This bundle includes all {len(selected)} available strict losses without fabricating extra rows.",
        ]),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
