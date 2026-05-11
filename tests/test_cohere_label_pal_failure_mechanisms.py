from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts import cohere_label_pal_failure_mechanisms as labeler


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    assert rows
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_default_dry_run_writes_outputs_and_makes_zero_api_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    coverage = tmp_path / "case_coverage_details.csv"
    failure = tmp_path / "failures.csv"
    gold_absent = tmp_path / "gold_absent.csv"
    anchor = tmp_path / "anchor.csv"
    out_dir = tmp_path / "out"

    _write_csv(
        coverage,
        [
            {
                "case_id": "c1",
                "method": labeler.DEFAULT_METHOD,
                "coverage_status": "still_fails",
                "selected_source_path": "",
                "selected_prediction": "10",
                "selected_gold": "12",
                "failure_family": "unknown",
            },
        ],
    )
    _write_csv(
        failure,
        [
            {
                "case_id": "c1",
                "method_id": labeler.DEFAULT_METHOD,
                "method_version": "v1",
                "evidence_completeness": "FULL",
                "failure_family": "unknown",
                "problem_text": "What is 6+6?",
                "gold_answer": "12",
                "selected_answer": "10",
                "selected_source": "none",
                "artifact_source": "outputs/x/pal_results.csv",
                "has_candidate_metadata": "unknown",
                "has_trace_metadata": "unknown",
                "has_pal_metadata": "unknown",
                "local_or_tracked_source": "local",
                "notes": "",
            }
        ],
    )
    _write_csv(
        gold_absent,
        [
            {
                "case_id": "c1",
                "question_type": "money/cost/revenue",
                "error_type": "unknown",
                "gold": "12",
                "predicted": "10",
                "abs_error": "2",
                "rel_error": "0.1",
                "distance_bucket": "unknown",
                "num_candidate_groups": "1",
                "diversity_bucket": "low (1 group)",
                "external_contrast": "Both wrong",
                "notes": "",
            }
        ],
    )
    _write_csv(
        anchor,
        [
            {
                "case_id": "c1",
                "question_type": "money/cost/revenue",
                "error_type": "unknown",
                "gold": "12",
                "original_predicted": "10",
                "anchor_answer": "10",
                "has_anchor": "1",
                "diversity_before": "1",
                "diversity_after": "1",
                "diversity_increased": "0",
                "gold_recovered": "0",
                "anchor_matches_l1_max": "1",
                "external_l1_exact": "0",
            }
        ],
    )

    # Ensure any accidental cohere import fails the test (dry-run must not need it).
    monkeypatch.setitem(labeler.__dict__, "_load_cohere_client", lambda: (_ for _ in ()).throw(AssertionError("no api")))

    rc = labeler.main(
        [
            "--coverage-details-csv",
            str(coverage),
            "--failure-csv",
            str(failure),
            "--gold-absent-csv",
            str(gold_absent),
            "--anchor-effect-csv",
            str(anchor),
            "--subset",
            "direct_l1_potential",
            "--limit",
            "1",
            "--output-dir",
            str(out_dir),
        ]
    )
    assert rc == 0
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["actual_calls"] == 0
    assert (out_dir / "label_rows.jsonl").is_file()
    assert (out_dir / "summary.json").is_file()
    assert (out_dir / "report.md").is_file()


