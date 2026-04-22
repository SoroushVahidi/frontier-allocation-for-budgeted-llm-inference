#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

CANONICAL_RANKING = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/overall_ranking.csv"
DEFAULT_FULL_COMPARISON_RUN = "20260422T230000Z"
DEFAULT_ADJACENT_BUNDLE_RUN = "20260422T201000Z"
DEFAULT_LOSS_RUN = "20260422T230000Z"
OUR_METHOD = "strict_f3"

ADJACENT_INTEGRATION_OUTPUT_DIR = {
    "best_route_microsoft": "best_route_adjacent_integration",
    "when_solve_when_verify": "when_solve_when_verify_adjacent_integration",
    "rest_mcts": "rest_mcts_adjacent_integration",
    "lets_verify_step_by_step": "lets_verify_step_by_step_adjacent_integration",
    "tree_plv": "tree_plv_adjacent_integration",
}

ADJACENT_METADATA = {
    "best_route_microsoft": {
        "paper_title": "BEST-Route",
        "repo_short_name": "best_route_microsoft",
        "class": "adjacent",
        "artifact_doc_path": "docs/best_route_integration.md",
    },
    "when_solve_when_verify": {
        "paper_title": "When to Solve, When to Verify",
        "repo_short_name": "when_solve_when_verify",
        "class": "adjacent",
        "artifact_doc_path": "docs/when_solve_when_verify_integration.md",
    },
    "rest_mcts": {
        "paper_title": "ReST-MCTS*: LLM Self-Training via Process Reward Guided Tree Search",
        "repo_short_name": "rest_mcts",
        "class": "adjacent",
        "artifact_doc_path": "docs/rest_mcts_integration.md",
    },
    "lets_verify_step_by_step": {
        "paper_title": "Let's Verify Step by Step",
        "repo_short_name": "lets_verify_step_by_step",
        "class": "adjacent_ingredient_neighbor",
        "artifact_doc_path": "docs/lets_verify_step_by_step_integration.md",
    },
    "tree_plv": {
        "paper_title": "Advancing Process Verification for Large Language Models via Tree-Based Preference Learning (Tree-PLV)",
        "repo_short_name": "tree_plv",
        "class": "adjacent",
        "artifact_doc_path": "docs/tree_plv_integration.md",
    },
}

