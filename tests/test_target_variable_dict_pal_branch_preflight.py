from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.prepare_target_variable_dict_pal_branch_v1_preflight import (
    _extract_question_cues,
    _transformed_target_cue_count,
    _score_case,
    render_prompt,
    audit_prompt,
    _load_prompt_template,
    parse_gold_pool_report,
    main,
    EXPERIMENT_ID,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_case(
    case_id: str = "test_001",
    question: str = "How much profit did she earn?",
    gold_absent: bool = True,
) -> dict:
    return {
        "case_id": case_id,
        "question": question,
        "candidate_answers": ["42", "50"],
        "candidate_answer_groups": [],
        "structural_fields": {"candidate_rows": []},
        "pal_exec_summary": {"pal_exec_ok": "0", "pal_execution_status": ""},
        "selector_metadata": {
            "selected_answer": "42",
            "selected_source": "controller_metadata_final_answer",
            "selector_candidate_pool_size": 2,
            "gold_present_in_candidate_pool": "",
        },
        "failure_audit_labels": {"question_type": "money", "diversity_bucket": "low",
                                  "candidate_pool_status": "Both wrong", "num_candidate_groups": 1},
        "action_trace_summary": {"trace_excerpt": [], "action_trace_step_count": 2},
        "subset_memberships": [{
            "subset": "wrong_supported_consensus_97",
            "selection_logic": "gold_absent rows" if gold_absent else "gold_present rows",
        }],
        "primary_subset": "wrong_supported_consensus_97",
        "frontier_candidate_answer": "42",
        "direct_reserve_answer": "42",
    }


def _write_packets(path: Path, cases: list[dict]) -> None:
    batch = {"batch_id": "test", "case_count": len(cases), "cases": cases}
    path.write_text(json.dumps(batch) + "\n", encoding="utf-8")


def _write_casebook(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("case_id\n", encoding="utf-8")
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Cue extraction (gold-free)
# ---------------------------------------------------------------------------

class TestCueExtraction:
    def test_profit_cue(self):
        cues = _extract_question_cues("How much profit did she earn?")
        assert "profit_revenue_cost" in cues

    def test_ratio_cue(self):
        cues = _extract_question_cues("What percentage of items remain?")
        assert "ratio_base" in cues

    def test_difference_cue(self):
        cues = _extract_question_cues("How many apples are left after eating 3?")
        assert "difference_or_remainder" in cues

    def test_original_before_cue(self):
        cues = _extract_question_cues("Before the sale, what was the original price?")
        assert "original_before_process" in cues

    def test_per_unit_cue(self):
        cues = _extract_question_cues("How much does each item cost?")
        assert "per_unit_share" in cues

    def test_unit_conversion_cue(self):
        cues = _extract_question_cues("Convert 5 feet to meters.")
        assert "unit_conversion" in cues

    def test_no_cue(self):
        cues = _extract_question_cues("John has 3 apples.")
        assert cues == []

    def test_multiple_cues(self):
        cues = _extract_question_cues("What is the profit per item after conversion?")
        assert "profit_revenue_cost" in cues
        assert "per_unit_share" in cues

    def test_transformed_cue_count_nonzero(self):
        count = _transformed_target_cue_count("How much profit remains after cost?")
        assert count >= 2

    def test_transformed_cue_count_zero(self):
        count = _transformed_target_cue_count("John has 3 apples.")
        assert count == 0


# ---------------------------------------------------------------------------
# parse_gold_pool_report
# ---------------------------------------------------------------------------

def _write_mock_gold_pool_report(path: Path, gold_absent_ids: list[str], gold_present_ids: list[str]) -> None:
    lines = [
        "# Mock gold pool report",
        "",
        "## A. gold_present_not_selected",
        "",
        "| case_id | question_type |",
        "|---|---|",
    ]
    for cid in gold_present_ids:
        lines.append(f"| {cid} | entity_value |")
    lines += [
        "",
        "## B. gold_absent_from_pool",
        "",
        "### branch (N)",
        "",
        "| case_id | question_type | selected prediction |",
        "|---|---|---|",
    ]
    for cid in gold_absent_ids:
        lines.append(f"| {cid} | entity_value | 42 |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestParseGoldPoolReport:
    def test_returns_correct_gold_absent_ids(self, tmp_path):
        absent = ["case_001", "case_002", "case_003"]
        present = ["case_004", "case_005"]
        report = tmp_path / "report.md"
        _write_mock_gold_pool_report(report, absent, present)
        gold_absent, gold_present = parse_gold_pool_report(report)
        assert gold_absent == set(absent)
        assert gold_present == set(present)

    def test_header_row_excluded(self, tmp_path):
        report = tmp_path / "report.md"
        _write_mock_gold_pool_report(report, ["case_001"], ["case_002"])
        gold_absent, gold_present = parse_gold_pool_report(report)
        assert "case_id" not in gold_absent
        assert "case_id" not in gold_present

    def test_empty_sections(self, tmp_path):
        report = tmp_path / "report.md"
        report.write_text(
            "## A. gold_present_not_selected\n\n## B. gold_absent_from_pool\n\n",
            encoding="utf-8",
        )
        gold_absent, gold_present = parse_gold_pool_report(report)
        assert gold_absent == set()
        assert gold_present == set()

    def test_disjoint_sets(self, tmp_path):
        absent = [f"case_{i:03d}" for i in range(5)]
        present = [f"case_{i:03d}" for i in range(5, 8)]
        report = tmp_path / "report.md"
        _write_mock_gold_pool_report(report, absent, present)
        gold_absent, gold_present = parse_gold_pool_report(report)
        assert gold_absent & gold_present == set()

    def test_count_matches_sections(self, tmp_path):
        absent = [f"case_{i:03d}" for i in range(70)]
        present = [f"case_{i:03d}" for i in range(70, 91)]
        report = tmp_path / "report.md"
        _write_mock_gold_pool_report(report, absent, present)
        gold_absent, gold_present = parse_gold_pool_report(report)
        assert len(gold_absent) == 70
        assert len(gold_present) == 21


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

class TestScoring:
    def test_bftc_det_rec_adds_3(self):
        s = _score_case("c1", "profit", ["profit_revenue_cost"], 1, "backward_from_target_check", "")
        assert s >= 3

    def test_bftc_heldout_label_adds_2(self):
        s = _score_case("c1", "profit", [], 0, "", "backward_from_target_check")
        assert s >= 2

    def test_transformed_cue_adds_2(self):
        s_with = _score_case("c1", "q", [], 3, "", "")
        s_without = _score_case("c1", "q", [], 0, "", "")
        assert s_with > s_without

    def test_cues_add_score(self):
        s_multi = _score_case("c1", "q", ["profit_revenue_cost", "ratio_base"], 0, "", "")
        s_none = _score_case("c1", "q", [], 0, "", "")
        assert s_multi > s_none

    def test_combined_score(self):
        s = _score_case("c1", "q", ["profit_revenue_cost", "ratio_base"], 2, "backward_from_target_check", "backward_from_target_check")
        assert s >= 3 + 2 + 2 + 2  # det_rec + heldout + cues + transformed


# ---------------------------------------------------------------------------
# Prompt rendering and gold audit
# ---------------------------------------------------------------------------

class TestPromptAudit:
    def test_render_replaces_placeholder(self):
        template = "Q: {{question}}\nAnswer:"
        rendered = render_prompt(template, "What is 2+2?")
        assert "{{question}}" not in rendered
        assert "What is 2+2?" in rendered

    def test_render_raises_on_unresolved_placeholder(self):
        template = "Q: {{question}} and {{other}}"
        with pytest.raises(ValueError, match="unresolved placeholder"):
            render_prompt(template, "test question")

    def test_audit_gold_free_clean_prompt(self):
        result = audit_prompt("Solve this math problem: 5 + 3 = ?", "c001")
        assert result["gold_free"] is True
        assert result["violations"] == []

    def test_audit_detects_gold_answer_leak(self):
        result = audit_prompt("gold_answer: 42\nSolve: 5 + 3", "c001")
        assert result["gold_free"] is False
        assert len(result["violations"]) > 0

    def test_audit_detects_answer_key_leak(self):
        result = audit_prompt("answer_key: 42", "c001")
        assert result["gold_free"] is False

    def test_audit_detects_gold_colon_leak(self):
        result = audit_prompt("gold: 100", "c001")
        assert result["gold_free"] is False

    def test_audit_includes_sha256(self):
        result = audit_prompt("hello", "c001")
        assert len(result["prompt_sha256"]) == 64

    def test_real_template_is_gold_free(self):
        template = _load_prompt_template()
        rendered = render_prompt(template, "How much profit did she earn from selling 10 items at $5 each?")
        result = audit_prompt(rendered, "smoke_test")
        assert result["gold_free"] is True, f"Template leaked gold: {result['violations']}"

    def test_real_template_has_no_unresolved_placeholders(self):
        template = _load_prompt_template()
        rendered = render_prompt(template, "Test question.")
        assert "{{" not in rendered
        assert "}}" not in rendered


# ---------------------------------------------------------------------------
# Schema field requirements (prompt content checks)
# ---------------------------------------------------------------------------

class TestPromptSchema:
    def _get_rendered(self, question: str = "How much profit did she earn?") -> str:
        template = _load_prompt_template()
        return render_prompt(template, question)

    def test_prompt_requires_problem_summary(self):
        rendered = self._get_rendered()
        assert "problem_summary" in rendered

    def test_prompt_requires_target_question(self):
        rendered = self._get_rendered()
        assert "target_question" in rendered

    def test_prompt_requires_target_variable_name(self):
        rendered = self._get_rendered()
        assert "target_variable_name" in rendered

    def test_prompt_requires_target_unit(self):
        rendered = self._get_rendered()
        assert "target_unit" in rendered

    def test_prompt_requires_variables(self):
        rendered = self._get_rendered()
        assert '"variables"' in rendered

    def test_prompt_requires_rejected_non_final_variables(self):
        rendered = self._get_rendered()
        assert "rejected_non_final_variables" in rendered

    def test_prompt_requires_answer_variable_name(self):
        rendered = self._get_rendered()
        assert "answer_variable_name" in rendered

    def test_prompt_requires_final_answer(self):
        rendered = self._get_rendered()
        assert "final_answer" in rendered

    def test_prompt_forbids_generic_variable_names(self):
        rendered = self._get_rendered()
        # Prompt must explicitly say to not use generic names
        assert "generic" in rendered.lower() or "semantic" in rendered.lower()

    def test_prompt_requires_bare_numeric_final_answer(self):
        rendered = self._get_rendered()
        # Prompt must state no $, %, commas, or units in final_answer
        assert "bare" in rendered.lower() or "no $" in rendered or "no `$`" in rendered

    def test_prompt_requires_answer_variable_equals_target(self):
        rendered = self._get_rendered()
        assert "answer_variable_name" in rendered
        assert "target_variable_name" in rendered


# ---------------------------------------------------------------------------
# CLI / integration
# ---------------------------------------------------------------------------

class TestCLISmoke:
    _QUESTIONS = [
        "How much profit did she earn after paying costs?",
        "What percentage of items remain after selling?",
        "How many apples are left after eating 3?",
        "What was the original price before the discount?",
        "How much does each item cost per unit?",
        "Convert 5 feet to meters.",
        "If there are 10 items shared equally among 2 people, how many per person?",
        "A simple addition problem: 5 + 3.",
        "What is the total after adding 10 and 20?",
        "How many more does Alice have than Bob?",
    ]

    def _write_packets_and_report(self, tmp_path: Path, n_gold_absent: int = 7):
        """Write trace packets and a matching gold pool report."""
        packets = tmp_path / "packets.jsonl"
        report = tmp_path / "report.md"
        n_cases = len(self._QUESTIONS)

        cases = [
            _make_case(f"case_{i:03d}", gold_absent=True, question=q)
            for i, q in enumerate(self._QUESTIONS)
        ]
        _write_packets(packets, cases)

        absent_ids = [f"case_{i:03d}" for i in range(n_gold_absent)]
        present_ids = [f"case_{i:03d}" for i in range(n_gold_absent, n_cases)]
        _write_mock_gold_pool_report(report, absent_ids, present_ids)
        return packets, report

    def _run(self, tmp_path: Path, **kwargs) -> dict:
        packets, report = self._write_packets_and_report(
            tmp_path, n_gold_absent=kwargs.pop("n_gold_absent", 7)
        )
        out_dir = tmp_path / "out"

        argv = [
            "--trace-packets", str(packets),
            "--gold-pool-report", str(report),
            "--out-dir", str(out_dir),
            "--subset", kwargs.get("subset", "gold_absent"),
        ]
        if "limit" in kwargs:
            argv += ["--limit", str(kwargs["limit"])]

        return main(argv)

    def test_all_outputs_exist(self, tmp_path):
        result = self._run(tmp_path)
        out_dir = Path(result["out_dir"])
        for fname in result["outputs"]:
            assert (out_dir / fname).exists(), f"Missing: {fname}"

    def test_no_api_calls(self, tmp_path):
        result = self._run(tmp_path)
        assert result["api_calls_made"] == 0

    def test_gold_leakage_not_allowed(self, tmp_path):
        result = self._run(tmp_path)
        assert result["gold_leakage_allowed"] is False

    def test_all_prompts_gold_free(self, tmp_path):
        result = self._run(tmp_path)
        assert result["all_prompts_gold_free"] is True

    def test_subset_gold_absent_uses_report_ids(self, tmp_path):
        """gold_absent selection must use report IDs, not subset_memberships inference."""
        result = self._run(tmp_path, subset="gold_absent", n_gold_absent=7)
        # Exactly 7 gold-absent IDs in the report → 7 selected
        assert result["cases_selected"] == 7, (
            f"Expected 7 (from report), got {result['cases_selected']}. "
            "Likely falling back to batch-level selection_logic inference."
        )

    def test_subset_gold_absent_not_all_cases(self, tmp_path):
        """Under --subset gold_absent, must not select all 10 cases when only 7 are gold-absent."""
        result = self._run(tmp_path, subset="gold_absent", n_gold_absent=7)
        assert result["cases_selected"] != 10, (
            "Selected all 10 cases under --subset gold_absent — "
            "the batch-level selection_logic bug is still present."
        )

    def test_case_selection_source_is_gold_pool_report(self, tmp_path):
        result = self._run(tmp_path)
        assert result["case_selection_source"] == "gold_pool_report"

    def test_gold_absent_ids_from_report_in_manifest(self, tmp_path):
        result = self._run(tmp_path, n_gold_absent=7)
        assert result["gold_absent_ids_from_report"] == 7

    def test_subset_all_includes_all(self, tmp_path):
        result = self._run(tmp_path, subset="all")
        assert result["cases_selected"] == 10

    def test_limit_respected(self, tmp_path):
        result = self._run(tmp_path, subset="all", limit=3)
        assert result["cases_selected"] == 3

    def test_without_report_uses_all_wrong_consensus_label(self, tmp_path):
        """Without --gold-pool-report, manifest must not claim gold_absent selection."""
        packets = tmp_path / "packets.jsonl"
        out_dir = tmp_path / "out"
        cases = [_make_case(f"case_{i:03d}", gold_absent=True, question=q)
                 for i, q in enumerate(self._QUESTIONS)]
        _write_packets(packets, cases)

        result = main([
            "--trace-packets", str(packets),
            "--out-dir", str(out_dir),
            "--subset", "gold_absent",
        ])
        assert result["case_selection_source"] == "all_wrong_consensus_cases", (
            "Without a gold pool report, must not claim gold_absent source."
        )
        # All 10 cases included because we can't filter without the report
        assert result["cases_selected"] == 10

    def test_provider_requests_have_required_fields(self, tmp_path):
        result = self._run(tmp_path)
        out_dir = Path(result["out_dir"])
        rows = []
        with open(out_dir / "provider_requests_dry_run.jsonl") as f:
            for line in f:
                rows.append(json.loads(line))
        required = ["request_id", "case_id", "prompt_text", "dry_run",
                    "api_call_made", "prompt_sha256", "max_output_tokens"]
        for row in rows:
            for field in required:
                assert field in row, f"Missing field '{field}' in provider request"

    def test_provider_requests_are_dry_run(self, tmp_path):
        result = self._run(tmp_path)
        out_dir = Path(result["out_dir"])
        with open(out_dir / "provider_requests_dry_run.jsonl") as f:
            for line in f:
                row = json.loads(line)
                assert row["dry_run"] is True
                assert row["api_call_made"] is False

    def test_routing_summary_has_case_ids(self, tmp_path):
        result = self._run(tmp_path)
        out_dir = Path(result["out_dir"])
        with open(out_dir / "routing_summary.csv") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0
        assert all("case_id" in r for r in rows)

    def test_prompt_audit_all_pass(self, tmp_path):
        result = self._run(tmp_path)
        out_dir = Path(result["out_dir"])
        with open(out_dir / "prompt_audit.json") as f:
            audit = json.load(f)
        assert audit["all_gold_free"] is True
        assert audit["violations"] == []

    def test_selected_cases_have_scores(self, tmp_path):
        result = self._run(tmp_path)
        out_dir = Path(result["out_dir"])
        rows = []
        with open(out_dir / "selected_cases.jsonl") as f:
            for line in f:
                rows.append(json.loads(line))
        assert all("score" in r for r in rows)
        assert all("gold_absent" in r for r in rows)

    def test_cue_distribution_in_manifest(self, tmp_path):
        result = self._run(tmp_path)
        assert "cue_distribution" in result
        assert isinstance(result["cue_distribution"], dict)

    def test_no_gold_in_question_cue_features(self, tmp_path):
        result = self._run(tmp_path)
        # Gold fields must not appear in cue_distribution keys
        for key in result["cue_distribution"]:
            assert "gold" not in key.lower()


# ---------------------------------------------------------------------------
# Optional input integration
# ---------------------------------------------------------------------------

class TestOptionalInputs:
    def test_missing_edge_recs_boost_score(self, tmp_path):
        """Cases with bftc det_rec should rank higher than those without."""
        packets = tmp_path / "packets.jsonl"
        recs_path = tmp_path / "recs.csv"
        report = tmp_path / "report.md"
        out_dir = tmp_path / "out"

        n = 4
        cases = [_make_case(f"case_{i:03d}", gold_absent=True,
                             question="How much profit after costs?")
                 for i in range(n)]
        _write_packets(packets, cases)

        # All 4 cases are gold-absent
        _write_mock_gold_pool_report(report, [f"case_{i:03d}" for i in range(n)], [])

        # Only case_000 gets the bftc recommendation
        with open(recs_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["case_id", "primary_recommendation",
                                              "recommended_next_edges", "recommendation_reasons"])
            w.writeheader()
            w.writerow({"case_id": "case_000", "primary_recommendation": "backward_from_target_check",
                        "recommended_next_edges": '["backward_from_target_check"]', "recommendation_reasons": "test"})
            for i in range(1, n):
                w.writerow({"case_id": f"case_{i:03d}", "primary_recommendation": "none",
                            "recommended_next_edges": '["none"]', "recommendation_reasons": "test"})

        result = main([
            "--trace-packets", str(packets),
            "--gold-pool-report", str(report),
            "--missing-edge-recommendations", str(recs_path),
            "--out-dir", str(out_dir),
            "--subset", "gold_absent",
        ])
        out_dir_path = Path(result["out_dir"])
        with open(out_dir_path / "selected_cases.jsonl") as f:
            rows = [json.loads(line) for line in f]

        # case_000 (bftc rec) should appear first
        assert rows[0]["case_id"] == "case_000"
