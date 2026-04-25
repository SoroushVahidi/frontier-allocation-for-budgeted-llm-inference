from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tot_matched_budget_baseline_fixture"
DOC = REPO_ROOT / "docs" / "TOT_MATCHED_BUDGET_BASELINE_REPORT.md"


def test_fixture_paper_builder_writes_table(tmp_path: Path) -> None:
    out_csv = tmp_path / "table.csv"
    out_tex = tmp_path / "table.tex"
    plot_csv = tmp_path / "plot.csv"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "paper" / "build_tot_matched_budget_baseline_table.py"),
        "--input-dir",
        str(FIXTURE),
        "--output-csv",
        str(out_csv),
        "--output-tex",
        str(out_tex),
        "--output-plot-csv",
        str(plot_csv),
    ]
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True, capture_output=True, text=True)
    text = out_csv.read_text(encoding="utf-8")
    assert "strict_f3_anti_collapse_weak_v1" in text
    assert "tot_beam_matched_budget" in text
    assert "tot_bfs_matched_budget" in text
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert rows, "expected non-empty paper table"


def test_report_and_table_avoid_forbidden_universal_dominance_claims() -> None:
    blob = DOC.read_text(encoding="utf-8").lower()
    forbidden = [
        "official tree of thoughts",
        "universally dominates",
        "tot is solved",
    ]
    for phrase in forbidden:
        assert phrase not in blob, f"unexpected phrase in report: {phrase!r}"


def test_tot_adapters_respect_action_budget() -> None:
    import random

    from experiments.branching import SimulatedBranchGenerator
    from experiments.scoring import ScoreConfig, SimpleBranchScorer
    from experiments.tot_matched_budget_adapters import (
        TotBeamMatchedBudgetController,
        TotBfsMatchedBudgetController,
        TotDfsMatchedBudgetController,
    )

    scorer = SimpleBranchScorer(ScoreConfig())
    for budget in (4, 6, 8):
        for cls in (TotBfsMatchedBudgetController, TotDfsMatchedBudgetController, TotBeamMatchedBudgetController):
            gen = SimulatedBranchGenerator(rng=random.Random(42), max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
            ctrl = cls(gen, scorer, budget)
            res = ctrl.run("What is 2+2?", "4")
            assert res.actions_used <= budget, (cls.__name__, budget, res.actions_used)


def test_bundled_paper_table_contains_frontier_and_tot_rows() -> None:
    path = REPO_ROOT / "outputs" / "paper_tables" / "table_tot_matched_budget_baseline.csv"
    if not path.exists():
        pytest.skip("paper table not generated in this checkout")
    txt = path.read_text(encoding="utf-8")
    assert "strict_f3_anti_collapse_weak_v1" in txt
    assert "tot_beam_matched_budget" in txt
    assert "tot_dfs_matched_budget" in txt
