from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts import label_failure_mechanisms_multi_api as labeler


def _packet(case_id: str, subset: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "primary_subset": subset,
        "subset_memberships": [{"subset": subset, "rank": 1, "approximate": False, "selection_logic": "exact"}],
        "question": f"Question for {case_id}",
        "model_final_prediction": "7",
        "candidate_answers": ["7"],
        "candidate_answer_groups": [],
        "selector_metadata": {"selected_source": "frontier"},
        "action_trace_summary": {"failure_family": "unknown"},
        "pal_exec_summary": {"pal_execution_status": "success"},
        "structural_fields": {"target_tuple": {"question_kind": "count"}},
        "failure_audit_labels": {"question_type": "multi-step arithmetic"},
        "prompt_template_id": labeler.DEFAULT_PROMPT_TEMPLATE_ID,
        "include_gold_for_labeling": False,
        "gold_assisted": False,
    }


def test_agreement_summary_and_frequency_outputs(tmp_path: Path) -> None:
    out_dir = tmp_path / "agreement"
    case_packets = [_packet("c1", "diagnostic_30"), _packet("c2", "target_staged_15")]
    prompt_packets = [{**packet, "prompt": f"PROMPT {packet['case_id']}", "prompt_sha256": f"sha-{packet['case_id']}"} for packet in case_packets]
    parsed_rows = [
        {
            "request_id": "cohere:c1:1",
            "case_id": "c1",
            "provider": "cohere",
            "model": "m1",
            "subset_memberships": "[]",
            "primary_subset": "diagnostic_30",
            "prompt_template_id": labeler.DEFAULT_PROMPT_TEMPLATE_ID,
            "prompt_sha256": "sha-c1",
            "request_sha256": "req-c1",
            "dry_run": False,
            "api_call_made": 1,
            "label_status": "parsed",
            "case_id": "c1",
            "primary_label": "wrong_target_variable",
            "secondary_labels": ["wrong_relation"],
            "selector_vs_generation": "generation_failure",
            "candidate_pool_status": "gold_absent",
            "confidence": 0.9,
            "evidence": "reason",
            "recommended_fix_family": "target_schema",
            "label_valid": True,
            "label_errors": [],
        },
        {
            "request_id": "cerebras:c1:1",
            "case_id": "c1",
            "provider": "cerebras",
            "model": "m1",
            "subset_memberships": "[]",
            "primary_subset": "diagnostic_30",
            "prompt_template_id": labeler.DEFAULT_PROMPT_TEMPLATE_ID,
            "prompt_sha256": "sha-c1",
            "request_sha256": "req-c1b",
            "dry_run": False,
            "api_call_made": 1,
            "label_status": "parsed",
            "primary_label": "wrong_target_variable",
            "secondary_labels": ["wrong_relation"],
            "selector_vs_generation": "generation_failure",
            "candidate_pool_status": "gold_absent",
            "confidence": 0.8,
            "evidence": "reason",
            "recommended_fix_family": "target_schema",
            "label_valid": True,
            "label_errors": [],
        },
        {
            "request_id": "fireworks:c1:1",
            "case_id": "c1",
            "provider": "fireworks",
            "model": "m1",
            "subset_memberships": "[]",
            "primary_subset": "diagnostic_30",
            "prompt_template_id": labeler.DEFAULT_PROMPT_TEMPLATE_ID,
            "prompt_sha256": "sha-c1",
            "request_sha256": "req-c1c",
            "dry_run": False,
            "api_call_made": 1,
            "label_status": "parsed",
            "primary_label": "wrong_target_variable",
            "secondary_labels": ["wrong_relation"],
            "selector_vs_generation": "generation_failure",
            "candidate_pool_status": "gold_absent",
            "confidence": 0.85,
            "evidence": "reason",
            "recommended_fix_family": "target_schema",
            "label_valid": True,
            "label_errors": [],
        },
        {
            "request_id": "cohere:c2:1",
            "case_id": "c2",
            "provider": "cohere",
            "model": "m1",
            "subset_memberships": "[]",
            "primary_subset": "target_staged_15",
            "prompt_template_id": labeler.DEFAULT_PROMPT_TEMPLATE_ID,
            "prompt_sha256": "sha-c2",
            "request_sha256": "req-c2",
            "dry_run": False,
            "api_call_made": 1,
            "label_status": "parsed",
            "primary_label": "wrong_relation",
            "secondary_labels": ["wrong_operator"],
            "selector_vs_generation": "selector_failure",
            "candidate_pool_status": "gold_absent",
            "confidence": 0.6,
            "evidence": "reason",
            "recommended_fix_family": "selector_structural",
            "label_valid": True,
            "label_errors": [],
        },
        {
            "request_id": "cerebras:c2:1",
            "case_id": "c2",
            "provider": "cerebras",
            "model": "m1",
            "subset_memberships": "[]",
            "primary_subset": "target_staged_15",
            "prompt_template_id": labeler.DEFAULT_PROMPT_TEMPLATE_ID,
            "prompt_sha256": "sha-c2",
            "request_sha256": "req-c2b",
            "dry_run": False,
            "api_call_made": 1,
            "label_status": "parsed",
            "primary_label": "wrong_relation",
            "secondary_labels": ["wrong_operator"],
            "selector_vs_generation": "selector_failure",
            "candidate_pool_status": "gold_absent",
            "confidence": 0.65,
            "evidence": "reason",
            "recommended_fix_family": "selector_structural",
            "label_valid": True,
            "label_errors": [],
        },
        {
            "request_id": "fireworks:c2:1",
            "case_id": "c2",
            "provider": "fireworks",
            "model": "m1",
            "subset_memberships": "[]",
            "primary_subset": "target_staged_15",
            "prompt_template_id": labeler.DEFAULT_PROMPT_TEMPLATE_ID,
            "prompt_sha256": "sha-c2",
            "request_sha256": "req-c2c",
            "dry_run": False,
            "api_call_made": 1,
            "label_status": "parsed",
            "primary_label": "wrong_operator",
            "secondary_labels": ["wrong_relation"],
            "selector_vs_generation": "mixed",
            "candidate_pool_status": "gold_absent",
            "confidence": 0.7,
            "evidence": "reason",
            "recommended_fix_family": "equation_relation",
            "label_valid": True,
            "label_errors": [],
        },
    ]
    manifest = {
        "allow_api": False,
        "dry_run": True,
        "api_clients_constructed": False,
        "include_gold_for_labeling": False,
        "gold_assisted": False,
        "providers": ["cohere", "cerebras", "fireworks"],
        "provider_models": {"cohere": "m1", "cerebras": "m1", "fireworks": "m1"},
        "provider_caps": {"cohere": 0, "cerebras": 0, "fireworks": 0},
        "planned_request_count": 6,
        "api_call_count": 0,
    }

    agreement = labeler._build_outputs(
        case_packets=case_packets,
        providers=["cohere", "cerebras", "fireworks"],
        provider_models={"cohere": "m1", "cerebras": "m1", "fireworks": "m1"},
        provider_caps={"cohere": 0, "cerebras": 0, "fireworks": 0},
        allow_api=False,
        include_gold_for_labeling=False,
        max_calls_total=0,
        prompt_packets=prompt_packets,
        request_rows=[],
        raw_rows=[],
        parsed_rows=parsed_rows,
        packet_completeness_summary={"question_present_rate": 1.0, "prediction_present_rate": 1.0, "warnings": [], "per_subset": {}, "candidate_pool_present_rate": 1.0, "action_trace_present_rate": 1.0, "pal_execution_present_rate": 1.0, "structural_fields_present_rate": 1.0, "empty_packet_count": 0},
        output_dir=out_dir,
        manifest=manifest,
    )

    assert agreement["all_agree_case_count"] == 1
    assert agreement["disagreement_case_count"] == 1
    assert agreement["missing_label_case_count"] == 0
    assert agreement["provider_label_counts"]["cohere"]["wrong_target_variable"] == 1
    assert agreement["provider_label_counts"]["fireworks"]["wrong_operator"] == 1

    matrix_rows = list(csv.DictReader((out_dir / "case_label_matrix.csv").open(encoding="utf-8")))
    by_case = {row["case_id"]: row for row in matrix_rows}
    assert by_case["c1"]["agreement_status"] == "all_agree"
    assert by_case["c1"]["consensus_primary_label"] == "wrong_target_variable"
    assert by_case["c2"]["agreement_status"] == "disagreement"
    assert by_case["c2"]["consensus_primary_label"] == "wrong_relation"

    frequency_rows = list(csv.DictReader((out_dir / "label_frequency_summary.csv").open(encoding="utf-8")))
    overall = [row for row in frequency_rows if row["scope"] == "overall" and row["metric"] == "primary_label"]
    assert any(row["label"] == "wrong_target_variable" and row["count"] == "3" for row in overall)
    assert any(row["label"] == "wrong_relation" and row["count"] == "2" for row in overall)
    assert any(row["label"] == "wrong_operator" and row["count"] == "1" for row in overall)

    disagreement_rows = list(csv.DictReader((out_dir / "disagreement_cases.csv").open(encoding="utf-8")))
    assert [row["case_id"] for row in disagreement_rows] == ["c2"]


