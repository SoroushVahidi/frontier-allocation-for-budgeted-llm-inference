#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import random
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode, load_pilot_examples

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)

METHOD_RUNTIME_MAP = {
    "strict_f3": STRICT_F3_RUNTIME,
    "external_l1_max": "external_l1_max",
    "external_s1_budget_forcing": "external_s1_budget_forcing",
    "external_tale_prompt_budgeting": "external_tale_prompt_budgeting",
}

PRIORITY_DATASETS = [
    "allenai/drop",
    "TAUR-Lab/MuSR",
    "openeval/BIG-Bench-Hard",
    "deepmind/aqua_rat",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_csv(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _parse_int_csv(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _safe_mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def main() -> None:
    p = argparse.ArgumentParser(description="Run publication-facing breadth dataset evaluation bundle.")
    p.add_argument("--run-id", default=_utc_now())
    p.add_argument("--datasets", default=",".join(PRIORITY_DATASETS))
    p.add_argument("--methods", default="strict_f3,external_l1_max,external_s1_budget_forcing")
    p.add_argument("--subset-size", type=int, default=24)
    p.add_argument("--seeds", default="11,23")
    p.add_argument("--budgets", default="6,8")
    args = p.parse_args()

    run_id = args.run_id
    out_dir = REPO_ROOT / "outputs/breadth_dataset_eval" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    datasets = _parse_csv(args.datasets)
    methods = _parse_csv(args.methods)
    seeds = _parse_int_csv(args.seeds)
    budgets = _parse_int_csv(args.budgets)

    dataset_order = sorted(datasets, key=lambda d: PRIORITY_DATASETS.index(d) if d in PRIORITY_DATASETS else 999)

    method_rows: list[dict[str, Any]] = []
    per_example_rows: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    attempt_rows: list[dict[str, Any]] = []

    for dataset in dataset_order:
        dataset_load_ok = True
        dataset_examples_by_seed: dict[int, list[Any]] = {}
        load_error = ""

        for seed in seeds:
            try:
                dataset_examples_by_seed[seed] = load_pilot_examples(dataset, args.subset_size, seed)
            except Exception as exc:  # noqa: BLE001
                dataset_load_ok = False
                load_error = f"{type(exc).__name__}: {exc}"
                attempt_rows.append(
                    {
                        "dataset": dataset,
                        "seed": seed,
                        "budget": None,
                        "method": None,
                        "status": "load_failed",
                        "error": load_error,
                    }
                )
                break

        if not dataset_load_ok:
            for method in methods:
                status_rows.append(
                    {
                        "dataset": dataset,
                        "method": method,
                        "status": "integrated_but_not_runnable",
                        "n_runs": 0,
                        "n_examples": 0,
                        "reason": load_error,
                    }
                )
            blocked_rows.append(
                {
                    "dataset": dataset,
                    "status": "integrated but not runnable",
                    "reason": load_error,
                    "what_was_attempted": "load_pilot_examples across requested seeds",
                    "blocker_type": "temporary_or_environmental",
                    "partial_value_obtained": "none",
                }
            )
            continue

        for method in methods:
            runtime_method = METHOD_RUNTIME_MAP.get(method)
            if runtime_method is None:
                status_rows.append(
                    {
                        "dataset": dataset,
                        "method": method,
                        "status": "failed",
                        "n_runs": 0,
                        "n_examples": 0,
                        "reason": "method_not_supported",
                    }
                )
                blocked_rows.append(
                    {
                        "dataset": dataset,
                        "status": "failed",
                        "reason": f"Unsupported method mapping: {method}",
                        "what_was_attempted": "method selection in runner",
                        "blocker_type": "structural",
                        "partial_value_obtained": "none",
                    }
                )
                continue

            run_count = 0
            ex_count = 0
            method_errors: list[str] = []
            acc_values: list[float] = []
            actions_values: list[float] = []
            exp_values: list[float] = []
            ver_values: list[float] = []
            exhaust_values: list[float] = []

            for seed in seeds:
                examples = dataset_examples_by_seed[seed]
                example_lookup = {ex.example_id: asdict(ex) for ex in examples}
                for budget in budgets:
                    rng = random.Random(1000003 * seed + 97 * budget + 13)
                    factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
                    try:
                        strategies = build_frontier_strategies(
                            factory,
                            budget,
                            [1],
                            rng,
                            use_openai_api=False,
                            include_external_s1_baseline=True,
                            include_external_tale_baseline=True,
                            include_external_l1_baseline=True,
                            include_broad_diversity_aggregation_methods=True,
                        )
                        if runtime_method not in strategies:
                            raise KeyError(f"Runtime strategy missing: {runtime_method}")
                        controller = strategies[runtime_method]
                        local_correct = 0
                        local_actions = 0
                        local_exp = 0
                        local_ver = 0
                        local_exhaust = 0

                        for ex in examples:
                            r = controller.run(ex.question, ex.answer)
                            is_correct = bool(r.is_correct)
                            local_correct += int(is_correct)
                            local_actions += int(r.actions_used)
                            local_exp += int(r.expansions)
                            local_ver += int(r.verifications)
                            local_exhaust += int(bool(r.budget_exhausted))
                            per_example_rows.append(
                                {
                                    "dataset": dataset,
                                    "seed": seed,
                                    "budget": budget,
                                    "method": method,
                                    "example_id": ex.example_id,
                                    "question": example_lookup[ex.example_id]["question"],
                                    "ground_truth": example_lookup[ex.example_id]["answer"],
                                    "is_correct": is_correct,
                                    "actions_used": int(r.actions_used),
                                    "expansions": int(r.expansions),
                                    "verifications": int(r.verifications),
                                    "budget_exhausted": bool(r.budget_exhausted),
                                }
                            )

                        n = max(1, len(examples))
                        acc_values.append(local_correct / n)
                        actions_values.append(local_actions / n)
                        exp_values.append(local_exp / n)
                        ver_values.append(local_ver / n)
                        exhaust_values.append(local_exhaust / n)
                        run_count += 1
                        ex_count += len(examples)
                        attempt_rows.append(
                            {
                                "dataset": dataset,
                                "seed": seed,
                                "budget": budget,
                                "method": method,
                                "status": "ok",
                                "error": "",
                            }
                        )
                    except Exception as exc:  # noqa: BLE001
                        err = f"{type(exc).__name__}: {exc}"
                        method_errors.append(err)
                        attempt_rows.append(
                            {
                                "dataset": dataset,
                                "seed": seed,
                                "budget": budget,
                                "method": method,
                                "status": "failed",
                                "error": err,
                            }
                        )

            if run_count == 0:
                status = "failed"
                reason = method_errors[0] if method_errors else "no_successful_runs"
            elif method_errors:
                status = "partial"
                reason = method_errors[0]
            else:
                status = "success"
                reason = ""

            status_rows.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "status": status,
                    "n_runs": run_count,
                    "n_examples": ex_count,
                    "reason": reason,
                }
            )

            method_rows.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "primary_metric_name": "accuracy",
                    "primary_metric_value": _safe_mean(acc_values) if run_count > 0 else None,
                    "mean_actions": _safe_mean(actions_values) if run_count > 0 else None,
                    "mean_expansions": _safe_mean(exp_values) if run_count > 0 else None,
                    "mean_verifications": _safe_mean(ver_values) if run_count > 0 else None,
                    "mean_budget_exhaustion_rate": _safe_mean(exhaust_values) if run_count > 0 else None,
                    "n_runs": run_count,
                    "n_examples": ex_count,
                    "status": status,
                    "status_reason": reason,
                }
            )

            if status != "success":
                blocked_rows.append(
                    {
                        "dataset": dataset,
                        "status": "partial" if status == "partial" else "failed",
                        "reason": reason,
                        "what_was_attempted": f"{method} across seeds={seeds} budgets={budgets}",
                        "blocker_type": "temporary_or_environmental" if "Connection" in reason or "timeout" in reason.lower() else "structural_or_runtime",
                        "partial_value_obtained": f"successful_runs={run_count}" if run_count > 0 else "none",
                    }
                )

    _write_csv(out_dir / "dataset_results_by_method.csv", method_rows)

    # dataset aggregate (over methods)
    ds_rows: list[dict[str, Any]] = []
    for dataset in dataset_order:
        drows = [r for r in method_rows if r["dataset"] == dataset]
        successful = [r for r in drows if r["status"] == "success"]
        ds_rows.append(
            {
                "dataset": dataset,
                "methods_requested": len(methods),
                "methods_successful": len(successful),
                "dataset_status": "success" if len(successful) == len(methods) else ("partial" if len(successful) > 0 else "integrated_but_not_runnable"),
                "notes": "" if len(successful) == len(methods) else "See blocked_or_partial_datasets.csv",
            }
        )
    _write_csv(out_dir / "dataset_results.csv", ds_rows)
    _write_csv(out_dir / "dataset_status_matrix.csv", status_rows)
    _write_csv(out_dir / "blocked_or_partial_datasets.csv", blocked_rows)

    # per-example jsonl
    with (out_dir / "per_example_rows.jsonl").open("w", encoding="utf-8") as f:
        for row in per_example_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # comparison summary
    method_lookup = {(r["dataset"], r["method"]): r for r in method_rows}
    comparison_rows: list[dict[str, Any]] = []
    for dataset in dataset_order:
        strict = method_lookup.get((dataset, "strict_f3"))
        l1 = method_lookup.get((dataset, "external_l1_max"))
        strict_ahead = None
        if strict and l1 and strict.get("primary_metric_value") is not None and l1.get("primary_metric_value") is not None:
            strict_ahead = float(strict["primary_metric_value"]) > float(l1["primary_metric_value"])

        for method in methods:
            row = method_lookup.get((dataset, method))
            if row is None:
                continue
            status = str(row["status"])
            if status == "success":
                placement = "appendix"
                caveat = "Expansion-dataset evidence; canonical main table remains math-core matched surface."
            elif status == "partial":
                placement = "qualitative_support_only"
                caveat = f"Partial run: {row['status_reason']}"
            else:
                placement = "qualitative_support_only"
                caveat = f"Not runnable: {row['status_reason']}"
            comparison_rows.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "primary_metric": "accuracy",
                    "primary_metric_value": row["primary_metric_value"],
                    "strict_f3_beats_external_l1_max": strict_ahead,
                    "paper_usability": placement,
                    "important_caveat": caveat,
                }
            )

    _write_csv(out_dir / "breadth_comparison_summary.csv", comparison_rows)

    md_lines = [
        f"# Breadth dataset evaluation ({run_id})",
        "",
        "## Scope",
        f"- Datasets (priority order): {', '.join(dataset_order)}",
        f"- Methods: {', '.join(methods)}",
        f"- Seeds: {seeds}",
        f"- Budgets: {budgets}",
        f"- Subset size per dataset/seed: {args.subset_size}",
        "",
        "## Strict_f3 vs external_l1_max by dataset",
    ]
    for dataset in dataset_order:
        s = method_lookup.get((dataset, "strict_f3"))
        l = method_lookup.get((dataset, "external_l1_max"))
        if s is None or l is None:
            md_lines.append(f"- {dataset}: unavailable")
            continue
        if s.get("primary_metric_value") is None or l.get("primary_metric_value") is None:
            md_lines.append(f"- {dataset}: unavailable ({s.get('status')} / {l.get('status')})")
            continue
        delta = float(s["primary_metric_value"]) - float(l["primary_metric_value"])
        md_lines.append(
            f"- {dataset}: strict_f3={float(s['primary_metric_value']):.4f}, external_l1_max={float(l['primary_metric_value']):.4f}, delta={delta:+.4f}"
        )

    (out_dir / "breadth_comparison_summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    completed = [r["dataset"] for r in ds_rows if r["dataset_status"] == "success"]
    partial_or_blocked = [r["dataset"] for r in ds_rows if r["dataset_status"] != "success"]
    strict_wins = 0
    strict_total = 0
    for dataset in dataset_order:
        s = method_lookup.get((dataset, "strict_f3"))
        l = method_lookup.get((dataset, "external_l1_max"))
        if not s or not l:
            continue
        if s.get("primary_metric_value") is None or l.get("primary_metric_value") is None:
            continue
        strict_total += 1
        strict_wins += int(float(s["primary_metric_value"]) > float(l["primary_metric_value"]))

    summary = {
        "run_id": run_id,
        "datasets": dataset_order,
        "methods": methods,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": args.subset_size,
        "successful_datasets": completed,
        "partial_or_blocked_datasets": partial_or_blocked,
        "strict_f3_vs_external_l1_max": {
            "datasets_comparable": strict_total,
            "strict_f3_wins": strict_wins,
            "strict_f3_win_rate": (strict_wins / strict_total) if strict_total else None,
        },
    }

    status = {
        "status": "ok" if not partial_or_blocked else "partial_ok",
        "failed_or_partial_dataset_count": len(partial_or_blocked),
        **summary,
    }

    _write_json(out_dir / "summary.json", summary)
    _write_json(out_dir / "status.json", status)
    _write_json(
        out_dir / "manifest.json",
        {
            "run_id": run_id,
            "generated_files": [
                "status.json",
                "summary.json",
                "summary.md",
                "manifest.json",
                "dataset_results.csv",
                "dataset_results_by_method.csv",
                "dataset_status_matrix.csv",
                "blocked_or_partial_datasets.csv",
                "config_snapshot.json",
                "command_snapshot.txt",
                "per_example_rows.jsonl",
                "breadth_comparison_summary.csv",
                "breadth_comparison_summary.md",
            ],
            "attempt_log": "dataset_status_matrix.csv",
        },
    )
    _write_json(
        out_dir / "config_snapshot.json",
        {
            "args": vars(args),
            "method_runtime_map": METHOD_RUNTIME_MAP,
            "strict_f3_runtime": STRICT_F3_RUNTIME,
            "attempts": attempt_rows,
        },
    )

    cmd = (
        "python scripts/run_breadth_dataset_eval.py "
        f"--run-id {run_id} --datasets {args.datasets} --methods {args.methods} "
        f"--subset-size {args.subset_size} --seeds {args.seeds} --budgets {args.budgets}"
    )
    (out_dir / "command_snapshot.txt").write_text(cmd + "\n", encoding="utf-8")

    summary_md = [
        f"# Breadth dataset eval summary ({run_id})",
        "",
        f"- Successful datasets: {completed}",
        f"- Partial/blocked datasets: {partial_or_blocked}",
        f"- strict_f3 vs external_l1_max wins: {strict_wins}/{strict_total}",
        "",
        "See `breadth_comparison_summary.csv` and `blocked_or_partial_datasets.csv` for details.",
    ]
    (out_dir / "summary.md").write_text("\n".join(summary_md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
