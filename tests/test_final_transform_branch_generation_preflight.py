from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import prepare_final_transform_branch_generation_v1_preflight as preflight


def _write_trace_packets(path: Path, cases: list[dict[str, str]]) -> None:
    payload = {"batch_id": "test", "case_count": len(cases), "cases": cases}
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_gold_absent_report(path: Path, rows: list[tuple[str, str, str, str, str, str]]) -> None:
    lines = [
        "# Wrong-supported-consensus gold-pool split",
        "",
        "## B. gold_absent_from_pool",
        "",
        "| case_id | question_type | selected prediction | nearest candidate values | final-transform subtype | generation branch needed |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("question", "expected_family"),
    [
        ("What fraction of the total is 12?", "ratio_base_branch"),
        ("Out of the total, what percent is 12?", "ratio_base_branch"),
        ("What is the probability the team wins?", "ratio_base_branch"),
        ("What was the original amount before the price doubled?", "original_before_process_branch"),
        ("What amount did they have initially after doubling and losing some?", "original_before_process_branch"),
        ("If 18 apples are split evenly, how many does each person get?", "per_unit_share_branch"),
        ("What is the profit if revenue is $20 and cost is $12?", "profit_revenue_cost_branch"),
        ("How many more apples are there than oranges?", "difference_or_remainder_branch"),
        ("Convert 3 hours to minutes.", "unit_conversion_branch"),
    ],
)
def test_question_routing_targets_expected_branch_family(question: str, expected_family: str) -> None:
    families, cues, reason = preflight.classify_branch_families(question)
    assert expected_family in families
    assert cues
    assert reason


def test_prompt_rendering_has_no_placeholders_or_gold_markers() -> None:
    question = "What percentage of the total is 12?"
    schema = preflight.build_target_schema(question, case_id="openai_gsm8k_demo")

    for template_id in preflight.PROMPT_TEMPLATE_IDS:
        rendered = preflight.render_prompt(template_id, question=question, target_schema=schema)
        assert "{{" not in rendered and "}}" not in rendered
        assert question in rendered
        assert f"BRANCH_FAMILY: {template_id}" in rendered
        lowered = rendered.lower()
        assert "gold_answer" not in lowered
        assert "answer_key" not in lowered
        assert "hidden labels" not in lowered


def test_target_first_fallback_routes_multi_step_transformed_target() -> None:
    question = "Wendy is five times as old as Colin will be seven years from now. What is Colin's age now?"
    families, cues, reason = preflight.classify_branch_families(question, "10[pal_candidate|0.4], 7[baseline_candidate|0.3], 12[retry_candidate|0.2]")
    assert families == ["target_first_final_transform_branch"]
    assert cues == []
    assert "fallback" in reason


def test_target_first_fallback_routes_comparative_ratio_story() -> None:
    question = "Jerry has two pools, both with leaks emptying them out at 4 gallons/minute. 4 minutes ago, the big pool had twice as much water as the small pool. Now the big pool has four times as much water as the small pool. How much water does the small pool have now?"
    families, cues, reason = preflight.classify_branch_families(question, "12[pal_candidate|0.4], 7[baseline_candidate|0.3], 10[retry_candidate|0.2]")
    assert families == ["target_first_final_transform_branch"]
    assert cues == []
    assert "fallback" in reason


def test_ratio_priority_beats_generic_target_first() -> None:
    question = "Out of the total, what fraction is 12?"
    families, cues, reason = preflight.classify_branch_families(question, "12[baseline_candidate|0.4], 3[pal_candidate|0.3], 4[retry_candidate|0.2]")
    assert families == ["ratio_base_branch"]
    assert "ratio_base" in cues
    assert "fallback" not in reason


def test_profit_priority_beats_ratio_and_per_unit() -> None:
    question = "Each box is $100.00 and currently 10% off. If he buys 2 boxes, how much will it cost?"
    families, cues, reason = preflight.classify_branch_families(question, "100[pal_candidate|0.4], 90[baseline_candidate|0.3], 2[retry_candidate|0.2]")
    assert families == ["profit_revenue_cost_branch"]
    assert "profit_revenue_cost" in cues
    assert "ratio_base" in cues
    assert "per_unit_share" not in cues
    assert "fallback" not in reason


