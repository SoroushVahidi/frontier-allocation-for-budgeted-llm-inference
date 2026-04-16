from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import run_oracle_label_generator_heavy as heavy


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def test_deterministic_state_id_and_resume_skip(monkeypatch, tmp_path: Path) -> None:
    # Tiny synthetic contract-compatible inputs.
    pilot_config = tmp_path / "pilot_config.json"
    selection_config = tmp_path / "selection_config.json"
    state_manifest = tmp_path / "pilot_state_manifest.jsonl"
    out_dir = tmp_path / "out"

    _write_json(
        pilot_config,
        {
            "pilot_name": "unit-test",
            "teacher": {
                "teacher_mode": "offline_policy_coupled_oracle_rollout",
                "horizon": 2,
                "rollout_depth": 2,
                "paired_rollouts_per_state": 2,
            },
        },
    )
    _write_json(
        selection_config,
        {
            "source_pipeline": {
                "n_init_branches": 2,
                "max_depth": 3,
                "finish_prob_base": 0.16,
                "answer_noise": 0.12,
            },
            "candidate_generation": {"episodes_per_seed_budget": 1},
        },
    )

    rows = [
        {
            "state_id": "s7_b3_e0_d0_b_0",
            "source_seed": 7,
            "budget": 3,
            "episode_id": 0,
            "decision_id": 0,
            "current_branch_id": "b_0",
            "remaining_budget": 3,
        },
        {
            "state_id": "s7_b3_e0_d0_b_1",
            "source_seed": 7,
            "budget": 3,
            "episode_id": 0,
            "decision_id": 0,
            "current_branch_id": "b_1",
            "remaining_budget": 3,
        },
    ]
    _write_jsonl(state_manifest, rows)

    # Patch reconstruction + local value to keep this test small, deterministic, and fast.
    def fake_replay_group_snapshots(**kwargs):
        manifest_rows = kwargs["rows"]
        return {
            (int(r["episode_id"]), int(r["decision_id"]), str(r["current_branch_id"])): [object(), object()]
            for r in manifest_rows
        }

    call_counter = {"n": 0}

    def fake_local_rollout_value(**kwargs):
        call_counter["n"] += 1
        forced = kwargs.get("forced_first_branch_id")
        # Ensure deterministic act>stop for b_0 and act<stop for b_1.
        if forced == "b_0":
            return 0.9
        if forced is None:
            skipped = kwargs.get("skip_first_branch_id")
            return 0.4 if skipped == "b_0" else 0.8
        return 0.2

    monkeypatch.setattr(heavy, "_replay_group_snapshots", fake_replay_group_snapshots)
    monkeypatch.setattr(heavy, "_local_rollout_value", fake_local_rollout_value)

    base_args = dict(
        pilot_config=str(pilot_config),
        selection_config=str(selection_config),
        state_manifest=str(state_manifest),
        output_dir=str(out_dir),
        labels_out="",
        manifest_out="",
        progress_out="",
        state_errors_out="",
        seed=123,
        paired_rollouts=2,
        max_states=0,
        progress_every=1,
        continue_on_state_error=False,
        max_state_errors=0,
        allow_partial_output=False,
        shard_name="",
        shard_id=-1,
        split_manifest="",
        expected_state_count=2,
    )

    # First run writes all rows.
    monkeypatch.setattr(heavy, "_parse_args", lambda: argparse.Namespace(**base_args, resume=False))
    heavy.main()

    labels_path = out_dir / "oracle_stop_vs_act_labels.jsonl"
    first_rows = heavy._read_jsonl(labels_path)
    assert [r["state_id"] for r in first_rows] == ["s7_b3_e0_d0_b_0", "s7_b3_e0_d0_b_1"]
    assert len(first_rows) == 2

    # Second run with resume should skip already-completed states (no duplicate rows).
    monkeypatch.setattr(heavy, "_parse_args", lambda: argparse.Namespace(**base_args, resume=True))
    heavy.main()

    second_rows = heavy._read_jsonl(labels_path)
    assert second_rows == first_rows

    progress = json.loads((out_dir / "oracle_label_progress.json").read_text(encoding="utf-8"))
    assert progress["rows_skipped_by_resume"] == 2


def test_stable_seed_helper_is_deterministic() -> None:
    seed_1 = heavy._stable_int_seed(11, "state-x", 0)
    seed_2 = heavy._stable_int_seed(11, "state-x", 0)
    seed_3 = heavy._stable_int_seed(11, "state-x", 1)
    assert seed_1 == seed_2
    assert seed_1 != seed_3