def test_allow_api_requires_max_calls(tmp_path: Path) -> None:
    coverage = tmp_path / "case_coverage_details.csv"
    failure = tmp_path / "failures.csv"
    gold_absent = tmp_path / "gold_absent.csv"
    anchor = tmp_path / "anchor.csv"

    _write_csv(
        coverage,
        [
            {
                "case_id": "c1",
                "method": labeler.DEFAULT_METHOD,
                "coverage_status": "still_fails",
                "selected_source_path": "",
                "selected_prediction": "10",
                "selected_gold": "12",
                "failure_family": "unknown",
            }
        ],
    )
    _write_csv(
        failure,
        [
            {
                "case_id": "c1",
                "method_id": labeler.DEFAULT_METHOD,
                "method_version": "v1",
                "evidence_completeness": "FULL",
                "failure_family": "unknown",
                "problem_text": "What is 6+6?",
                "gold_answer": "12",
                "selected_answer": "10",
                "selected_source": "none",
                "artifact_source": "outputs/x/pal_results.csv",
                "has_candidate_metadata": "unknown",
                "has_trace_metadata": "unknown",
                "has_pal_metadata": "unknown",
                "local_or_tracked_source": "local",
                "notes": "",
            }
        ],
    )
    _write_csv(
        gold_absent,
        [
            {
                "case_id": "c1",
                "question_type": "money/cost/revenue",
                "error_type": "unknown",
                "gold": "12",
                "predicted": "10",
                "abs_error": "",
                "rel_error": "",
                "distance_bucket": "",
                "num_candidate_groups": "1",
                "diversity_bucket": "low (1 group)",
                "external_contrast": "",
                "notes": "",
            }
        ],
    )
    _write_csv(
        anchor,
        [
            {
                "case_id": "c1",
                "question_type": "money/cost/revenue",
                "error_type": "unknown",
                "gold": "12",
                "original_predicted": "10",
                "anchor_answer": "10",
                "has_anchor": "1",
                "diversity_before": "",
                "diversity_after": "",
                "diversity_increased": "",
                "gold_recovered": "",
                "anchor_matches_l1_max": "1",
                "external_l1_exact": "0",
            }
        ],
    )

    with pytest.raises(ValueError, match="--allow-api requires a positive --max-calls"):
        labeler.main(
            [
                "--coverage-details-csv",
                str(coverage),
                "--failure-csv",
                str(failure),
                "--gold-absent-csv",
                str(gold_absent),
                "--anchor-effect-csv",
                str(anchor),
                "--subset",
                "direct_l1_potential",
                "--limit",
                "1",
                "--allow-api",
            ]
        )


def test_diagnostic_15_subset_selection_respects_limit(tmp_path: Path) -> None:
    # No IO needed; this just checks selection order and limit behavior.
    selected = labeler._select_case_ids(  # type: ignore[attr-defined]
        subset="diagnostic_15",
        limit=2,
        coverage_rows=[],
        method=labeler.DEFAULT_METHOD,
        gold_absent_map={},
        anchor_map={},
    )
    assert selected == list(labeler.DIAGNOSTIC_15_CASE_IDS[:2])


def test_invalid_json_response_is_recorded_as_parse_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    coverage = tmp_path / "case_coverage_details.csv"
    failure = tmp_path / "failures.csv"
    gold_absent = tmp_path / "gold_absent.csv"
    anchor = tmp_path / "anchor.csv"
    out_dir = tmp_path / "out"

    _write_csv(
        coverage,
        [
            {
                "case_id": "c1",
                "method": labeler.DEFAULT_METHOD,
                "coverage_status": "still_fails",
                "selected_source_path": "",
                "selected_prediction": "10",
                "selected_gold": "12",
                "failure_family": "unknown",
            }
        ],
    )
    _write_csv(
        failure,
        [
            {
                "case_id": "c1",
                "method_id": labeler.DEFAULT_METHOD,
                "method_version": "v1",
                "evidence_completeness": "FULL",
                "failure_family": "unknown",
                "problem_text": "What is 6+6?",
                "gold_answer": "12",
                "selected_answer": "10",
                "selected_source": "none",
                "artifact_source": "outputs/x/pal_results.csv",
                "has_candidate_metadata": "unknown",
                "has_trace_metadata": "unknown",
                "has_pal_metadata": "unknown",
                "local_or_tracked_source": "local",
                "notes": "",
            }
        ],
    )
    _write_csv(
        gold_absent,
        [
            {
                "case_id": "c1",
                "question_type": "money/cost/revenue",
                "error_type": "unknown",
                "gold": "12",
                "predicted": "10",
                "abs_error": "",
                "rel_error": "",
                "distance_bucket": "",
                "num_candidate_groups": "1",
                "diversity_bucket": "low (1 group)",
                "external_contrast": "",
                "notes": "",
            }
        ],
    )
    _write_csv(
        anchor,
        [
            {
                "case_id": "c1",
                "question_type": "money/cost/revenue",
                "error_type": "unknown",
                "gold": "12",
                "original_predicted": "10",
                "anchor_answer": "10",
                "has_anchor": "1",
                "diversity_before": "",
                "diversity_after": "",
                "diversity_increased": "",
                "gold_recovered": "",
                "anchor_matches_l1_max": "1",
                "external_l1_exact": "0",
            }
        ],
    )

    class _FakeClient:
        pass

    monkeypatch.setattr(labeler, "_load_cohere_client", lambda: _FakeClient())
    monkeypatch.setattr(labeler, "_call_cohere", lambda **_kwargs: ("not json", {"cohere_model": "fake"}))
    monkeypatch.setenv("COHERE_API_KEY", "dummy")

    rc = labeler.main(
        [
            "--coverage-details-csv",
            str(coverage),
            "--failure-csv",
            str(failure),
            "--gold-absent-csv",
            str(gold_absent),
            "--anchor-effect-csv",
            str(anchor),
            "--subset",
            "direct_l1_potential",
            "--limit",
            "1",
            "--allow-api",
            "--max-calls",
            "1",
            "--output-dir",
            str(out_dir),
        ]
    )
    assert rc == 0
    rows = _read_jsonl(out_dir / "label_rows.jsonl")
    assert rows[0]["label_json"] is None
    assert str(rows[0]["parse_error"]).startswith("json_parse_error")
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["actual_calls"] == 1


