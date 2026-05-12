from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts import label_failure_mechanisms_multi_api as labeler


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    assert rows
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_dry_run_reports_no_clients_and_writes_minimal_bundle(tmp_path: Path, monkeypatch) -> None:
    failure = tmp_path / "failure.csv"
    gold = tmp_path / "gold.csv"
    anchor = tmp_path / "anchor.csv"
    target_audit = tmp_path / "target_audit.jsonl"
    diag30 = tmp_path / "diagnostic_30.jsonl"
    target15 = tmp_path / "target_15.jsonl"
    structural = tmp_path / "candidate_feature_rows.csv"
    out_dir = tmp_path / "out"

    _write_csv(
        failure,
        [
            {
                "case_id": "c1",
                "method_id": labeler.DEFAULT_METHOD,
                "method_version": "v1",
                "evidence_completeness": "FULL",
                "failure_family": "unknown",
                "problem_text": "If there are 3 apples and 4 pears, how many fruits are there?",
                "gold_answer": "7",
                "selected_answer": "6",
                "selected_source": "frontier",
                "artifact_source": "outputs/example.csv",
                "has_candidate_metadata": "yes",
                "has_trace_metadata": "yes",
                "has_pal_metadata": "yes",
                "local_or_tracked_source": "local",
                "notes": "test row",
            }
        ],
    )
    _write_csv(
        gold,
        [
            {
                "case_id": "c1",
                "question_type": "multi-step arithmetic",
                "error_type": "unknown",
                "gold": "7",
                "predicted": "6",
                "abs_error": "1",
                "rel_error": "0.1429",
                "distance_bucket": "near (<10%)",
                "num_candidate_groups": "1",
                "diversity_bucket": "low (1 group)",
                "external_contrast": "Both wrong",
                "notes": "test row",
            }
        ],
    )
    _write_csv(
        anchor,
        [
            {
                "case_id": "c1",
                "question_type": "multi-step arithmetic",
                "error_type": "unknown",
                "gold": "7",
                "original_predicted": "6",
                "anchor_answer": "7",
                "has_anchor": "1",
                "diversity_before": "1",
                "diversity_after": "2",
                "diversity_increased": "1",
                "gold_recovered": "1",
                "anchor_matches_l1_max": "1",
                "external_l1_exact": "1",
            }
        ],
    )
    _write_jsonl(
        target_audit,
        [
            {
                "case_id": "c1",
                "question": "If there are 3 apples and 4 pears, how many fruits are there?",
                "selected_answer": "6",
                "selected_source": "frontier",
                "candidate_answers": ["6", "7"],
                "candidate_sources": ["frontier", "pal_seed"],
                "candidate_support_counts": {"6": 1, "7": 2},
                "direct_reserve_answer": "6",
                "frontier_answer": "6",
                "tiebreak_answer": "6",
                "structural_commit_reason": "candidate_pool_present",
                "gold_present_in_candidate_pool": "no",
                "correct_alternate_available": "yes",
                "failure_category": "wrong target",
                "latest_method_failure_tag": "frontier_collapse",
                "selection_reason": "test",
                "short_diagnosis": "test diagnosis",
                "likely_mismatch_subtype": "wrong_target_variable",
                "pal_answer": "7",
                "pal_code": "answer = 7",
                "pal_stdout": "7\n",
                "pal_execution_status": "success",
            }
        ],
    )
    _write_jsonl(
        diag30,
        [
            {"example_id": "c1", "question": "Q30"},
        ],
    )
    _write_jsonl(target15, [{"example_id": "c1", "question": "Q15"}])
    _write_csv(
        structural,
        [
            {
                "case_id": "c1",
                "target_tuple": json.dumps({"question_kind": "count", "target_surface": "total fruits", "target_entity": "fruits", "target_unit": "count"}),
                "entity_unit_ledger_proxy": json.dumps({"target_entity": "fruits", "target_unit": "count", "entity_hints": ["apples", "pears"]}),
                "final_answer_role": "target",
                "last_operation_family": "add",
                "target_alignment_score": "1.0",
                "intermediate_answer_penalty": "0.0",
                "duplicate_wrong_signature": "abc123",
                "structural_selector_score": "0.9",
                "slice_name": "primary",
                "group_key": "7",
                "candidate_answer": "7",
                "source_family": "target",
                "candidate_role": "target",
                "support_count": "2",
                "candidate_pool_size": "2",
            }
        ],
    )

    monkeypatch.setattr(
        labeler,
        "_call_provider_api",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API call attempted in dry run")),
    )
    monkeypatch.setattr(
        labeler,
        "_load_cohere_client",
        lambda: (_ for _ in ()).throw(AssertionError("Cohere client instantiated in dry run")),
    )
    monkeypatch.setattr(
        labeler,
        "_load_openai_client",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("OpenAI client instantiated in dry run")),
    )

    rc = labeler.main(
        [
            "--failure-csv",
            str(failure),
            "--gold-absent-csv",
            str(gold),
            "--anchor-effect-csv",
            str(anchor),
            "--target-audit-jsonl",
            str(target_audit),
            "--diagnostic-30-jsonl",
            str(diag30),
            "--target-staged-15-jsonl",
            str(target15),
            "--structural-feature-csv",
            str(structural),
            "--subsets",
            "diagnostic_30",
            "--providers",
            "cohere",
            "--output-dir",
            str(out_dir),
        ]
    )
    assert rc == 0

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["allow_api"] is False
    assert manifest["api_clients_constructed"] is False
    assert manifest["gold_assisted"] is False
    assert manifest["unique_case_count"] == 1
    assert manifest["planned_request_count"] == 1

    assert (out_dir / "trace_packets.jsonl").is_file()
    assert (out_dir / "provider_requests_dry_run.jsonl").is_file()
    assert (out_dir / "raw_provider_labels.jsonl").is_file()
    assert (out_dir / "parsed_labels.jsonl").is_file()
    assert (out_dir / "agreement_summary.json").is_file()

    parsed_rows = [json.loads(line) for line in (out_dir / "parsed_labels.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(parsed_rows) == 1
    assert parsed_rows[0]["label_status"] == "dry_run"
    assert parsed_rows[0]["label_valid"] is False


def test_dry_run_limit_reduces_request_count_and_records_manifest(tmp_path: Path, monkeypatch) -> None:
    failure = tmp_path / "failure.csv"
    gold = tmp_path / "gold.csv"
    anchor = tmp_path / "anchor.csv"
    target_audit = tmp_path / "target_audit.jsonl"
    diag30 = tmp_path / "diagnostic_30.jsonl"
    target15 = tmp_path / "target_15.jsonl"
    structural = tmp_path / "candidate_feature_rows.csv"
    out_dir = tmp_path / "out_limit"

    _write_csv(
        failure,
        [
            {
                "case_id": "c1",
                "method_id": labeler.DEFAULT_METHOD,
                "method_version": "v1",
                "evidence_completeness": "FULL",
                "failure_family": "unknown",
                "problem_text": "If there are 3 apples and 4 pears, how many fruits are there?",
                "gold_answer": "7",
                "selected_answer": "6",
                "selected_source": "frontier",
                "artifact_source": "outputs/example.csv",
                "has_candidate_metadata": "yes",
                "has_trace_metadata": "yes",
                "has_pal_metadata": "yes",
                "local_or_tracked_source": "local",
                "notes": "test row",
            }
        ],
    )
    _write_csv(
        gold,
        [
            {
                "case_id": "c1",
                "question_type": "multi-step arithmetic",
                "error_type": "unknown",
                "gold": "7",
                "predicted": "6",
                "abs_error": "1",
                "rel_error": "0.1429",
                "distance_bucket": "near (<10%)",
                "num_candidate_groups": "1",
                "diversity_bucket": "low (1 group)",
                "external_contrast": "Both wrong",
                "notes": "test row",
            }
        ],
    )
    _write_csv(
        anchor,
        [
            {
                "case_id": "c1",
                "question_type": "multi-step arithmetic",
                "error_type": "unknown",
                "gold": "7",
                "original_predicted": "6",
                "anchor_answer": "7",
                "has_anchor": "1",
                "diversity_before": "1",
                "diversity_after": "2",
                "diversity_increased": "1",
                "gold_recovered": "1",
                "anchor_matches_l1_max": "1",
                "external_l1_exact": "1",
            }
        ],
    )
    _write_jsonl(
        target_audit,
        [
            {
                "case_id": "c1",
                "question": "If there are 3 apples and 4 pears, how many fruits are there?",
                "selected_answer": "6",
                "selected_source": "frontier",
                "candidate_answers": ["6", "7"],
                "candidate_sources": ["frontier", "pal_seed"],
                "candidate_support_counts": {"6": 1, "7": 2},
                "direct_reserve_answer": "6",
                "frontier_answer": "6",
                "tiebreak_answer": "6",
                "structural_commit_reason": "candidate_pool_present",
                "gold_present_in_candidate_pool": "no",
                "correct_alternate_available": "yes",
                "failure_category": "wrong target",
                "latest_method_failure_tag": "frontier_collapse",
                "selection_reason": "test",
                "short_diagnosis": "test diagnosis",
                "likely_mismatch_subtype": "wrong_target_variable",
                "pal_answer": "7",
                "pal_code": "answer = 7",
                "pal_stdout": "7\n",
                "pal_execution_status": "success",
            }
        ],
    )
    _write_jsonl(
        diag30,
        [
            {"example_id": "c1", "question": "Q30-1"},
            {"example_id": "c2", "question": "Q30-2"},
        ],
    )
    _write_jsonl(target15, [{"example_id": "c1", "question": "Q15"}])
    _write_csv(
        structural,
        [
            {
                "case_id": "c1",
                "target_tuple": json.dumps({"question_kind": "count", "target_surface": "total fruits", "target_entity": "fruits", "target_unit": "count"}),
                "entity_unit_ledger_proxy": json.dumps({"target_entity": "fruits", "target_unit": "count", "entity_hints": ["apples", "pears"]}),
                "final_answer_role": "target",
                "last_operation_family": "add",
                "target_alignment_score": "1.0",
                "intermediate_answer_penalty": "0.0",
                "duplicate_wrong_signature": "abc123",
                "structural_selector_score": "0.9",
                "slice_name": "primary",
                "group_key": "7",
                "candidate_answer": "7",
                "source_family": "target",
                "candidate_role": "target",
                "support_count": "2",
                "candidate_pool_size": "2",
            }
        ],
    )

    monkeypatch.setattr(
        labeler,
        "_call_provider_api",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API call attempted in dry run")),
    )

    rc = labeler.main(
        [
            "--failure-csv",
            str(failure),
            "--gold-absent-csv",
            str(gold),
            "--anchor-effect-csv",
            str(anchor),
            "--target-audit-jsonl",
            str(target_audit),
            "--diagnostic-30-jsonl",
            str(diag30),
            "--target-staged-15-jsonl",
            str(target15),
            "--structural-feature-csv",
            str(structural),
            "--subsets",
            "diagnostic_30",
            "--providers",
            "cohere,cerebras,fireworks",
            "--limit",
            "1",
            "--output-dir",
            str(out_dir),
        ]
    )
    assert rc == 0

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["limit"] == 1
    assert manifest["prelimit_unique_case_count"] == 2
    assert manifest["requested_case_count"] == 2
    assert manifest["selected_case_count"] == 1
    assert manifest["unique_case_count"] == 1
    assert manifest["planned_request_count"] == 3
    assert manifest["expected_request_count"] == 3

    provider_requests = [json.loads(line) for line in (out_dir / "provider_requests_dry_run.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(provider_requests) == 3


def test_provider_config_check_records_models_without_clients(tmp_path: Path, monkeypatch) -> None:
    failure = tmp_path / "failure.csv"
    gold = tmp_path / "gold.csv"
    anchor = tmp_path / "anchor.csv"
    target_audit = tmp_path / "target_audit.jsonl"
    diag30 = tmp_path / "diagnostic_30.jsonl"
    target15 = tmp_path / "target_15.jsonl"
    structural = tmp_path / "candidate_feature_rows.csv"
    out_dir = tmp_path / "out_check"

    for key in ("COHERE_API_KEY", "CEREBRAS_API_KEY", "FIREWORKS_API_KEY", "OPENAI_API_KEY", "CO_API_KEY"):
        monkeypatch.setenv(key, f"{key}_VALUE")

    _write_csv(
        failure,
        [
            {
                "case_id": "c1",
                "method_id": labeler.DEFAULT_METHOD,
                "method_version": "v1",
                "evidence_completeness": "FULL",
                "failure_family": "unknown",
                "problem_text": "If there are 3 apples and 4 pears, how many fruits are there?",
                "gold_answer": "7",
                "selected_answer": "6",
                "selected_source": "frontier",
                "artifact_source": "outputs/example.csv",
                "has_candidate_metadata": "yes",
                "has_trace_metadata": "yes",
                "has_pal_metadata": "yes",
                "local_or_tracked_source": "local",
                "notes": "test row",
            }
        ],
    )
    _write_csv(
        gold,
        [
            {
                "case_id": "c1",
                "question_type": "multi-step arithmetic",
                "error_type": "unknown",
                "gold": "7",
                "predicted": "6",
                "abs_error": "1",
                "rel_error": "0.1429",
                "distance_bucket": "near (<10%)",
                "num_candidate_groups": "1",
                "diversity_bucket": "low (1 group)",
                "external_contrast": "Both wrong",
                "notes": "test row",
            }
        ],
    )
    _write_csv(
        anchor,
        [
            {
                "case_id": "c1",
                "question_type": "multi-step arithmetic",
                "error_type": "unknown",
                "gold": "7",
                "original_predicted": "6",
                "anchor_answer": "7",
                "has_anchor": "1",
                "diversity_before": "1",
                "diversity_after": "2",
                "diversity_increased": "1",
                "gold_recovered": "1",
                "anchor_matches_l1_max": "1",
                "external_l1_exact": "1",
            }
        ],
    )
    _write_jsonl(
        target_audit,
        [
            {
                "case_id": "c1",
                "question": "If there are 3 apples and 4 pears, how many fruits are there?",
                "selected_answer": "6",
                "selected_source": "frontier",
                "candidate_answers": ["6", "7"],
                "candidate_sources": ["frontier", "pal_seed"],
                "candidate_support_counts": {"6": 1, "7": 2},
                "direct_reserve_answer": "6",
                "frontier_answer": "6",
                "tiebreak_answer": "6",
                "structural_commit_reason": "candidate_pool_present",
                "gold_present_in_candidate_pool": "no",
                "correct_alternate_available": "yes",
                "failure_category": "wrong target",
                "latest_method_failure_tag": "frontier_collapse",
                "selection_reason": "test",
                "short_diagnosis": "test diagnosis",
                "likely_mismatch_subtype": "wrong_target_variable",
                "pal_answer": "7",
                "pal_code": "answer = 7",
                "pal_stdout": "7\n",
                "pal_execution_status": "success",
            }
        ],
    )
    _write_jsonl(diag30, [{"example_id": "c1", "question": "Q30"}])
    _write_jsonl(target15, [{"example_id": "c1", "question": "Q15"}])
    _write_csv(
        structural,
        [
            {
                "case_id": "c1",
                "target_tuple": json.dumps({"question_kind": "count", "target_surface": "total fruits", "target_entity": "fruits", "target_unit": "count"}),
                "entity_unit_ledger_proxy": json.dumps({"target_entity": "fruits", "target_unit": "count", "entity_hints": ["apples", "pears"]}),
                "final_answer_role": "target",
                "last_operation_family": "add",
                "target_alignment_score": "1.0",
                "intermediate_answer_penalty": "0.0",
                "duplicate_wrong_signature": "abc123",
                "structural_selector_score": "0.9",
                "slice_name": "primary",
                "group_key": "7",
                "candidate_answer": "7",
                "source_family": "target",
                "candidate_role": "target",
                "support_count": "2",
                "candidate_pool_size": "2",
            }
        ],
    )

    monkeypatch.setattr(
        labeler,
        "_call_provider_api",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API call attempted in config check")),
    )
    monkeypatch.setattr(
        labeler,
        "_load_cohere_client",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Cohere client instantiated in config check")),
    )

    rc = labeler.main(
        [
            "--failure-csv",
            str(failure),
            "--gold-absent-csv",
            str(gold),
            "--anchor-effect-csv",
            str(anchor),
            "--target-audit-jsonl",
            str(target_audit),
            "--diagnostic-30-jsonl",
            str(diag30),
            "--target-staged-15-jsonl",
            str(target15),
            "--structural-feature-csv",
            str(structural),
            "--subsets",
            "diagnostic_30",
            "--providers",
            "cohere,cerebras,fireworks",
            "--cohere-model",
            "cohere-x",
            "--cerebras-model",
            "cerebras-y",
            "--fireworks-model",
            "fireworks-z",
            "--check-provider-config",
            "--output-dir",
            str(out_dir),
        ]
    )
    assert rc == 0

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["check_provider_config"] is True
    assert manifest["provider_models"]["cohere"] == "cohere-x"
    assert manifest["provider_models"]["cerebras"] == "cerebras-y"
    assert manifest["provider_models"]["fireworks"] == "fireworks-z"
    assert manifest["provider_config_summary"]["cohere"]["model"] == "cohere-x"
    assert manifest["provider_config_summary"]["cerebras"]["model"] == "cerebras-y"
    assert manifest["provider_config_summary"]["fireworks"]["model"] == "fireworks-z"
    assert manifest["planned_request_count"] == 3
