#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import load_pilot_examples

CANONICAL_SCRIPT = REPO_ROOT / "scripts/run_canonical_real_model_validation.py"

OURS_METHODS = ["strict_f3", "strict_gate1_cap_k6", "strict_f2"]
EXTERNAL_METHODS = [
    "external_l1_max",
    "external_l1_exact",
    "external_tale_prompt_budgeting",
    "external_s1_budget_forcing",
    "self_consistency_3",
]
# Supported today by scripts/run_canonical_real_model_validation.py
CANONICAL_RUNNABLE_METHODS = {
    "strict_f3",
    "strict_gate1_cap_k6",
    "strict_f2",
    "external_l1_max",
    "self_consistency_3",
}

DEFAULT_DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024", "olympiadbench"]
DEFAULT_SEEDS = [11, 23]
DEFAULT_BUDGETS = [4, 6, 8]
DEFAULT_METHODS = ["strict_f3", "strict_gate1_cap_k6", "strict_f2", "external_l1_max", "self_consistency_3"]
DEFAULT_SUBSET = 20
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_COHERE_MODEL = "command-r-plus-08-2024"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Canonical real-model ours-vs-external validation wrapper (resumable)")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--providers", default="openai,cohere", help="Comma-separated provider list.")
    p.add_argument("--datasets", default=",".join(DEFAULT_DATASETS))
    p.add_argument("--subset-size", type=int, default=DEFAULT_SUBSET)
    p.add_argument("--seeds", default=",".join(str(x) for x in DEFAULT_SEEDS))
    p.add_argument("--budgets", default=",".join(str(x) for x in DEFAULT_BUDGETS))
    p.add_argument("--methods", default=",".join(DEFAULT_METHODS))
    p.add_argument("--openai-model", default=DEFAULT_OPENAI_MODEL)
    p.add_argument("--cohere-model", default=DEFAULT_COHERE_MODEL)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--max-evaluated-rows", type=int, default=0, help="If >0, cap newly generated rows per provider for staged runs.")
    return p.parse_args()


def parse_csv_list(text: str) -> list[str]:
    return [x.strip() for x in text.split(",") if x.strip()]


def parse_csv_ints(text: str) -> list[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def row_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("dataset", "")),
        str(row.get("seed", "")),
        str(row.get("budget", "")),
        str(row.get("example_id", "")),
        str(row.get("method", "")),
    )


def choose_datasets(requested: list[str], subset_size: int, seed: int) -> tuple[list[str], list[dict[str, Any]]]:
    active: list[str] = []
    statuses: list[dict[str, Any]] = []
    for d in requested:
        try:
            _ = load_pilot_examples(d, min(2, max(1, subset_size)), seed)
            active.append(d)
            statuses.append({"dataset": d, "included": True, "status": "ok", "detail": "loader probe succeeded"})
        except Exception as exc:  # noqa: BLE001
            statuses.append({"dataset": d, "included": False, "status": "excluded", "detail": f"loader probe failed: {type(exc).__name__}: {str(exc)[:200]}"})
    return active, statuses


def provider_api_key_present(provider: str) -> bool:
    p = provider.strip().lower()
    if p == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if p == "cohere":
        return bool(os.getenv("COHERE_API_KEY"))
    return False


def provider_model(provider: str, args: argparse.Namespace) -> str:
    return args.openai_model if provider == "openai" else args.cohere_model