def test_resume_skips_already_labeled_cases(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "label_rows.jsonl").write_text(json.dumps({"case_id": "c1"}) + "\n", encoding="utf-8")

    coverage = tmp_path / "case_coverage_details.csv"
    failure = tmp_path / "failures.csv"
    gold_absent = tmp_path / "gold_absent.csv"
    anchor = tmp_path / "anchor.csv"

    _write_csv(
        coverage,
        [
            {
                "case_id": "c1",
                "method": labeler.DEFAULT_METHOD,
                "coverage_status": "still_fails",
                "selected_source_path": "",
                "selected_prediction": "10",
                "selected_gold": "12",
                "failure_family": "unknown",
            }
        ],
    )
    _write_csv(
        failure,
        [
            {
                "case_id": "c1",
                "method_id": labeler.DEFAULT_METHOD,
                "method_version": "v1",
                "evidence_completeness": "FULL",
                "failure_family": "unknown",
                "problem_text": "What is 6+6?",
                "gold_answer": "12",
                "selected_answer": "10",
                "selected_source": "none",
                "artifact_source": "outputs/x/pal_results.csv",
                "has_candidate_metadata": "unknown",
                "has_trace_metadata": "unknown",
                "has_pal_metadata": "unknown",
                "local_or_tracked_source": "local",
                "notes": "",
            }
        ],
    )
    _write_csv(
        gold_absent,
        [
            {
                "case_id": "c1",
                "question_type": "money/cost/revenue",
                "error_type": "unknown",
                "gold": "12",
                "predicted": "10",
                "abs_error": "",
                "rel_error": "",
                "distance_bucket": "",
                "num_candidate_groups": "1",
                "diversity_bucket": "low (1 group)",
                "external_contrast": "",
                "notes": "",
            }
        ],
    )
    _write_csv(
        anchor,
        [
            {
                "case_id": "c1",
                "question_type": "money/cost/revenue",
                "error_type": "unknown",
                "gold": "12",
                "original_predicted": "10",
                "anchor_answer": "10",
                "has_anchor": "1",
                "diversity_before": "",
                "diversity_after": "",
                "diversity_increased": "",
                "gold_recovered": "",
                "anchor_matches_l1_max": "1",
                "external_l1_exact": "0",
            }
        ],
    )

    rc = labeler.main(
        [
            "--coverage-details-csv",
            str(coverage),
            "--failure-csv",
            str(failure),
            "--gold-absent-csv",
            str(gold_absent),
            "--anchor-effect-csv",
            str(anchor),
            "--subset",
            "direct_l1_potential",
            "--limit",
            "1",
            "--output-dir",
            str(out_dir),
            "--resume",
        ]
    )
    assert rc == 0
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["labeled_rows_written"] == 0
    assert manifest["actual_calls"] == 0
