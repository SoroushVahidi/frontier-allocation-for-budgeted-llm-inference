from __future__ import annotations

import json
from pathlib import Path

from scripts import label_failure_mechanisms_multi_api as labeler


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_subset_selectors_recover_expected_counts_from_repo_artifacts() -> None:
    failure_rows = labeler._read_csv_rows(labeler.DEFAULT_FAILURE_CSV)
    gold_rows = labeler._read_csv_rows(labeler.DEFAULT_GOLD_ABSENT_CSV)
    anchor_rows = labeler._read_csv_rows(labeler.DEFAULT_ANCHOR_EFFECT_CSV)

    pal_ids, pal_meta = labeler._select_pal_still_failing_case_ids(failure_rows)
    wrong_ids, wrong_meta = labeler._select_wrong_supported_consensus_case_ids(gold_rows)
    anchor_ids, anchor_meta = labeler._select_direct_l1_anchor_potential_case_ids(anchor_rows)
    diag_30_ids, diag_30_meta = labeler._select_exact_case_ids(labeler.DEFAULT_DIAGNOSTIC_30_JSONL, "diagnostic_30")
    target_15_ids, target_15_meta = labeler._select_exact_case_ids(labeler.DEFAULT_TARGET_STAGED_15_JSONL, "target_staged_15")

    assert len(pal_ids) == 157
    assert len(wrong_ids) == 97
    assert len(anchor_ids) == 43
    assert len(diag_30_ids) == 30
    assert len(target_15_ids) == 15

    assert pal_meta["approximate"] is True
    assert wrong_meta["approximate"] is True
    assert anchor_meta["approximate"] is True
    assert diag_30_meta["approximate"] is False
    assert target_15_meta["approximate"] is False


def test_prompt_rendering_and_label_schema_validation() -> None:
    packet = {
        "case_id": "c1",
        "primary_subset": "diagnostic_30",
        "subset_memberships": [{"subset": "diagnostic_30", "rank": 1, "approximate": False, "selection_logic": "exact"}],
        "question": "If a box has 3 apples and 4 pears, how many fruits are there in total?",
        "model_final_prediction": "7",
        "candidate_answers": ["7", "8"],
        "candidate_answer_groups": [{"candidate_answer": "7", "support_count": 2}],
        "selector_metadata": {"selected_source": "frontier"},
        "action_trace_summary": {"failure_family": "unknown"},
        "pal_exec_summary": {"pal_execution_status": "success"},
        "structural_fields": {"target_tuple": {"question_kind": "count"}},
        "failure_audit_labels": {"question_type": "multi-step arithmetic"},
        "prompt_template_id": labeler.DEFAULT_PROMPT_TEMPLATE_ID,
        "include_gold_for_labeling": False,
        "gold_assisted": False,
    }
    prompt = labeler._render_prompt(packet)
    assert "primary_label" in prompt
    assert "candidate_pool_status" in prompt
    assert "gold_answer" not in prompt.lower()
    assert "answer_key" not in prompt.lower()

    valid = labeler._parse_label_json(
        json.dumps(
            {
                "case_id": "c1",
                "primary_label": "wrong_target_variable",
                "secondary_labels": ["wrong_relation", "wrong_target_variable"],
                "selector_vs_generation": "generation_failure",
                "candidate_pool_status": "gold_absent",
                "confidence": 0.75,
                "evidence": "The final target is misread.",
                "recommended_fix_family": "target_schema",
            }
        )
    )
    payload, error = valid
    assert error == ""
    assert payload is not None
    assert payload["label_valid"] is True
    assert payload["primary_label"] == "wrong_target_variable"
    assert payload["secondary_labels"] == ["wrong_relation", "wrong_target_variable"]

    invalid_payload, invalid_error = labeler._parse_label_json(
        json.dumps(
            {
                "case_id": "c1",
                "primary_label": "not_a_label",
                "secondary_labels": [],
                "selector_vs_generation": "unknown",
                "candidate_pool_status": "unknown",
                "confidence": 2.0,
                "evidence": "",
                "recommended_fix_family": "unknown",
            }
        )
    )
    assert invalid_error == ""
    assert invalid_payload is not None
    assert invalid_payload["label_valid"] is False
    assert "invalid_primary_label" in invalid_payload["label_errors"]
    assert "invalid_confidence" in invalid_payload["label_errors"]


