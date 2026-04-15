#!/usr/bin/env python3
"""Run fair TALE baseline integration modes for the NeurIPS fixed-budget project.

MODE A (prompt_budgeting_inference_only):
- In-repo TALE-style prompt-level adaptive token budgeting adapter.

MODE B (official_full_adapter):
- Optional adapter path for externally produced official/full TALE results.
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
    "external_tale_prompt_budgeting",
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
    tale_token_budget_default: int
    tale_token_budget_min: int
    tale_token_budget_max: int
    tale_token_budget_per_question_char: float
    tale_token_per_action: float
    official_results_path: str | None


def _load_config(path: Path) -> RunConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = data["output"]
    mode = str(data.get("mode", "prompt_budgeting_inference_only"))
    official = data.get("official", {}) or {}
    tale = data.get("tale", {})
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
        output_root=REPO_ROOT / str(out.get("root_dir", "outputs/tale_baseline")),
        tale_token_budget_default=int(tale.get("token_budget_default", 256)),
        tale_token_budget_min=int(tale.get("token_budget_min", 64)),
        tale_token_budget_max=int(tale.get("token_budget_max", 512)),
        tale_token_budget_per_question_char=float(tale.get("token_budget_per_question_char", 0.75)),
        tale_token_per_action=float(tale.get("token_per_action", 64.0)),
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
    for r in ordered:
        acc = float(r[acc_key])
        if acc > best_acc:
            frontier.append(r)
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
    p = argparse.ArgumentParser(description="Run TALE baseline integration modes")
    p.add_argument("--config", default="configs/tale_prompt_budgeting_v1.json")
    p.add_argument("--run-id", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = _load_config(REPO_ROOT / args.config)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = cfg.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    rng_master = random.Random(20260416)

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
                include_external_tale_baseline=True,
                tale_token_budget_default=cfg.tale_token_budget_default,
                tale_token_budget_min=cfg.tale_token_budget_min,
                tale_token_budget_max=cfg.tale_token_budget_max,
                tale_token_budget_per_question_char=cfg.tale_token_budget_per_question_char,
                tale_token_per_action=cfg.tale_token_per_action,
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
                predicted_budgets = [
                    float((r.get("metadata") or {}).get("token_budget_predicted", budget * cfg.action_to_token_equivalent))
                    for r in mrows
                ]
                token_budget_violations = [
                    1.0
                    if bool((r.get("metadata") or {}).get("token_budget_violation", False))
                    else 0.0
                    for r in mrows
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
                        "avg_predicted_token_budget": _mean(predicted_budgets),
                        "avg_token_cost_equivalent": float(m["avg_actions"]) * cfg.action_to_token_equivalent,
                        "budget_adherence_rate": 1.0 - _mean(token_budget_violations),
                        "budget_violation_rate": _mean(token_budget_violations),
                        "budget_exhaustion_rate": float(m["budget_exhaustion_rate"]),
                    }
                )

            for row in eval_rows:
                method = str(row["strategy"])
                if method not in cfg.methods:
                    continue
                meta = row.get("metadata") or {}
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
                        "generated_tokens_estimate": float(meta.get("generated_tokens_estimate", row["actions_used"] * cfg.action_to_token_equivalent)),
                        "predicted_token_budget": float(meta.get("token_budget_predicted", budget * cfg.action_to_token_equivalent)),
                        "token_budget_violation": bool(meta.get("token_budget_violation", False)),
                        "budget_exhausted": bool(row["budget_exhausted"]),
                        "metadata": meta,
                    }
                )

    grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for row in per_seed_rows:
        grouped.setdefault((int(row["budget_actions"]), str(row["method"])), []).append(row)

    summary_rows: list[dict[str, Any]] = []
    for (budget, method), rows in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        summary_rows.append(
            {
                "mode": cfg.mode,
                "dataset": cfg.dataset,
                "budget_actions": budget,
                "budget_token_equivalent": budget * cfg.action_to_token_equivalent,
                "method": method,
                "num_seeds": len(rows),
                "mean_accuracy": _mean([float(r["accuracy"]) for r in rows]),
                "std_accuracy": float(statistics.pstdev([float(r["accuracy"]) for r in rows])) if len(rows) > 1 else 0.0,
                "mean_avg_actions": _mean([float(r["avg_actions"]) for r in rows]),
                "mean_avg_generated_tokens": _mean([float(r["avg_generated_tokens"]) for r in rows]),
                "mean_avg_predicted_token_budget": _mean([float(r["avg_predicted_token_budget"]) for r in rows]),
                "mean_avg_token_cost_equivalent": _mean([float(r["avg_token_cost_equivalent"]) for r in rows]),
                "mean_budget_adherence_rate": _mean([float(r["budget_adherence_rate"]) for r in rows]),
                "mean_budget_violation_rate": _mean([float(r["budget_violation_rate"]) for r in rows]),
                "mean_budget_exhaustion_rate": _mean([float(r["budget_exhaustion_rate"]) for r in rows]),
            }
        )

    by_budget_method = {(int(r["budget_actions"]), str(r["method"])): r for r in summary_rows}
    comparison_rows: list[dict[str, Any]] = []
    for budget in sorted({int(r["budget_actions"]) for r in summary_rows}):
        ours = by_budget_method.get((budget, "adaptive_min_expand_1"))
        tale = by_budget_method.get((budget, "external_tale_prompt_budgeting"))
        if ours is None or tale is None:
            continue
        comparison_rows.append(
            {
                "mode": cfg.mode,
                "comparison_type": "fixed_budget",
                "dataset": cfg.dataset,
                "budget_actions": budget,
                "our_method": "adaptive_min_expand_1",
                "baseline_method": "external_tale_prompt_budgeting",
                "our_accuracy": float(ours["mean_accuracy"]),
                "tale_accuracy": float(tale["mean_accuracy"]),
                "delta_accuracy_tale_minus_ours": float(tale["mean_accuracy"] - ours["mean_accuracy"]),
                "our_avg_tokens": float(ours["mean_avg_generated_tokens"]),
                "tale_avg_tokens": float(tale["mean_avg_generated_tokens"]),
                "delta_tokens_tale_minus_ours": float(tale["mean_avg_generated_tokens"] - ours["mean_avg_generated_tokens"]),
            }
        )

    # Matched average compute protocol: for each TALE budget point, compare against the OURS point
    # with closest mean generated-token cost.
    ours_rows = [r for r in summary_rows if str(r["method"]) == "adaptive_min_expand_1"]
    tale_rows = [r for r in summary_rows if str(r["method"]) == "external_tale_prompt_budgeting"]
    for trow in tale_rows:
        if not ours_rows:
            continue
        matched_ours = min(
            ours_rows,
            key=lambda r: abs(float(r["mean_avg_generated_tokens"]) - float(trow["mean_avg_generated_tokens"])),
        )
        comparison_rows.append(
            {
                "mode": cfg.mode,
                "comparison_type": "matched_average_compute",
                "dataset": cfg.dataset,
                "budget_actions": int(trow["budget_actions"]),
                "our_method": "adaptive_min_expand_1",
                "baseline_method": "external_tale_prompt_budgeting",
                "our_budget_actions_matched": int(matched_ours["budget_actions"]),
                "our_accuracy": float(matched_ours["mean_accuracy"]),
                "tale_accuracy": float(trow["mean_accuracy"]),
                "delta_accuracy_tale_minus_ours": float(trow["mean_accuracy"] - matched_ours["mean_accuracy"]),
                "our_avg_tokens": float(matched_ours["mean_avg_generated_tokens"]),
                "tale_avg_tokens": float(trow["mean_avg_generated_tokens"]),
                "delta_tokens_tale_minus_ours": float(trow["mean_avg_generated_tokens"] - matched_ours["mean_avg_generated_tokens"]),
            }
        )

    frontier_rows: list[dict[str, Any]] = []
    by_method: dict[str, list[dict[str, Any]]] = {}
    for row in summary_rows:
        by_method.setdefault(str(row["method"]), []).append(row)
    for method, rows in sorted(by_method.items()):
        frontier = _pareto_frontier(rows, "mean_accuracy", "mean_avg_generated_tokens")
        for r in frontier:
            frontier_rows.append({"method": method, **r})

    mode_b_official_rows: list[dict[str, Any]] = []
    mode_b_state = {"enabled": cfg.mode == "official_full_adapter", "status": "not_requested", "notes": ""}
    if cfg.mode == "official_full_adapter":
        if cfg.official_results_path:
            imported = _load_official_results(REPO_ROOT / cfg.official_results_path)
            if imported:
                mode_b_state["status"] = "imported_results"
                mode_b_state["notes"] = "Loaded externally-produced official/full TALE results for side-by-side reporting."
                for r in imported:
                    mode_b_official_rows.append({"mode": "official_full_adapter", "source": "official_import", **r})
            else:
                mode_b_state["status"] = "blocked"
                mode_b_state["notes"] = "Official/full TALE mode requested but results file missing/empty/unreadable."
        else:
            mode_b_state["status"] = "blocked"
            mode_b_state["notes"] = (
                "Official/full TALE mode requested, but this repo does not automatically reproduce TALE-PT or full TALE stack. "
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
        "model": {
            "use_openai_api": cfg.use_openai_api,
            "provider": cfg.api_provider,
            "name": cfg.model,
            "temperature": cfg.temperature,
            "max_output_tokens": cfg.max_output_tokens,
        },
        "tale_adapter": {
            "token_budget_default": cfg.tale_token_budget_default,
            "token_budget_min": cfg.tale_token_budget_min,
            "token_budget_max": cfg.tale_token_budget_max,
            "token_budget_per_question_char": cfg.tale_token_budget_per_question_char,
            "token_per_action": cfg.tale_token_per_action,
            "estimator": "char_length_linear",
            "prompt_injection_template": "Let's think step by step and use less than {budget} tokens.",
        },
        "budget_matching": {
            "action_to_token_equivalent": cfg.action_to_token_equivalent,
            "primary_protocol": "matched average generated-token compute across methods",
        },
        "mode_b_official": mode_b_state,
        "guardrail": (
            "TALE is treated as a strong published adjacent baseline (per-instance token budgeting), "
            "not an identical frontier stop-vs-act controller."
        ),
    }

    note_lines = [
        "# TALE baseline run note",
        "",
        f"- run_id: `{run_id}`",
        f"- mode: `{cfg.mode}`",
        f"- dataset: `{cfg.dataset}`",
        f"- subset_size_per_seed: `{cfg.subset_size}`",
        f"- seeds: `{', '.join(str(x) for x in cfg.seeds)}`",
        f"- budgets(actions): `{', '.join(str(x) for x in cfg.budgets)}`",
        "",
        "## Methodological honesty",
        "- MODE A is a faithful in-repo TALE-style prompt budgeting adapter, not full TALE-PT reproduction.",
        "- MODE B is separately labeled official/full adapter reporting and may include post-training assets.",
        "- Comparisons report matched-average-compute rows to reduce action-space mismatch bias.",
    ]

    fairness_lines = [
        "# Fairness report: TALE baseline integration",
        "",
        "## Problem-space mismatch statement",
        "- TALE performs per-instance token budget allocation; our primary method is a sequential frontier stop-vs-act allocator.",
        "- We therefore report matched-compute comparisons and avoid claiming strict control-equivalence.",
        "",
        "## Primary comparison protocol",
        "- Compare `adaptive_min_expand_1` vs `external_tale_prompt_budgeting` at fixed budget grid and matched-average-compute rows.",
        "",
        "## Caveats",
        "- Prompt-level TALE adapter here does not include TALE-PT post-training.",
        "- MODE B remains blocked unless official/full TALE outputs are provided.",
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
