from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode


STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)


def _write_planned(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "case_idx",
                "example_id",
                "dataset",
                "question",
                "gold_answer_raw",
                "gold_answer",
                "seed",
                "budget",
                "stratum",
            ],
        )
        w.writeheader()
        w.writerow(
            {
                "case_idx": 1,
                "example_id": "e1",
                "dataset": "openai/gsm8k",
                "question": "What is 2+2?",
                "gold_answer_raw": "4",
                "gold_answer": "4",
                "seed": 11,
                "budget": 4,
                "stratum": "absent_from_tree",
            }
        )


def test_methods_registered_and_strict_f3_unchanged() -> None:
    factory = generator_factory_for_mode(
        use_openai_api=False,
        rng=None,
        openai_model="mock",
        temperature=0.2,
        max_output_tokens=256,
        timeout_seconds=30,
    )
    specs = build_frontier_strategies(
        factory,
        budget=4,
        adaptive_min_expand_grid=[1],
        rng=None,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    assert "direct_reserve_strong_v1" in specs
    assert "direct_reserve_strong_plus_diverse_v1" in specs
    assert STRICT_F3_RUNTIME in specs
    assert getattr(specs[STRICT_F3_RUNTIME], "method_name", "") == STRICT_F3_RUNTIME


def test_dry_run_outputs_and_no_real_api_without_flag(tmp_path: Path) -> None:
    planned = tmp_path / "planned_cases.csv"
    _write_planned(planned)
    ts = "TEST_COHERE_COVERAGE_DRY"
    out = Path("outputs") / f"cohere_coverage_generation_ablation_{ts}"
    if out.exists():
        for p in sorted(out.glob("**/*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()

    cmd = [
        sys.executable,
        "scripts/run_cohere_coverage_generation_ablation.py",
        "--timestamp",
        ts,
        "--planned-cases",
        str(planned),
        "--max-cases",
        "1",
    ]
    env = dict(os.environ)
    env.pop("COHERE_API_KEY", None)
    subprocess.run(cmd, check=True, env=env)

    required = [
        "manifest.json",
        "per_case_candidates.csv",
        "answer_group_summary.csv",
        "coverage_summary.csv",
        "per_method_summary.csv",
        "per_stratum_summary.csv",
        "gold_present_cases.csv",
        "gold_absent_cases.csv",
        "README.md",
    ]
    for name in required:
        assert (out / name).exists(), name
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["real_api_enabled"] is False


def test_real_api_refused_when_key_missing(tmp_path: Path) -> None:
    planned = tmp_path / "planned_cases.csv"
    _write_planned(planned)
    cmd = [
        sys.executable,
        "scripts/run_cohere_coverage_generation_ablation.py",
        "--timestamp",
        "TEST_COHERE_COVERAGE_NO_KEY",
        "--planned-cases",
        str(planned),
        "--max-cases",
        "1",
        "--run-real-api",
    ]
    env = dict(os.environ)
    env.pop("COHERE_API_KEY", None)
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "COHERE_API_KEY missing" in (proc.stderr + proc.stdout)
