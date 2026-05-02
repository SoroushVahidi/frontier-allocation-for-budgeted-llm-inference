#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

INTERNAL_METHODS = ["strict_f3", "strict_gate1_cap_k6", "strict_f2"]
EXTERNAL_METHODS = ["external_l1_max", "tale", "s1"]
ALL_METHODS = INTERNAL_METHODS + EXTERNAL_METHODS


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run controlled 100-case main3 external vs best3 internal experiment.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--budget", type=int, default=6)
    p.add_argument("--seed", type=int, default=20260501)
    p.add_argument("--target-cases", type=int, default=100)
    p.add_argument("--max-examples", type=int, default=100)
    p.add_argument("--cohere-model", default="command-a-03-2025")
    p.add_argument("--output-root", default="outputs")
    p.add_argument("--skip-runner", action="store_true")
    p.add_argument("--runner-timestamp", default="")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    experiment_dir = REPO_ROOT / args.output_root / f"main3_external_vs_best3_internal_100case_{args.timestamp}"
    experiment_dir.mkdir(parents=True, exist_ok=True)

    runner_timestamp = args.runner_timestamp or args.timestamp
    runner_output_dir = REPO_ROOT / args.output_root / f"cohere_real_model_cost_normalized_validation_{runner_timestamp}"

    methods_csv = ",".join(ALL_METHODS)
    if not args.skip_runner:
        cmd = [
            sys.executable,
            "scripts/run_cohere_real_model_cost_normalized_validation.py",
            "--timestamp",
            runner_timestamp,
            "--providers",
            "cohere",
            "--cohere-model",
            args.cohere_model,
            "--datasets",
            "openai/gsm8k",
            "--budgets",
            str(args.budget),
            "--seeds",
            str(args.seed),
            "--methods",
            methods_csv,
            "--target-scored-per-slice",
            str(args.target_cases),
            "--max-examples",
            str(args.max_examples),
            "--resume",
        ]
        (experiment_dir / "command.sh").write_text(" ".join(cmd) + "\n", encoding="utf-8")
        run = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
        if run.returncode != 0:
            _write_json(
                experiment_dir / "summary.json",
                {
                    "status": "runner_failed",
                    "runner_exit_code": run.returncode,
                    "runner_output_dir": str(runner_output_dir.relative_to(REPO_ROOT)),
                },
            )
            return run.returncode

    records = _read_jsonl(runner_output_dir / "per_example_records.jsonl")
    filtered = [
        r
        for r in records
        if str(r.get("provider")) == "cohere"
        and str(r.get("dataset")) == "openai/gsm8k"
        and int(r.get("seed", -1)) == args.seed
        and int(r.get("budget", -1)) == args.budget
        and str(r.get("method")) in ALL_METHODS
    ]

    per_case = []
    grouped: dict[str, list[dict[str, Any]]] = {m: [] for m in ALL_METHODS}
    for r in filtered:
        grouped[str(r["method"])].append(r)
        per_case.append(
            {
                "case_id": str(r.get("example_id", "")),
                "dataset": str(r.get("dataset", "")),
                "seed": int(r.get("seed", 0)),
                "budget": int(r.get("budget", 0)),
                "method": str(r.get("method", "")),
                "status": str(r.get("status", "")),
                "exact_match": int(r.get("exact_match", 0)),
                "failure_tag": str(r.get("failure_tag", "")),
            }
        )

    method_rows = []
    for method in ALL_METHODS:
        rows = grouped[method]
        scored = [x for x in rows if str(x.get("status")) == "scored"]
        failed = [x for x in rows if str(x.get("status")) != "scored"]
        method_rows.append(
            {
                "method": method,
                "family": "internal" if method in INTERNAL_METHODS else "external",
                "n_total_rows": len(rows),
                "n_scored": len(scored),
                "n_failed_or_skipped": len(failed),
                "accuracy": _mean([float(x.get("exact_match", 0)) for x in scored]),
                "mean_total_tokens_per_scored_example": _mean([float(x.get("total_tokens", 0)) for x in scored]),
                "mean_latency_seconds_per_scored_example": _mean([float(x.get("latency_seconds", 0.0)) for x in scored]),
            }
        )

    comparison_rows = sorted(method_rows, key=lambda x: (-float(x["accuracy"]), x["method"]))
    for idx, row in enumerate(comparison_rows, start=1):
        row["rank_by_accuracy"] = idx

    best_internal = max((r for r in method_rows if r["family"] == "internal"), key=lambda x: float(x["accuracy"]), default=None)
    best_external = max((r for r in method_rows if r["family"] == "external"), key=lambda x: float(x["accuracy"]), default=None)

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok",
        "experiment_output_dir": str(experiment_dir.relative_to(REPO_ROOT)),
        "runner_output_dir": str(runner_output_dir.relative_to(REPO_ROOT)),
        "dataset": "openai/gsm8k",
        "seed": args.seed,
        "budget": args.budget,
        "target_cases_per_method": args.target_cases,
        "methods_internal": INTERNAL_METHODS,
        "methods_external": EXTERNAL_METHODS,
        "best_internal_method": None if not best_internal else best_internal["method"],
        "best_internal_accuracy": None if not best_internal else best_internal["accuracy"],
        "best_external_method": None if not best_external else best_external["method"],
        "best_external_accuracy": None if not best_external else best_external["accuracy"],
        "best_internal_minus_best_external": None
        if not (best_internal and best_external)
        else float(best_internal["accuracy"]) - float(best_external["accuracy"]),
    }

    manifest = {
        "experiment_name": "main3_external_vs_best3_internal_100case",
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit_sha": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=False, capture_output=True, text=True
        ).stdout.strip(),
        "methods": {"internal": INTERNAL_METHODS, "external": EXTERNAL_METHODS},
        "selection_reasoning": {
            "external": "From repository readiness matrix/docs: l1, TALE, s1 are canonical main-table-ready external baselines.",
            "internal": "From paper-facing method contract/docs: strict_f3, strict_gate1_cap_k6, strict_f2 are the most canonical best-supported internal methods.",
        },
        "dataset_slice": {
            "dataset": "openai/gsm8k",
            "split": "test",
            "seed": args.seed,
            "cases_per_method_target": args.target_cases,
            "matched_budget": args.budget,
        },
        "provider": "cohere",
        "model": args.cohere_model,
        "runner": {
            "script": "scripts/run_cohere_real_model_cost_normalized_validation.py",
            "timestamp": runner_timestamp,
            "output_dir": str(runner_output_dir.relative_to(REPO_ROOT)),
            "skip_runner": bool(args.skip_runner),
        },
        "commands": {
            "run": (experiment_dir / "command.sh").read_text(encoding="utf-8").strip() if (experiment_dir / "command.sh").exists() else "",
        },
        "oracle_guardrail": "No gold/oracle features are used for method decision logic; gold is evaluation-only in the canonical runner.",
    }

    _write_json(experiment_dir / "manifest.json", manifest)
    _write_json(experiment_dir / "summary.json", summary)
    _write_csv(experiment_dir / "summary.csv", [summary], fieldnames=list(summary.keys()))
    _write_jsonl(experiment_dir / "per_case_results.jsonl", per_case)
    _write_csv(experiment_dir / "method_level_metrics.csv", method_rows, fieldnames=list(method_rows[0].keys()) if method_rows else ["method"])
    _write_csv(experiment_dir / "comparison_table.csv", comparison_rows, fieldnames=list(comparison_rows[0].keys()) if comparison_rows else ["method"])

    report_lines = [
        "# Main3 External vs Best3 Internal (100-case) Report",
        "",
        f"- Output directory: `{experiment_dir.relative_to(REPO_ROOT)}`",
        f"- Runner output directory: `{runner_output_dir.relative_to(REPO_ROOT)}`",
        "- External baselines: `external_l1_max`, `tale`, `s1`",
        "- Internal methods: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`",
        "- Dataset/slice: `openai/gsm8k` test, fixed seed and matched budget.",
        "- This artifact is diagnostic/supporting evidence; interpret with repository claim-safety docs.",
        "",
        "## How to interpret",
        "- `method_level_metrics.csv` provides per-method scored counts, failures, and accuracy.",
        "- `comparison_table.csv` ranks all six methods by accuracy on the matched run settings.",
        "- `per_case_results.jsonl` preserves case-level status and outcomes.",
    ]
    (experiment_dir / "comparison_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    (experiment_dir / "README.md").write_text(
        "\n".join(
            [
                "# Run README",
                "",
                "This directory contains a controlled 100-case comparison of canonical external and internal methods using existing repo infrastructure.",
                "Methods were selected from canonical docs/configs; no new algorithm logic was introduced.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(str(experiment_dir.relative_to(REPO_ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
