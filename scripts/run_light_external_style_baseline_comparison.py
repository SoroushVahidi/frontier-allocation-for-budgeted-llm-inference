#!/usr/bin/env python3
"""Run a lightweight external-style baseline comparison in the local frontier environment.

This is a cheap, reproducible situational-awareness benchmark. External methods here are
paper-inspired approximations implemented with in-repo strategy families under matched local
settings; they are not exact reproductions of external papers.
"""

from __future__ import annotations

import argparse
import csv
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


METHOD_SPECS: list[dict[str, str]] = [
    {
        "method": "adaptive_min_expand_1",
        "family": "internal_anchor",
        "style": "repo_default_stop_vs_act_anchor",
        "description": "Current default adaptive min-expand controller (anchor baseline).",
    },
    {
        "method": "reasoning_greedy",
        "family": "external_style",
        "style": "gain_score_greedy",
        "description": "Simple greedy process/gain style expansion heuristic.",
    },
    {
        "method": "self_consistency_3",
        "family": "external_style",
        "style": "fixed_multi_sample_consensus",
        "description": "Self-consistency style fixed-sample policy (paper-inspired).",
    },
    {
        "method": "reasoning_beam2",
        "family": "external_style",
        "style": "beam_search_small_width",
        "description": "Small-beam process-score search heuristic (paper-inspired).",
    },
    {
        "method": "verifier_guided_search",
        "family": "external_style",
        "style": "uncertainty_verify_guided",
        "description": "Verifier-guided search / solve-vs-verify style heuristic (paper-inspired).",
    },
    {
        "method": "program_of_thought",
        "family": "external_style",
        "style": "structured_reasoning_prompting",
        "description": "Program-of-thought style structured reasoning baseline.",
    },
]


