from __future__ import annotations

from pathlib import Path

from scripts import prepare_target_staged_pal_frontier_v1_preflight as preflight


def test_call_plan_rows_pass_through_structural_validator_and_feature_builder() -> None:
    manifest = preflight._json_load(preflight.DEFAULT_MANIFEST_PATH)
    case_rows = [
        {
            "slice_name": "guardrail",
            "slice_label": "four_way_pilot_30",
            "case_id": "openai_gsm8k_trace_compat",
            "case_ordinal": 1,
            "case_count_target": 30,
            "case_source": "synthetic",
            "question_source": "synthetic_placeholder",
            "question": "A book costs $12 and a pen costs $3. What is the total cost?",
            "source_path": "synthetic",
            "source_metadata": {},
        }
    ]

    call_plan_rows, trace_rows, feature_rows = preflight.build_call_plan(manifest=manifest, case_rows=case_rows)
    assert len(call_plan_rows) == 6
    assert len(trace_rows) == 6
    assert len(feature_rows) == 6

    row = feature_rows[0]
    assert row["target_tuple"] == preflight.validate_gsm8k_candidate(
        problem_text=case_rows[0]["question"],
        candidate_answer="",
        candidate_trace=trace_rows[0]["rendered_prompt"],
        candidate_code=None,
        source_family=trace_rows[0]["prompt_template_id"],
        execution_metadata=call_plan_rows[0]["execution_metadata"],
    )["target_tuple"]
    assert "entity_unit_ledger_proxy" in row
    assert "structural_selector_score" in row
    assert row["trace_compat_ok"] is True
    assert row["parse_ok"] is True
    assert row["render_ok"] is True
    assert row["no_gold_leak_ok"] is True