def test_pattern_discovery_prompt_rendering_and_schema_validation() -> None:
    batch_packet = {
        "provider": "mistral",
        "model": "mistral-small-latest",
        "batch_id": "mistral:2:abc123",
        "cases_reviewed": ["c1", "c2"],
        "case_count": 2,
        "cases": [
            {
                "case_id": "c1",
                "question": "Question c1",
                "candidate_answers": ["7"],
                "candidate_answer_groups": [],
                "selector_metadata": {},
                "action_trace_summary": {},
                "pal_exec_summary": {},
                "structural_fields": {"target_tuple": {"question_kind": "count"}},
                "failure_audit_labels": {},
                "primary_subset": "diagnostic_30",
                "subset_memberships": [{"subset": "diagnostic_30", "rank": 1, "approximate": False, "selection_logic": "exact"}],
            }
        ],
        "mode": "pattern_discovery",
        "prompt_template_id": "failure_mechanism_multi_api_pattern_v1",
        "include_gold_for_labeling": False,
        "gold_assisted": False,
        "non_cohere_policy": "Allowed only for pattern discovery, not for algorithm comparison.",
        "not_accuracy_comparison": True,
    }
    prompt = labeler._render_pattern_prompt(batch_packet)
    assert "pattern discovery" in prompt.lower()
    assert "accuracy comparison" in prompt.lower()
    assert "gold_answer" not in prompt.lower()
    assert "answer_key" not in prompt.lower()

    parsed, error = labeler._parse_pattern_discovery_json(
        "```json\n"
        + json.dumps(
            {
                "provider": "mistral",
                "model": "mistral-small-latest",
                "batch_id": "mistral:2:abc123",
                "cases_reviewed": ["c1", "c2"],
                "top_patterns": [
                    {
                        "pattern_name": "target extraction drift",
                        "description": "The target variable is misread before solving.",
                        "supporting_case_ids": ["c1"],
                        "negative_or_uncertain_case_ids": ["c2"],
                        "confidence": 0.82,
                        "evidence_summary": "The trace shows the wrong target being carried into the solution.",
                        "likely_failure_stage": "target_extraction",
                    }
                ],
                "recommended_taxonomy_changes": ["Add target binding diagnostics."],
                "what_extra_metadata_is_needed": ["target schema"],
                "do_not_claim": ["This is not an accuracy comparison."],
            }
        )
        + "\n```"
    )
    assert error == ""
    assert parsed is not None
    assert parsed["pattern_valid"] is True
    assert parsed["label_valid"] is True
    assert parsed["cases_reviewed"] == ["c1", "c2"]
    assert parsed["top_patterns"][0]["likely_failure_stage"] == "target_extraction"

    invalid_parsed, invalid_error = labeler._parse_pattern_discovery_json(
        json.dumps(
            {
                "provider": "mistral",
                "model": "mistral-small-latest",
                "batch_id": "mistral:2:abc123",
                "cases_reviewed": ["c1"],
                "top_patterns": [
                    {
                        "pattern_name": "bad",
                        "description": "bad",
                        "supporting_case_ids": [],
                        "negative_or_uncertain_case_ids": [],
                        "confidence": 0.5,
                        "evidence_summary": "evidence",
                        "likely_failure_stage": "not_a_stage",
                    }
                ],
                "recommended_taxonomy_changes": [],
                "what_extra_metadata_is_needed": [],
                "do_not_claim": [],
            }
        )
    )
    assert invalid_error == ""
    assert invalid_parsed is not None
    assert invalid_parsed["pattern_valid"] is False
    assert "invalid_likely_failure_stage" in invalid_parsed["pattern_errors"]
