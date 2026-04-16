from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from experiments.branch_scorer_v3 import SimBranch
from experiments.bruteforce_branch_labels import (
    BruteForceLabelConfig,
    FrontierState,
    evaluate_state_candidates,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _tiny_state() -> FrontierState:
    return FrontierState(
        state_id="state_tiny",
        example_id="mock_0",
        question="What is 2+2?",
        answer="4",
        source_episode_id=0,
        decision_index=0,
        remaining_budget=3,
        active_branches=[
            SimBranch(branch_id="b0", latent_quality=0.9, score=0.8),
            SimBranch(branch_id="b1", latent_quality=0.4, score=0.35),
        ],
    )


def test_label_schema_contains_required_fields() -> None:
    cfg = BruteForceLabelConfig(
        exact_mode=True,
        rollout_samples_per_candidate=4,
        max_exact_remaining_budget=4,
        max_exact_branches=3,
    )
    result = evaluate_state_candidates(_tiny_state(), cfg)
    assert "state_summary" in result
    assert "candidate_labels" in result
    assert "pairwise_labels" in result
    assert "raw_rollouts" in result
    c0 = result["candidate_labels"][0]
    required = {
        "branch_id",
        "estimated_value_if_allocate_next",
        "best_followup_allocation",
        "outside_option_value",
        "branch_vs_outside_gap",
    }
    assert required.issubset(set(c0.keys()))


def test_pairwise_label_prefers_higher_estimated_value() -> None:
    cfg = BruteForceLabelConfig(exact_mode=True, rollout_samples_per_candidate=6)
    result = evaluate_state_candidates(_tiny_state(), cfg)
    candidates = {row["branch_id"]: row for row in result["candidate_labels"]}
    pair = result["pairwise_labels"][0]
    i = pair["branch_i"]
    j = pair["branch_j"]
    margin = candidates[i]["estimated_value_if_allocate_next"] - candidates[j]["estimated_value_if_allocate_next"]
    if margin > 0:
        assert pair["preference"] == 1
    else:
        assert pair["preference"] == 0


def test_resume_safe_behavior() -> None:
    run_id = "pytest_resume"
    out_root = REPO_ROOT / "outputs" / "branch_label_bruteforce" / run_id
    if out_root.exists():
        for path in sorted(out_root.glob("*")):
            path.unlink()
        out_root.rmdir()

    cmd = [
        sys.executable,
        "scripts/run_bruteforce_branch_label_generator.py",
        "--run-id",
        run_id,
        "--max-frontier-states",
        "2",
        "--episodes-per-example",
        "1",
        "--rollout-samples-per-candidate",
        "2",
        "--max-allocation-samples",
        "4",
        "--frontier-budget",
        "4",
        "--min-remaining-budget",
        "2",
        "--max-remaining-budget",
        "3",
    ]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    summaries_path = out_root / "state_summaries.jsonl"
    before_rows = summaries_path.read_text(encoding="utf-8").strip().splitlines()
    subprocess.run(cmd + ["--resume"], cwd=REPO_ROOT, check=True)
    after_rows = summaries_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(before_rows) == len(after_rows)


def test_manifest_integrity_has_checksums_and_counts() -> None:
    run_id = "pytest_manifest"
    out_root = REPO_ROOT / "outputs" / "branch_label_bruteforce" / run_id
    if out_root.exists():
        for path in sorted(out_root.glob("*")):
            path.unlink()
        out_root.rmdir()

    cmd = [
        sys.executable,
        "scripts/run_bruteforce_branch_label_generator.py",
        "--run-id",
        run_id,
        "--max-frontier-states",
        "2",
        "--episodes-per-example",
        "1",
        "--rollout-samples-per-candidate",
        "2",
        "--max-allocation-samples",
        "4",
    ]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    manifest = json.loads((out_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["generator"] == "branch_label_bruteforce_v1"
    assert manifest["counts"]["states_completed"] >= 1
    checksums = manifest["checksums"]
    assert checksums["state_summaries_sha256"]
    assert checksums["candidate_labels_sha256"]
    assert checksums["pairwise_labels_sha256"]
    assert checksums["raw_rollouts_sha256"]
