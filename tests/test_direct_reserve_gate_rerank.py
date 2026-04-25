from __future__ import annotations

import csv
import random
import shutil
import subprocess
from pathlib import Path

from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies


def _specs() -> dict[str, object]:
    return build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(211), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=8,
        adaptive_min_expand_grid=[1],
        rng=random.Random(223),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )


def test_method_registered_and_metadata_fields() -> None:
    specs = _specs()
    assert "strict_f3_direct_reserve_gate_rerank_v1" in specs
    res = specs["strict_f3_direct_reserve_gate_rerank_v1"].run("What is 12+13?", "25")
    meta = dict(res.metadata or {})
    assert meta.get("diagnostic_only") is True
    assert "branching_gate_decision" in meta
    assert "answer_group_support_counts" in meta
    assert "absent_from_tree" in meta
    assert "present_not_selected" in meta


def test_runner_offline_outputs_required_fields(tmp_path: Path) -> None:
    src = tmp_path / "per_example_rows.csv"
    src.write_text(
        "provider,dataset,seed,budget,example_id,method,is_correct,absent_from_tree,present_not_selected\n"
        "cohere,openai/gsm8k,11,4,e1,strict_f3,0,1,0\n"
        "cohere,openai/gsm8k,11,4,e1,external_l1_max,1,0,0\n"
        "cohere,openai/gsm8k,11,4,e1,strict_gate1_cap_k6,0,1,0\n",
        encoding="utf-8",
    )
    ts = "20260425T_DIRECT_RESERVE_GATE_RERANK_TEST_DRY"
    out = Path("outputs") / f"direct_reserve_gate_rerank_eval_{ts}"
    if out.exists():
        shutil.rmtree(out)
    subprocess.run(
        [
            "python",
            "scripts/run_direct_reserve_gate_rerank_eval.py",
            "--timestamp",
            ts,
            "--input-per-example",
            str(src),
            "--budgets",
            "4",
            "--seeds",
            "11",
        ],
        check=True,
    )

    assert (out / "summary.csv").exists()
    assert (out / "paired_deltas.csv").exists()
    assert (out / "per_example_rows.csv").exists()
    with (out / "per_example_rows.csv").open("r", encoding="utf-8", newline="") as f:
        hdr = list(csv.DictReader(f).fieldnames or [])
    assert "method" in hdr
    assert "absent_from_tree" in hdr
    assert "present_not_selected" in hdr
