#!/usr/bin/env python3
"""Smoke-verify runnability and mode boundaries for integrated external baselines.

This script intentionally runs tiny, deterministic checks for:
- s1 MODE A + MODE B
- TALE MODE A + MODE B
- L1 MODE A + MODE B
- BEST-Route adjacent import validator against a local fixture package
- when_solve_when_verify adjacent import validator against a local fixture package
- cascade_routing adjacent import validator against a local fixture package
- mob_majority_of_bests adjacent import validator against a local fixture package

Outputs:
- outputs/external_baseline_runnability/<run_id>/verification_summary.json
- outputs/external_baseline_runnability/<run_id>/verification_summary.csv
- outputs/external_baseline_runnability/<run_id>/verification_note.md
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "outputs" / "external_baseline_runnability"


BASELINE_CASES: list[dict[str, str]] = [
    {
        "baseline": "s1",
        "mode": "mode_a",
        "script": "scripts/run_s1_budget_forcing_baseline.py",
        "config": "configs/s1_budget_forcing_inference_only_v1.json",
        "expected_mode_b_status": "not_requested",
    },
    {
        "baseline": "s1",
        "mode": "mode_b",
        "script": "scripts/run_s1_budget_forcing_baseline.py",
        "config": "configs/s1_full_or_official_adapter_v1.json",
        "expected_mode_b_status": "blocked",
    },
    {
        "baseline": "tale",
        "mode": "mode_a",
        "script": "scripts/run_tale_baseline.py",
        "config": "configs/tale_prompt_budgeting_v1.json",
        "expected_mode_b_status": "not_requested",
    },
    {
        "baseline": "tale",
        "mode": "mode_b",
        "script": "scripts/run_tale_baseline.py",
        "config": "configs/tale_official_adapter_v1.json",
        "expected_mode_b_status": "blocked",
    },
    {
        "baseline": "l1",
        "mode": "mode_a",
        "script": "scripts/run_l1_baseline.py",
        "config": "configs/l1_inference_adapter_v1.json",
        "expected_mode_b_status": "not_requested",
    },
    {
        "baseline": "l1",
        "mode": "mode_b",
        "script": "scripts/run_l1_baseline.py",
        "config": "configs/l1_official_full_adapter_v1.json",
        "expected_mode_b_status": "blocked",
    },
]

BEST_ROUTE_FIXTURE_CASE = {
    "baseline": "best_route",
    "mode": "adjacent_import",
    "script": "scripts/verify_best_route_import.py",
    "results_path": "tests/fixtures/best_route_import_valid",
    "expected_status": "valid",
}


CASCADE_ROUTING_FIXTURE_CASE = {
    "baseline": "cascade_routing",
    "mode": "adjacent_import",
    "script": "scripts/verify_cascade_routing_import.py",
    "results_path": "tests/fixtures/cascade_routing_import_valid",
    "expected_status": "valid",
}


MOB_FIXTURE_CASE = {
    "baseline": "mob_majority_of_bests",
    "mode": "adjacent_import",
    "script": "scripts/verify_mob_import.py",
    "results_path": "tests/fixtures/mob_import_valid",
    "expected_status": "valid",
}

WHEN_SOLVE_WHEN_VERIFY_FIXTURE_CASE = {
    "baseline": "when_solve_when_verify",
    "mode": "adjacent_import",
    "script": "scripts/verify_when_solve_when_verify_import.py",
    "results_path": "tests/fixtures/when_solve_when_verify_import_valid",
    "expected_status": "valid",
}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                keys.append(k)
                seen.add(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = OUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []

    for idx, case in enumerate(BASELINE_CASES):
        cmd = [
            sys.executable,
            str(REPO_ROOT / case["script"]),
            "--config",
            case["config"],
            "--run-id",
            f"verify_{run_id}_{idx}_{case['baseline']}_{case['mode']}",
        ]
        proc = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)

        stdout_text = proc.stdout.strip()
        parsed: dict[str, Any] = {}
        if stdout_text:
            try:
                parsed = json.loads(stdout_text)
            except json.JSONDecodeError:
                parsed = {"raw_stdout": stdout_text}

        mode_b = parsed.get("mode_b", {}) if isinstance(parsed, dict) else {}
        observed_mode_b_status = str(mode_b.get("status", "unknown"))
        mode_b_matches = observed_mode_b_status == case["expected_mode_b_status"]

        results.append(
            {
                "baseline": case["baseline"],
                "mode": case["mode"],
                "script": case["script"],
                "config": case["config"],
                "return_code": int(proc.returncode),
                "runnable": proc.returncode == 0,
                "run_dir": parsed.get("run_dir", "") if isinstance(parsed, dict) else "",
                "observed_mode_b_status": observed_mode_b_status,
                "expected_mode_b_status": case["expected_mode_b_status"],
                "mode_b_status_matches_expectation": mode_b_matches,
                "mode_b_notes": str(mode_b.get("notes", "")),
                "stderr_tail": "\n".join(proc.stderr.strip().splitlines()[-6:]),
            }
        )

    best_route_cmd = [
        sys.executable,
        str(REPO_ROOT / BEST_ROUTE_FIXTURE_CASE["script"]),
        "--results-path",
        str(REPO_ROOT / BEST_ROUTE_FIXTURE_CASE["results_path"]),
        "--expected-dataset",
        "gsm8k",
        "--expected-split",
        "test",
        "--expected-budgets",
        "1,2",
    ]
    best_route_proc = subprocess.run(best_route_cmd, cwd=REPO_ROOT, text=True, capture_output=True)
    best_route_parsed: dict[str, Any] = {}
    if best_route_proc.stdout.strip():
        try:
            best_route_parsed = json.loads(best_route_proc.stdout.strip())
        except json.JSONDecodeError:
            best_route_parsed = {"raw_stdout": best_route_proc.stdout.strip()}

    best_route_status = str(best_route_parsed.get("status", "unknown"))
    results.append(
        {
            "baseline": BEST_ROUTE_FIXTURE_CASE["baseline"],
            "mode": BEST_ROUTE_FIXTURE_CASE["mode"],
            "script": BEST_ROUTE_FIXTURE_CASE["script"],
            "config": BEST_ROUTE_FIXTURE_CASE["results_path"],
            "return_code": int(best_route_proc.returncode),
            "runnable": best_route_proc.returncode == 0 and best_route_status == "valid",
            "run_dir": "",
            "observed_mode_b_status": best_route_status,
            "expected_mode_b_status": BEST_ROUTE_FIXTURE_CASE["expected_status"],
            "mode_b_status_matches_expectation": best_route_status == BEST_ROUTE_FIXTURE_CASE["expected_status"],
            "mode_b_notes": "BEST-Route adjacent import fixture validation",
            "stderr_tail": "\n".join(best_route_proc.stderr.strip().splitlines()[-6:]),
        }
    )

    wswv_cmd = [
        sys.executable,
        str(REPO_ROOT / WHEN_SOLVE_WHEN_VERIFY_FIXTURE_CASE["script"]),
        "--results-path",
        str(REPO_ROOT / WHEN_SOLVE_WHEN_VERIFY_FIXTURE_CASE["results_path"]),
        "--expected-dataset",
        "math128",
        "--expected-split",
        "test",
    ]
    wswv_proc = subprocess.run(wswv_cmd, cwd=REPO_ROOT, text=True, capture_output=True)
    wswv_parsed: dict[str, Any] = {}
    if wswv_proc.stdout.strip():
        try:
            wswv_parsed = json.loads(wswv_proc.stdout.strip())
        except json.JSONDecodeError:
            wswv_parsed = {"raw_stdout": wswv_proc.stdout.strip()}

    wswv_status = str(wswv_parsed.get("status", "unknown"))
    results.append(
        {
            "baseline": WHEN_SOLVE_WHEN_VERIFY_FIXTURE_CASE["baseline"],
            "mode": WHEN_SOLVE_WHEN_VERIFY_FIXTURE_CASE["mode"],
            "script": WHEN_SOLVE_WHEN_VERIFY_FIXTURE_CASE["script"],
            "config": WHEN_SOLVE_WHEN_VERIFY_FIXTURE_CASE["results_path"],
            "return_code": int(wswv_proc.returncode),
            "runnable": wswv_proc.returncode == 0 and wswv_status == "valid",
            "run_dir": "",
            "observed_mode_b_status": wswv_status,
            "expected_mode_b_status": WHEN_SOLVE_WHEN_VERIFY_FIXTURE_CASE["expected_status"],
            "mode_b_status_matches_expectation": wswv_status == WHEN_SOLVE_WHEN_VERIFY_FIXTURE_CASE["expected_status"],
            "mode_b_notes": "when_solve_when_verify adjacent import fixture validation",
            "stderr_tail": "\n".join(wswv_proc.stderr.strip().splitlines()[-6:]),
        }
    )

    cascade_cmd = [
        sys.executable,
        str(REPO_ROOT / CASCADE_ROUTING_FIXTURE_CASE["script"]),
        "--results-path",
        str(REPO_ROOT / CASCADE_ROUTING_FIXTURE_CASE["results_path"]),
        "--expected-dataset",
        "routerbench",
        "--expected-split",
        "test",
    ]
    cascade_proc = subprocess.run(cascade_cmd, cwd=REPO_ROOT, text=True, capture_output=True)
    cascade_parsed: dict[str, Any] = {}
    if cascade_proc.stdout.strip():
        try:
            cascade_parsed = json.loads(cascade_proc.stdout.strip())
        except json.JSONDecodeError:
            cascade_parsed = {"raw_stdout": cascade_proc.stdout.strip()}

    cascade_status = str(cascade_parsed.get("status", "unknown"))
    results.append(
        {
            "baseline": CASCADE_ROUTING_FIXTURE_CASE["baseline"],
            "mode": CASCADE_ROUTING_FIXTURE_CASE["mode"],
            "script": CASCADE_ROUTING_FIXTURE_CASE["script"],
            "config": CASCADE_ROUTING_FIXTURE_CASE["results_path"],
            "return_code": int(cascade_proc.returncode),
            "runnable": cascade_proc.returncode == 0 and cascade_status == "valid",
            "run_dir": "",
            "observed_mode_b_status": cascade_status,
            "expected_mode_b_status": CASCADE_ROUTING_FIXTURE_CASE["expected_status"],
            "mode_b_status_matches_expectation": cascade_status == CASCADE_ROUTING_FIXTURE_CASE["expected_status"],
            "mode_b_notes": "cascade_routing adjacent import fixture validation",
            "stderr_tail": "\n".join(cascade_proc.stderr.strip().splitlines()[-6:]),
        }
    )


    mob_cmd = [
        sys.executable,
        str(REPO_ROOT / MOB_FIXTURE_CASE["script"]),
        "--results-path",
        str(REPO_ROOT / MOB_FIXTURE_CASE["results_path"]),
        "--expected-benchmark",
        "gsm8k",
        "--expected-gen-model",
        "qwen2.5-3b-instruct",
        "--expected-reward-model",
        "grm3b",
        "--expected-num-samples",
        "128",
    ]
    mob_proc = subprocess.run(mob_cmd, cwd=REPO_ROOT, text=True, capture_output=True)
    mob_parsed: dict[str, Any] = {}
    if mob_proc.stdout.strip():
        try:
            mob_parsed = json.loads(mob_proc.stdout.strip())
        except json.JSONDecodeError:
            mob_parsed = {"raw_stdout": mob_proc.stdout.strip()}

    mob_status = str(mob_parsed.get("status", "unknown"))
    results.append(
        {
            "baseline": MOB_FIXTURE_CASE["baseline"],
            "mode": MOB_FIXTURE_CASE["mode"],
            "script": MOB_FIXTURE_CASE["script"],
            "config": MOB_FIXTURE_CASE["results_path"],
            "return_code": int(mob_proc.returncode),
            "runnable": mob_proc.returncode == 0 and mob_status == "valid",
            "run_dir": "",
            "observed_mode_b_status": mob_status,
            "expected_mode_b_status": MOB_FIXTURE_CASE["expected_status"],
            "mode_b_status_matches_expectation": mob_status == MOB_FIXTURE_CASE["expected_status"],
            "mode_b_notes": "mob_majority_of_bests adjacent import fixture validation",
            "stderr_tail": "\n".join(mob_proc.stderr.strip().splitlines()[-6:]),
        }
    )

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "policy": "Tiny smoke checks only; do not interpret as full benchmark reproduction.",
        "results": results,
    }

    (run_dir / "verification_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_csv(run_dir / "verification_summary.csv", results)

    lines = [
        "# External baseline runnability verification note",
        "",
        f"- run_id: `{run_id}`",
        "- scope: s1 / TALE / L1 mode-A and mode-B adapter paths + BEST-Route + when_solve_when_verify + cascade_routing + mob_majority_of_bests adjacent import validators",
        "- interpretation: smoke verification only (runnability + blocker-state consistency)",
        "",
        "| baseline | mode | runnable | mode_b_status | expected | matches |",
        "|---|---|---:|---|---|---:|",
    ]
    for row in results:
        lines.append(
            f"| {row['baseline']} | {row['mode']} | {row['runnable']} | {row['observed_mode_b_status']} | {row['expected_mode_b_status']} | {row['mode_b_status_matches_expectation']} |"
        )
    (run_dir / "verification_note.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "run_dir": str(run_dir)}, indent=2))


if __name__ == "__main__":
    main()