def _parse_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _oracle_accuracy(eval_rows: list[dict[str, Any]]) -> float:
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in eval_rows:
        by_ex.setdefault(str(row["example_id"]), []).append(row)
    n = len(by_ex)
    if n == 0:
        return 0.0
    correct = sum(1 for rows in by_ex.values() if any(r["is_correct"] for r in rows))
    return float(correct / n)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Light external-style baseline comparison")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=24)
    p.add_argument("--seeds", default="11,23,37")
    p.add_argument("--budgets", default="4,6")
    p.add_argument("--adaptive-grid", default="0,1,2")
    p.add_argument("--vgs-candidates", type=int, default=3)
    p.add_argument("--vgs-min-expansions", type=int, default=1)
    p.add_argument("--output-dir", default="outputs/light_external_style_baseline_comparison")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    seeds = _parse_ints(args.seeds)
    budgets = _parse_ints(args.budgets)
    adaptive_grid = _parse_ints(args.adaptive_grid)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    method_catalog = {m["method"]: m for m in METHOD_SPECS}
    method_names = [m["method"] for m in METHOD_SPECS]
    rng_master = random.Random(99173)

    per_seed_rows: list[dict[str, Any]] = []

    for seed in seeds:
        examples = load_pilot_examples(args.dataset, args.subset_size, seed)
        rng = random.Random(rng_master.randint(0, 10**9))
        gen_factory = generator_factory_for_mode(
            False,
            rng,
            "gpt-4.1-mini",
            0.2,
            180,
            45,
        )

        for budget in budgets:
            strategies = build_frontier_strategies(
                gen_factory,
                budget,
                adaptive_grid,
                rng,
                use_openai_api=False,
                vgs_candidates=args.vgs_candidates,
                vgs_min_expansions=args.vgs_min_expansions,
            )
            eval_metrics, eval_rows = evaluate_strategies_on_examples(examples, strategies)
            oracle_acc = _oracle_accuracy(eval_rows)

            for method in method_names:
                if method not in eval_metrics:
                    continue
                m = eval_metrics[method]
                spec = method_catalog[method]
                per_seed_rows.append(
                    {
                        "dataset": args.dataset,
                        "seed": seed,
                        "budget": budget,
                        "method": method,
                        "family": spec["family"],
                        "style": spec["style"],
                        "n_eval_examples": int(m["n_examples"]),
                        "accuracy": float(m["accuracy"]),
                        "avg_actions": float(m["avg_actions"]),
                        "avg_expansions": float(m["avg_expansions"]),
                        "avg_verifications": float(m["avg_verifications"]),
                        "budget_exhaustion_rate": float(m["budget_exhaustion_rate"]),
                        "oracle_accuracy": float(oracle_acc),
                        "gap_to_oracle": float(oracle_acc - float(m["accuracy"])),
                    }
                )

    # Aggregate summary per method x budget.
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for row in per_seed_rows:
        grouped.setdefault((int(row["budget"]), str(row["method"])), []).append(row)

    summary_rows: list[dict[str, Any]] = []
    for (budget, method), rows in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        acc = [float(r["accuracy"]) for r in rows]
        acts = [float(r["avg_actions"]) for r in rows]
        gap = [float(r["gap_to_oracle"]) for r in rows]
        summary_rows.append(
            {
                "dataset": args.dataset,
                "budget": budget,
                "method": method,
                "family": method_catalog[method]["family"],
                "style": method_catalog[method]["style"],
                "num_seeds": len(rows),
                "mean_accuracy": float(sum(acc) / len(acc)),
                "std_accuracy": float(statistics.pstdev(acc)) if len(acc) > 1 else 0.0,
                "mean_avg_actions": float(sum(acts) / len(acts)),
                "std_avg_actions": float(statistics.pstdev(acts)) if len(acts) > 1 else 0.0,
                "mean_gap_to_oracle": float(sum(gap) / len(gap)),
            }
        )

    # Pairwise vs anchor.
    by_budget_method = {(int(r["budget"]), str(r["method"])): r for r in summary_rows}
    pairwise_rows: list[dict[str, Any]] = []
    for budget in sorted(set(int(r["budget"]) for r in summary_rows)):
        anchor = by_budget_method.get((budget, "adaptive_min_expand_1"))
        if anchor is None:
            continue
        for method in method_names:
            row = by_budget_method.get((budget, method))
            if row is None:
                continue
            pairwise_rows.append(
                {
                    "dataset": args.dataset,
                    "budget": budget,
                    "anchor_method": "adaptive_min_expand_1",
                    "other_method": method,
                    "other_family": row["family"],
                    "other_style": row["style"],
                    "delta_accuracy_other_minus_anchor": float(row["mean_accuracy"] - anchor["mean_accuracy"]),
                    "delta_avg_actions_other_minus_anchor": float(row["mean_avg_actions"] - anchor["mean_avg_actions"]),
                    "delta_gap_to_oracle_other_minus_anchor": float(row["mean_gap_to_oracle"] - anchor["mean_gap_to_oracle"]),
                }
            )

    # Rank summary by mean accuracy averaged over budgets.
    rank_rows: list[dict[str, Any]] = []
    for method in method_names:
        rows = [r for r in summary_rows if str(r["method"]) == method]
        if not rows:
            continue
        rank_rows.append(
            {
                "method": method,
                "family": method_catalog[method]["family"],
                "style": method_catalog[method]["style"],
                "mean_accuracy_over_budgets": float(sum(float(r["mean_accuracy"]) for r in rows) / len(rows)),
                "mean_gap_to_oracle_over_budgets": float(sum(float(r["mean_gap_to_oracle"]) for r in rows) / len(rows)),
            }
        )
    rank_rows = sorted(rank_rows, key=lambda r: (-float(r["mean_accuracy_over_budgets"]), float(r["mean_gap_to_oracle_over_budgets"])))

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": args.dataset,
        "subset_size": args.subset_size,
        "seeds": seeds,
        "budgets": budgets,
        "method_catalog": METHOD_SPECS,
        "note": (
            "External-style methods are paper-inspired approximations executed inside the same local repo environment; "
            "they are not direct reproductions of external paper systems."
        ),
    }

    summary_json = {
        "manifest": manifest,
        "rank_overview": rank_rows,
        "num_rows": {
            "per_seed": len(per_seed_rows),
            "summary": len(summary_rows),
            "pairwise_vs_anchor": len(pairwise_rows),
        },
    }

    _write_csv(run_dir / "method_metrics_per_seed.csv", per_seed_rows)
    _write_csv(run_dir / "method_summary.csv", summary_rows)
    _write_csv(run_dir / "pairwise_vs_anchor.csv", pairwise_rows)
    (run_dir / "comparison_summary.json").write_text(json.dumps(summary_json, indent=2), encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    md_lines = [
        "# Light external-style baseline comparison (non-claim)",
        "",
        f"- Run ID: `{run_id}`",
        f"- Dataset: `{args.dataset}`",
        f"- Subset size per seed: `{args.subset_size}`",
        f"- Seeds: `{', '.join(str(s) for s in seeds)}`",
        f"- Budgets: `{', '.join(str(b) for b in budgets)}`",
        "",
        "External-style baselines are **paper-inspired approximations** in this repo environment, not exact paper reproductions.",
        "",
        "## Mean accuracy over budgets (higher is better)",
        "",
        "| Rank | Method | Family | Style | Mean accuracy | Mean gap-to-oracle |",
        "|---:|---|---|---|---:|---:|",
    ]
    for i, row in enumerate(rank_rows, start=1):
        md_lines.append(
            f"| {i} | {row['method']} | {row['family']} | {row['style']} | "
            f"{float(row['mean_accuracy_over_budgets']):.4f} | {float(row['mean_gap_to_oracle_over_budgets']):.4f} |"
        )

    md_lines += [
        "",
        "## Per-budget summary",
        "",
        "| Budget | Method | Family | Mean accuracy | Mean avg actions | Mean gap-to-oracle |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for r in sorted(summary_rows, key=lambda x: (int(x["budget"]), -float(x["mean_accuracy"]))):
        md_lines.append(
            f"| {int(r['budget'])} | {r['method']} | {r['family']} | "
            f"{float(r['mean_accuracy']):.4f} | {float(r['mean_avg_actions']):.4f} | {float(r['mean_gap_to_oracle']):.4f} |"
        )

    md_lines += [
        "",
        "## Pairwise deltas vs anchor (`adaptive_min_expand_1`)",
        "",
        "| Budget | Other method | Family | Δaccuracy (other-anchor) | Δavg_actions (other-anchor) |",
        "|---:|---|---|---:|---:|",
    ]
    for r in sorted(pairwise_rows, key=lambda x: (int(x["budget"]), x["other_method"])):
        if r["other_method"] == "adaptive_min_expand_1":
            continue
        md_lines.append(
            f"| {int(r['budget'])} | {r['other_method']} | {r['other_family']} | "
            f"{float(r['delta_accuracy_other_minus_anchor']):+.4f} | {float(r['delta_avg_actions_other_minus_anchor']):+.4f} |"
        )

    md_lines += [
        "",
        "## Guardrail",
        "- This is a lightweight local benchmark for situational awareness only.",
        "- Do not treat this as a claim of beating external literature systems.",
    ]
    (run_dir / "RESULT_NOTE.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "run_dir": str(run_dir)}, indent=2))


if __name__ == "__main__":
    main()
