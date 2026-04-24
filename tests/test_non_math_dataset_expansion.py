from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.run_non_math_dataset_expansion import _load_gpqa_examples, _load_natural_plan_examples

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_gpqa_loader_is_deterministic() -> None:
    a = _load_gpqa_examples(subset_size=5, seed=11)
    b = _load_gpqa_examples(subset_size=5, seed=11)
    assert [x.question for x in a] == [x.question for x in b]
    assert [x.answer for x in a] == [x.answer for x in b]


@pytest.mark.skipif(
    not (REPO_ROOT / "datasets/natural-plan").exists(),
    reason="Natural Plan local git dataset clone unavailable in test environment.",
)
def test_natural_plan_loader_is_deterministic() -> None:
    a = _load_natural_plan_examples(subset_size=5, seed=11, task_name="trip_planning")
    b = _load_natural_plan_examples(subset_size=5, seed=11, task_name="trip_planning")
    assert [x.example_id for x in a] == [x.example_id for x in b]
    assert [x.question for x in a] == [x.question for x in b]
    assert [x.answer for x in a] == [x.answer for x in b]


def test_non_math_dataset_expansion_outputs_and_guards() -> None:
    ts = "TESTNMDSEXP20260424T000000Z"
    out_dir = REPO_ROOT / "outputs" / f"non_math_dataset_expansion_{ts}"

    cmd = [
        sys.executable,
        "scripts/run_non_math_dataset_expansion.py",
        "--timestamp",
        ts,
        "--subset-size",
        "6",
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
        "per_dataset_summary.csv",
        "per_budget_summary.csv",
        "per_seed_summary.csv",
        "pairwise_statistical_tests.csv",
        "summary.md",
    ]
    for name in required:
        assert (out_dir / name).exists(), name

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    datasets = set(manifest.get("datasets_ran", []))
    assert datasets
    assert ("google-deepmind/natural-plan" in datasets) or ("Idavidrein/gpqa" in datasets) or ("TIGER-Lab/MMLU-Pro" in datasets)

    methods = {r["method"] for r in _read_csv(out_dir / "main_summary.csv")}
    for needed in [
        "strict_f3",
        "strict_gate1_cap_k6",
        "strict_f3_anti_collapse_weak_v1",
        "external_l1_max",
        "external_s1_budget_forcing",
        "self_consistency_3",
    ]:
        assert needed in methods

    assert "self_consistency_5" in methods

    pairwise = _read_csv(out_dir / "pairwise_statistical_tests.csv")
    assert len(pairwise) >= 5

    summary_text = (out_dir / "summary.md").read_text(encoding="utf-8").lower()
    assert "universal dominance" in summary_text

    generated_text = []
    for path in out_dir.glob("*"):
        if path.is_file() and path.suffix in {".json", ".md", ".csv", ".tex"}:
            generated_text.append(path.read_text(encoding="utf-8"))
    combined_text = "\n".join(generated_text).lower()
    assert "hf_" not in combined_text
    for env_key in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACEHUB_API_TOKEN"):
        token = (os.getenv(env_key) or "").strip()
        if token:
            assert token.lower() not in combined_text


def test_table_builder_outputs() -> None:
    cmd = [sys.executable, "scripts/paper/build_non_math_dataset_expansion_table.py"]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)

    assert (REPO_ROOT / "outputs/paper_tables/table_non_math_dataset_expansion.csv").exists()
    assert (REPO_ROOT / "outputs/paper_tables/table_non_math_dataset_expansion.tex").exists()
    assert (REPO_ROOT / "outputs/paper_plot_data/non_math_dataset_expansion.csv").exists()
