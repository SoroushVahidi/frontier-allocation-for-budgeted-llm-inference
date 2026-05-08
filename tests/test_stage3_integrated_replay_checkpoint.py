from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/run_stage3_integrated_vs_external_replay_checkpoint.py"


def _make_cases(path: Path) -> None:
    rows = [
        {
            "case_id": f"openai_gsm8k_{1000+i}",
            "problem_text": "Compute final value from a short story with two equations.",
            "gold_answer": str(100 + i),
            "pal_prediction": "0",
            "pal_correct": "0",
            "external_l1_prediction": str(200 + i),
            "external_l1_correct": "1",
            "tale_prediction": str(300 + i),
            "tale_correct": "1",
            "s1_prediction": str(400 + i),
            "s1_correct": "1",
            "best_external_prediction": str(500 + i),
            "best_external_correct": "1",
            "best_external_winner": "external_l1_max",
            "planned_integrated_action": "stage3_pilot_integrated_action",
            "expected_new_cohere_call": "1",
            "source_artifacts": "x.csv",
            "notes": "",
        }
        for i in range(50)
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def test_stage3_replay_dry_run_schema_and_flags(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness"
    readiness.mkdir(parents=True, exist_ok=True)
    case_file = readiness / "stage3_pilot_cases.csv"
    _make_cases(case_file)

    out = tmp_path / "out"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--readiness-dir",
            str(readiness),
            "--case-file",
            str(case_file),
            "--stage-name",
            "stage3_pilot",
            "--max-new-cohere-calls",
            "50",
            "--reuse-external-outputs",
            "--dry-run-only",
            "--method-name",
            "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1_validated_fixes",
            "--output-dir",
            str(out),
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    required = [
        "stage3_checkpoint_manifest.json",
        "selected_stage3_cases.csv",
        "preflight_status.json",
        "stage3_call_plan.csv",
        "stage3_dry_run_report.md",
        "stage3_live_schema.md",
    ]
    for name in required:
        p = out / name
        assert p.exists()
        assert p.stat().st_size > 0

    manifest = json.loads((out / "stage3_checkpoint_manifest.json").read_text(encoding="utf-8"))
    preflight = json.loads((out / "preflight_status.json").read_text(encoding="utf-8"))
    selected = list(csv.DictReader((out / "selected_stage3_cases.csv").open(encoding="utf-8")))
    call_plan = list(csv.DictReader((out / "stage3_call_plan.csv").open(encoding="utf-8")))

    assert manifest["no_api_calls"] is True
    assert "live_execution_supported" in manifest
    assert manifest["method_name"].endswith("validated_fixes")
    assert len(selected) == 50
    assert len(call_plan) == 50
    assert preflight["planned_calls_ok"] is True
    assert preflight["external_outputs_complete"] is True
    assert {"external_l1_prediction", "tale_prediction", "s1_prediction", "best_external_prediction"}.issubset(
        selected[0].keys()
    )
    assert selected[0]["no_gold_leakage"] == "1"
    assert selected[0]["no_external_prediction_leakage"] == "1"
    prompt_text = (out / selected[0]["prompt_path"]).read_text(encoding="utf-8")
    assert selected[0]["gold_answer"] not in prompt_text
    assert selected[0]["external_l1_prediction"] not in prompt_text


def test_stage3_live_preflight_blocks_api_without_execute_live(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness"
    readiness.mkdir(parents=True, exist_ok=True)
    case_file = readiness / "stage3_pilot_cases.csv"
    _make_cases(case_file)

    out = tmp_path / "out_live_preflight"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--readiness-dir",
            str(readiness),
            "--case-file",
            str(case_file),
            "--stage-name",
            "stage3_pilot",
            "--max-new-cohere-calls",
            "50",
            "--reuse-external-outputs",
            "--output-dir",
            str(out),
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )
    required = [
        "stage3_checkpoint_manifest.json",
        "selected_stage3_cases.csv",
        "preflight_status.json",
        "stage3_call_plan.csv",
        "stage3_live_schema.md",
        "stage3_preflight_report.md",
    ]
    for name in required:
        p = out / name
        assert p.exists()
        assert p.stat().st_size > 0
    assert not (out / "stage3_live_results.csv").exists()
    manifest = json.loads((out / "stage3_checkpoint_manifest.json").read_text(encoding="utf-8"))
    preflight = json.loads((out / "preflight_status.json").read_text(encoding="utf-8"))
    selected = list(csv.DictReader((out / "selected_stage3_cases.csv").open(encoding="utf-8")))
    plan = list(csv.DictReader((out / "stage3_call_plan.csv").open(encoding="utf-8")))
    assert manifest["no_api_calls"] is True
    assert manifest["live_execution_supported"] is True
    assert manifest["execute_live"] is False
    assert manifest["would_call_cohere"] is True
    assert manifest["planned_new_cohere_calls"] == 50
    assert len(selected) == 50
    assert len(plan) == 50
    assert preflight["planned_calls_ok"] is True
    assert preflight["external_outputs_complete"] is True
