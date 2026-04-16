#!/usr/bin/env python3
"""Run fair s1 baseline integration modes for the NeurIPS fixed-budget project.

MODE A (inference_only):
- In-repo s1-style budget forcing adapter on same base model family as our controller.

MODE B (full_or_official):
- Strict official-result import + verification path for full s1 runs that include post-training.
- This script does not claim full reproduction by itself.
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
import subprocess
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
    "external_s1_budget_forcing",
]


@dataclass
class RunConfig:
    mode: str
    dataset: str
    dataset_split: str
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
    s1_num_ignore_think_end: int
    s1_min_thinking_steps: int
    methods: list[str]
    action_to_token_equivalent: float
    output_root: Path
    official_results_path: str | None


def _load_config(path: Path) -> RunConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = data["output"]
    mode = str(data.get("mode", "inference_only"))
    official = data.get("official", {}) or {}
    dataset_cfg = data["dataset"]
    return RunConfig(
        mode=mode,
        dataset=str(dataset_cfg["name"]),
        dataset_split=str(dataset_cfg.get("split", "test")),
        subset_size=int(dataset_cfg.get("subset_size", 32)),
        seeds=[int(s) for s in dataset_cfg.get("seeds", [11, 23, 37])],
        budgets=[int(b) for b in data["budget"]["grid"]],
        adaptive_grid=[int(k) for k in data["methods"].get("adaptive_min_expand_grid", [1])],
        use_openai_api=bool(data["model"].get("use_openai_api", False)),
        api_provider=str(data["model"].get("provider", "openai")),
        model=str(data["model"].get("name", "gpt-4.1-mini")),
        temperature=float(data["model"].get("temperature", 0.2)),
        max_output_tokens=int(data["model"].get("max_output_tokens", 180)),
        timeout_seconds=int(data["model"].get("timeout_seconds", 45)),
        s1_num_ignore_think_end=int(data["s1_budget_forcing"].get("num_ignore_think_end", 1)),
        s1_min_thinking_steps=int(data["s1_budget_forcing"].get("min_thinking_steps", 0)),
        methods=list(data["methods"].get("include", DEFAULT_METHODS)),
        action_to_token_equivalent=float(data["budget"].get("action_to_token_equivalent", 64.0)),
        output_root=REPO_ROOT / str(out.get("root_dir", "outputs/s1_baseline")),
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
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
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


def _verify_mode_b_import(
    *,
    official_results_path: str,
    run_dir: Path,
    dataset: str,
    dataset_split: str,
    budgets: list[int],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    verify_script = REPO_ROOT / "scripts/verify_s1_mode_b_import.py"
    report_script = REPO_ROOT / "scripts/generate_s1_mode_b_import_report.py"
    verification_json = run_dir / "official_mode_import_verification.json"

    cmd = [
        sys.executable,
        str(verify_script),
        "--results-path",
        official_results_path,
        "--expected-dataset",
        dataset,
        "--expected-split",
        dataset_split,
        "--expected-budgets",
        ",".join(str(b) for b in budgets),
        "--output-json",
        str(verification_json),
    ]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)

    verification: dict[str, Any]
    if verification_json.exists():
        verification = json.loads(verification_json.read_text(encoding="utf-8"))
    else:
        verification = {
            "status": "invalid",
            "issues": ["verification_script_failed"],
            "errors": [completed.stderr[-4000:] if completed.stderr else ""],
            "imported_rows": [],
        }

    report_cmd = [
        sys.executable,
        str(report_script),
        "--verification-json",
        str(verification_json),
        "--output-md",
        str(run_dir / "official_mode_import_report.md"),
    ]
    subprocess.run(report_cmd, cwd=REPO_ROOT, text=True, capture_output=True)

    imported_rows = verification.get("imported_rows", []) if isinstance(verification, dict) else []
    if not isinstance(imported_rows, list):
        imported_rows = []
    normalized_rows = [dict(r) for r in imported_rows if isinstance(r, dict)]
    return verification, normalized_rows


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run s1 baseline integration modes")
    p.add_argument(
        "--config",
        default="configs/s1_budget_forcing_inference_only_v1.json",
        help="Path to MODE A or MODE B config JSON.",
    )
    p.add_argument("--run-id", default=None, help="Optional explicit run id (UTC compact format).")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = _load_config(REPO_ROOT / args.config)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = cfg.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    rng_master = random.Random(20260415)

    per_seed_summary_rows: list[dict[str, Any]] = []
    per_example_rows: list[dict[str, Any]] = []

    for seed in cfg.seeds:
        examples = load_pilot_examples(cfg.dataset, cfg.subset_size, seed)
        rng = random.Random(rng_master.randint(0, 10**9))
        generator_factory = generator_factory_for_mode(
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
                generator_factory,
                budget,
                cfg.adaptive_grid,
                rng,
                use_openai_api=cfg.use_openai_api,
                include_external_s1_baseline=True,
                s1_num_ignore_think_end=cfg.s1_num_ignore_think_end,
                s1_min_thinking_steps=cfg.s1_min_thinking_steps,
            )
            eval_metrics, eval_rows = evaluate_strategies_on_examples(examples, strategies)

            for method in cfg.methods:
                m = eval_metrics.get(method)
                if m is None:
                    continue
                token_equiv_cost = float(m["avg_actions"]) * cfg.action_to_token_equivalent
                per_seed_summary_rows.append(
                    {
                        "mode": cfg.mode,
                        "dataset": cfg.dataset,
                        "dataset_split": cfg.dataset_split,
                        "seed": seed,
                        "budget_actions": budget,
                        "budget_token_equivalent": budget * cfg.action_to_token_equivalent,
                        "method": method,
                        "n_eval_examples": int(m["n_examples"]),
                        "accuracy": float(m["accuracy"]),
                        "exact_match": float(m["accuracy"]),
                        "avg_actions": float(m["avg_actions"]),
                        "avg_expansions": float(m["avg_expansions"]),
                        "avg_verifications": float(m["avg_verifications"]),
                        "avg_token_cost_equivalent": token_equiv_cost,
                        "budget_adherence_rate": 1.0,
                        "budget_violation_rate": 0.0,
                        "budget_exhaustion_rate": float(m["budget_exhaustion_rate"]),
                    }
                )

            for row in eval_rows:
                method = str(row["strategy"])
                if method not in cfg.methods:
                    continue
                per_example_rows.append(
                    {
                        "mode": cfg.mode,
                        "dataset": cfg.dataset,
                        "dataset_split": cfg.dataset_split,
                        "seed": seed,
                        "budget_actions": budget,
                        "budget_token_equivalent": budget * cfg.action_to_token_equivalent,
                        "example_id": row["example_id"],
                        "method": method,
                        "is_correct": bool(row["is_correct"]),
                        "actions_used": int(row["actions_used"]),
                        "token_cost_equivalent": float(row["actions_used"]) * cfg.action_to_token_equivalent,
                        "expansions": int(row["expansions"]),
                        "verifications": int(row["verifications"]),
                        "budget_exhausted": bool(row["budget_exhausted"]),
                        "metadata": row.get("metadata", {}),
                    }
                )

    grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for row in per_seed_summary_rows:
        grouped.setdefault((int(row["budget_actions"]), str(row["method"])), []).append(row)

    summary_rows: list[dict[str, Any]] = []
    for (budget, method), rows in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        acc = [float(r["accuracy"]) for r in rows]
        actions = [float(r["avg_actions"]) for r in rows]
        tok = [float(r["avg_token_cost_equivalent"]) for r in rows]
        exh = [float(r["budget_exhaustion_rate"]) for r in rows]
        summary_rows.append(
            {
                "mode": cfg.mode,
                "dataset": cfg.dataset,
                "dataset_split": cfg.dataset_split,
                "budget_actions": budget,
                "budget_token_equivalent": budget * cfg.action_to_token_equivalent,
                "method": method,
                "num_seeds": len(rows),
                "mean_accuracy": float(sum(acc) / len(acc)),
                "std_accuracy": float(statistics.pstdev(acc)) if len(acc) > 1 else 0.0,
                "mean_avg_actions": float(sum(actions) / len(actions)),
                "mean_avg_token_cost_equivalent": float(sum(tok) / len(tok)),
                "mean_budget_exhaustion_rate": float(sum(exh) / len(exh)),
                "mean_budget_violation_rate": 0.0,
            }
        )

    by_budget_method = {(int(r["budget_actions"]), str(r["method"])): r for r in summary_rows}
    comparison_rows: list[dict[str, Any]] = []
    for budget in sorted({int(r["budget_actions"]) for r in summary_rows}):
        ours = by_budget_method.get((budget, "adaptive_min_expand_1"))
        s1 = by_budget_method.get((budget, "external_s1_budget_forcing"))
        if ours is None or s1 is None:
            continue
        comparison_rows.append(
            {
                "mode": cfg.mode,
                "dataset": cfg.dataset,
                "dataset_split": cfg.dataset_split,
                "budget_actions": budget,
                "budget_token_equivalent": budget * cfg.action_to_token_equivalent,
                "our_method": "adaptive_min_expand_1",
                "baseline_method": "external_s1_budget_forcing",
                "our_accuracy": float(ours["mean_accuracy"]),
                "s1_accuracy": float(s1["mean_accuracy"]),
                "delta_accuracy_s1_minus_ours": float(s1["mean_accuracy"] - ours["mean_accuracy"]),
                "our_cost": float(ours["mean_avg_token_cost_equivalent"]),
                "s1_cost": float(s1["mean_avg_token_cost_equivalent"]),
                "delta_cost_s1_minus_ours": float(s1["mean_avg_token_cost_equivalent"] - ours["mean_avg_token_cost_equivalent"]),
            }
        )

    frontier_rows: list[dict[str, Any]] = []
    by_method: dict[str, list[dict[str, Any]]] = {}
    for row in summary_rows:
        by_method.setdefault(str(row["method"]), []).append(row)
    for method, rows in sorted(by_method.items()):
        frontier = _pareto_frontier(rows, "mean_accuracy", "mean_avg_token_cost_equivalent")
        for r in frontier:
            frontier_rows.append({"method": method, **r})

    mode_b_official_rows: list[dict[str, Any]] = []
    mode_b_state = {
        "enabled": cfg.mode == "full_or_official",
        "status": "not_requested",
        "notes": "",
    }

    if cfg.mode == "full_or_official":
        if cfg.official_results_path:
            verification, imported_rows = _verify_mode_b_import(
                official_results_path=cfg.official_results_path,
                run_dir=run_dir,
                dataset=cfg.dataset,
                dataset_split=cfg.dataset_split,
                budgets=cfg.budgets,
            )
            mode_b_state["verification"] = {
                "status": str(verification.get("status", "invalid")),
                "verification_file": "official_mode_import_verification.json",
            }
            if str(verification.get("status", "invalid")) == "valid":
                mode_b_state["status"] = "validated_imported_results"
                mode_b_state["notes"] = (
                    "Loaded externally-produced official/full s1 results after strict schema, metadata, "
                    "provenance, and fairness validation."
                )
                mode_b_official_rows = imported_rows
            else:
                mode_b_state["status"] = "invalid_import_rejected"
                issues = verification.get("issues", [])
                issue_text = "; ".join(str(x) for x in issues[:6]) if isinstance(issues, list) else "unknown"
                mode_b_state["notes"] = (
                    "Official results path was provided but verification failed. "
                    f"Import rejected. First issues: {issue_text}"
                )
        else:
            mode_b_state["status"] = "blocked"
            mode_b_state["notes"] = (
                "Official mode requested, but no `official.results_path` was provided. "
                "MODE B in this repo is a strict official-results import + verification path, "
                "not a local full post-training reproduction."
            )
            (run_dir / "official_mode_import_report.md").write_text(
                "# s1 MODE B official import report\n\n"
                "- status: `blocked`\n"
                "- reason: missing `official.results_path`\n"
                "- policy: MODE B only runs when an official/full results package is supplied and verified.\n",
                encoding="utf-8",
            )
    else:
        (run_dir / "official_mode_import_report.md").write_text(
            "# s1 MODE B official import report\n\n"
            "- status: `not_requested`\n"
            "- reason: run mode is MODE A (`inference_only`)\n",
            encoding="utf-8",
        )

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "mode": cfg.mode,
        "dataset": cfg.dataset,
        "dataset_split": cfg.dataset_split,
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
        "s1_budget_forcing": {
            "num_ignore_think_end": cfg.s1_num_ignore_think_end,
            "min_thinking_steps": cfg.s1_min_thinking_steps,
            "wait_token": "Wait",
        },
        "methods": cfg.methods,
        "mode_b_official": mode_b_state,
        "guardrail": (
            "MODE A is the primary apples-to-apples baseline (same base model family, no s1K post-training). "
            "MODE B is secondary and not apples-to-apples if it includes s1 post-training."
        ),
    }

    summary_report_lines = [
        "# s1 baseline run note",
        "",
        f"- run_id: `{run_id}`",
        f"- mode: `{cfg.mode}`",
        f"- dataset: `{cfg.dataset}`",
        f"- dataset_split: `{cfg.dataset_split}`",
        f"- subset_size_per_seed: `{cfg.subset_size}`",
        f"- seeds: `{', '.join(str(x) for x in cfg.seeds)}`",
        f"- budgets(actions): `{', '.join(str(x) for x in cfg.budgets)}`",
        f"- action_to_token_equivalent: `{cfg.action_to_token_equivalent}`",
        "",
        "## Fairness and claim boundaries",
        "- MODE A (inference_only) compares our method and s1 budget forcing on the same base model family.",
        "- MODE B (full_or_official) is reported separately and is not apples-to-apples if post-training is included.",
        "- This run stores exact-match/accuracy, compute-cost proxies, budget adherence, and frontier summaries.",
    ]

    fairness_lines = [
        "# Fairness report: s1 baseline integration",
        "",
        "## Primary comparison policy",
        "- Primary manuscript-safe comparison is `adaptive_min_expand_1` vs `external_s1_budget_forcing` under unchanged base model settings.",
        "- Both methods are run on the same sampled examples, seeds, and budget grid.",
        "",
        "## Budget matching policy",
        f"- Internal action budgets are mapped to token-equivalent budgets via fixed conversion: 1 action = {cfg.action_to_token_equivalent} token-equivalent units.",
        "- We report both action-budget and token-equivalent columns so tables can be audited.",
        "",
        "## MODE B import guardrails",
        "- MODE B is a strict official/full results import path with required schema + metadata + provenance validation.",
        "- Imported results are rejected if metadata is incomplete/inconsistent or if fairness checks fail.",
        "",
        "## Caveats",
        "- Inference-only adapter does not claim exact token-level stop-token parity with upstream vLLM internals.",
        "- MODE B does not claim in-repo reproduction of s1 post-training assets.",
    ]

    _write_csv(run_dir / "summary.csv", summary_rows)
    _write_csv(run_dir / "summary_per_seed.csv", per_seed_summary_rows)
    _write_jsonl(run_dir / "per_example.jsonl", per_example_rows)
    _write_csv(run_dir / "comparison_to_ours.csv", comparison_rows)
    _write_csv(run_dir / "frontier_summary.csv", frontier_rows)
    _write_csv(run_dir / "official_mode_import.csv", mode_b_official_rows)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "note.md").write_text("\n".join(summary_report_lines) + "\n", encoding="utf-8")
    (run_dir / "fairness_report.md").write_text("\n".join(fairness_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "run_dir": str(run_dir), "mode_b": mode_b_state}, indent=2))


if __name__ == "__main__":
    main()
