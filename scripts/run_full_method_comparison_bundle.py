#!/usr/bin/env python3
"""Run a bounded but audit-friendly full method comparison bundle.

This script compares:
- current recommended in-repo anchor (`adaptive_min_expand_1`),
- strong internal baselines,
- earlier in-repo method lines (`adaptive_min_expand_0/2`),
- integrated external MODE A adapters (s1 / TALE / L1),
- and explicit status rows for import-validated-only adjacent baselines.

Outputs are written under outputs/full_method_comparison_bundle/<run_id>/.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import statistics
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (  # noqa: E402
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
)

OUR_METHOD = "adaptive_min_expand_1"

METHOD_INFO: dict[str, dict[str, str]] = {
    "adaptive_min_expand_0": {
        "family": "earlier_repo_line",
        "comparability": "direct",
        "status": "runnable_direct",
    },
    "adaptive_min_expand_1": {
        "family": "our_current_main",
        "comparability": "direct",
        "status": "runnable_direct",
    },
    "adaptive_min_expand_2": {
        "family": "earlier_repo_line",
        "comparability": "direct",
        "status": "runnable_direct",
    },
    "reasoning_greedy": {
        "family": "internal_baseline",
        "comparability": "direct",
        "status": "runnable_direct",
    },
    "self_consistency_3": {
        "family": "internal_baseline",
        "comparability": "direct",
        "status": "runnable_direct",
    },
    "reasoning_beam2": {
        "family": "internal_baseline",
        "comparability": "direct",
        "status": "runnable_direct",
    },
    "verifier_guided_search": {
        "family": "internal_baseline",
        "comparability": "direct",
        "status": "runnable_direct",
    },
    "program_of_thought": {
        "family": "internal_baseline",
        "comparability": "direct",
        "status": "runnable_direct",
    },
    "external_s1_budget_forcing": {
        "family": "external_baseline",
        "comparability": "adapter_mode_a",
        "status": "runnable_direct",
    },
    "external_tale_prompt_budgeting": {
        "family": "external_baseline",
        "comparability": "adapter_mode_a",
        "status": "runnable_direct",
    },
    "external_l1_exact": {
        "family": "external_baseline",
        "comparability": "adapter_mode_a",
        "status": "runnable_direct",
    },
    "external_l1_max": {
        "family": "external_baseline",
        "comparability": "adapter_mode_a",
        "status": "runnable_direct",
    },
}

ADJACENT_IMPORT_VALIDATED = [
    "best_route",
    "when_solve_when_verify",
    "cascade_routing",
    "mob_majority_of_bests",
    "rest_mcts",
    "openr",
]
BLOCKED = ["compute_optimal_tts"]


def _parse_int_csv(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _safe_mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_sorted = sorted(
        rows,
        key=lambda r: (
            -float(r["mean_accuracy"]),
            float(r["mean_avg_actions"]),
            -float(r["mean_coverage"]),
            str(r["method"]),
        ),
    )
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows_sorted, start=1):
        out.append({**row, "rank": idx})
    return out


def _failure_subtype(ours: dict[str, Any], other: dict[str, Any]) -> str:
    if int(ours["actions_used"]) + 2 <= int(other["actions_used"]):
        return "under_exploration_or_early_commit"
    if int(other["verifications"]) > int(ours["verifications"]):
        return "verification_gap"
    if int(other["expansions"]) > int(ours["expansions"]):
        return "branch_allocation_gap"
    if bool(ours["budget_exhausted"]) and not bool(other["budget_exhausted"]):
        return "inefficient_budget_spend"
    return "selection_or_aggregation_gap"


def _advantage_source(ours: dict[str, Any], other: dict[str, Any]) -> str:
    subtype = _failure_subtype(ours, other)
    mapping = {
        "under_exploration_or_early_commit": "better stopping / continuation timing",
        "verification_gap": "better verification",
        "branch_allocation_gap": "better search / branch allocation",
        "inefficient_budget_spend": "better stopping and budget discipline",
        "selection_or_aggregation_gap": "better aggregation / selection",
    }
    return mapping[subtype]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run full method comparison bundle")
    p.add_argument("--config", required=True, help="Path to JSON config file")
    p.add_argument("--output-root", default="outputs/full_method_comparison_bundle")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))

    datasets: list[str] = cfg["datasets"]
    subset_size = int(cfg.get("subset_size", 24))
    seeds = [int(x) for x in cfg["seeds"]]
    budgets = [int(x) for x in cfg["budgets"]]
    adaptive_grid = [int(x) for x in cfg.get("adaptive_grid", [0, 1, 2])]

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / args.output_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    all_method_rows: list[dict[str, Any]] = []
    all_example_rows: list[dict[str, Any]] = []

    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, subset_size, seed)
            example_lookup = {ex.example_id: asdict(ex) for ex in examples}
            rng = random.Random(1000003 * seed + 17)
            factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)

            for budget in budgets:
                strategies = build_frontier_strategies(
                    factory,
                    budget,
                    adaptive_grid,
                    rng,
                    use_openai_api=False,
                    vgs_candidates=3,
                    vgs_min_expansions=1,
                    include_external_s1_baseline=True,
                    include_external_tale_baseline=True,
                    include_external_l1_baseline=True,
                )
                metrics, rows = evaluate_strategies_on_examples(examples, strategies)

                for method, metric in metrics.items():
                    info = METHOD_INFO.get(method, {"family": "other", "comparability": "other", "status": "runnable_direct"})
                    all_method_rows.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "method": method,
                            "family": info["family"],
                            "comparability": info["comparability"],
                            "status": info["status"],
                            "n_eval_examples": int(metric["n_examples"]),
                            "accuracy": float(metric["accuracy"]),
                            "avg_actions": float(metric["avg_actions"]),
                            "avg_expansions": float(metric["avg_expansions"]),
                            "avg_verifications": float(metric["avg_verifications"]),
                            "coverage": 1.0,
                            "defer_rate": 0.0,
                            "abstention_rate": 0.0,
                            "budget_exhaustion_rate": float(metric["budget_exhaustion_rate"]),
                            "underspend_rate": float(max(0.0, 1.0 - (float(metric["avg_actions"]) / float(budget)))),
                        }
                    )

                for row in rows:
                    ex = example_lookup[row["example_id"]]
                    all_example_rows.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "example_id": row["example_id"],
                            "question": ex["question"],
                            "ground_truth": ex["answer"],
                            "method": row["strategy"],
                            "is_correct": bool(row["is_correct"]),
                            "actions_used": int(row["actions_used"]),
                            "expansions": int(row["expansions"]),
                            "verifications": int(row["verifications"]),
                            "budget_exhausted": bool(row["budget_exhausted"]),
                            "metadata_json": json.dumps(row.get("metadata", {}), sort_keys=True),
                        }
                    )

    # Aggregate per method (global)
    by_method: dict[str, list[dict[str, Any]]] = {}
    for row in all_method_rows:
        by_method.setdefault(str(row["method"]), []).append(row)

    per_method_metrics: list[dict[str, Any]] = []
    for method, rows in sorted(by_method.items()):
        per_method_metrics.append(
            {
                "method": method,
                "family": rows[0]["family"],
                "comparability": rows[0]["comparability"],
                "status": rows[0]["status"],
                "mean_accuracy": _safe_mean([float(r["accuracy"]) for r in rows]),
                "mean_avg_actions": _safe_mean([float(r["avg_actions"]) for r in rows]),
                "mean_coverage": _safe_mean([float(r["coverage"]) for r in rows]),
                "mean_defer_rate": _safe_mean([float(r["defer_rate"]) for r in rows]),
                "mean_abstention_rate": _safe_mean([float(r["abstention_rate"]) for r in rows]),
                "mean_budget_exhaustion_rate": _safe_mean([float(r["budget_exhaustion_rate"]) for r in rows]),
                "mean_underspend_rate": _safe_mean([float(r["underspend_rate"]) for r in rows]),
                "n_rows": len(rows),
            }
        )

    aggregate_ranking = _rank_rows(per_method_metrics)

    # Ranking per dataset and per budget
    per_dataset_rows: list[dict[str, Any]] = []
    for dataset in sorted(set(r["dataset"] for r in all_method_rows)):
        ds_rows = [r for r in all_method_rows if r["dataset"] == dataset]
        methods = sorted(set(r["method"] for r in ds_rows))
        compact: list[dict[str, Any]] = []
        for method in methods:
            mr = [r for r in ds_rows if r["method"] == method]
            compact.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "family": mr[0]["family"],
                    "comparability": mr[0]["comparability"],
                    "status": mr[0]["status"],
                    "mean_accuracy": _safe_mean([float(x["accuracy"]) for x in mr]),
                    "mean_avg_actions": _safe_mean([float(x["avg_actions"]) for x in mr]),
                    "mean_coverage": _safe_mean([float(x["coverage"]) for x in mr]),
                }
            )
        per_dataset_rows.extend(_rank_rows(compact))

    per_budget_rows: list[dict[str, Any]] = []
    for budget in sorted(set(int(r["budget"]) for r in all_method_rows)):
        b_rows = [r for r in all_method_rows if int(r["budget"]) == budget]
        methods = sorted(set(r["method"] for r in b_rows))
        compact = []
        for method in methods:
            mr = [r for r in b_rows if r["method"] == method]
            compact.append(
                {
                    "budget": budget,
                    "method": method,
                    "family": mr[0]["family"],
                    "comparability": mr[0]["comparability"],
                    "status": mr[0]["status"],
                    "mean_accuracy": _safe_mean([float(x["accuracy"]) for x in mr]),
                    "mean_avg_actions": _safe_mean([float(x["avg_actions"]) for x in mr]),
                    "mean_coverage": _safe_mean([float(x["coverage"]) for x in mr]),
                }
            )
        per_budget_rows.extend(_rank_rows(compact))

    # Win/loss registry and defeat casebook against our method
    by_key: dict[tuple[str, int, int, str, str], dict[str, Any]] = {}
    for row in all_example_rows:
        key = (str(row["dataset"]), int(row["seed"]), int(row["budget"]), str(row["example_id"]), str(row["method"]))
        by_key[key] = row

    methods = sorted(set(r["method"] for r in all_method_rows if r["method"] != OUR_METHOD))
    win_loss_rows: list[dict[str, Any]] = []
    defeat_cases: list[dict[str, Any]] = []

    for method in methods:
        ours_wins = 0
        other_wins = 0
        ties = 0
        for dataset in datasets:
            for seed in seeds:
                for budget in budgets:
                    ex_rows = [r for r in all_example_rows if r["dataset"] == dataset and r["seed"] == seed and r["budget"] == budget and r["method"] == OUR_METHOD]
                    for ours in ex_rows:
                        other = by_key.get((dataset, seed, budget, ours["example_id"], method))
                        if not other:
                            continue
                        if bool(ours["is_correct"]) and not bool(other["is_correct"]):
                            ours_wins += 1
                        elif not bool(ours["is_correct"]) and bool(other["is_correct"]):
                            other_wins += 1
                            subtype = _failure_subtype(ours, other)
                            defeat_cases.append(
                                {
                                    "dataset": dataset,
                                    "seed": seed,
                                    "budget": budget,
                                    "example_id": ours["example_id"],
                                    "other_method": method,
                                    "question": ours["question"],
                                    "ground_truth": ours["ground_truth"],
                                    "our_prediction_action_summary": (
                                        f"correct={ours['is_correct']}; actions={ours['actions_used']}; expansions={ours['expansions']}; "
                                        f"verifications={ours['verifications']}; budget_exhausted={ours['budget_exhausted']}; "
                                        f"metadata={ours['metadata_json'][:240]}"
                                    ),
                                    "other_prediction_action_summary": (
                                        f"correct={other['is_correct']}; actions={other['actions_used']}; expansions={other['expansions']}; "
                                        f"verifications={other['verifications']}; budget_exhausted={other['budget_exhausted']}; "
                                        f"metadata={other['metadata_json'][:240]}"
                                    ),
                                    "why_ours_failed": subtype,
                                    "why_other_succeeded": _advantage_source(ours, other),
                                    "failure_subtype": subtype,
                                    "advantage_source": _advantage_source(ours, other),
                                }
                            )
                        else:
                            ties += 1
        total = ours_wins + other_wins + ties
        win_loss_rows.append(
            {
                "our_method": OUR_METHOD,
                "other_method": method,
                "ours_wins": ours_wins,
                "other_wins": other_wins,
                "ties": ties,
                "total_compared": total,
                "net_margin_other_minus_ours": other_wins - ours_wins,
            }
        )

    defeat_cases = sorted(
        defeat_cases,
        key=lambda r: (int(r["budget"]), str(r["dataset"]), str(r["other_method"]), str(r["example_id"])),
    )
    defeat_case_registry = defeat_cases[: int(cfg.get("max_defeat_cases", 80))]

    method_status_rows: list[dict[str, Any]] = []
    for method in sorted(METHOD_INFO):
        meta = METHOD_INFO[method]
        method_status_rows.append(
            {
                "method": method,
                "family": meta["family"],
                "comparability": meta["comparability"],
                "status": meta["status"],
                "fairness_caveat": (
                    "MODE A adapter path" if meta["comparability"] == "adapter_mode_a" else "direct in-repo"
                ),
            }
        )
    for m in ADJACENT_IMPORT_VALIDATED:
        method_status_rows.append(
            {
                "method": m,
                "family": "external_baseline",
                "comparability": "adjacent_import_validated",
                "status": "import_validated_only",
                "fairness_caveat": "requires external package/import validation; not direct control-equivalent",
            }
        )
    for m in BLOCKED:
        method_status_rows.append(
            {
                "method": m,
                "family": "external_baseline",
                "comparability": "adjacent",
                "status": "blocked",
                "fairness_caveat": "blocked in current repo completeness status",
            }
        )

    ranking_summary = {
        "primary_ranking_rule": "Rank by mean_accuracy over all matched dataset/seed/budget rows.",
        "tie_break_rule": "Lower mean_avg_actions, then higher mean_coverage, then lexical method name.",
        "our_method": OUR_METHOD,
        "aggregate_top_method": aggregate_ranking[0]["method"] if aggregate_ranking else None,
        "aggregate_top_rank": aggregate_ranking[0] if aggregate_ranking else None,
        "our_method_rank": next((r for r in aggregate_ranking if r["method"] == OUR_METHOD), None),
    }

    manifest = {
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": args.config,
        "datasets": datasets,
        "subset_size": subset_size,
        "seeds": seeds,
        "budgets": budgets,
        "scripts": ["scripts/run_full_method_comparison_bundle.py"],
        "assumptions": [
            "Simulator-mode bounded run for matched comparison coverage.",
            "Coverage/defer/abstention are explicitly emitted; this run has no abstention path so defer/abstention are zero.",
            "External adjacent baselines without import packages are status-tracked, not numerically ranked.",
        ],
        "caveats": [
            "Not an official full reproduction of external papers.",
            "Bounded subset sizes and seeds are for robustness screening, not final paper scale.",
            "Prediction strings are unavailable in this simulator path; casebook uses auditable action summaries.",
        ],
        "command": f"python scripts/run_full_method_comparison_bundle.py --config {args.config}",
    }

    _write_csv(out_dir / "per_method_metrics.csv", per_method_metrics)
    _write_csv(out_dir / "aggregate_ranking.csv", aggregate_ranking)
    _write_csv(out_dir / "per_dataset_ranking.csv", per_dataset_rows)
    _write_csv(out_dir / "per_budget_ranking.csv", per_budget_rows)
    _write_csv(out_dir / "method_status_fairness_caveats.csv", method_status_rows)
    _write_csv(out_dir / "win_loss_registry.csv", win_loss_rows)
    _write_csv(out_dir / "defeat_case_registry.csv", defeat_case_registry)
    _write_csv(out_dir / "per_seed_method_metrics.csv", all_method_rows)
    _write_csv(out_dir / "per_example_outcomes.csv", all_example_rows)

    (out_dir / "aggregate_comparison_summary.json").write_text(json.dumps({
        "ranking_summary": ranking_summary,
        "aggregate_ranking": aggregate_ranking,
        "coverage_metrics_note": "coverage/defer/abstention included per requirements",
    }, indent=2), encoding="utf-8")
    (out_dir / "ranking_summary.json").write_text(json.dumps(ranking_summary, indent=2), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "commands_assumptions_caveats.json").write_text(
        json.dumps(
            {
                "command": manifest["command"],
                "assumptions": manifest["assumptions"],
                "caveats": manifest["caveats"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Markdown tables
    def _md_table(rows: list[dict[str, Any]], cols: list[str]) -> str:
        header = "| " + " | ".join(cols) + " |"
        sep = "|" + "|".join(["---" for _ in cols]) + "|"
        lines = [header, sep]
        for row in rows:
            lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
        return "\n".join(lines)

    compact_rank_md = _md_table(
        aggregate_ranking[:10],
        ["rank", "method", "family", "mean_accuracy", "mean_avg_actions", "status"],
    )

    note_lines = [
        "# Full method comparison bundle status note",
        "",
        f"- run_id: `{run_id}`",
        f"- generated_utc: `{manifest['generated_utc']}`",
        "",
        "## Methods actually compared numerically",
    ]
    compared = sorted(set(r["method"] for r in all_method_rows))
    for m in compared:
        note_lines.append(f"- `{m}`")

    note_lines += [
        "",
        "## Methods not fully compared and why",
        "- Adjacent import-validated only baselines are tracked in status table and not numerically ranked without import artifacts:",
        f"  {', '.join(ADJACENT_IMPORT_VALIDATED)}.",
        f"- Blocked baseline: `{', '.join(BLOCKED)}`.",
        "",
        "## Primary ranking rule",
        f"- {ranking_summary['primary_ranking_rule']}",
        f"- Tie-break: {ranking_summary['tie_break_rule']}",
        "",
        "## Compact aggregate ranking",
        "",
        compact_rank_md,
        "",
        "## Fairness assumptions",
        "- MODE A adapters are included as runnable fair baselines.",
        "- MODE B and official full reproductions are not claimed here.",
        "",
        "## Strongest wins/losses for our method",
    ]
    our_pair = [r for r in win_loss_rows if r["our_method"] == OUR_METHOD]
    top_losses = sorted(our_pair, key=lambda r: r["net_margin_other_minus_ours"], reverse=True)[:5]
    top_wins = sorted(our_pair, key=lambda r: r["net_margin_other_minus_ours"])[:5]
    note_lines.append("- Biggest losses (other beats ours):")
    for row in top_losses:
        note_lines.append(f"  - `{row['other_method']}`: net {row['net_margin_other_minus_ours']} (other_wins={row['other_wins']}, ours_wins={row['ours_wins']}).")
    note_lines.append("- Biggest wins (ours beats other):")
    for row in top_wins:
        note_lines.append(f"  - `{row['other_method']}`: net {row['net_margin_other_minus_ours']} (other_wins={row['other_wins']}, ours_wins={row['ours_wins']}).")

    (out_dir / "status_note.md").write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    case_lines = [
        "# External-baseline defeat casebook",
        "",
        f"This casebook records cases where another compared method beat `{OUR_METHOD}` in this bounded matched run.",
        "",
    ]
    for idx, case in enumerate(defeat_case_registry, start=1):
        case_lines += [
            f"## Case {idx}: {case['dataset']} / budget {case['budget']} / {case['example_id']} / {case['other_method']}",
            f"- Dataset/example id: `{case['dataset']}` / `{case['example_id']}`",
            f"- Full problem statement: {case['question']}",
            f"- Ground truth: `{case['ground_truth']}`",
            f"- Our method prediction/action summary: {case['our_prediction_action_summary']}",
            f"- Other method prediction/action summary: {case['other_prediction_action_summary']}",
            f"- Why our method failed: `{case['why_ours_failed']}`",
            f"- Why other method succeeded: `{case['why_other_succeeded']}`",
            f"- Failure subtype: `{case['failure_subtype']}`",
            f"- Advantage source: `{case['advantage_source']}`",
            "",
        ]
    (out_dir / "defeat_casebook.md").write_text("\n".join(case_lines), encoding="utf-8")

    print(json.dumps({"status": "ok", "run_id": run_id, "output_dir": str(out_dir.relative_to(REPO_ROOT))}, indent=2))


if __name__ == "__main__":
    main()
