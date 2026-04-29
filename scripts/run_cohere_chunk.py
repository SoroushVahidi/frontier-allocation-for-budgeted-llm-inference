#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path


def _sorted_unique(rows: list[dict[str, str]], key: str) -> str:
    vals = sorted({str(r[key]) for r in rows}, key=lambda x: (float(x) if x.isdigit() else x))
    return ",".join(vals)


def _build_base_cmd(a: argparse.Namespace, row: dict[str, str]) -> list[str]:
    return [
        sys.executable,
        a.runner_script,
        "--timestamp",
        a.timestamp,
        "--providers",
        a.providers,
        "--cohere-model",
        a.cohere_model,
        "--datasets",
        row["dataset"],
        "--budgets",
        row["budget"],
        "--seeds",
        row["seed"],
        "--methods",
        row["method"],
        "--target-scored-per-slice",
        row["target_scored_per_slice"],
        "--max-examples",
        row["target_scored_per_slice"],
        "--resume",
        "--emit-trace-audit",
        "--output-root",
        a.output_root,
    ]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--chunk-id", type=int, required=True)
    p.add_argument("--chunk-plan", required=True)
    p.add_argument("--timestamp", required=True)
    p.add_argument("--max-walltime-minutes", type=int, default=20)
    p.add_argument("--providers", default="cohere")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--output-root", default="outputs")
    p.add_argument("--runner-script", default="scripts/run_cohere_real_model_cost_normalized_validation.py")
    p.add_argument("--dry-run", action="store_true", help="Print resolved execution command(s) and exit.")
    a = p.parse_args()

    with Path(a.chunk_plan).open(encoding="utf-8") as f:
        plan_rows = list(csv.DictReader(f))
    row = next((r for r in plan_rows if int(r["chunk_id"]) == a.chunk_id), None)
    if not row:
        raise SystemExit(f"chunk_id {a.chunk_id} not found in {a.chunk_plan}")

    run_cmd = _build_base_cmd(a, row)
    all_datasets = _sorted_unique(plan_rows, "dataset")
    all_budgets = _sorted_unique(plan_rows, "budget")
    all_seeds = _sorted_unique(plan_rows, "seed")
    all_methods = _sorted_unique(plan_rows, "method")
    summarize_cmd = [
        sys.executable,
        a.runner_script,
        "--timestamp",
        a.timestamp,
        "--providers",
        a.providers,
        "--cohere-model",
        a.cohere_model,
        "--datasets",
        all_datasets,
        "--budgets",
        all_budgets,
        "--seeds",
        all_seeds,
        "--methods",
        all_methods,
        "--target-scored-per-slice",
        row["target_scored_per_slice"],
        "--summarize-only",
        "--output-root",
        a.output_root,
    ]

    print("run_command:", " ".join(run_cmd))
    print("summarize_command:", " ".join(summarize_cmd))
    if a.dry_run:
        return 0

    t0 = time.time()
    proc = subprocess.run(run_cmd, timeout=max(60, a.max_walltime_minutes * 60), check=False)
    if proc.returncode != 0:
        print(f"exit_code={proc.returncode} elapsed_sec={time.time() - t0:.1f}")
        return proc.returncode

    sum_proc = subprocess.run(summarize_cmd, timeout=600, check=False)
    rc = sum_proc.returncode
    print(f"exit_code={rc} elapsed_sec={time.time() - t0:.1f}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
