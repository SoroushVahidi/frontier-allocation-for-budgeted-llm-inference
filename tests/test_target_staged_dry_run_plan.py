from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import prepare_target_staged_pal_frontier_v1_preflight as preflight


def test_dry_run_writes_expected_outputs_and_never_touches_api_clients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args, **kwargs):  # noqa: ANN001, ANN002
        raise AssertionError("API client construction should not be touched in dry-run preflight")

    monkeypatch.setattr("experiments.branching.APIBranchGenerator.__init__", boom, raising=False)

    summary = preflight.run(
        [
            "--manifest",
            str(preflight.DEFAULT_MANIFEST_PATH),
            "--output-root",
            str(tmp_path / "outputs"),
            "--timestamp",
            "20260511T130000Z",
            "--case-source",
            "synthetic",
            "--max-cases-per-slice",
            "1",
        ]
    )

    out_dir = tmp_path / "outputs" / f"{preflight.EXPERIMENT_ID}_20260511T130000Z"
    assert summary["dry_run_only"] is True
    assert summary["no_api_clients_constructed"] is True
    assert summary["case_count"] == 4
    assert summary["call_plan_row_count"] == 24
    assert summary["trace_row_count"] == 24
    assert summary["candidate_feature_row_count"] == 24
    assert (out_dir / "manifest.resolved.json").is_file()
    assert (out_dir / "call_plan.jsonl").is_file()
    assert (out_dir / "traces.jsonl").is_file()
    assert (out_dir / "candidate_feature_rows.csv").is_file()
    assert (out_dir / "candidate_feature_rows.jsonl").is_file()
    assert (out_dir / "validation_summary.json").is_file()
    assert (out_dir / "replay_summary.json").is_file()
    assert (out_dir / "dry_run_report.md").is_file()
    assert (out_dir / "replay_report.md").is_file()

    with (out_dir / "call_plan.jsonl").open(encoding="utf-8") as handle:
        first = json.loads(next(handle))
    for key in (
        "experiment_id",
        "slice_name",
        "case_id",
        "target_schema",
        "branch_family",
        "branch_slot",
        "prompt_template_id",
        "call_plan_id",
        "budget_total",
        "parse_ok",
        "render_ok",
        "no_gold_leak_ok",
        "trace_compat_ok",
    ):
        assert key in first
    assert first["parse_ok"] is True
    assert first["render_ok"] is True
    assert first["no_gold_leak_ok"] is True
    assert first["trace_compat_ok"] is True
