#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

SURFACE_DIR = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z"
SURFACE_OUTCOMES = SURFACE_DIR / "per_case_outcomes.csv"
SURFACE_RANKING = SURFACE_DIR / "overall_ranking.csv"
BASELINE_STATUS = REPO_ROOT / "outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.csv"

EXPERIMENT_NAME = "paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3"

INHOUSE_REQUIRED = [
    "strict_gate1_cap_k6",
    "strict_gate1",
    "strict_f2",
    "strict_f3",
    "strict_gate2",
]
EXTERNAL_REQUIRED = [
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
    "external_l1_exact",
    "external_l1_max",
]


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _mean_accuracy(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    return float(df["is_correct"].astype(float).mean())


def _method_metrics(df: pd.DataFrame, method: str) -> dict[str, Any]:
    sub = df[df["method"] == method]
    if sub.empty:
        return {
            "method": method,
            "n_cases": 0,
            "mean_accuracy": None,
            "avg_actions": None,
            "avg_expansions": None,
            "avg_verifications": None,
            "absent_from_tree_rate": None,
            "present_not_selected_rate": None,
            "output_layer_mismatch_rate": None,
            "repeated_same_family_rate": None,
        }
    return {
        "method": method,
        "n_cases": int(len(sub)),
        "mean_accuracy": float(sub["is_correct"].astype(float).mean()),
        "avg_actions": float(sub["actions"].mean()),
        "avg_expansions": float(sub["expansions"].mean()),
        "avg_verifications": float(sub["verifications"].mean()),
        "absent_from_tree_rate": float(sub["absent_from_tree"].astype(float).mean()),
        "present_not_selected_rate": float(sub["present_not_selected"].astype(float).mean()),
        "output_layer_mismatch_rate": float(sub["output_layer_mismatch"].astype(float).mean()),
        "repeated_same_family_rate": float(sub["repeated_same_family_present"].astype(float).mean()),
    }


def _recommendation(metrics_by_method: dict[str, dict[str, Any]], strongest_external: str) -> dict[str, Any]:
    sg = metrics_by_method.get("strict_gate1_cap_k6", {})
    sf3 = metrics_by_method.get("strict_f3", {})
    ext = metrics_by_method.get(strongest_external, {})
    if not sg or not sf3 or sg.get("mean_accuracy") is None or sf3.get("mean_accuracy") is None:
        return {
            "recommendation": "evidence remains inconclusive",
            "reason": "One or both core in-house contenders are missing from the chosen decision surface.",
        }

    sg_acc = float(sg["mean_accuracy"])
    sf3_acc = float(sf3["mean_accuracy"])
    ext_acc = float(ext["mean_accuracy"]) if ext and ext.get("mean_accuracy") is not None else None

    if sg_acc > sf3_acc and (ext_acc is None or sg_acc >= ext_acc):
        return {
            "recommendation": "paper should center strict_gate1_cap_k6",
            "reason": "strict_gate1_cap_k6 is higher than strict_f3 on the decision surface and is at least as strong as the top fair near-direct external comparator.",
        }
    if sf3_acc > sg_acc and (ext_acc is None or sf3_acc >= ext_acc):
        return {
            "recommendation": "paper should center strict_f3",
            "reason": "strict_f3 remains stronger on the decision surface and is at least as strong as the top fair near-direct external comparator.",
        }
    return {
        "recommendation": "evidence remains inconclusive",
        "reason": "Accuracy ordering and fair-external comparison do not produce a robust single-method winner under this bounded surface.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build strict_gate1_cap_k6 vs strict_f3 paper-decision bundle.")
    parser.add_argument("--run-id", default=_utc_run_id())
    args = parser.parse_args()

    if not SURFACE_OUTCOMES.exists() or not SURFACE_RANKING.exists():
        raise FileNotFoundError("Canonical matched decision surface is missing required files.")

    run_id = args.run_id
    out_dir = REPO_ROOT / "outputs" / EXPERIMENT_NAME / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    outcomes = pd.read_csv(SURFACE_OUTCOMES)
    ranking = pd.read_csv(SURFACE_RANKING)
    baseline_status = pd.read_csv(BASELINE_STATUS) if BASELINE_STATUS.exists() else pd.DataFrame()

    requested_methods = INHOUSE_REQUIRED + EXTERNAL_REQUIRED
    available_methods = set(outcomes["method"].unique().tolist())
    runnable_methods = [m for m in requested_methods if m in available_methods]
    blocked_methods = [m for m in requested_methods if m not in available_methods]

    blocked_rows: list[dict[str, Any]] = []
    for method in blocked_methods:
        blocker = "method_not_present_on_canonical_matched_surface"
        caveat = "Blocked for this decision bundle; kept in manifest for transparent comparability accounting."
        blocked_rows.append(
            {
                "method": method,
                "class": "inhouse" if method in INHOUSE_REQUIRED else "near_direct_external",
                "status": "blocked",
                "comparability": "not_comparable_on_surface",
                "blocker_reason": blocker,
                "caveat": caveat,
            }
        )
    blocked_df = pd.DataFrame(blocked_rows)
    blocked_df.to_csv(out_dir / "blocked_or_caveated_methods.csv", index=False)

    decision_df = outcomes[outcomes["method"].isin(runnable_methods)].copy()
    decision_df["method_class"] = decision_df["method"].map(
        lambda m: "inhouse" if m in INHOUSE_REQUIRED else "near_direct_external"
    )

    metrics_rows = [_method_metrics(decision_df, m) for m in runnable_methods]
    comparison_df = pd.DataFrame(metrics_rows).sort_values(
        ["mean_accuracy", "method"], ascending=[False, True], na_position="last"
    )
    comparison_df.to_csv(out_dir / "comparison_table.csv", index=False)

    per_dataset = (
        decision_df.groupby(["dataset", "method", "method_class"], as_index=False)
        .agg(
            n_cases=("is_correct", "size"),
            mean_accuracy=("is_correct", "mean"),
            avg_actions=("actions", "mean"),
            avg_expansions=("expansions", "mean"),
            avg_verifications=("verifications", "mean"),
            absent_from_tree_rate=("absent_from_tree", "mean"),
            present_not_selected_rate=("present_not_selected", "mean"),
            output_layer_mismatch_rate=("output_layer_mismatch", "mean"),
            repeated_same_family_rate=("repeated_same_family_present", "mean"),
        )
    )
    per_dataset.to_csv(out_dir / "per_dataset_summary.csv", index=False)

    per_seed = (
        decision_df.groupby(["seed", "method", "method_class"], as_index=False)
        .agg(
            n_cases=("is_correct", "size"),
            mean_accuracy=("is_correct", "mean"),
            avg_actions=("actions", "mean"),
            avg_expansions=("expansions", "mean"),
            avg_verifications=("verifications", "mean"),
            absent_from_tree_rate=("absent_from_tree", "mean"),
            present_not_selected_rate=("present_not_selected", "mean"),
            output_layer_mismatch_rate=("output_layer_mismatch", "mean"),
            repeated_same_family_rate=("repeated_same_family_present", "mean"),
        )
    )
    per_seed.to_csv(out_dir / "per_seed_summary.csv", index=False)

    failure = (
        decision_df.groupby(["method", "method_class"], as_index=False)
        .agg(
            n_cases=("is_correct", "size"),
            absent_from_tree_n=("absent_from_tree", "sum"),
            present_not_selected_n=("present_not_selected", "sum"),
            output_layer_mismatch_n=("output_layer_mismatch", "sum"),
            absent_from_tree_rate=("absent_from_tree", "mean"),
            present_not_selected_rate=("present_not_selected", "mean"),
            output_layer_mismatch_rate=("output_layer_mismatch", "mean"),
        )
    )
    failure.to_csv(out_dir / "failure_decomposition.csv", index=False)

    collapse = (
        decision_df.groupby(["method", "method_class"], as_index=False)
        .agg(
            n_cases=("is_correct", "size"),
            repeated_same_family_case_rate=("repeated_same_family_present", "mean"),
            avg_actions=("actions", "mean"),
            avg_expansions=("expansions", "mean"),
            avg_verifications=("verifications", "mean"),
        )
    )
    collapse.to_csv(out_dir / "collapse_diagnostics.csv", index=False)

    # Figure-ready outputs
    budget_frontier = (
        decision_df.groupby(["budget", "method", "method_class"], as_index=False)
        .agg(mean_accuracy=("is_correct", "mean"), avg_actions=("actions", "mean"))
    )
    budget_frontier.to_csv(out_dir / "budget_performance_frontier.csv", index=False)

    inhouse_runnable = [m for m in INHOUSE_REQUIRED if m in runnable_methods]
    key_cols = ["dataset", "seed", "budget", "example_id"]
    if inhouse_runnable:
        pivot = (
            decision_df[decision_df["method"].isin(inhouse_runnable)]
            .pivot_table(index=key_cols, columns="method", values="is_correct", aggfunc="first")
            .reset_index()
        )
        oracle_series = pivot[inhouse_runnable].max(axis=1)
        oracle_df = pivot[key_cols].copy()
        oracle_df["oracle_inhouse"] = oracle_series.astype(float)
        regret_rows: list[dict[str, Any]] = []
        for method in runnable_methods:
            msub = decision_df[decision_df["method"] == method][key_cols + ["is_correct"]]
            merged = oracle_df.merge(msub, on=key_cols, how="inner")
            merged["regret"] = merged["oracle_inhouse"] - merged["is_correct"].astype(float)
            for budget, bdf in merged.groupby("budget"):
                regret_rows.append(
                    {
                        "budget": int(budget),
                        "method": method,
                        "method_class": "inhouse" if method in INHOUSE_REQUIRED else "near_direct_external",
                        "mean_regret_vs_inhouse_oracle": float(bdf["regret"].mean()),
                        "oracle_accuracy": float(bdf["oracle_inhouse"].mean()),
                        "method_accuracy": float(bdf["is_correct"].astype(float).mean()),
                    }
                )
        oracle_gap = pd.DataFrame(regret_rows)
    else:
        oracle_gap = pd.DataFrame(
            columns=[
                "budget",
                "method",
                "method_class",
                "mean_regret_vs_inhouse_oracle",
                "oracle_accuracy",
                "method_accuracy",
            ]
        )
    oracle_gap.to_csv(out_dir / "oracle_gap_regret.csv", index=False)
    collapse.to_csv(out_dir / "anti_collapse_plot_data.csv", index=False)
    failure.to_csv(out_dir / "failure_decomposition_plot_data.csv", index=False)

    strongest_external = None
    external_comp = comparison_df[comparison_df["method"].isin(EXTERNAL_REQUIRED) & comparison_df["mean_accuracy"].notna()]
    if not external_comp.empty:
        strongest_external = str(external_comp.sort_values(["mean_accuracy", "method"], ascending=[False, True]).iloc[0]["method"])

    decision_table_methods = ["strict_gate1_cap_k6", "strict_f3"]
    if strongest_external:
        decision_table_methods.append(strongest_external)
    decision_table = comparison_df[comparison_df["method"].isin(decision_table_methods)].copy()
    decision_table.to_csv(out_dir / "decision_table.csv", index=False)

    metrics_by_method = {str(row["method"]): row for row in comparison_df.to_dict("records")}
    recommendation = _recommendation(metrics_by_method, strongest_external or "")
    recommendation_payload = {
        "experiment_name": EXPERIMENT_NAME,
        "run_id": run_id,
        "surface": {
            "surface_id": "canonical_full_method_ranking_20260421T212948Z",
            "surface_path": str(SURFACE_DIR.relative_to(REPO_ROOT)),
            "datasets": sorted(decision_df["dataset"].unique().tolist()),
            "seeds": sorted([int(x) for x in decision_df["seed"].unique().tolist()]),
            "budgets": sorted([int(x) for x in decision_df["budget"].unique().tolist()]),
        },
        "strongest_fair_near_direct_external": strongest_external,
        "recommendation": recommendation["recommendation"],
        "reason": recommendation["reason"],
    }
    _write_json(out_dir / "decision_recommendation.json", recommendation_payload)

    aggregate_summary = {
        "experiment_name": EXPERIMENT_NAME,
        "run_id": run_id,
        "surface_id": "canonical_full_method_ranking_20260421T212948Z",
        "requested_methods": requested_methods,
        "runnable_methods": runnable_methods,
        "blocked_methods": blocked_methods,
        "inhouse_question": {
            "strict_gate1_cap_k6_mean_accuracy": metrics_by_method.get("strict_gate1_cap_k6", {}).get("mean_accuracy"),
            "strict_f3_mean_accuracy": metrics_by_method.get("strict_f3", {}).get("mean_accuracy"),
            "strict_gate1_cap_k6_minus_strict_f3": (
                None
                if "strict_gate1_cap_k6" not in metrics_by_method or "strict_f3" not in metrics_by_method
                else float(metrics_by_method["strict_gate1_cap_k6"]["mean_accuracy"])
                - float(metrics_by_method["strict_f3"]["mean_accuracy"])
            ),
        },
        "external_question": {
            "strongest_fair_near_direct_external": strongest_external,
            "strict_gate1_cap_k6_gap_vs_strongest_external": (
                None
                if not strongest_external or "strict_gate1_cap_k6" not in metrics_by_method
                else float(metrics_by_method["strict_gate1_cap_k6"]["mean_accuracy"])
                - float(metrics_by_method[strongest_external]["mean_accuracy"])
            ),
            "strict_f3_gap_vs_strongest_external": (
                None
                if not strongest_external or "strict_f3" not in metrics_by_method
                else float(metrics_by_method["strict_f3"]["mean_accuracy"])
                - float(metrics_by_method[strongest_external]["mean_accuracy"])
            ),
        },
        "recommendation": recommendation_payload,
    }
    _write_json(out_dir / "aggregate_summary.json", aggregate_summary)

    status_rows = []
    baseline_status_lookup = {}
    if not baseline_status.empty:
        for _, row in baseline_status.iterrows():
            baseline_status_lookup[str(row.get("baseline_id", ""))] = row.to_dict()
    for method in requested_methods:
        status = "runnable" if method in runnable_methods else "blocked"
        status_rows.append(
            {
                "method": method,
                "class": "inhouse" if method in INHOUSE_REQUIRED else "near_direct_external",
                "status": status,
                "on_decision_surface": method in runnable_methods,
                "baseline_status_matrix_row": baseline_status_lookup.get(method, {}),
            }
        )

    eval_manifest = {
        "experiment_name": EXPERIMENT_NAME,
        "run_id": run_id,
        "surface_selection": {
            "surface_id": "canonical_full_method_ranking_20260421T212948Z",
            "reason": "Single reproducible matched surface that already includes fair near-direct external baselines and both core manuscript contenders strict_gate1_cap_k6 and strict_f3.",
            "source_files": [
                str(SURFACE_OUTCOMES.relative_to(REPO_ROOT)),
                str(SURFACE_RANKING.relative_to(REPO_ROOT)),
            ],
            "datasets": sorted(decision_df["dataset"].unique().tolist()),
            "seeds": sorted([int(x) for x in decision_df["seed"].unique().tolist()]),
            "budgets": sorted([int(x) for x in decision_df["budget"].unique().tolist()]),
        },
        "requested_methods": requested_methods,
        "method_status_table": status_rows,
        "output_files": sorted([p.name for p in out_dir.iterdir() if p.is_file()]),
    }
    _write_json(out_dir / "eval_manifest.json", eval_manifest)

    summary_lines = [
        f"# {EXPERIMENT_NAME}",
        "",
        f"Run ID: `{run_id}`",
        "",
        "## Surface",
        "- `outputs/canonical_full_method_ranking_20260421T212948Z/`",
        "- single matched decision surface for in-house strict variants and fair near-direct externals",
        "",
        "## Methods",
        f"- requested: {', '.join(requested_methods)}",
        f"- runnable: {', '.join(runnable_methods)}",
        f"- blocked: {', '.join(blocked_methods) if blocked_methods else 'none'}",
        "",
        "## Main result snapshot",
        f"- strongest fair near-direct external: `{strongest_external}`" if strongest_external else "- strongest fair near-direct external: unavailable",
        f"- recommendation: **{recommendation_payload['recommendation']}**",
        f"- reason: {recommendation_payload['reason']}",
        "",
        "## Outputs",
        "- `comparison_table.csv`",
        "- `aggregate_summary.json`",
        "- `per_dataset_summary.csv`",
        "- `per_seed_summary.csv`",
        "- `failure_decomposition.csv`",
        "- `collapse_diagnostics.csv`",
        "- `blocked_or_caveated_methods.csv`",
        "- `decision_recommendation.json`",
        "- figure-ready: `budget_performance_frontier.csv`, `oracle_gap_regret.csv`, `anti_collapse_plot_data.csv`, `failure_decomposition_plot_data.csv`, `decision_table.csv`",
    ]
    (out_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    doc_path = REPO_ROOT / "docs" / f"PAPER_METHOD_DECISION_BUNDLE_{run_id}.md"
    doc_lines = [
        f"# Paper Method Decision Bundle ({run_id})",
        "",
        "## Chosen decision surface",
        "- Surface: `outputs/canonical_full_method_ranking_20260421T212948Z/`.",
        "- Why: this is the cleanest single matched surface in-repo that includes the key in-house contenders and all fair near-direct external baselines under one budget/dataset/seed contract.",
        "",
        "## Compared methods",
        f"- Requested in-house: {', '.join(INHOUSE_REQUIRED)}",
        f"- Requested fair near-direct externals: {', '.join(EXTERNAL_REQUIRED)}",
        f"- Runnable on surface: {', '.join(runnable_methods)}",
        f"- Blocked/caveated: {', '.join(blocked_methods) if blocked_methods else 'none'}",
        "",
        "## Aggregate results",
    ]
    for _, row in comparison_df.iterrows():
        doc_lines.append(
            f"- `{row['method']}`: acc={row['mean_accuracy'] if pd.notna(row['mean_accuracy']) else 'NA'}, "
            f"absent={row['absent_from_tree_rate'] if pd.notna(row['absent_from_tree_rate']) else 'NA'}, "
            f"present_not_selected={row['present_not_selected_rate'] if pd.notna(row['present_not_selected_rate']) else 'NA'}"
        )
    doc_lines.extend(
        [
            "",
            "## Mechanism diagnostics",
            "- Budget-performance frontier: `budget_performance_frontier.csv`.",
            "- Oracle-gap/regret: `oracle_gap_regret.csv`.",
            "- Anti-collapse diagnostics: `collapse_diagnostics.csv` and `anti_collapse_plot_data.csv`.",
            "- Failure decomposition: `failure_decomposition.csv` and `failure_decomposition_plot_data.csv`.",
            "",
            "## Fairness caveats",
            "- Near-direct externals are inference-only adapter comparisons under matched substrate conventions.",
            "- Adjacent baselines are not merged into this decision surface.",
            "",
            "## Final recommendation",
            f"- Recommendation: **{recommendation_payload['recommendation']}**",
            f"- Reason: {recommendation_payload['reason']}",
            "",
            "## Artifact paths",
            f"- `outputs/{EXPERIMENT_NAME}/{run_id}/`",
            f"- `docs/PAPER_METHOD_DECISION_BUNDLE_{run_id}.md`",
        ]
    )
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")

    print(f"output_dir=outputs/{EXPERIMENT_NAME}/{run_id}")
    print(f"report=docs/PAPER_METHOD_DECISION_BUNDLE_{run_id}.md")


if __name__ == "__main__":
    main()

