#!/usr/bin/env python3
"""Run fair L1 baseline integration modes for the NeurIPS fixed-budget project.

MODE A (inference_only_adapter):
- In-repo L1-style length-conditioned inference adapter (exact + max variants).

MODE B (official_full_adapter):
- Optional reporting path for externally produced official/full L1 results.
- No claim of full in-repo RL reproduction.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
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


DEFAULT_METHODS = [
    "adaptive_min_expand_1",
    "reasoning_greedy",
    "self_consistency_3",
    "verifier_guided_search",
    "external_l1_exact",
    "external_l1_max",
]


@dataclass
class RunConfig:
    mode: str
    dataset: str
    subset_size: int
    seeds: list[int]
    budgets: list[int]
    adaptive_grid: list[int]
    use_openai_api: bool
    api_provider: str
    model: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: int
    methods: list[str]
    action_to_token_equivalent: float
    output_root: Path
    l1_exact_token_budget: int
    l1_max_token_budget: int
    l1_token_per_action: float
    l1_prompt_style: str
    official_results_path: str | None


def _load_config(path: Path) -> RunConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = data["output"]
    mode = str(data.get("mode", "inference_only_adapter"))
    official = data.get("official", {}) or {}
    l1 = data.get("l1", {})
    return RunConfig(
        mode=mode,
        dataset=str(data["dataset"]["name"]),
        subset_size=int(data["dataset"].get("subset_size", 32)),
        seeds=[int(s) for s in data["dataset"].get("seeds", [11, 23, 37])],
        budgets=[int(b) for b in data["budget"]["grid"]],
        adaptive_grid=[int(k) for k in data["methods"].get("adaptive_min_expand_grid", [1])],
        use_openai_api=bool(data["model"].get("use_openai_api", False)),
        api_provider=str(data["model"].get("provider", "openai")),
        model=str(data["model"].get("name", "gpt-4.1-mini")),
        temperature=float(data["model"].get("temperature", 0.2)),
        max_output_tokens=int(data["model"].get("max_output_tokens", 180)),
        timeout_seconds=int(data["model"].get("timeout_seconds", 45)),
        methods=list(data["methods"].get("include", DEFAULT_METHODS)),
        action_to_token_equivalent=float(data["budget"].get("action_to_token_equivalent", 64.0)),
        output_root=REPO_ROOT / str(out.get("root_dir", "outputs/l1_baseline")),
        l1_exact_token_budget=int(l1.get("exact_token_budget", 512)),
        l1_max_token_budget=int(l1.get("max_token_budget", 512)),
        l1_token_per_action=float(l1.get("token_per_action", 64.0)),
        l1_prompt_style=str(
            l1.get("prompt_style", "Let's think step by step and output the final answer within \\boxed{}.")
        ),
        official_results_path=(
            str(official["results_path"])
            if isinstance(official, dict) and official.get("results_path")
            else None
        ),
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _pareto_frontier(rows: list[dict[str, Any]], acc_key: str, cost_key: str) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda r: (float(r[cost_key]), -float(r[acc_key])))
    best_acc = -1.0
    frontier: list[dict[str, Any]] = []
    for row in ordered:
        acc = float(row[acc_key])
        if acc > best_acc:
            frontier.append(row)
            best_acc = acc
    return frontier


def _load_official_results(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".json":
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, list):
            return [dict(x) for x in loaded]
        if isinstance(loaded, dict) and isinstance(loaded.get("rows"), list):
            return [dict(x) for x in loaded["rows"]]
        return []
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as f:
            return [dict(r) for r in csv.DictReader(f)]
    return []


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run L1 baseline integration modes")
    p.add_argument("--config", default="configs/l1_inference_adapter_v1.json")
    p.add_argument("--run-id", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = _load_config(REPO_ROOT / args.config)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = cfg.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    rng_master = random.Random(20260415)

    per_seed_rows: list[dict[str, Any]] = []
    per_example_rows: list[dict[str, Any]] = []

    for seed in cfg.seeds:
        examples = load_pilot_examples(cfg.dataset, cfg.subset_size, seed)
        rng = random.Random(rng_master.randint(0, 10**9))
        gen_factory = generator_factory_for_mode(
            cfg.use_openai_api,
            rng,
            cfg.model,
            cfg.temperature,
            cfg.max_output_tokens,
            cfg.timeout_seconds,
            cfg.api_provider,
        )

        for budget in cfg.budgets:
            strategies = build_frontier_strategies(
                gen_factory,
                budget,
                cfg.adaptive_grid,
                rng,
                use_openai_api=cfg.use_openai_api,
                include_external_l1_baseline=True,
                l1_exact_token_budget=cfg.l1_exact_token_budget,
                l1_max_token_budget=cfg.l1_max_token_budget,
                l1_token_per_action=cfg.l1_token_per_action,
                l1_prompt_style=cfg.l1_prompt_style,
            )
            eval_metrics, eval_rows = evaluate_strategies_on_examples(examples, strategies)

            by_method_rows: dict[str, list[dict[str, Any]]] = {}
            for row in eval_rows:
                m = str(row["strategy"])
                by_method_rows.setdefault(m, []).append(row)

            for method in cfg.methods:
                m = eval_metrics.get(method)
                if m is None:
                    continue
                mrows = by_method_rows.get(method, [])

                generated_tokens = [
                    float((r.get("metadata") or {}).get("generated_tokens_estimate", r["actions_used"] * cfg.action_to_token_equivalent))
                    for r in mrows
                ]
                budget_errors = [float((r.get("metadata") or {}).get("budget_error_tokens", 0.0)) for r in mrows]
                violations = [
                    1.0 if bool((r.get("metadata") or {}).get("token_budget_violation", False)) else 0.0 for r in mrows
                ]

                per_seed_rows.append(
                    {
                        "mode": cfg.mode,
                        "dataset": cfg.dataset,
                        "seed": seed,
                        "budget_actions": budget,
                        "budget_token_equivalent": budget * cfg.action_to_token_equivalent,
                        "method": method,
                        "n_eval_examples": int(m["n_examples"]),
                        "accuracy": float(m["accuracy"]),
                        "exact_match": float(m["accuracy"]),
                        "avg_actions": float(m["avg_actions"]),
                        "avg_generated_tokens": _mean(generated_tokens),
                        "avg_budget_error_tokens": _mean(budget_errors),
                        "avg_token_cost_equivalent": float(m["avg_actions"]) * cfg.action_to_token_equivalent,
                        "budget_adherence_rate": 1.0 - _mean(violations),
                        "budget_violation_rate": _mean(violations),
                        "budget_exhaustion_rate": float(m["budget_exhaustion_rate"]),
                    }
                )

            for row in eval_rows:
                method = str(row["strategy"])
                if method not in cfg.methods:
                    continue
                md = row.get("metadata") or {}
                per_example_rows.append(
                    {
                        "mode": cfg.mode,
                        "dataset": cfg.dataset,
                        "seed": seed,
                        "budget_actions": budget,
                        "budget_token_equivalent": budget * cfg.action_to_token_equivalent,
                        "example_id": row["example_id"],
                        "method": method,
                        "is_correct": bool(row["is_correct"]),
                        "actions_used": int(row["actions_used"]),
                        "token_cost_equivalent": float(row["actions_used"]) * cfg.action_to_token_equivalent,
                        "generated_tokens_estimate": float(md.get("generated_tokens_estimate", row["actions_used"] * cfg.action_to_token_equivalent)),
                        "budget_error_tokens": float(md.get("budget_error_tokens", 0.0)),
                        "token_budget_violation": bool(md.get("token_budget_violation", False)),
                        "l1_control_mode": md.get("l1_control_mode", "na"),
                        "budget_instruction_tokens": md.get("token_budget_instruction", "na"),
                        "expansions": int(row["expansions"]),
                        "verifications": int(row["verifications"]),
                        "budget_exhausted": bool(row["budget_exhausted"]),
                        "metadata": md,
                    }
                )

    grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for row in per_seed_rows:
        grouped.setdefault((int(row["budget_actions"]), str(row["method"])), []).append(row)

    summary_rows: list[dict[str, Any]] = []
    for (budget, method), rows in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        acc = [float(r["accuracy"]) for r in rows]
        actions = [float(r["avg_actions"]) for r in rows]
        toks = [float(r["avg_generated_tokens"]) for r in rows]
        tok_cost = [float(r["avg_token_cost_equivalent"]) for r in rows]
        budget_err = [float(r["avg_budget_error_tokens"]) for r in rows]
        violation = [float(r["budget_violation_rate"]) for r in rows]
        exhaustion = [float(r["budget_exhaustion_rate"]) for r in rows]
        summary_rows.append(
            {
                "mode": cfg.mode,
                "dataset": cfg.dataset,
                "budget_actions": budget,
                "budget_token_equivalent": budget * cfg.action_to_token_equivalent,
                "method": method,
                "num_seeds": len(rows),
                "mean_accuracy": _mean(acc),
                "std_accuracy": float(statistics.pstdev(acc)) if len(acc) > 1 else 0.0,
                "mean_avg_actions": _mean(actions),
                "mean_avg_generated_tokens": _mean(toks),
                "mean_avg_token_cost_equivalent": _mean(tok_cost),
                "mean_avg_budget_error_tokens": _mean(budget_err),
                "mean_budget_violation_rate": _mean(violation),
                "mean_budget_adherence_rate": 1.0 - _mean(violation),
                "mean_budget_exhaustion_rate": _mean(exhaustion),
            }
        )

    by_budget_method = {(int(r["budget_actions"]), str(r["method"])): r for r in summary_rows}
    comparison_rows: list[dict[str, Any]] = []
    for budget in sorted({int(r["budget_actions"]) for r in summary_rows}):
        ours = by_budget_method.get((budget, "adaptive_min_expand_1"))
        l1_exact = by_budget_method.get((budget, "external_l1_exact"))
        l1_max = by_budget_method.get((budget, "external_l1_max"))
        if ours is None:
            continue
        if l1_exact is not None:
            comparison_rows.append(
                {
                    "mode": cfg.mode,
                    "dataset": cfg.dataset,
                    "budget_actions": budget,
                    "budget_token_equivalent": budget * cfg.action_to_token_equivalent,
                    "our_method": "adaptive_min_expand_1",
                    "baseline_method": "external_l1_exact",
                    "our_accuracy": float(ours["mean_accuracy"]),
                    "baseline_accuracy": float(l1_exact["mean_accuracy"]),
                    "delta_accuracy_baseline_minus_ours": float(l1_exact["mean_accuracy"] - ours["mean_accuracy"]),
                    "our_cost": float(ours["mean_avg_token_cost_equivalent"]),
                    "baseline_cost": float(l1_exact["mean_avg_token_cost_equivalent"]),
                    "delta_cost_baseline_minus_ours": float(l1_exact["mean_avg_token_cost_equivalent"] - ours["mean_avg_token_cost_equivalent"]),
                    "baseline_budget_violation_rate": float(l1_exact["mean_budget_violation_rate"]),
                }
            )
        if l1_max is not None:
            comparison_rows.append(
                {
                    "mode": cfg.mode,
                    "dataset": cfg.dataset,
                    "budget_actions": budget,
                    "budget_token_equivalent": budget * cfg.action_to_token_equivalent,
                    "our_method": "adaptive_min_expand_1",
                    "baseline_method": "external_l1_max",
                    "our_accuracy": float(ours["mean_accuracy"]),
                    "baseline_accuracy": float(l1_max["mean_accuracy"]),
                    "delta_accuracy_baseline_minus_ours": float(l1_max["mean_accuracy"] - ours["mean_accuracy"]),
                    "our_cost": float(ours["mean_avg_token_cost_equivalent"]),
                    "baseline_cost": float(l1_max["mean_avg_token_cost_equivalent"]),
                    "delta_cost_baseline_minus_ours": float(l1_max["mean_avg_token_cost_equivalent"] - ours["mean_avg_token_cost_equivalent"]),
                    "baseline_budget_violation_rate": float(l1_max["mean_budget_violation_rate"]),
                }
            )

    frontier_rows: list[dict[str, Any]] = []
    by_method: dict[str, list[dict[str, Any]]] = {}
    for row in summary_rows:
        by_method.setdefault(str(row["method"]), []).append(row)
    for method, rows in sorted(by_method.items()):
        frontier = _pareto_frontier(rows, "mean_accuracy", "mean_avg_token_cost_equivalent")
        for row in frontier:
            frontier_rows.append({"method": method, **row})

    mode_b_official_rows: list[dict[str, Any]] = []
    mode_b_state = {
        "enabled": cfg.mode == "official_full_adapter",
        "status": "not_requested",
        "notes": "",
    }
    if cfg.mode == "official_full_adapter":
        if cfg.official_results_path:
            imported = _load_official_results(REPO_ROOT / cfg.official_results_path)
            if imported:
                mode_b_state["status"] = "imported_results"
                mode_b_state["notes"] = "Loaded externally-produced official/full L1 results for side-by-side reporting."
                for row in imported:
                    mode_b_official_rows.append({"mode": "official_full_adapter", "source": "official_import", **row})
            else:
                mode_b_state["status"] = "blocked"
                mode_b_state["notes"] = "Official mode requested but results file missing/empty/unreadable."
        else:
            mode_b_state["status"] = "blocked"
            mode_b_state["notes"] = (
                "Official mode requested, but this repo does not reproduce L1 RL training automatically. "
                "Provide `official.results_path` with exported official run metrics to complete MODE B reporting."
            )

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "mode": cfg.mode,
        "dataset": cfg.dataset,
        "subset_size": cfg.subset_size,
        "seeds": cfg.seeds,
        "budget_grid_actions": cfg.budgets,
        "budget_matching": {
            "action_to_token_equivalent": cfg.action_to_token_equivalent,
            "policy": "fixed linear conversion for matched-budget reporting",
        },
        "model": {
            "use_openai_api": cfg.use_openai_api,
            "provider": cfg.api_provider,
            "name": cfg.model,
            "temperature": cfg.temperature,
            "max_output_tokens": cfg.max_output_tokens,
        },
        "l1_adapter": {
            "exact_token_budget": cfg.l1_exact_token_budget,
            "max_token_budget": cfg.l1_max_token_budget,
            "token_per_action": cfg.l1_token_per_action,
            "prompt_style": cfg.l1_prompt_style,
            "variants": ["external_l1_exact", "external_l1_max"],
        },
        "methods": cfg.methods,
        "mode_b_official": mode_b_state,
        "guardrail": (
            "MODE A is inference-only L1-style conditioning on unchanged base model family. "
            "MODE B is secondary and not apples-to-apples if it includes RL-trained L1 checkpoints."
        ),
    }

    note_lines = [
        "# L1 baseline run note",
        "",
        f"- run_id: `{run_id}`",
        f"- mode: `{cfg.mode}`",
        f"- dataset: `{cfg.dataset}`",
        f"- subset_size_per_seed: `{cfg.subset_size}`",
        f"- seeds: `{', '.join(str(x) for x in cfg.seeds)}`",
        f"- budgets(actions): `{', '.join(str(x) for x in cfg.budgets)}`",
        f"- action_to_token_equivalent: `{cfg.action_to_token_equivalent}`",
        f"- l1_exact_token_budget: `{cfg.l1_exact_token_budget}`",
        f"- l1_max_token_budget: `{cfg.l1_max_token_budget}`",
        "",
        "## Fairness and claim boundaries",
        "- MODE A compares our method against inference-only L1-style length control (Exact/Max) on the same base model family.",
        "- MODE B (official_full_adapter) is separate reporting and is not apples-to-apples if RL-trained L1 checkpoints are used.",
        "- This run stores exact-match/accuracy, budget adherence/violation, budget error, and frontier summaries.",
    ]

    fairness_lines = [
        "# Fairness report: L1 baseline integration",
        "",
        "## Primary comparison policy",
        "- Primary manuscript-safe comparison is `adaptive_min_expand_1` vs `external_l1_exact` and `external_l1_max` under unchanged base-model settings.",
        "- All compared methods share sampled examples, seeds, and action-budget grid.",
        "",
        "## L1 variant handling",
        "- `external_l1_exact` maps to LCPO-Exact-style instruction conditioning (exact target length).",
        "- `external_l1_max` maps to LCPO-Max-style instruction conditioning (upper-bound length).",
        "",
        "## Budget matching policy",
        f"- Internal action budgets are mapped to token-equivalent budgets via 1 action = {cfg.action_to_token_equivalent} token-equivalent units.",
        "- We report both action-budget and generated-token-estimate fields for auditability.",
        "",
        "## Caveats",
        "- Inference-only adapter does not reproduce RL training or official L1 checkpoints.",
        "- MODE B remains blocked unless official/full outputs are imported.",
        "- Control granularity differs from frontier stop-vs-act control; comparisons are matched-budget, not control-identical.",
    ]

    _write_csv(run_dir / "summary.csv", summary_rows)
    _write_csv(run_dir / "summary_per_seed.csv", per_seed_rows)
    _write_jsonl(run_dir / "per_example.jsonl", per_example_rows)
    _write_csv(run_dir / "comparison_to_ours.csv", comparison_rows)
    _write_csv(run_dir / "frontier_summary.csv", frontier_rows)
    _write_csv(run_dir / "official_mode_import.csv", mode_b_official_rows)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "note.md").write_text("\n".join(note_lines) + "\n", encoding="utf-8")
    (run_dir / "fairness_report.md").write_text("\n".join(fairness_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "run_dir": str(run_dir), "mode_b": mode_b_state}, indent=2))


if __name__ == "__main__":
    main()
