#!/usr/bin/env python3
"""Smoke-verify runnability and mode boundaries for integrated external baselines.

This script intentionally runs tiny, deterministic checks for:
- s1 MODE A + MODE B
- TALE MODE A + MODE B
- L1 MODE A + MODE B

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
        "- scope: s1 / TALE / L1 mode-A and mode-B adapter paths",
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
