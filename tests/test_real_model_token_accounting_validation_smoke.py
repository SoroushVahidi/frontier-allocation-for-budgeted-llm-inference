from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def test_real_model_token_accounting_validation_cohere_dry_run(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ts = "20260424T130000Z_COHERE_DRY"
    cmd = [
        sys.executable,
        str(repo_root / "scripts/run_real_model_token_accounting_validation.py"),
        "--timestamp",
        ts,
        "--provider",
        "cohere",
        "--dry-run",
        "--datasets",
        "openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024",
        "--seeds",
        "11",
        "--budgets",
        "4,6,8",
        "--subset-size",
        "1",
        "--output-root",
        str(tmp_path),
        "--skip-doc-write",
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)

    run_dir = tmp_path / f"real_model_token_accounting_validation_{ts}"
    assert run_dir.exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "per_case_results.csv").exists()
    assert (run_dir / "summary_by_method_budget.csv").exists()
    assert (run_dir / "summary_by_method.csv").exists()
    assert (run_dir / "STATUS.md").exists()

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["providers"] == ["cohere"]
    assert manifest["provider_status"][0]["mode"] == "dry_run"


def test_cross_provider_dry_run_writes_combined_outputs(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ts = "20260424T130000Z_CROSS_DRY"
    cmd = [
        sys.executable,
        str(repo_root / "scripts/run_real_model_token_accounting_validation.py"),
        "--timestamp",
        ts,
        "--providers",
        "openai,cohere",
        "--dry-run",
        "--datasets",
        "openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024",
        "--seeds",
        "11",
        "--budgets",
        "4",
        "--subset-size",
        "1",
        "--output-root",
        str(tmp_path),
        "--skip-doc-write",
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)

    run_dir = tmp_path / f"cross_provider_real_model_token_accounting_validation_{ts}"
    assert run_dir.exists()

    required = [
        "manifest.json",
        "per_case_results.csv",
        "summary_by_provider_method_budget.csv",
        "summary_by_provider_method.csv",
        "STATUS.md",
    ]
    for rel in required:
        assert (run_dir / rel).exists(), rel

    with (run_dir / "per_case_results.csv").open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert {r["provider"] for r in rows} == {"openai", "cohere"}
