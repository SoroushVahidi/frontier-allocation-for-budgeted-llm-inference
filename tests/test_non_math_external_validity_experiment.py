from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_non_math_external_validity_outputs_and_claim_safety() -> None:
    ts = "TESTNONMATH20260424T000000Z"
    out_dir = REPO_ROOT / "outputs" / f"non_math_external_validity_{ts}"
    if out_dir.exists():
        for p in sorted(out_dir.glob("**/*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()

    cmd = [
        sys.executable,
        "scripts/run_non_math_external_validity_experiment.py",
        "--timestamp",
        ts,
        "--dataset",
        "TIGER-Lab/MMLU-Pro",
        "--subset-size",
        "8",
        "--seeds",
        "11,23",
        "--budgets",
        "4,6",
    ]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)

    required = [
        "manifest.json",
        "per_case_outcomes.csv",
        "main_summary.csv",
        "per_budget_summary.csv",
        "per_dataset_summary.csv",
        "per_seed_summary.csv",
        "pairwise_statistical_tests.csv",
        "summary.md",
    ]
    for name in required:
        assert (out_dir / name).exists(), name

    per_dataset = _read_csv(out_dir / "per_dataset_summary.csv")
    assert any(r.get("dataset") == "TIGER-Lab/MMLU-Pro" for r in per_dataset)

    main_summary = _read_csv(out_dir / "main_summary.csv")
    methods = {r["method"] for r in main_summary}
    assert "self_consistency_3" in methods

    pairwise = _read_csv(out_dir / "pairwise_statistical_tests.csv")
    assert len(pairwise) >= 3

    summary = (out_dir / "summary.md").read_text(encoding="utf-8").lower()
    assert "universal dominance" in summary


def test_paper_builder_outputs_exist() -> None:
    cmd = [sys.executable, "scripts/paper/build_non_math_external_validity_table.py"]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)

    assert (REPO_ROOT / "outputs/paper_tables/table_non_math_external_validity.csv").exists()
    assert (REPO_ROOT / "outputs/paper_tables/table_non_math_external_validity.tex").exists()
    assert (REPO_ROOT / "outputs/paper_plot_data/non_math_external_validity.csv").exists()
    assert (REPO_ROOT / "outputs/paper_tables/table_real_model_quantitative_audit.csv").exists()
    assert (REPO_ROOT / "outputs/paper_tables/table_real_model_quantitative_audit.tex").exists()