def summarize_rows(rows: list[dict[str, str]], group_keys: list[str]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        k = tuple(str(r.get(k, "")) for k in group_keys)
        buckets[k].append(r)

    out: list[dict[str, Any]] = []
    for key, group in sorted(buckets.items(), key=lambda kv: kv[0]):
        prefix = {name: key[i] for i, name in enumerate(group_keys)}
        out.append(
            {
                **prefix,
                "n": len(group),
                "accuracy": mean([float(x.get("is_correct", 0)) for x in group]),
                "absent_from_tree_rate": mean([float(x.get("absent_from_tree", 0)) for x in group]),
                "present_not_selected_rate": mean([float(x.get("present_not_selected", 0)) for x in group]),
                "output_layer_mismatch_rate": mean([float(x.get("output_layer_mismatch", 0)) for x in group]),
                "rescue_applied_rate": mean([float(x.get("rescue_applied", 0)) for x in group]),
                "avg_actions": mean([float(x.get("actions_used", 0)) for x in group]),
                "avg_expansions": mean([float(x.get("expansions", 0)) for x in group]),
                "avg_verifications": mean([float(x.get("verifications", 0)) for x in group]),
            }
        )
    return out


def provider_best_stats(rows: list[dict[str, str]]) -> dict[str, Any]:
    by_method = summarize_rows(rows, ["method"]) if rows else []
    method_to_acc = {r["method"]: float(r["accuracy"]) for r in by_method}
    ours_candidates = [m for m in OURS_METHODS if m in method_to_acc]
    ext_candidates = [m for m in EXTERNAL_METHODS if m in method_to_acc]
    best_ours = max(ours_candidates, key=lambda m: method_to_acc[m]) if ours_candidates else ""
    best_ext = max(ext_candidates, key=lambda m: method_to_acc[m]) if ext_candidates else ""
    best_ours_acc = method_to_acc.get(best_ours, 0.0)
    best_ext_acc = method_to_acc.get(best_ext, 0.0)
    return {
        "rows": len(rows),
        "best_ours_method": best_ours,
        "best_ours_accuracy": best_ours_acc,
        "best_external_method": best_ext,
        "best_external_accuracy": best_ext_acc,
        "ours_minus_external": best_ours_acc - best_ext_acc,
    }


def failure_for_method(rows: list[dict[str, str]], method: str) -> dict[str, Any]:
    fails = [r for r in rows if r.get("method") == method and int(float(r.get("is_correct", 0))) == 0]
    c = Counter(r.get("failure_type", "") for r in fails)
    n = max(1, len(fails))
    return {
        "method": method,
        "n_failures": len(fails),
        "absent_from_tree": c.get("absent_from_tree", 0),
        "present_not_selected": c.get("present_not_selected", 0),
        "output_layer_mismatch": c.get("output_layer_mismatch", 0),
        "absent_from_tree_share": c.get("absent_from_tree", 0) / n,
        "present_not_selected_share": c.get("present_not_selected", 0) / n,
        "output_layer_mismatch_share": c.get("output_layer_mismatch", 0) / n,
    }


def claim_label(
    *,
    openai_completed: bool,
    has_rows: bool,
    total_rows: int,
    gap: float,
    slice_positive_majority: bool,
    subset_size: int,
    cross_provider_completed: bool,
) -> str:
    # conservative: small openai-only smoke cannot be main-paper safe
    if not has_rows:
        return "not safe"
    if subset_size < 20 or not cross_provider_completed:
        if gap > 0 and openai_completed and slice_positive_majority and total_rows > 0:
            return "supportive-only claim"
        if gap > 0:
            return "appendix-only claim"
        return "not safe"
    if gap > 0 and openai_completed and slice_positive_majority:
        return "main paper claim"
    return "appendix-only claim" if gap > 0 else "not safe"


def run_canonical_shard(
    *,
    provider: str,
    model: str,
    timestamp: str,
    dataset: str,
    seed: int,
    budget: int,
    methods: list[str],
    subset_size: int,
    dry_run: bool,
    commands: list[str],
) -> dict[str, Any]:
    if dry_run:
        return {"completed": False, "reason": "dry_run_no_api_calls", "rows": [], "errors": []}

    shard_ts = f"{timestamp}_{provider}_{seed}_{budget}_{dataset.replace('/', '_')}"
    cmd = [
        sys.executable,
        str(CANONICAL_SCRIPT),
        "--timestamp",
        shard_ts,
        "--provider",
        provider,
        "--model",
        model,
        "--datasets",
        dataset,
        "--subset-size",
        str(subset_size),
        "--seeds",
        str(seed),
        "--budgets",
        str(budget),
        "--methods",
        ",".join(methods),
    ]
    commands.append(" ".join(cmd))
    try:
        subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        return {"completed": False, "reason": f"canonical_shard_failed_exit_{exc.returncode}", "rows": [], "errors": []}

    shard_dir = REPO_ROOT / f"outputs/canonical_real_model_validation_{shard_ts}"
    rows = read_csv(shard_dir / "per_example_rows.csv")
    errors = read_csv(shard_dir / "retry_error_log.csv")
    return {"completed": True, "reason": "ok", "rows": rows, "errors": errors, "shard_dir": str(shard_dir.relative_to(REPO_ROOT))}


def ensure_provider_files(provider_dir: Path) -> None:
    provider_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "aggregate_summary.csv",
        "per_dataset_summary.csv",
        "per_budget_summary.csv",
        "seed_summary.csv",
        "per_example_rows.csv",
        "failure_decomposition.csv",
        "retry_error_log.csv",
    ]:
        p = provider_dir / name
        if not p.exists():
            p.write_text("", encoding="utf-8")


