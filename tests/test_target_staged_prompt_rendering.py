from __future__ import annotations

from scripts import prepare_target_staged_pal_frontier_v1_preflight as preflight


def test_all_prompt_templates_render_without_placeholders() -> None:
    question = "A book costs $12 and a pen costs $3. What is the total cost?"
    schema = preflight.build_target_schema(question, case_id="openai_gsm8k_synth", slice_name="guardrail")

    for template_id in preflight.PROMPT_TEMPLATE_IDS:
        rendered = preflight.render_prompt(template_id, question=question, target_schema=schema)
        assert "{{" not in rendered and "}}" not in rendered
        assert question in rendered
        assert f"BRANCH_FAMILY: {template_id}" in rendered
        assert "bind the final target" in rendered.lower()
        if template_id == "target_schema_prepass":
            assert "TARGET_SCHEMA_JSON" not in rendered
        else:
            assert "TARGET_SCHEMA_JSON" in rendered
