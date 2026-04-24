from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path


REQUIRED = {
    "manifest.json",
    "per_case_results.csv",
    "summary_by_dataset_budget_method.csv",
    "summary_by_dataset_method.csv",
    "summary_by_method.csv",
    "pairwise_tests.csv",
    "winner_instability_by_dataset_budget.csv",
    "held_out_claim_safety_table.csv",
    "dataset_loading_status.csv",
    "STATUS.md",
}


def test_held_out_surface_generalization_claim_safety_dry_run(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    ts = "20990101T000000Z"

    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env.pop("COHERE_API_KEY", None)
    env.pop("GROQ_API_KEY", None)
    env.pop("GEMINI_API_KEY", None)
    env.pop("GOOGLE_API_KEY", None)

    cmd = [
        sys.executable,
        str(repo / "scripts" / "run_held_out_surface_generalization_claim_safety.py"),
        "--timestamp",
        ts,
        "--dry-run",
        "--subset-size",
        "2",
        "--seeds",
        "11",
        "--budgets",
        "4",
        "--datasets",
        "Idavidrein/gpqa",
    ]
    subprocess.run(cmd, check=True, cwd=repo, env=env)

    out_dir = repo / f"outputs/held_out_surface_generalization_claim_safety_{ts}"
    assert out_dir.is_dir()

    produced = {p.name for p in out_dir.iterdir() if p.is_file()}
    assert REQUIRED.issubset(produced)

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["api_requirements"]["openai"] is False
    assert manifest["api_requirements"]["cohere"] is False
    assert manifest["hf_token_present"] in {True, False}

    status_text = (out_dir / "STATUS.md").read_text(encoding="utf-8")
    assert "HF_TOKEN" in status_text
    assert "hf_" not in status_text.lower() or "present" in status_text.lower()


def test_missing_dataset_handled_gracefully(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    ts = "20990101T000001Z"
    cmd = [
        sys.executable,
        str(repo / "scripts" / "run_held_out_surface_generalization_claim_safety.py"),
        "--timestamp",
        ts,
        "--subset-size",
        "20",
        "--seeds",
        "11",
        "--budgets",
        "4",
        "--datasets",
        "definitely/not_a_dataset",
    ]
    subprocess.run(cmd, check=True, cwd=repo)
    out_dir = repo / f"outputs/held_out_surface_generalization_claim_safety_{ts}"
    rows = list(csv.DictReader((out_dir / "dataset_loading_status.csv").open("r", encoding="utf-8")))
    assert rows
    assert any(r.get("status") == "failed" for r in rows)
