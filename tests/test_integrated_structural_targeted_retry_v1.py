from __future__ import annotations

import csv
import json
import random
import subprocess
import sys
from pathlib import Path

from experiments.frontier_matrix_core import build_frontier_strategies
from experiments.targeted_discovery_retry import (
    TARGETED_RETRY_RECOMMENDED_PROMPT_VERSIONS_V1,
    build_targeted_discovery_retry_integration_config_v1,
)
from scripts.run_cohere_real_model_cost_normalized_validation import METHODS

REPO = Path(__file__).resolve().parents[1]
METHOD_ID = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_"
    "structural_commit_v1_targeted_retry_v1"
)


def test_method_registry_contains_integrated_method_id() -> None:
    assert METHOD_ID in METHODS
    assert METHODS[METHOD_ID]["runtime"] == METHOD_ID


def test_targeted_retry_config_uses_recommended_prompt_versions() -> None:
    cfg = build_targeted_discovery_retry_integration_config_v1(
        enable_targeted_discovery_retry_v1=True,
        targeted_retry_allowlist_case_ids={"openai_gsm8k_841"},
        targeted_retry_no_api_mode=True,
    )
    assert cfg.enable_targeted_discovery_retry_v1 is True
    assert cfg.targeted_retry_no_api_mode is True
    assert cfg.targeted_retry_prompt_versions == TARGETED_RETRY_RECOMMENDED_PROMPT_VERSIONS_V1
    assert "openai_gsm8k_841" in cfg.targeted_retry_allowlist_case_ids


def test_build_frontier_strategies_contains_integrated_runtime() -> None:
    rng = random.Random(0)

    def factory():
        return None

    specs = build_frontier_strategies(
        factory,
        budget=6,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )
    assert METHOD_ID in specs
    ctl = specs[METHOD_ID]
    assert getattr(ctl, "enable_structural_commitment_v1", False) is True


def test_integrated_replay_script_emits_outputs_without_api(tmp_path: Path) -> None:
    out_dir = tmp_path / "integrated"
    cmd = [
        sys.executable,
        str(REPO / "scripts/replay_integrated_structural_commit_and_targeted_retry_v1.py"),
        "--output-dir",
        str(out_dir),
    ]
    proc = subprocess.run(cmd, cwd=str(REPO), check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    required = [
        "integrated_replay_manifest.json",
        "integrated_replay_cases.csv",
        "integrated_replay_summary.json",
        "integrated_replay_report.md",
    ]
    for name in required:
        p = out_dir / name
        assert p.exists()
        assert p.stat().st_size > 0
    manifest = json.loads((out_dir / "integrated_replay_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((out_dir / "integrated_replay_summary.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((out_dir / "integrated_replay_cases.csv").open(encoding="utf-8")))
    assert manifest.get("no_api_calls") is True
    assert summary.get("no_api_calls") is True
    assert rows
    assert summary["estimated_unfixed_or_not_covered_total"] == (
        summary["total_known_loss_cases"] - summary["estimated_fixed_combined"]
    )
    allowed = {
        "fixed_estimated",
        "not_fixed_estimated",
        "untested_targeted_retry",
        "unknown_mechanism",
        "insufficient_provenance",
        "not_applicable",
        "unknown",
    }
    for r in rows:
        assert r["integrated_result"] in allowed