def main() -> None:
    args = parse_args()
    ts = args.timestamp
    providers = [p.lower() for p in parse_csv_list(args.providers)]
    datasets_requested = parse_csv_list(args.datasets)
    seeds = parse_csv_ints(args.seeds)
    budgets = parse_csv_ints(args.budgets)
    methods_requested = parse_csv_list(args.methods)

    out_dir = REPO_ROOT / f"outputs/real_model_ours_vs_external_validation_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    active_datasets, dataset_probe = choose_datasets(datasets_requested, args.subset_size, seeds[0] if seeds else 11)
    runnable_methods = [m for m in methods_requested if m in CANONICAL_RUNNABLE_METHODS]
    unsupported_methods = [m for m in methods_requested if m not in CANONICAL_RUNNABLE_METHODS]

    api_ready = {
        "openai_api_key_present": provider_api_key_present("openai"),
        "cohere_api_key_present": provider_api_key_present("cohere"),
    }
    (out_dir / "api_key_readiness.json").write_text(json.dumps(api_ready, indent=2) + "\n", encoding="utf-8")

    run_config = {
        "experiment": "real_model_ours_vs_external_validation",
        "timestamp": ts,
        "dry_run": bool(args.dry_run),
        "resume": bool(args.resume),
        "max_evaluated_rows": int(args.max_evaluated_rows),
        "providers_requested": providers,
        "datasets_requested": datasets_requested,
        "datasets_active": active_datasets,
        "dataset_probe": dataset_probe,
        "subset_size": args.subset_size,
        "seeds": seeds,
        "budgets": budgets,
        "methods_requested": methods_requested,
        "methods_runnable": runnable_methods,
        "methods_unsupported": unsupported_methods,
        "models": {"openai": args.openai_model, "cohere": args.cohere_model},
        "notes": [
            "Headline claim is best ours vs best external under shared substrate.",
            "Internal variant ordering is non-headline and surface-sensitive.",
            "External baselines are near-direct matched adapter baselines.",
        ],
    }
    (out_dir / "run_config.json").write_text(json.dumps(run_config, indent=2) + "\n", encoding="utf-8")

    commands = [f"python scripts/run_real_model_ours_vs_external_validation.py --timestamp {ts}"]
    provider_status: dict[str, dict[str, Any]] = {}

    for provider in providers:
        p_dir = out_dir / provider
        ensure_provider_files(p_dir)

        p_status: dict[str, Any] = {
            "provider": provider,
            "requested": True,
            "attempted": False,
            "completed": False,
            "partial": False,
            "reason": "",
            "model": provider_model(provider, args),
            "new_rows_written": 0,
            "new_errors_written": 0,
            "shards_completed": 0,
            "shards_total": len(active_datasets) * len(seeds) * len(budgets),
        }

        if provider not in {"openai", "cohere"}:
            p_status["reason"] = "unsupported_provider"
            provider_status[provider] = p_status
            continue

        if not provider_api_key_present(provider):
            p_status["reason"] = f"missing_{provider.upper()}_API_KEY"
            provider_status[provider] = p_status
            continue

        if not runnable_methods:
            p_status["reason"] = "no_runnable_methods"
            provider_status[provider] = p_status
            continue

        p_status["attempted"] = True
        existing_rows = read_csv(p_dir / "per_example_rows.csv")
        existing_errors = read_csv(p_dir / "retry_error_log.csv")
        rows_by_key = {row_key(r): r for r in existing_rows}
        errs_by_key = {row_key(r): r for r in existing_errors}

        expected_per_shard = args.subset_size * len(runnable_methods)
        new_rows_budget = args.max_evaluated_rows if args.max_evaluated_rows > 0 else 10**12
        new_rows_written = 0
        new_errors_written = 0

        for dataset in active_datasets:
            for seed in seeds:
                for budget in budgets:
                    shard_existing = 0
                    for r in rows_by_key.values():
                        if str(r.get("dataset")) == dataset and str(r.get("seed")) == str(seed) and str(r.get("budget")) == str(budget):
                            shard_existing += 1
                    for r in errs_by_key.values():
                        if str(r.get("dataset")) == dataset and str(r.get("seed")) == str(seed) and str(r.get("budget")) == str(budget):
                            shard_existing += 1

                    if args.resume and shard_existing >= expected_per_shard:
                        p_status["shards_completed"] += 1
                        continue

                    if new_rows_written >= new_rows_budget:
                        p_status["partial"] = True
                        p_status["reason"] = "stopped_by_max_evaluated_rows"
                        break

                    shard = run_canonical_shard(
                        provider=provider,
                        model=provider_model(provider, args),
                        timestamp=ts,
                        dataset=dataset,
                        seed=seed,
                        budget=budget,
                        methods=runnable_methods,
                        subset_size=args.subset_size,
                        dry_run=args.dry_run,
                        commands=commands,
                    )

                    if shard["completed"]:
                        p_status["shards_completed"] += 1
                    else:
                        p_status["partial"] = True
                        p_status["reason"] = shard.get("reason", "shard_failed")

                    # merge with dedupe by row key
                    for r in shard.get("rows", []):
                        k = row_key(r)
                        if k not in rows_by_key:
                            rows_by_key[k] = r
                            new_rows_written += 1
                    for r in shard.get("errors", []):
                        k = row_key(r)
                        if k not in errs_by_key:
                            errs_by_key[k] = r
                            new_errors_written += 1

                if p_status.get("partial") and p_status.get("reason") == "stopped_by_max_evaluated_rows":
                    break
            if p_status.get("partial") and p_status.get("reason") == "stopped_by_max_evaluated_rows":
                break

        merged_rows = sorted(rows_by_key.values(), key=row_key)
        merged_errors = sorted(errs_by_key.values(), key=row_key)

        write_csv(p_dir / "per_example_rows.csv", merged_rows)
        write_csv(p_dir / "retry_error_log.csv", merged_errors)

        # provider summaries
        agg = summarize_rows(merged_rows, ["method"])
        ds = summarize_rows(merged_rows, ["dataset", "method"])
        bdg = summarize_rows(merged_rows, ["budget", "method"])
        sed = summarize_rows(merged_rows, ["seed", "method"])
        write_csv(p_dir / "aggregate_summary.csv", agg)
        write_csv(p_dir / "per_dataset_summary.csv", ds)
        write_csv(p_dir / "per_budget_summary.csv", bdg)
        write_csv(p_dir / "seed_summary.csv", sed)

        fails = [r for r in merged_rows if int(float(r.get("is_correct", 0))) == 0]
        fail_rows = []
        for method in sorted({r.get("method", "") for r in fails}):
            fm = failure_for_method(merged_rows, method)
            fail_rows.append(
                {
                    "method": method,
                    "n_failures": fm["n_failures"],
                    "absent_from_tree_share": fm["absent_from_tree_share"],
                    "present_not_selected_share": fm["present_not_selected_share"],
                    "output_layer_mismatch_share": fm["output_layer_mismatch_share"],
                }
            )
        write_csv(p_dir / "failure_decomposition.csv", fail_rows)

        p_status["new_rows_written"] = new_rows_written
        p_status["new_errors_written"] = new_errors_written
        p_status["completed"] = (not args.dry_run) and (p_status["shards_completed"] == p_status["shards_total"]) and (not p_status["partial"])
        if args.dry_run:
            p_status["reason"] = "dry_run_no_api_calls"

        provider_status[provider] = p_status

    # combined summaries
    all_rows: list[dict[str, str]] = []
    combined_provider_rows = []
    for provider in providers:
        p_rows = read_csv(out_dir / provider / "per_example_rows.csv")
        all_rows.extend(p_rows)
        st = provider_best_stats(p_rows)
        combined_provider_rows.append(
            {
                "provider": provider,
                "best_ours_method": st["best_ours_method"],
                "best_ours_accuracy": st["best_ours_accuracy"],
                "best_external_method": st["best_external_method"],
                "best_external_accuracy": st["best_external_accuracy"],
                "ours_minus_external": st["ours_minus_external"],
                "n_rows": st["rows"],
            }
        )

    combined = provider_best_stats(all_rows)
    write_csv(
        out_dir / "combined_ours_vs_external_summary.csv",
        [
            {
                "scope": "combined_across_available_providers",
                "best_ours_method": combined["best_ours_method"],
                "best_ours_accuracy": combined["best_ours_accuracy"],
                "best_external_method": combined["best_external_method"],
                "best_external_accuracy": combined["best_external_accuracy"],
                "ours_minus_external": combined["ours_minus_external"],
                "n_rows": combined["rows"],
            }
        ],
    )
    write_csv(out_dir / "combined_provider_summary.csv", combined_provider_rows)
    write_csv(out_dir / "combined_budget_curve.csv", summarize_rows(all_rows, ["budget", "method"]))
    write_csv(out_dir / "combined_dataset_summary.csv", summarize_rows(all_rows, ["dataset", "method"]))

    cf_rows = []
    if combined["best_ours_method"]:
        cf_rows.append({"scope": "combined", "role": "best_ours", **failure_for_method(all_rows, combined["best_ours_method"])})
    if combined["best_external_method"]:
        cf_rows.append({"scope": "combined", "role": "best_external", **failure_for_method(all_rows, combined["best_external_method"])})
    for provider in providers:
        p_rows = read_csv(out_dir / provider / "per_example_rows.csv")
        pst = provider_best_stats(p_rows)
        if pst["best_ours_method"]:
            cf_rows.append({"scope": provider, "role": "best_ours", **failure_for_method(p_rows, pst["best_ours_method"])})
        if pst["best_external_method"]:
            cf_rows.append({"scope": provider, "role": "best_external", **failure_for_method(p_rows, pst["best_external_method"])})
    write_csv(out_dir / "combined_failure_decomposition.csv", cf_rows)

    # claim safety matrix
    claim_rows: list[dict[str, Any]] = []
    openai_rows = read_csv(out_dir / "openai/per_example_rows.csv")
    openai_errors = read_csv(out_dir / "openai/retry_error_log.csv")
    openai_stats = provider_best_stats(openai_rows)

    dataset_budget_gaps = []
    dbucket: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for r in openai_rows:
        dbucket[(str(r.get("dataset")), str(r.get("budget")))].append(r)
    for (dataset, budget), rows in sorted(dbucket.items()):
        st = provider_best_stats(rows)
        dataset_budget_gaps.append({"dataset": dataset, "budget": budget, "ours_minus_external": st["ours_minus_external"]})
    majority_positive = sum(1 for r in dataset_budget_gaps if float(r["ours_minus_external"]) > 0) > (len(dataset_budget_gaps) / 2) if dataset_budget_gaps else False

    cross_provider_completed = bool(provider_status.get("openai", {}).get("completed")) and bool(provider_status.get("cohere", {}).get("completed"))
    label = claim_label(
        openai_completed=bool(provider_status.get("openai", {}).get("completed")),
        has_rows=bool(openai_rows),
        total_rows=len(openai_rows),
        gap=float(openai_stats["ours_minus_external"]),
        slice_positive_majority=majority_positive,
        subset_size=args.subset_size,
        cross_provider_completed=cross_provider_completed,
    )

    claim_rows.append(
        {
            "scope": "openai",
            "provider_completed": int(bool(provider_status.get("openai", {}).get("completed"))),
            "partial": int(bool(provider_status.get("openai", {}).get("partial"))),
            "expected_rows": len(active_datasets) * len(seeds) * len(budgets) * len(runnable_methods) * args.subset_size,
            "evaluated_rows": len(openai_rows),
            "error_rows": len(openai_errors),
            "api_failure_rate": (len(openai_errors) / max(1, len(openai_rows) + len(openai_errors))),
            "best_ours_method": openai_stats["best_ours_method"],
            "best_ours_accuracy": openai_stats["best_ours_accuracy"],
            "best_external_method": openai_stats["best_external_method"],
            "best_external_accuracy": openai_stats["best_external_accuracy"],
            "ours_minus_external": openai_stats["ours_minus_external"],
            "positive_dataset_budget_majority": int(majority_positive),
            "safe_main_paper": int(label == "main paper claim"),
            "safe_appendix_only": int(label == "appendix-only claim"),
            "safe_supportive_only": int(label == "supportive-only claim"),
            "not_safe": int(label == "not safe"),
            "final_safety_label": label,
        }
    )
    write_csv(out_dir / "claim_safety_matrix.csv", claim_rows)

    # commands and docs
    main_next_cmd = (
        "python scripts/run_real_model_ours_vs_external_validation.py "
        "--timestamp 20260424T_OPENAI_REAL_MAIN "
        "--providers openai "
        "--datasets openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024 "
        "--subset-size 20 --seeds 11,23 --budgets 4,6,8 "
        "--methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,external_l1_exact,external_tale_prompt_budgeting,external_s1_budget_forcing,self_consistency_3 "
        "--resume"
    )
    commands.extend([
        "",
        "# Next larger OpenAI run (prepared)",
        main_next_cmd,
    ])
    (out_dir / "commands.sh").write_text("\n".join(commands) + "\n", encoding="utf-8")

    summary_lines = [
        "# Real-model ours-vs-external validation summary",
        "",
        "## Provider execution status",
    ]
    for provider in providers:
        st = provider_status.get(provider, {})
        summary_lines.append(
            f"- {provider}: attempted={st.get('attempted', False)} completed={st.get('completed', False)} partial={st.get('partial', False)} shards={st.get('shards_completed', 0)}/{st.get('shards_total', 0)} reason={st.get('reason', '')}"
        )

    summary_lines.extend(
        [
            "",
            "## Ours vs external headline (OpenAI)",
            f"- Did best ours beat best external overall? {'YES' if openai_stats['ours_minus_external'] > 0 else 'NO'}",
            f"- Best ours method: {openai_stats['best_ours_method'] or 'N/A'} ({openai_stats['best_ours_accuracy']:.4f})",
            f"- Best external method: {openai_stats['best_external_method'] or 'N/A'} ({openai_stats['best_external_accuracy']:.4f})",
            f"- Ours minus external gap: {openai_stats['ours_minus_external']:+.4f}",
            f"- Evaluated rows: {len(openai_rows)}",
            f"- API/runtime error rows: {len(openai_errors)}",
            f"- Claim safety status: {label}",
            "",
            "## Slice support (dataset-budget)",
        ]
    )
    if dataset_budget_gaps:
        for row in dataset_budget_gaps:
            summary_lines.append(f"- {row['dataset']} @ budget {row['budget']}: gap={float(row['ours_minus_external']):+.4f}")
    else:
        summary_lines.append("- No OpenAI dataset-budget slices available yet.")

    if openai_stats["best_ours_method"] and openai_stats["best_external_method"]:
        fo = failure_for_method(openai_rows, openai_stats["best_ours_method"])
        fe = failure_for_method(openai_rows, openai_stats["best_external_method"])
        summary_lines.extend(
            [
                "",
                "## Failure decomposition",
                f"- Best ours ({openai_stats['best_ours_method']}): absent_from_tree={fo['absent_from_tree']}, present_not_selected={fo['present_not_selected']}, output_layer_mismatch={fo['output_layer_mismatch']}",
                f"- Best external ({openai_stats['best_external_method']}): absent_from_tree={fe['absent_from_tree']}, present_not_selected={fe['present_not_selected']}, output_layer_mismatch={fe['output_layer_mismatch']}",
            ]
        )

    summary_lines.extend(
        [
            "",
            "## Conservative interpretation",
            "- Headline claim remains ours-family vs external baselines under a shared substrate.",
            "- Internal ordering among strict_f3/strict_gate1_cap_k6/strict_f2 is non-headline.",
            "- This smoke run is OpenAI-only and small; it cannot be main-paper-safe.",
            "",
            "## Next prepared run",
            f"- {main_next_cmd}",
        ]
    )
    (out_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    manifest = {
        "artifact_family": "real_model_ours_vs_external_validation",
        "timestamp": ts,
        "partial": any(bool(provider_status.get(p, {}).get("partial")) for p in providers),
        "provider_status": provider_status,
        "datasets_active": active_datasets,
        "methods_runnable": runnable_methods,
        "methods_unsupported": unsupported_methods,
        "files": [
            "manifest.json",
            "run_config.json",
            "commands.sh",
            "api_key_readiness.json",
            "openai/per_example_rows.csv",
            "openai/aggregate_summary.csv",
            "openai/per_dataset_summary.csv",
            "openai/per_budget_summary.csv",
            "openai/seed_summary.csv",
            "openai/failure_decomposition.csv",
            "openai/retry_error_log.csv",
            "combined_ours_vs_external_summary.csv",
            "combined_provider_summary.csv",
            "combined_budget_curve.csv",
            "combined_dataset_summary.csv",
            "combined_failure_decomposition.csv",
            "claim_safety_matrix.csv",
            "summary.md",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    doc_path = REPO_ROOT / f"docs/REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION_{ts}.md"
    doc_lines = [
        "# REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION",
        "",
        f"Timestamp: `{ts}`.",
        f"Artifact package: `outputs/real_model_ours_vs_external_validation_{ts}/`.",
        "",
        "## Contract used",
        f"- Providers requested: {providers}",
        f"- Datasets active: {active_datasets}",
        f"- Subset size: {args.subset_size}",
        f"- Seeds: {seeds}",
        f"- Budgets: {budgets}",
        f"- Methods requested: {methods_requested}",
        f"- Methods runnable: {runnable_methods}",
        f"- Unsupported in current canonical runner: {unsupported_methods}",
        "",
        "## Required headline answers",
        f"1. Did best ours beat best external overall? {'YES' if openai_stats['ours_minus_external'] > 0 else 'NO'}",
        f"2. Best ours method: {openai_stats['best_ours_method'] or 'N/A'} ({openai_stats['best_ours_accuracy']:.4f})",
        f"3. Best external method: {openai_stats['best_external_method'] or 'N/A'} ({openai_stats['best_external_accuracy']:.4f})",
        f"4. Ours-minus-external gap: {openai_stats['ours_minus_external']:+.4f}",
        "5. Dataset/budget slices: see `summary.md` and `combined_dataset_summary.csv` + `combined_budget_curve.csv`.",
        "6. Failure decomposition categories reported in `combined_failure_decomposition.csv`.",
        f"7. API/runtime errors: {len(openai_errors)} row(s) in `openai/retry_error_log.csv`.",
        f"8. Claim safety: {label}.",
        "",
        "## Guardrails",
        "- This run does not claim strict_f3 universally beats strict_gate1_cap_k6.",
        "- Headline remains best-ours family vs best external baseline adapters under shared substrate.",
        "- This is not an official reproduction of external papers.",
        "",
        "## Next larger run prepared",
        f"- `{main_next_cmd}`",
    ]
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