def test_dry_run_creates_call_plan_and_stays_within_branch_slots(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace_packets.jsonl"
    report_path = tmp_path / "gold_pool_report.md"
    out_dir = tmp_path / "out"

    _write_trace_packets(
        trace_path,
        [
            {
                "case_id": "openai_gsm8k_ratio",
                "question": "What percentage of the total is 12?",
                "selector_candidate_pool": ["12", "3", "4"],
                "candidate_answers": ["12", "3", "4"],
            },
            {
                "case_id": "openai_gsm8k_original",
                "question": "What was the original amount before the price doubled?",
                "selector_candidate_pool": ["10", "20"],
                "candidate_answers": ["10", "20"],
            },
            {
                "case_id": "openai_gsm8k_fallback",
                "question": "Wendy is five times as old as Colin will be seven years from now. What is Colin's age now?",
                "selector_candidate_pool": ["10", "7", "12"],
                "candidate_answers": ["10", "7", "12"],
            },
        ],
    )
    _write_gold_absent_report(
        report_path,
        [
            (
                "openai_gsm8k_ratio",
                "ratio_part",
                "12",
                "12[baseline_candidate|0.1], 3[pal_candidate|0.2]",
                "mistargeted_final_transformation",
                "ratio-base branch",
            ),
            (
                "openai_gsm8k_original",
                "remaining",
                "20",
                "20[baseline_candidate|0.1], 10[pal_candidate|0.2]",
                "mistargeted_final_transformation",
                "original-before-process branch",
            ),
            (
                "openai_gsm8k_fallback",
                "entity_value",
                "7",
                "10[baseline_candidate|0.1], 7[pal_candidate|0.2], 12[retry_candidate|0.3]",
                "other",
                "target-first final-transform",
            ),
        ],
    )

    summary = preflight.run(
        [
            "--trace-packets",
            str(trace_path),
            "--gold-pool-report",
            str(report_path),
            "--out-dir",
            str(out_dir),
            "--timestamp",
            "20260512T010101Z",
            "--max-branch-slots-per-case",
            "1",
        ]
    )

    assert summary["case_count"] == 3
    assert summary["selected_case_count"] == 3
    assert summary["call_plan_row_count"] == 3
    assert summary["no_api_clients_constructed"] is True
    assert summary["branch_family_counts"]["target_first_final_transform_branch"] == 1
    assert (out_dir / "manifest.json").is_file()
    assert (out_dir / "call_plan.jsonl").is_file()
    assert (out_dir / "routing_summary.csv").is_file()
    assert (out_dir / "dry_run_report.md").is_file()

    call_plan_rows = [json.loads(line) for line in (out_dir / "call_plan.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(call_plan_rows) == 3
    assert {row["selected_branch_family"] for row in call_plan_rows} == {
        "ratio_base_branch",
        "original_before_process_branch",
        "target_first_final_transform_branch",
    }
    assert all(row["render_ok"] for row in call_plan_rows)
    assert all(row["no_gold_leak_ok"] for row in call_plan_rows)
    assert summary["branch_family_counts"]["target_first_final_transform_branch"] == 1
    assert summary["branch_family_counts"]["ratio_base_branch"] == 1


def test_fixed_budget_does_not_append_more_than_configured_slots(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace_packets.jsonl"
    report_path = tmp_path / "gold_pool_report.md"
    out_dir = tmp_path / "out"

    _write_trace_packets(
        trace_path,
        [
            {
                "case_id": "openai_gsm8k_multi_cue",
                "question": "What percentage is each person paying per item?",
                "selector_candidate_pool": ["1", "2", "3"],
                "candidate_answers": ["1", "2", "3"],
            }
        ],
    )
    _write_gold_absent_report(
        report_path,
        [
            (
                "openai_gsm8k_multi_cue",
                "ratio_part",
                "2",
                "2[baseline_candidate|0.1], 3[pal_candidate|0.2]",
                "mistargeted_final_transformation",
                "ratio-base branch",
            )
        ],
    )

    summary = preflight.run(
        [
            "--trace-packets",
            str(trace_path),
            "--gold-pool-report",
            str(report_path),
            "--out-dir",
            str(out_dir),
            "--timestamp",
            "20260512T020202Z",
            "--max-branch-slots-per-case",
            "1",
        ]
    )
    assert summary["call_plan_row_count"] == 1
    rows = [json.loads(line) for line in (out_dir / "call_plan.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["branch_slot"] == 1
    assert rows[0]["selected_branch_family"] in preflight.BRANCH_FAMILIES


def test_target_first_prompt_renders_without_placeholders() -> None:
    question = "Wendy is five times as old as Colin will be seven years from now. What is Colin's age now?"
    schema = preflight.build_target_schema(question, case_id="openai_gsm8k_fallback")
    rendered = preflight.render_prompt("target_first_final_transform_branch", question=question, target_schema=schema)
    assert "{{" not in rendered and "}}" not in rendered
    assert "BRANCH_FAMILY: target_first_final_transform_branch" in rendered
    assert "gold_answer" not in rendered.lower()
    assert "answer_key" not in rendered.lower()
