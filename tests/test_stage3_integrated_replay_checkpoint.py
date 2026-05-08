from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/run_stage3_integrated_vs_external_replay_checkpoint.py"


def test_stage3_replay_dry_run_schema_and_flags(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness"
    readiness.mkdir(parents=True, exist_ok=True)
    case_file = readiness / "stage3_pilot_cases.csv"

    rows = [
        {
            "case_id": f"openai_gsm8k_{1000+i}",
            "problem_text": "Q",
            "gold_answer": "1",
            "pal_prediction": "1",
            "pal_correct": "1",
            "external_l1_prediction": "1",
            "external_l1_correct": "1",
            "tale_prediction": "1",
            "tale_correct": "1",
            "s1_prediction": "1",
            "s1_correct": "1",
            "best_external_prediction": "1",
            "best_external_correct": "1",
            "best_external_winner": "external_l1_max",
            "planned_integrated_action": "stage3_validated_fixes_method_eval",
            "expected_new_cohere_call": "1",
            "source_artifacts": "x.csv",
            "notes": "",
        }
        for i in range(50)
    ]
    with case_file.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

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
