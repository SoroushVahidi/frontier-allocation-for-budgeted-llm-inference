from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_local_runner_simulated_no_api_schema_and_plan() -> None:
    out = REPO / "outputs" / "main_table_baselines_live_sanity_local_cases_test"
    if out.exists():
        for p in sorted(out.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()

    cmd = [
        sys.executable,
        "scripts/run_main_table_baselines_live_sanity_local_cases.py",
        "--simulate-no-api",
        "--output-dir",
        str(out),
    ]
    subprocess.run(cmd, cwd=REPO, check=True, capture_output=True, text=True)

    call_plan = list(csv.DictReader((out / "call_plan.csv").open(encoding="utf-8")))
    assert len(call_plan) == 12  # 2 cases x 6 methods
    assert sum(int(r["planned_logical_calls"]) for r in call_plan) <= 20

    records_path = out / "per_example_records.jsonl"
    assert records_path.exists() and records_path.stat().st_size > 0
    rows = [json.loads(x) for x in records_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 12
    for r in rows:
        assert "method" in r
        assert "status" in r
        assert "logical_calls" in r
        assert r["status"] in {"success", "method_execution_error", "parsing_failure"}

    summary = json.loads((out / "sanity_summary.json").read_text(encoding="utf-8"))
    assert summary["case_count"] == 2
    assert summary["planned_logical_calls"] <= 20
    assert summary["simulate_no_api"] is True


def test_s1_observability_fields_helper() -> None:
    from scripts.run_main_table_core4_baselines_10case_two_slices import build_s1_observability

    md = {
        "forced_continue_count": 1,
        "stop_boundary_detected_count": 1,
        "final_answer_tokens_estimate": 0,
        "raw_last_response_text": "Working...",
    }
    obs = build_s1_observability("external_s1_budget_forcing_faithful_v1", md, parsed_answer="")
    assert obs["forced_continue_count"] == 1
    assert obs["stop_boundary_detected_count"] == 1
    assert obs["final_answer_tokens_estimate"] == 0
    assert obs["raw_last_response_text"] == "Working..."
    assert obs["s1_no_final_answer_detected"] is True
