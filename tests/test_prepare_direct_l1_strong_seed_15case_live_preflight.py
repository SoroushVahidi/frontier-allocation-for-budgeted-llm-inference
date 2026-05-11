from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from scripts import prepare_direct_l1_strong_seed_15case_live_preflight as preflight


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "prepare_direct_l1_strong_seed_15case_live_preflight.py"


def _exact_case_rows(ids: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for idx, case_id in enumerate(ids, start=1):
        rows.append(
            {
                "dataset": "openai/gsm8k",
                "example_id": case_id,
                "question": f"Synthetic exact-case question {idx}?",
                "gold_answer_canonical": str(10_000 + idx),
                "selection_reason": "synthetic test slice",
            }
        )
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _write_exact_case_slice(path: Path, ids: list[str]) -> None:
    _write_jsonl(path, _exact_case_rows(ids))


def _fake_validate_report(tmp_path: Path) -> dict[str, object]:
    report_path = tmp_path / "cohere_real_model_cost_normalized_validation_20260511" / "exact_case_validation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "exact_cases_jsonl": "synthetic",
                "case_count": 15,
                "expected_case_count": 15,
                "datasets": [{"dataset": "openai/gsm8k", "case_count": 15, "mismatch_count": 0}],
                "methods": [],
                "mismatch_count": 0,
                "mismatches": [],
                "api_calls_made": 0,
                "shuffled_loader_used": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "_report_path": str(report_path),
        "_stdout": "exact_case_count=15 mismatch_count=0 api_calls_made=0 shuffled_loader_used=false",
        "case_count": 15,
        "expected_case_count": 15,
        "mismatch_count": 0,
        "api_calls_made": 0,
        "shuffled_loader_used": False,
    }


def test_preflight_writes_summary_report_and_future_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exact_cases = tmp_path / "exact_cases.jsonl"
    output_dir = tmp_path / "preflight"
    _write_exact_case_slice(exact_cases, list(preflight.EXPECTED_CASE_IDS))

    monkeypatch.setattr(preflight, "_run_validate_only", lambda command: _fake_validate_report(tmp_path))

    summary = preflight.run(
        [
            "--exact-cases-jsonl",
            str(exact_cases),
            "--output-dir",
            str(output_dir),
            "--timestamp",
            "20260511T120000Z",
        ]
    )

    assert summary["exact_case_count"] == 15
    assert summary["unique_case_id_count"] == 15
    assert summary["case_id_order_matches_expected"] is True
    assert summary["missing_case_ids"] == []
    assert summary["extra_case_ids"] == []
    assert summary["method_ids"] == [
        preflight.DEFAULT_BASELINE_METHOD,
        preflight.DEFAULT_TREATMENT_METHOD,
    ]
    assert summary["estimated_future_call_cap"] == 15 * 2 * preflight.DEFAULT_BUDGET + 15
    assert summary["validate_only_result"]["api_calls_made"] == 0

    summary_path = output_dir / "summary.json"
    report_path = output_dir / "direct_l1_strong_seed_15case_live_preflight_report.md"
    future_command_path = output_dir / "future_live_command.sh"
    assert summary_path.is_file()
    assert report_path.is_file()
    assert future_command_path.is_file()

    saved = json.loads(summary_path.read_text(encoding="utf-8"))
    assert saved["future_live_command_path"] == "future_live_command.sh"
    assert saved["validate_only_report_path"].endswith("exact_case_validation_report.json")
    assert saved["validate_only_result"]["api_calls_made"] == 0

    report = report_path.read_text(encoding="utf-8")
    assert "Future live command not run here" in report
    assert "No external-baseline claim." in report
    assert preflight.DEFAULT_BASELINE_METHOD in report
    assert preflight.DEFAULT_TREATMENT_METHOD in report
    assert "estimated_future_call_cap" in report

    future_command = future_command_path.read_text(encoding="utf-8")
    assert future_command.startswith("#!/usr/bin/env bash\n")
    assert "NOT RUN IN THIS PR." in future_command
    assert "--provider cohere" in future_command
    assert preflight.DEFAULT_TREATMENT_METHOD in future_command