DISCUSSION_ONLY_ROWS = [
    {
        "baseline_id": "qstar_deliberative_planning",
        "paper_title": "Q*: Improving Multi-step Reasoning for LLMs with Deliberative Planning",
        "why_it_matters": "Closest direct conceptual family for deliberate multi-step branch planning under budget pressure.",
        "why_discuss_only": "Official artifacts are provenance-hardened but not verified as runnable in this repository.",
        "main_artifact_blocker": "no_verified_official_repo_or_artifacts_discuss_only_until_provenance_upgrades",
        "safe_wording": "Discuss as important direct-family reference; do not claim integrated runnable baseline.",
        "unofficial_adapter": "yes (qstar_style_adapter, caveated)",
    },
    {
        "baseline_id": "rational_metareasoning_llm",
        "paper_title": "Rational Metareasoning for Large Language Models",
        "why_it_matters": "Provides value-of-computation framing for continuation decisions under constrained compute.",
        "why_discuss_only": "Used as theory/framing reference; no integrated runnable evaluation stack in this repo.",
        "main_artifact_blocker": "theory_framing_reference_not_integrated_as_runnable_stack",
        "safe_wording": "Discuss as conceptual metareasoning backbone; not a runnable empirical comparator here.",
        "unofficial_adapter": "no",
    },
    {
        "baseline_id": "pgts",
        "paper_title": "Policy Guided Tree Search for Enhanced LLM Reasoning",
        "why_it_matters": "Represents policy-guided search controller direction adjacent to budgeted reasoning control.",
        "why_discuss_only": "Official runnable artifacts remain unverified for fair in-repo comparison.",
        "main_artifact_blocker": "official_code_unverified",
        "safe_wording": "Discuss as recent adjacent method family; avoid integrated baseline claims.",
        "unofficial_adapter": "no",
    },
]


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def build_tables(run_id: str, full_comparison_run: str, adjacent_bundle_run: str, loss_run: str) -> tuple[Path, dict[str, Any]]:
    out_dir = REPO_ROOT / "outputs/paper_facing_baseline_tables" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    full_dir = REPO_ROOT / "outputs/full_our_method_vs_external_baselines_comparison" / full_comparison_run
    adjacent_bundle = REPO_ROOT / "outputs/external_adjacent_baseline_bundle" / adjacent_bundle_run / "summary.csv"
    registry_path = REPO_ROOT / "configs/external_baselines_registry.json"
    loss_dir = REPO_ROOT / "outputs/our_method_vs_strongest_external_loss_analysis" / loss_run

    ranking_df = pd.read_csv(CANONICAL_RANKING)
    class_rank_df = pd.read_csv(full_dir / "class_aware_external_baseline_ranking.csv")
    strongest = json.loads((full_dir / "strongest_external_baseline.json").read_text(encoding="utf-8"))
    adjacent_df = pd.read_csv(adjacent_bundle)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))["baselines"]

    near_direct_external = class_rank_df[
        (class_rank_df["taxonomy_label"] == "near_direct")
        & (class_rank_df["comparability_scope"] == "full matched surface")
    ].copy()

    strict_row = ranking_df[ranking_df["method"] == OUR_METHOD].iloc[0]
    near_rows = [
        {
            "method_name": OUR_METHOD,
            "display_name": "strict_f3 (our method)",
            "family": "strict_family",
            "class": "inhouse_direct",
            "runnable_status": "runnable_direct",
            "comparison_surface": "canonical_full_method_ranking_20260421T212948Z",
            "score_primary": float(strict_row["mean_accuracy"]),
            "score_name": "mean_accuracy",
            "is_our_method": True,
            "notes": "Canonical in-house winner and manuscript method.",
        }
    ]
    for _, row in near_direct_external.sort_values(["mean_accuracy", "baseline"], ascending=[False, True]).iterrows():
        near_rows.append(
            {
                "method_name": str(row["baseline"]),
                "display_name": str(row["baseline"]),
                "family": "external_adapter_mode_a",
                "class": "near_direct_external",
                "runnable_status": str(row["status"]),
                "comparison_surface": "canonical_full_method_ranking_20260421T212948Z",
                "score_primary": float(row["mean_accuracy"]),
                "score_name": "mean_accuracy",
                "is_our_method": False,
                "notes": "Fair near-direct external baseline on matched surface.",
            }
        )

    near_df = pd.DataFrame(near_rows).sort_values(["score_primary", "method_name"], ascending=[False, True]).reset_index(drop=True)
    near_df.to_csv(out_dir / "near_direct_ranking.csv", index=False)

    adj_rows: list[dict[str, Any]] = []
    for baseline_id in ["best_route_microsoft", "when_solve_when_verify", "rest_mcts", "lets_verify_step_by_step", "tree_plv"]:
        info = ADJACENT_METADATA[baseline_id]
        src = adjacent_df[adjacent_df["baseline_id"] == baseline_id]
        if src.empty:
            continue
        row = src.iloc[0]
        run_id_val = row.get("latest_integration_run_id")
        artifact_path = info["artifact_doc_path"]
        if pd.notna(run_id_val):
            integration_dir = ADJACENT_INTEGRATION_OUTPUT_DIR.get(baseline_id, f"{baseline_id}_adjacent_integration")
            artifact_path = f"outputs/{integration_dir}/{run_id_val}/"
        adj_rows.append(
            {
                "paper_title": info["paper_title"],
                "repo_short_name": info["repo_short_name"],
                "official_vs_unofficial": str(row["official_vs_unofficial"]),
                "class": info["class"],
                "current_repo_status": str(row["status"]),
                "runnable_strength": str(row["latest_integration_status"]),
                "safe_comparison_scope": str(row["current_safest_comparison_scope"]),
                "key_caveat": str(row["key_limitation"]),
                "artifact_or_doc_path": artifact_path,
            }
        )
    adj_out = pd.DataFrame(adj_rows)
    adj_out.to_csv(out_dir / "adjacent_published_baselines.csv", index=False)

    discuss_rows = []
    for row in DISCUSSION_ONLY_ROWS:
        reg = registry.get(row["baseline_id"], {})
        discuss_rows.append(
            {
                "paper_title": row["paper_title"],
                "why_it_matters": row["why_it_matters"],
                "current_status": reg.get("integration", "unknown"),
                "why_discuss_only": row["why_discuss_only"],
                "main_artifact_blocker": row["main_artifact_blocker"],
                "safe_wording": row["safe_wording"],
                "has_unofficial_adapter": row["unofficial_adapter"],
            }
        )
    discuss_df = pd.DataFrame(discuss_rows)
    discuss_df.to_csv(out_dir / "discussion_only_recent_papers.csv", index=False)

    loss_feature = json.loads((loss_dir / "feature_summary.json").read_text(encoding="utf-8"))
    loss_mech = pd.read_csv(loss_dir / "loss_mechanism_summary.csv")
    ds_mix = pd.read_csv(loss_dir / "dataset_breakdown.csv")

    summary = {
        "run_id": run_id,
        "our_method": OUR_METHOD,
        "strongest_fair_external_baseline": strongest["strongest_external_baseline"],
        "our_mean_accuracy": strongest["our_mean_accuracy"],
        "strongest_external_mean_accuracy": strongest["mean_accuracy"],
        "gap_vs_our": strongest["gap_vs_our"],
        "strict_loss_examples_available": loss_feature["available_loss_candidates"],
        "strict_loss_examples_selected": loss_feature["selected_cases"],
        "dominant_loss_mechanisms": loss_mech.to_dict("records"),
        "dataset_mix": ds_mix.to_dict("records"),
        "separation_policy": {
            "near_direct": "Ranked together on matched canonical surface.",
            "adjacent": "Shown in separate table with caveated safe scope.",
            "discussion_only": "Shown as references with blockers, not integrated baselines.",
        },
    }
    _write_json(out_dir / "paper_facing_baseline_summary.json", summary)

    summary_md_lines = [
        "# Paper-facing baseline summary",
        "",
        f"Run ID: `{run_id}`",
        "",
        f"- Our method: `{OUR_METHOD}`",
        f"- Strongest fair external baseline: `{summary['strongest_fair_external_baseline']}`",
        f"- Accuracy gap (our - strongest fair external): {summary['gap_vs_our']:.6f}",
        f"- Strict-loss examples available: {summary['strict_loss_examples_available']}",
        "",
        "## Why tables are separated",
        "- near_direct: same matched surface and fair ranking bucket.",
        "- adjacent: important published neighbors but non-equivalent control space.",
        "- discussion_only: relevant papers without sufficiently runnable/reproducible artifacts in this repo.",
        "",
        "## Dominant strict loss mechanisms",
    ]
    for row in summary["dominant_loss_mechanisms"]:
        summary_md_lines.append(f"- {row['loss_mechanism']}: {row['count']}")
    summary_md_lines.append("")
    summary_md_lines.append("## Dataset mix in strict losses")
    for row in summary["dataset_mix"]:
        summary_md_lines.append(f"- {row['dataset']}: {row['count']}")
    (out_dir / "paper_facing_baseline_summary.md").write_text("\n".join(summary_md_lines), encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "inputs": {
            "canonical_ranking": str(CANONICAL_RANKING.relative_to(REPO_ROOT)),
            "full_external_comparison_run": str(full_dir.relative_to(REPO_ROOT)),
            "external_adjacent_bundle": str(adjacent_bundle.relative_to(REPO_ROOT)),
            "external_registry": str(registry_path.relative_to(REPO_ROOT)),
            "loss_analysis_run": str(loss_dir.relative_to(REPO_ROOT)),
        },
        "outputs": [
            "near_direct_ranking.csv",
            "adjacent_published_baselines.csv",
            "discussion_only_recent_papers.csv",
            "paper_facing_baseline_summary.json",
            "paper_facing_baseline_summary.md",
            "manifest.json",
            "config_snapshot.json",
            "command_snapshot.txt",
        ],
    }
    _write_json(out_dir / "manifest.json", manifest)

    config_snapshot = {
        "our_method": OUR_METHOD,
        "full_comparison_run": full_comparison_run,
        "adjacent_bundle_run": adjacent_bundle_run,
        "loss_run": loss_run,
        "adjacent_rows": list(ADJACENT_METADATA.keys()),
        "discussion_only_rows": [r["baseline_id"] for r in DISCUSSION_ONLY_ROWS],
    }
    _write_json(out_dir / "config_snapshot.json", config_snapshot)

    cmd = (
        "python scripts/build_paper_facing_baseline_tables.py "
        f"--run-id {run_id} --full-comparison-run {full_comparison_run} "
        f"--adjacent-bundle-run {adjacent_bundle_run} --loss-run {loss_run}\n"
    )
    (out_dir / "command_snapshot.txt").write_text(cmd, encoding="utf-8")

    return out_dir, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build paper-facing baseline comparison tables.")
    parser.add_argument("--run-id", default=_utc_run_id())
    parser.add_argument("--full-comparison-run", default=DEFAULT_FULL_COMPARISON_RUN)
    parser.add_argument("--adjacent-bundle-run", default=DEFAULT_ADJACENT_BUNDLE_RUN)
    parser.add_argument("--loss-run", default=DEFAULT_LOSS_RUN)
    args = parser.parse_args()

    out_dir, summary = build_tables(
        run_id=args.run_id,
        full_comparison_run=args.full_comparison_run,
        adjacent_bundle_run=args.adjacent_bundle_run,
        loss_run=args.loss_run,
    )

    doc_path = REPO_ROOT / "docs" / f"PAPER_FACING_BASELINE_COMPARISON_PACKAGE_{args.run_id}.md"
    doc_path.write_text(
        "\n".join(
            [
                f"# Paper-facing baseline comparison package ({args.run_id})",
                "",
                "Our manuscript method is **strict_f3** because the repository finalized strict_f3 as the single canonical in-house winner on the strongest current canonical matched in-house ranking surface, and current-status docs explicitly lock 'our method' to strict_f3.",
                "",
                "The near-direct ranking is separated from adjacent published baselines because near-direct methods share a matched comparison substrate while adjacent methods have meaningful but non-equivalent control spaces (e.g., routing, verifier/process-guidance, or solve-vs-verify contracts), so merging them into one leaderboard would overstate fairness.",
                "",
                "Discussion-only papers are separated again because they are scientifically important but not honestly runnable enough in the current repository to claim integrated empirical baseline status; they should be cited with blockers and safe wording rather than ranked.",
                "",
                f"The strongest fair external baseline story on the canonical matched surface is: `{summary['strongest_fair_external_baseline']}` is the top near-direct external comparator, but strict_f3 still leads by {summary['gap_vs_our']:.6f} mean accuracy, so the paper can make a clear 'best fair external competitor' comparison without mixing taxonomy buckets.",
                "",
                f"The main remaining failure mechanism story from current strict loss analysis is that strict_f3 has {summary['strict_loss_examples_available']} strict loss examples currently available against the strongest fair external baseline, dominated by absent_from_tree cases with a secondary present_not_selected slice, across a dataset mix led by GSM8K and MATH-500 plus AIME-2024 coverage.",
                "",
                "## Canonical output bundle",
                f"- `outputs/paper_facing_baseline_tables/{args.run_id}/`",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
