from __future__ import annotations

import json

from scripts import prepare_target_staged_pal_frontier_v1_preflight as preflight


def test_target_schema_roundtrip_preserves_required_keys_and_uncertainty() -> None:
    raw = {
        "target_variable": "final total cost",
        "entity": "cost",
        "unit": "money",
        "time_or_state": "final_state",
        "operation_goal": "add",
        "known_quantities": [
            {"name": "price", "value": "12", "unit": "money"},
            {"name": "fee", "value": "3", "unit": "money"},
        ],
        "required_relations": ["bind_target:final total cost", "preserve_unit_consistency"],
        "uncertainty": True,
        "extra_field": "ignored",
    }

    parsed = preflight.parse_target_schema(raw)
    assert "extra_field" not in parsed
    assert parsed["uncertainty"] is True
    assert parsed["known_quantities"][0]["name"] == "price"

    serialized = preflight.serialize_target_schema(parsed)
    reparsed = preflight.parse_target_schema(json.loads(serialized))
    assert reparsed == parsed


def test_build_target_schema_has_expected_keys() -> None:
    schema = preflight.build_target_schema(
        "A book costs $12 and a pen costs $3. What is the total cost?",
        case_id="openai_gsm8k_synth",
        slice_name="primary",
    )
    assert set(schema) == {
        "target_variable",
        "entity",
        "unit",
        "time_or_state",
        "operation_goal",
        "known_quantities",
        "required_relations",
        "uncertainty",
    }
    assert schema["target_variable"]
    assert schema["required_relations"]
