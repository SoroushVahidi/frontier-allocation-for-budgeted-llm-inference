#!/usr/bin/env python3
"""Run a lightweight exploratory all-methods comparison bundle.

This script is intentionally small/cheap and conservative. It produces one bundle under
outputs/light_comparison_bundle/<run_id>/ with unified summaries across:
- our frontier anchor family (adaptive_min_expand_*),
- strong in-repo baselines,
- integrated external adapters (s1 / TALE / L1),
- and a separate stop-vs-act lightweight controller run (non-directly comparable setting).
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (  # noqa: E402
    adaptive_anti_collapse_stats,
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
)

REQUIRED_AUDIT_DOCS = [
    "README.md",
    "docs/PROJECT_MASTER_PLAN.md",
    "docs/CURRENT_PROJECT_STATUS.md",
    "docs/CURRENT_BOTTLENECKS.md",
    "docs/CURRENT_SAFE_CLAIMS.md",
    "docs/PAPER_POSITIONING_NOTE.md",
    "docs/REPO_MAP.md",
    "scripts/README.md",
    "configs/README.md",
]

REQUIRED_SCRIPT_PATHS = [
    "scripts/run_new_paper_frontier_matrix.py",
    "scripts/run_comparative_frontier_audit.py",
    "scripts/run_new_paper_stop_vs_act_controller.py",
    "scripts/run_light_external_style_baseline_comparison.py",
    "scripts/run_light_anchor_vs_s1_comparison.py",
    "scripts/run_s1_budget_forcing_baseline.py",
    "scripts/run_tale_baseline.py",
    "scripts/run_l1_baseline.py",
]

METHOD_CATALOG: dict[str, dict[str, str]] = {
    "adaptive_min_expand_0": {
        "group": "ours_frontier",
        "description": "Adaptive anti-collapse allocator (min_expand=0).",
    },
    "adaptive_min_expand_1": {
        "group": "ours_frontier",
        "description": "Canonical adaptive anti-collapse allocator anchor (min_expand=1).",
    },
    "adaptive_min_expand_2": {
        "group": "ours_frontier",
        "description": "Adaptive anti-collapse allocator (min_expand=2).",
    },
    "reasoning_greedy": {
        "group": "in_repo_baseline",
        "description": "Greedy reasoning baseline.",
    },
    "self_consistency_3": {
        "group": "in_repo_baseline",
        "description": "Self-consistency baseline (3 candidates).",
    },
    "reasoning_beam2": {
        "group": "in_repo_baseline",
        "description": "Beam search baseline (width=2).",
    },
    "verifier_guided_search": {
        "group": "in_repo_baseline",
        "description": "Verifier-guided search baseline.",
    },
    "program_of_thought": {
        "group": "in_repo_baseline",
        "description": "Program-of-thought structured reasoning baseline.",
    },
    "external_s1_budget_forcing": {
        "group": "external_integrated",
        "description": "Integrated s1-style budget forcing adapter.",
    },
    "external_tale_prompt_budgeting": {
        "group": "external_integrated",
        "description": "Integrated TALE-style prompt budgeting adapter.",
    },
    "external_l1_exact": {
        "group": "external_integrated",
        "description": "Integrated L1-style exact length-control adapter.",
    },
    "external_l1_max": {
        "group": "external_integrated",
        "description": "Integrated L1-style max length-control adapter.",
    },
}


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _audit_scripts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel in REQUIRED_SCRIPT_PATHS:
        path = REPO_ROOT / rel
        if not path.exists():
            rows.append({"script": rel, "exists": False, "help_exit_code": None, "runnable_help": False})
            continue
        proc = subprocess.run([sys.executable, str(path), "--help"], capture_output=True, text=True)
        rows.append(
            {
                "script": rel,
                "exists": True,
                "help_exit_code": int(proc.returncode),
                "runnable_help": bool(proc.returncode == 0),
            }
        )
    return rows


def _run_stop_vs_act(bundle_dir: Path, seed: int, budget: int) -> dict[str, Any]:
    out_dir = bundle_dir / "stop_vs_act_light"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_new_paper_stop_vs_act_controller.py"),
        "--output-dir",
        str(out_dir),
        "--episodes",
        "220",
        "--eval-episodes",
        "120",
        "--budget",
        str(max(6, budget)),
        "--seed",
        str(seed),
        "--uncertain-policy",
        "downweight",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    result: dict[str, Any] = {
        "cmd": cmd,
        "returncode": int(proc.returncode),
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "output_dir": str(out_dir),
    }
    summary_path = out_dir / "stop_vs_act_train_eval.json"
    if proc.returncode == 0 and summary_path.exists():
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        result["summary"] = {
            "classification_accuracy": payload["classification"].get("accuracy"),
            "classification_roc_auc": payload["classification"].get("roc_auc"),
            "learned_accuracy": next((r["accuracy"] for r in payload["controller_comparison"]["rows"] if r["policy"] == "learned_stop_vs_act"), None),
            "heuristic_accuracy": next((r["accuracy"] for r in payload["controller_comparison"]["rows"] if r["policy"] == "heuristic_gain_gap"), None),
            "learned_vs_heuristic_margin": payload["controller_comparison"]["margins"].get("learned_vs_heuristic_accuracy_margin"),
        }
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="Light exploratory all-methods comparison bundle")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=24)
    p.add_argument("--seeds", default="11")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--adaptive-grid", default="0,1,2")
    p.add_argument("--vgs-candidates", type=int, default=3)
    p.add_argument("--vgs-min-expansions", type=int, default=1)
    p.add_argument("--output-root", default="outputs/light_comparison_bundle")
    args = p.parse_args()

    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_grid)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_dir = REPO_ROOT / args.output_root / run_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    docs_audit = [{"path": p, "exists": (REPO_ROOT / p).exists()} for p in REQUIRED_AUDIT_DOCS]
    scripts_audit = _audit_scripts()

    per_method_rows: list[dict[str, Any]] = []
    per_example_rows: list[dict[str, Any]] = []
    anti_collapse_rows: list[dict[str, Any]] = []

    rng_master = random.Random(20260415)

    for seed in seeds:
        examples = load_pilot_examples(args.dataset, args.subset_size, seed)
        rng = random.Random(rng_master.randint(0, 10**9))
        factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)

        for budget in budgets:
            strategies = build_frontier_strategies(
                factory,
                budget,
                adaptive_grid,
                rng,
                use_openai_api=False,
                vgs_candidates=args.vgs_candidates,
                vgs_min_expansions=args.vgs_min_expansions,
                include_external_s1_baseline=True,
                include_external_tale_baseline=True,
                include_external_l1_baseline=True,
            )
            metrics, rows = evaluate_strategies_on_examples(examples, strategies)
            anti = adaptive_anti_collapse_stats(rows)
            for k, st in anti.items():
                anti_collapse_rows.append(
                    {
                        "dataset": args.dataset,
                        "seed": seed,
                        "budget": budget,
                        "adaptive_k": k,
                        **st,
                    }
                )

            for method, m in metrics.items():
                meta = METHOD_CATALOG.get(method, {"group": "other", "description": ""})
                per_method_rows.append(
                    {
                        "dataset": args.dataset,
                        "seed": seed,
                        "budget": budget,
                        "method": method,
                        "group": meta["group"],
                        "description": meta["description"],
                        "n_eval_examples": int(m["n_examples"]),
                        "accuracy": float(m["accuracy"]),
                        "avg_actions": float(m["avg_actions"]),
                        "avg_expansions": float(m["avg_expansions"]),
                        "avg_verifications": float(m["avg_verifications"]),
                        "budget_exhaustion_rate": float(m["budget_exhaustion_rate"]),
                        "underspend_rate_vs_budget": float(max(0.0, 1.0 - (float(m["avg_actions"]) / float(budget)))),
                    }
                )
            for r in rows:
                per_example_rows.append(
                    {
                        "dataset": args.dataset,
                        "seed": seed,
                        "budget": budget,
                        "example_id": r["example_id"],
                        "method": r["strategy"],
                        "is_correct": bool(r["is_correct"]),
                        "actions_used": int(r["actions_used"]),
                        "budget_exhausted": bool(r["budget_exhausted"]),
                    }
                )

    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for r in per_method_rows:
        grouped.setdefault((str(r["method"]), int(r["budget"])), []).append(r)

    comparison_rows: list[dict[str, Any]] = []
    for budget in sorted(set(int(r["budget"]) for r in per_method_rows)):
        rows = []
        for (method, b), vals in grouped.items():
            if b != budget:
                continue
            acc = [float(v["accuracy"]) for v in vals]
            actions = [float(v["avg_actions"]) for v in vals]
            underspend = [float(v["underspend_rate_vs_budget"]) for v in vals]
            exhaustion = [float(v["budget_exhaustion_rate"]) for v in vals]
            rows.append(
                {
                    "dataset": args.dataset,
                    "budget": budget,
                    "method": method,
                    "group": vals[0]["group"],
                    "mean_accuracy": float(sum(acc) / len(acc)),
                    "std_accuracy": float(statistics.pstdev(acc)) if len(acc) > 1 else 0.0,
                    "mean_avg_actions": float(sum(actions) / len(actions)),
                    "mean_underspend_rate": float(sum(underspend) / len(underspend)),
                    "mean_budget_exhaustion_rate": float(sum(exhaustion) / len(exhaustion)),
                }
            )
        rows = sorted(rows, key=lambda x: (-float(x["mean_accuracy"]), float(x["mean_avg_actions"])))
        for rank, row in enumerate(rows, start=1):
            row["rank_by_accuracy_within_budget"] = rank
            comparison_rows.append(row)

    by_method: dict[str, list[dict[str, Any]]] = {}
    for r in comparison_rows:
        by_method.setdefault(str(r["method"]), []).append(r)

    per_method_summary: list[dict[str, Any]] = []
    for method, rows in sorted(by_method.items()):
        group = rows[0]["group"]
        mean_acc = float(sum(float(r["mean_accuracy"]) for r in rows) / len(rows))
        mean_rank = float(sum(float(r["rank_by_accuracy_within_budget"]) for r in rows) / len(rows))
        mean_under = float(sum(float(r["mean_underspend_rate"]) for r in rows) / len(rows))
        per_method_summary.append(
            {
                "dataset": args.dataset,
                "method": method,
                "group": group,
                "mean_accuracy_over_budgets": mean_acc,
                "mean_rank_over_budgets": mean_rank,
                "mean_underspend_rate_over_budgets": mean_under,
            }
        )
    per_method_summary = sorted(per_method_summary, key=lambda x: (-float(x["mean_accuracy_over_budgets"]), float(x["mean_rank_over_budgets"])))

    stop_vs_act_result = _run_stop_vs_act(bundle_dir, seed=seeds[0], budget=max(budgets))

    skipped_methods = [
        {
            "method": "adaptive_bt_pairwise",
            "reason": "Not included in this light run because no explicit trained BT pairwise model path was provided for a fair same-run invocation.",
        }
    ]

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "label": "light exploratory comparison (not final benchmark)",
        "dataset": args.dataset,
        "subset_size": args.subset_size,
        "seeds": seeds,
        "budgets": budgets,
        "adaptive_grid": adaptive_grid,
        "docs_audit": docs_audit,
        "scripts_audit": scripts_audit,
        "methods_run": [m for m in METHOD_CATALOG.keys() if any(r["method"] == m for r in per_method_rows)],
        "skipped_methods": skipped_methods,
        "stop_vs_act_run": stop_vs_act_result,
        "scripts_used": [
            "scripts/run_light_all_methods_comparison.py",
            "scripts/run_new_paper_stop_vs_act_controller.py",
            "experiments/frontier_matrix_core.py",
        ],
    }

    top = per_method_summary[0] if per_method_summary else None
    summary_row = {
        "run_id": run_id,
        "label": "light exploratory comparison (not final benchmark)",
        "dataset": args.dataset,
        "subset_size": args.subset_size,
        "num_seeds": len(seeds),
        "budgets": ",".join(str(b) for b in budgets),
        "num_methods_run": len(manifest["methods_run"]),
        "top_method_by_mean_accuracy": top["method"] if top else "na",
        "top_method_mean_accuracy_over_budgets": float(top["mean_accuracy_over_budgets"]) if top else 0.0,
        "stop_vs_act_returncode": int(stop_vs_act_result["returncode"]),
    }

    _write_csv(bundle_dir / "summary.csv", [summary_row])
    _write_csv(bundle_dir / "per_method_summary.csv", per_method_summary)
    _write_csv(bundle_dir / "comparison_table.csv", comparison_rows)
    _write_csv(bundle_dir / "per_seed_method_metrics.csv", per_method_rows)
    _write_csv(bundle_dir / "anti_collapse_stats.csv", anti_collapse_rows)

    (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    note = [
        "# Light exploratory comparison note",
        "",
        "**Important:** This is a **light exploratory comparison**, not a final benchmark or paper-ready result.",
        "",
        "## Exact scripts used",
        "- scripts/run_light_all_methods_comparison.py",
        "- scripts/run_new_paper_stop_vs_act_controller.py (subrun for stop-vs-act controller-path snapshot)",
        "",
        "## Exact setup",
        f"- Dataset: `{args.dataset}`",
        f"- Subset size: `{args.subset_size}`",
        f"- Budgets: `{', '.join(str(b) for b in budgets)}`",
        f"- Seeds: `{', '.join(str(s) for s in seeds)}`",
        "- Backend: in-repo simulator mode (no paid API calls)",
        "",
        "## Methods actually run",
    ]
    for m in manifest["methods_run"]:
        note.append(f"- `{m}` ({METHOD_CATALOG[m]['group']})")
    note += ["", "## Methods skipped and why"]
    for sk in skipped_methods:
        note.append(f"- `{sk['method']}`: {sk['reason']}")
    note += [
        "",
        "## Conservative interpretation",
        "- Ranking and margins here are only directional because this run is tiny (small subset + few seeds).",
        "- External methods are integrated adapters, not exact full paper-system reproductions.",
        "- Stop-vs-act controller subrun is included as a canonical-path snapshot but is not directly apples-to-apples with frontier-table methods.",
        "- Any budget matching imperfections should be interpreted with `mean_underspend_rate` and `mean_budget_exhaustion_rate` in `comparison_table.csv`.",
        "",
        "## Direct answer scaffold",
        "- Q1 strongest in this light setup: see top row of `per_method_summary.csv`.",
        "- Q2 competitiveness of our method: compare `adaptive_min_expand_1` versus strong in-repo baselines in `comparison_table.csv`.",
        "- Q3 external baseline strength: compare `external_s1_budget_forcing`, `external_tale_prompt_budgeting`, `external_l1_exact`, `external_l1_max` rows.",
        "- Q4 under-spend/misallocation: inspect `mean_underspend_rate` + `mean_budget_exhaustion_rate`.",
        "- Q5 next priorities: see drawbacks_and_takeaways.md.",
    ]
    (bundle_dir / "note.md").write_text("\n".join(note) + "\n", encoding="utf-8")

    drawbacks = [
        "# Drawbacks and takeaways (light exploratory pass)",
        "",
        "## Drawbacks",
        "- Very small run size (subset + seeds) => high variance risk.",
        "- Simulator-mode evaluation only in this bundle; no real-model API evidence.",
        "- Pairwise BT branch-scorer was not included in this exact run table due to missing explicit model artifact path.",
        "- External baselines are integrated fair adapters (MODE A style), not full official reproductions.",
        "",
        "## Practical takeaways",
        "- Use this run only for shortlisting where to spend next compute.",
        "- Prioritize methods that are simultaneously strong on mean accuracy and stable spend behavior (low under-spend).",
        "- If `adaptive_min_expand_1` is close to top but under-spends, prioritize stop-vs-act target/threshold calibration before large sweeps.",
        "- Next cheap step: add one more seed and one second dataset only for top 3-4 methods.",
    ]
    (bundle_dir / "drawbacks_and_takeaways.md").write_text("\n".join(drawbacks) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "run_id": run_id, "bundle_dir": str(bundle_dir)}, indent=2))


if __name__ == "__main__":
    main()
