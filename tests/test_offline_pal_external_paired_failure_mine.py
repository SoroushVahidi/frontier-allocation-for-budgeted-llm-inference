"""Unit tests for offline paired failure mining (no artifacts required)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script_module():
    path = ROOT / "scripts" / "offline_pal_external_paired_failure_mine.py"
    spec = importlib.util.spec_from_file_location("offline_pal_external_paired_failure_mine", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load_script_module()


def test_regret_bucket():
    assert _MOD.regret_bucket(1, 1) == "both_correct"
    assert _MOD.regret_bucket(1, 0) == "external_only"
    assert _MOD.regret_bucket(0, 1) == "pal_only"
    assert _MOD.regret_bucket(0, 0) == "both_wrong"


def test_extract_retry_from_pal_row():
    pal_row = {
        "result_metadata": {
            "pal_execution": {
                "pal_empty_code_retry_enabled": True,
                "pal_empty_code_retry_ran": 1,
                "pal_selected_candidate_source": "pal_empty_code_retry",
                "pal_empty_code_retry_skipped_reason": "",
                "pal_empty_code_retry_execution": {
                    "pal_exec_ok": 1,
                    "pal_parse_ok": 1,
                    "pal_safety_ok": 1,
                    "pal_candidate_is_strong": 1,
                    "pal_code": "print(1)",
                },
            }
        }
    }
    r = _MOD.extract_retry_from_pal_row(pal_row)
    assert r["truth_retry_enabled"] == 1
    assert r["truth_retry_ran"] == 1
    assert r["truth_retry_selected_source"] == "pal_empty_code_retry"
    assert r["truth_retry_exec_ok"] == 1


def test_mine_failure_modes_fixture():
    fixture_dir = ROOT / "tests" / "fixtures" / "offline_pal_external_failure_mine_minimal"
    cb_rows = _MOD._read_csv_rows(fixture_dir / "paired_casebook.csv")
    pal_by_id = _MOD._index_pal_results(fixture_dir / "pal_results.jsonl")
    mined = _MOD.mine_failure_modes(
        casebook_rows=cb_rows,
        pal_by_id=pal_by_id,
        top_signatures=10,
        anchors_per_signature=5,
    )
    assert mined["bucket_counts"]["both_correct"] == 1
    assert mined["bucket_counts"]["external_only"] == 1
    assert mined["bucket_counts"]["pal_only"] == 1
    assert mined["bucket_counts"]["both_wrong"] == 1
    assert mined["retry_recompute"]["truth_retry_ran_count"] == 1
    assert mined["retry_recompute"]["missing_pal_results_rows"] == 0


@pytest.mark.parametrize(
    "paired_summary_exists",
    [False, True],
)
def test_run_from_paths_smoke(tmp_path: Path, paired_summary_exists: bool):
    fixture_dir = ROOT / "tests" / "fixtures" / "offline_pal_external_failure_mine_minimal"
    out = tmp_path / "out"
    ps = tmp_path / "paired_summary.json"
    if paired_summary_exists:
        ps.write_text(json.dumps({"selected_fresh_examples_count": 4}), encoding="utf-8")
    summary = _MOD.run_from_paths(
        casebook_path=fixture_dir / "paired_casebook.csv",
        pal_results_path=fixture_dir / "pal_results.jsonl",
        paired_summary_path=ps if paired_summary_exists else None,
        materialization_path=None,
        output_dir=out,
        top_signatures=5,
        anchors_per_signature=3,
    )
    assert (out / "summary.json").is_file()
    assert (out / "failure_mode_table.csv").is_file()
    assert (out / "anchor_cases.csv").is_file()
    assert (out / "report.md").is_file()
    assert summary["bucket_counts"]["external_only"] == 1
