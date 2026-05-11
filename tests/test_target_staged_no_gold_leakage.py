from __future__ import annotations

from scripts import prepare_target_staged_pal_frontier_v1_preflight as preflight


def test_rendered_prompts_do_not_leak_gold_fields() -> None:
    question = "Maddy is buying pizza for her cousin's soccer game. How much does she spend?"
    schema = preflight.build_target_schema(question, case_id="openai_gsm8k_leak", slice_name="caution")

    for template_id in preflight.PROMPT_TEMPLATE_IDS:
        rendered = preflight.render_prompt(template_id, question=question, target_schema=schema)
        assert preflight._contains_forbidden_prompt_markers(rendered) == []
        lowered = rendered.lower()
        assert "gold_answer:" not in lowered
        assert "answer_key:" not in lowered
        assert "hidden labels:" not in lowered