def test_provider_readiness_summary_classifies_403_and_404_errors() -> None:
    parsed_rows = [
        {
            "case_id": "c1",
            "provider": "cohere",
            "label_status": "parsed",
            "provider_readiness": "ready",
            "provider_http_status": None,
            "provider_error_code": "",
            "provider_error_message_short": "",
        },
        {
            "case_id": "c1",
            "provider": "cerebras",
            "label_status": "api_error",
            "api_error": "HTTP error from https://api.cerebras.ai/v1/chat/completions: 403 error code: 1010",
            "label_parse_error": "",
            "provider_readiness": "auth_error",
            "provider_http_status": 403,
            "provider_error_code": "1010",
            "provider_error_message_short": "403 error code: 1010",
        },
        {
            "case_id": "c1",
            "provider": "fireworks",
            "label_status": "api_error",
            "api_error": 'HTTP error from https://api.fireworks.ai/inference/v1/chat/completions: 404 {"error":{"message":"Model not found, inaccessible, and/or not deployed","code":"NOT_FOUND"}}',
            "label_parse_error": "",
            "provider_readiness": "model_not_found",
            "provider_http_status": 404,
            "provider_error_code": "NOT_FOUND",
            "provider_error_message_short": "404 {\"error\":{\"message\":\"Model not found, inaccessible, and/or not deployed\",\"code\":\"NOT_FOUND\"}}",
        },
    ]

    summary = labeler._provider_readiness_summary(parsed_rows, ["cohere", "cerebras", "fireworks"])

    assert summary["provider_readiness_counts"]["cohere"]["ready"] == 1
    assert summary["provider_readiness_counts"]["cerebras"]["auth_error"] == 1
    assert summary["provider_readiness_counts"]["fireworks"]["model_not_found"] == 1
    assert summary["provider_error_samples"]["cerebras"][0]["provider_readiness"] == "auth_error"
    assert summary["provider_error_samples"]["fireworks"][0]["provider_http_status"] == 404


