from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
import random

from experiments.branching import SimulatedBranchGenerator
from experiments.data import PilotExample
from experiments.frontier_matrix_core import build_frontier_strategies

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _build_specs(seed: int, budget: int):
    rng = random.Random(seed)
    return build_frontier_strategies(
        lambda: SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12),
        budget,
        [0, 1, 2],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )


def test_tot_methods_registered_and_budget_guarded_and_deterministic() -> None:
    example = PilotExample(example_id="x", question="What is 2+3?", answer="5")
    for method in ["tot_bfs_matched_budget", "tot_beam_matched_budget", "tot_dfs_matched_budget"]:
        specs_a = _build_specs(seed=123, budget=6)
        specs_b = _build_specs(seed=123, budget=6)
        assert method in specs_a

        ra = specs_a[method].run(example.question, example.answer)
        rb = specs_b[method].run(example.question, example.answer)
        assert ra.actions_used <= 6
        assert rb.actions_used <= 6
        assert ra.actions_used == rb.actions_used
        assert ra.expansions == rb.expansions
        assert ra.prediction == rb.prediction


def test_tot_baseline_runner_outputs_and_text_guards() -> None:
    ts = "TESTTOTMB20260424T000000Z"
    out_dir = REPO_ROOT / "outputs" / f"tot_matched_budget_baseline_{ts}"
    cmd = [
        sys.executable,
        "scripts/run_tot_matched_budget_baseline.py",
        "--timestamp",
        ts,
        "--subset-size",
        "4",
        "--seeds",
        "11",
        "--budgets",
        "4,6",
        "--math-only",
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
        "failure_decomposition.csv",
        "token_latency_accounting.csv",
        "summary.md",
    ]
    for name in required:
        assert (out_dir / name).exists(), name

    methods = {r["method"] for r in _read_csv(out_dir / "main_summary.csv")}
    for needed in [
        "strict_f3_anti_collapse_weak_v1",
        "strict_f3",
        "strict_gate1_cap_k6",
        "tot_bfs_matched_budget",
        "tot_beam_matched_budget",
        "tot_dfs_matched_budget",
        "self_consistency_3",
        "self_consistency_5",
        "external_l1_max",
    ]:
        assert needed in methods

    pairwise = _read_csv(out_dir / "pairwise_statistical_tests.csv")
    assert len(pairwise) >= 7

    text = "\n".join(p.read_text(encoding="utf-8") for p in out_dir.glob("*") if p.is_file() and p.suffix in {".json", ".md", ".csv", ".tex"}).lower()
    assert "official tot reproduction" not in text
    assert "universal dominance" in text

    per_case = _read_csv(out_dir / "per_case_outcomes.csv")
    assert per_case
    assert all(int(r["actions"]) <= int(r["budget"]) for r in per_case)

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "tot_adapter_note" in manifest


def test_tot_paper_table_builder_outputs() -> None:
    cmd = [
        sys.executable,
        "scripts/paper/build_tot_matched_budget_baseline_table.py",
    ]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)

    assert (REPO_ROOT / "outputs/paper_tables/table_tot_matched_budget_baseline.csv").exists()
    assert (REPO_ROOT / "outputs/paper_tables/table_tot_matched_budget_baseline.tex").exists()
    assert (REPO_ROOT / "outputs/paper_plot_data/tot_matched_budget_baseline.csv").exists()