def test_preflight_can_include_diverse_anchor_and_recompute_call_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exact_cases = tmp_path / "exact_cases.jsonl"
    output_dir = tmp_path / "preflight_anchor"
    _write_exact_case_slice(exact_cases, list(preflight.EXPECTED_CASE_IDS))

    monkeypatch.setattr(preflight, "_run_validate_only", lambda command: _fake_validate_report(tmp_path))

    summary = preflight.run(
        [
            "--exact-cases-jsonl",
            str(exact_cases),
            "--output-dir",
            str(output_dir),
            "--timestamp",
            "20260511T120001Z",
            "--include-diverse-anchor",
        ]
    )

    assert summary["method_ids"] == [
        preflight.DEFAULT_BASELINE_METHOD,
        preflight.DEFAULT_TREATMENT_METHOD,
        preflight.DEFAULT_DIV_ANCHOR_METHOD,
    ]
    assert summary["method_resolution_rows"] and len(summary["method_resolution_rows"]) == 3
    assert summary["estimated_future_call_cap"] == 15 * 3 * preflight.DEFAULT_BUDGET + 15


def test_preflight_rejects_case_id_order_mismatch_without_opt_in(tmp_path: Path) -> None:
    exact_cases = tmp_path / "exact_cases.jsonl"
    scrambled = list(preflight.EXPECTED_CASE_IDS)
    scrambled[0], scrambled[1] = scrambled[1], scrambled[0]
    _write_exact_case_slice(exact_cases, scrambled)

    with pytest.raises(ValueError, match="Exact-case IDs do not match expected list"):
        preflight.run(
            [
                "--exact-cases-jsonl",
                str(exact_cases),
                "--timestamp",
                "20260511T120002Z",
            ]
        )


def test_preflight_allows_case_id_mismatch_when_explicitly_requested(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exact_cases = tmp_path / "exact_cases.jsonl"
    output_dir = tmp_path / "preflight_allow"
    scrambled = list(preflight.EXPECTED_CASE_IDS)
    scrambled[0], scrambled[1] = scrambled[1], scrambled[0]
    _write_exact_case_slice(exact_cases, scrambled)

    monkeypatch.setattr(preflight, "_run_validate_only", lambda command: _fake_validate_report(tmp_path))

    summary = preflight.run(
        [
            "--exact-cases-jsonl",
            str(exact_cases),
            "--output-dir",
            str(output_dir),
            "--timestamp",
            "20260511T120003Z",
            "--allow-different-ids",
        ]
    )

    assert summary["case_id_order_matches_expected"] is False
    assert summary["allow_different_ids"] is True
    assert summary["missing_case_ids"] == []
    assert summary["extra_case_ids"] == []


def test_preflight_dry_run_does_not_write_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exact_cases = tmp_path / "exact_cases.jsonl"
    output_dir = tmp_path / "dry_run_output"
    _write_exact_case_slice(exact_cases, list(preflight.EXPECTED_CASE_IDS))

    called = {"value": False}

    def _should_not_run(command: list[str]) -> dict[str, object]:
        called["value"] = True
        return _fake_validate_report(tmp_path)

    monkeypatch.setattr(preflight, "_run_validate_only", _should_not_run)

    summary = preflight.run(
        [
            "--exact-cases-jsonl",
            str(exact_cases),
            "--output-dir",
            str(output_dir),
            "--timestamp",
            "20260511T120004Z",
            "--dry-run",
        ]
    )

    assert called["value"] is False
    assert not output_dir.exists()
    assert summary["future_live_command_path"] == "future_live_command.sh"
    assert summary["validate_only_result"] == {}


def test_script_has_no_api_client_imports() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])

    forbidden = {"openai", "cohere", "anthropic", "requests", "google"}
    assert imported_modules.isdisjoint(forbidden)