def test_provider_error_details_classify_mistral_http_errors() -> None:
    cases = [
        (401, "auth_error"),
        (403, "auth_error"),
        (404, "model_not_found"),
        (429, "rate_limited"),
        (500, "unknown_error"),
    ]

    for status_code, expected in cases:
        details = labeler._provider_error_details(
            label_status="api_error",
            api_error=f"HTTP error from https://api.mistral.ai/v1/chat/completions: {status_code} test-error",
        )
        assert details["provider_readiness"] == expected
        assert details["provider_http_status"] == status_code


def test_provider_error_details_extract_retry_after_from_rate_limit() -> None:
    details = labeler._provider_error_details(
        label_status="api_error",
        api_error="HTTP error from https://api.mistral.ai/v1/chat/completions: 429 rate limited retry_after=30",
    )

    assert details["provider_readiness"] == "rate_limited"
    assert details["provider_http_status"] == 429
    assert details["provider_retry_after"] == "30"


def test_pattern_discovery_summary_aggregates_names_stages_and_hypotheses() -> None:
    parsed_rows = [
        {
            "provider": "openai",
            "label_valid": True,
            "top_patterns": [
                {
                    "pattern_name": "target drift",
                    "likely_failure_stage": "target_extraction",
                    "supporting_case_ids": ["c1", "c2"],
                    "negative_or_uncertain_case_ids": ["c3"],
                },
                {
                    "pattern_name": "selector collapse",
                    "likely_failure_stage": "selector",
                    "supporting_case_ids": ["c4"],
                    "negative_or_uncertain_case_ids": ["c5", "c6"],
                },
            ],
        },
        {
            "provider": "cohere",
            "label_valid": True,
            "top_patterns": [
                {
                    "pattern_name": "target drift",
                    "likely_failure_stage": "target_extraction",
                    "supporting_case_ids": ["c7"],
                    "negative_or_uncertain_case_ids": ["c8"],
                },
                {
                    "pattern_name": "metadata gap",
                    "likely_failure_stage": "metadata",
                    "supporting_case_ids": ["c9", "c10"],
                    "negative_or_uncertain_case_ids": [],
                },
            ],
        },
        {
            "provider": "fireworks",
            "label_valid": False,
            "top_patterns": [
                {
                    "pattern_name": "ignored",
                    "likely_failure_stage": "unknown",
                    "supporting_case_ids": ["c11"],
                    "negative_or_uncertain_case_ids": [],
                }
            ],
        },
    ]

    summary = labeler._summarize_pattern_discovery(parsed_rows, ["openai", "cohere", "fireworks"])

    assert summary["provider_pattern_name_counts"]["openai"]["target drift"] == 1
    assert summary["provider_supporting_case_counts"]["openai"]["target drift"] == 2
    assert summary["provider_likely_failure_stage_distribution"]["openai"]["target_extraction"] == 1
    assert summary["provider_ambiguous_case_ids"]["openai"] == ["c3", "c5", "c6"]
    assert summary["provider_unique_hypotheses"]["openai"] == ["selector collapse"]
    assert summary["provider_unique_hypotheses"]["cohere"] == ["metadata gap"]
    assert summary["provider_total_pattern_rows"]["fireworks"] == 0
