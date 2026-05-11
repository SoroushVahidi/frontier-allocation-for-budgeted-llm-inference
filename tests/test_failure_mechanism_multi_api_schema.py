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
