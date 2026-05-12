"""Tests for prepare_backward_from_target_check_live_pilot_v1_preflight.py (no API)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.prepare_backward_from_target_check_live_pilot_v1_preflight import (
    EXPERIMENT_ID,
    _REQUIRED_OUTPUT_FIELDS,
    _build_candidate_pool_summary,
    _extract_candidate_pool,
    _load_prompt_template,
    _select_cases,
    audit_prompt,
    main,
    parse_gold_pool_report,
    render_prompt,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_case(
    case_id: str = "test_001",
    question: str = "How much profit did she earn?",
    candidates: list[str] | None = None,
    selected_answer: str = "42",
) -> dict:
    if candidates is None:
        candidates = ["42", "50"]
    return {
        "case_id": case_id,
        "question": question,
        "candidate_answers": candidates,
        "selector_metadata": {
            "selected_answer": selected_answer,
            "selector_candidate_pool_size": len(candidates),
            "gold_present_in_candidate_pool": "",
        },
        "frontier_candidate_answer": selected_answer,
        "subset_memberships": [{"subset": "wrong_supported_consensus_97"}],
        "primary_subset": "wrong_supported_consensus_97",
    }


def _write_packets(path: Path, cases: list[dict]) -> None:
    batch = {"batch_id": "test", "case_count": len(cases), "cases": cases}
    path.write_text(json.dumps(batch) + "\n", encoding="utf-8")


def _write_gold_pool_report(
    path: Path,
    gold_absent_ids: list[str],
    gold_present_ids: list[str],
) -> None:
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


def _run(tmp_path: Path, cases: list[dict], **kwargs) -> dict:
    packets = tmp_path / "packets.jsonl"
    _write_packets(packets, cases)
    out_dir = tmp_path / "out"

    argv = ["--trace-packets", str(packets), "--out-dir", str(out_dir)]

    if "gold_absent_ids" in kwargs:
        report = tmp_path / "report.md"
        _write_gold_pool_report(
            report,
            kwargs["gold_absent_ids"],
            kwargs.get("gold_present_ids", []),
        )
        argv += ["--gold-pool-report", str(report)]
    if "limit" in kwargs:
        argv += ["--limit", str(kwargs["limit"])]

    return main(argv)


# ---------------------------------------------------------------------------
# Module-level: no API clients at import time
# ---------------------------------------------------------------------------

class TestNoApiAtImport:
    def test_module_loads_without_api_keys(self):
        # If this import succeeds without env vars, no API client is constructed.
        import scripts.prepare_backward_from_target_check_live_pilot_v1_preflight  # noqa: F401

    def test_no_cohere_in_module(self):
        import inspect
        import scripts.prepare_backward_from_target_check_live_pilot_v1_preflight as mod
        src = inspect.getsource(mod)
        assert "cohere.ClientV2" not in src
        assert "import cohere" not in src

    def test_no_openai_in_module(self):
        import inspect
        import scripts.prepare_backward_from_target_check_live_pilot_v1_preflight as mod
        src = inspect.getsource(mod)
        assert "import openai" not in src
        assert "openai.Client" not in src

    def test_no_cerebras_client_in_module(self):
        import inspect
        import scripts.prepare_backward_from_target_check_live_pilot_v1_preflight as mod
        src = inspect.getsource(mod)
        assert "cerebras.cloud" not in src


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

class TestPromptTemplate:
    def test_template_loads(self):
        template = _load_prompt_template()
        assert len(template) > 50

    def test_template_has_question_placeholder(self):
        template = _load_prompt_template()
        assert "{{question}}" in template

    def test_template_has_candidate_pool_placeholder(self):
        template = _load_prompt_template()
        assert "{{candidate_pool_summary}}" in template

    def test_template_mentions_backward_reasoning(self):
        template = _load_prompt_template()
        assert "backward" in template.lower()

    def test_template_mentions_target(self):
        template = _load_prompt_template()
        assert "target" in template.lower()

    def test_template_requires_final_answer(self):
        template = _load_prompt_template()
        assert "final_answer" in template

    def test_template_requires_backward_check_steps(self):
        template = _load_prompt_template()
        assert "backward_check_steps" in template

    def test_template_requires_candidate_pool_review(self):
        template = _load_prompt_template()
        assert "candidate_pool_review" in template

    def test_template_requires_bare_number(self):
        template = _load_prompt_template()
        assert "bare" in template.lower() or "no $" in template or "no `$`" in template

    def test_template_forbids_gold_reference(self):
        template = _load_prompt_template()
        lower = template.lower()
        assert "reference answer" in lower or "hidden" in lower or "label metadata" in lower


# ---------------------------------------------------------------------------
# render_prompt
# ---------------------------------------------------------------------------

class TestRenderPrompt:
    def _template(self) -> str:
        return _load_prompt_template()

    def test_replaces_question(self):
        rendered = render_prompt(self._template(), "What is 2+2?", "(no candidates)")
        assert "What is 2+2?" in rendered
        assert "{{question}}" not in rendered

    def test_replaces_candidate_pool_summary(self):
        rendered = render_prompt(self._template(), "Q?", "42, 50")
        assert "42, 50" in rendered
        assert "{{candidate_pool_summary}}" not in rendered

    def test_raises_on_unresolved_placeholder(self):
        template = "Q: {{question}} and {{other}}"
        with pytest.raises(ValueError, match="Unresolved placeholder"):
            render_prompt(template, "test", "candidates")

    def test_no_unresolved_placeholders_after_render(self):
        rendered = render_prompt(self._template(), "Test question?", "42, 100")
        assert "{{" not in rendered
        assert "}}" not in rendered


# ---------------------------------------------------------------------------
# audit_prompt (gold leakage detection)
# ---------------------------------------------------------------------------

class TestAuditPrompt:
    def test_clean_prompt_is_gold_free(self):
        result = audit_prompt("Solve: 5 + 3 = ?", "c001")
        assert result["gold_free"] is True
        assert result["violations"] == []

    def test_gold_answer_leak_detected(self):
        result = audit_prompt("gold_answer: 42\nSolve: ...", "c001")
        assert result["gold_free"] is False
        assert len(result["violations"]) > 0

    def test_answer_key_leak_detected(self):
        result = audit_prompt("answer_key: 42", "c001")
        assert result["gold_free"] is False

    def test_gold_colon_leak_detected(self):
        result = audit_prompt("gold: 100", "c001")
        assert result["gold_free"] is False

    def test_sha256_present(self):
        result = audit_prompt("hello world", "c001")
        assert len(result["prompt_sha256"]) == 64

    def test_real_template_is_gold_free(self):
        template = _load_prompt_template()
        rendered = render_prompt(
            template,
            "How much profit did she earn from selling 10 items at $5 each?",
            "42, 50 (these are model-generated values; none confirmed correct)",
        )
        result = audit_prompt(rendered, "smoke_test")
        assert result["gold_free"] is True, f"Template leaked gold: {result['violations']}"

    def test_candidate_pool_values_alone_do_not_trigger_leak(self):
        template = _load_prompt_template()
        rendered = render_prompt(
            template, "How many?", "100, 200, 300 (model-generated; none confirmed correct)"
        )
        result = audit_prompt(rendered, "c002")
        assert result["gold_free"] is True


# ---------------------------------------------------------------------------
# _extract_candidate_pool
# ---------------------------------------------------------------------------

class TestExtractCandidatePool:
    def test_extracts_string_candidates(self):
        case = _make_case(candidates=["42", "50", "100"])
        assert _extract_candidate_pool(case) == ["42", "50", "100"]

    def test_extracts_numeric_candidates(self):
        case = _make_case(candidates=[42, 50])
        pool = _extract_candidate_pool(case)
        assert "42" in pool
        assert "50" in pool

    def test_empty_candidates(self):
        case = _make_case(candidates=[])
        assert _extract_candidate_pool(case) == []

    def test_missing_field(self):
        case = {"case_id": "x", "question": "q"}
        assert _extract_candidate_pool(case) == []

    def test_filters_empty_strings(self):
        case = _make_case(candidates=["42", "", "  ", "50"])
        pool = _extract_candidate_pool(case)
        assert "" not in pool
        assert "42" in pool
        assert "50" in pool


# ---------------------------------------------------------------------------
# _build_candidate_pool_summary
# ---------------------------------------------------------------------------

class TestBuildCandidatePoolSummary:
    def test_empty_returns_placeholder(self):
        summary = _build_candidate_pool_summary([])
        assert "no prior" in summary.lower()

    def test_values_appear_in_summary(self):
        summary = _build_candidate_pool_summary(["42", "50"])
        assert "42" in summary
        assert "50" in summary

    def test_summary_says_not_confirmed(self):
        summary = _build_candidate_pool_summary(["42"])
        lower = summary.lower()
        assert "confirmed" in lower or "not" in lower or "none" in lower

    def test_no_gold_reference_in_summary(self):
        summary = _build_candidate_pool_summary(["42", "100"])
        assert "gold" not in summary.lower()
        assert "correct" in summary.lower() or "confirmed" in summary.lower()


# ---------------------------------------------------------------------------
# parse_gold_pool_report
# ---------------------------------------------------------------------------

class TestParseGoldPoolReport:
    def test_returns_gold_absent_ids(self, tmp_path):
        report = tmp_path / "report.md"
        _write_gold_pool_report(report, ["case_001", "case_002"], ["case_003"])
        absent, present = parse_gold_pool_report(report)
        assert "case_001" in absent
        assert "case_002" in absent
        assert "case_003" in present

    def test_header_excluded(self, tmp_path):
        report = tmp_path / "report.md"
        _write_gold_pool_report(report, ["case_001"], ["case_002"])
        absent, present = parse_gold_pool_report(report)
        assert "case_id" not in absent
        assert "case_id" not in present

    def test_empty_sections(self, tmp_path):
        report = tmp_path / "report.md"
        report.write_text(
            "## A. gold_present_not_selected\n\n## B. gold_absent_from_pool\n\n",
            encoding="utf-8",
        )
        absent, present = parse_gold_pool_report(report)
        assert absent == set()
        assert present == set()

    def test_disjoint_sets(self, tmp_path):
        report = tmp_path / "report.md"
        _write_gold_pool_report(report, ["a1", "a2"], ["b1", "b2"])
        absent, present = parse_gold_pool_report(report)
        assert absent & present == set()

    def test_count_matches(self, tmp_path):
        absent_ids = [f"case_{i:03d}" for i in range(70)]
        present_ids = [f"case_{i:03d}" for i in range(70, 91)]
        report = tmp_path / "report.md"
        _write_gold_pool_report(report, absent_ids, present_ids)
        absent, present = parse_gold_pool_report(report)
        assert len(absent) == 70
        assert len(present) == 21


# ---------------------------------------------------------------------------
# _select_cases
# ---------------------------------------------------------------------------

class TestSelectCases:
    def _cases(self, n: int) -> list[dict]:
        return [_make_case(f"case_{i:03d}") for i in range(n)]

    def test_limit_respected(self):
        cases = self._cases(10)
        selected = _select_cases(cases, None, 5)
        assert len(selected) == 5

    def test_deterministic_order(self):
        cases = self._cases(10)
        s1 = _select_cases(cases, None, 5)
        s2 = _select_cases(list(reversed(cases)), None, 5)
        assert [c["case_id"] for c in s1] == [c["case_id"] for c in s2]

    def test_filters_by_gold_absent_ids(self):
        cases = self._cases(10)
        gold_absent = {"case_000", "case_002", "case_004"}
        selected = _select_cases(cases, gold_absent, 10)
        ids = {c["case_id"] for c in selected}
        assert ids == gold_absent

    def test_no_duplicates(self):
        cases = self._cases(10)
        selected = _select_cases(cases, None, 10)
        ids = [c["case_id"] for c in selected]
        assert len(ids) == len(set(ids))

    def test_limit_larger_than_pool(self):
        cases = self._cases(3)
        selected = _select_cases(cases, None, 20)
        assert len(selected) == 3

    def test_empty_gold_absent_ids_returns_nothing(self):
        cases = self._cases(5)
        selected = _select_cases(cases, set(), 10)
        assert selected == []


# ---------------------------------------------------------------------------
# main (CLI integration)
# ---------------------------------------------------------------------------

class TestCLISmoke:
    def _cases(self, n: int = 5) -> list[dict]:
        return [
            _make_case(
                f"case_{i:03d}",
                question=f"How much profit from {i} items?",
                candidates=[str(i * 10), str(i * 10 + 5)],
            )
            for i in range(n)
        ]

    def test_all_outputs_exist(self, tmp_path):
        result = _run(tmp_path, self._cases())
        out_dir = Path(result["out_dir"])
        for fname in result["outputs"]:
            assert (out_dir / fname).exists(), f"Missing output: {fname}"

    def test_api_calls_zero(self, tmp_path):
        result = _run(tmp_path, self._cases())
        assert result["api_calls_made"] == 0

    def test_gold_leakage_not_allowed(self, tmp_path):
        result = _run(tmp_path, self._cases())
        assert result["gold_leakage_allowed"] is False

    def test_all_prompts_gold_free(self, tmp_path):
        result = _run(tmp_path, self._cases())
        assert result["all_prompts_gold_free"] is True

    def test_limit_applied(self, tmp_path):
        result = _run(tmp_path, self._cases(10), limit=3)
        assert result["cases_selected"] == 3

    def test_gold_pool_report_filters_correctly(self, tmp_path):
        cases = self._cases(6)
        gold_absent = [f"case_{i:03d}" for i in range(4)]
        result = _run(tmp_path, cases, gold_absent_ids=gold_absent)
        assert result["cases_selected"] == 4
        assert result["case_selection_source"] == "gold_pool_report"

    def test_without_report_uses_all_wrong_consensus(self, tmp_path):
        result = _run(tmp_path, self._cases(5))
        assert result["case_selection_source"] == "all_wrong_consensus_cases"
        assert result["cases_selected"] == 5

    def test_missing_trace_packets_exits(self, tmp_path):
        out_dir = tmp_path / "out"
        with pytest.raises(SystemExit):
            main([
                "--trace-packets", str(tmp_path / "nonexistent.jsonl"),
                "--out-dir", str(out_dir),
            ])

    def test_missing_gold_pool_report_exits(self, tmp_path):
        packets = tmp_path / "packets.jsonl"
        _write_packets(packets, self._cases(3))
        out_dir = tmp_path / "out"
        with pytest.raises(SystemExit):
            main([
                "--trace-packets", str(packets),
                "--gold-pool-report", str(tmp_path / "nonexistent.md"),
                "--out-dir", str(out_dir),
            ])


# ---------------------------------------------------------------------------
# Provider request schema
# ---------------------------------------------------------------------------

class TestProviderRequestSchema:
    def _get_requests(self, tmp_path: Path) -> list[dict]:
        cases = [
            _make_case(f"case_{i:03d}", f"Question {i}?", [str(i * 10)])
            for i in range(3)
        ]
        result = _run(tmp_path, cases)
        out_dir = Path(result["out_dir"])
        rows = []
        with open(out_dir / "provider_requests_dry_run.jsonl") as f:
            for line in f:
                rows.append(json.loads(line))
        return rows

    def test_required_fields_present(self, tmp_path):
        rows = self._get_requests(tmp_path)
        required = [
            "request_id", "case_id", "question", "prompt_text",
            "candidate_pool", "baseline_answer", "dry_run",
            "api_call_made", "prompt_sha256", "max_output_tokens",
            "required_output_fields",
        ]
        for row in rows:
            for field in required:
                assert field in row, f"Missing field '{field}' in request {row.get('case_id')}"

    def test_dry_run_true(self, tmp_path):
        rows = self._get_requests(tmp_path)
        assert all(r["dry_run"] is True for r in rows)

    def test_api_call_made_false(self, tmp_path):
        rows = self._get_requests(tmp_path)
        assert all(r["api_call_made"] is False for r in rows)

    def test_max_output_tokens_is_2048(self, tmp_path):
        rows = self._get_requests(tmp_path)
        assert all(r["max_output_tokens"] == 2048 for r in rows)

    def test_required_output_fields_present(self, tmp_path):
        rows = self._get_requests(tmp_path)
        for row in rows:
            assert set(_REQUIRED_OUTPUT_FIELDS).issubset(set(row["required_output_fields"]))

    def test_prompt_text_is_gold_free(self, tmp_path):
        rows = self._get_requests(tmp_path)
        for row in rows:
            result = audit_prompt(row["prompt_text"], row["case_id"])
            assert result["gold_free"] is True, (
                f"Gold leak in prompt for {row['case_id']}: {result['violations']}"
            )

    def test_prompt_text_contains_question(self, tmp_path):
        rows = self._get_requests(tmp_path)
        for row in rows:
            assert row["question"] in row["prompt_text"]

    def test_prompt_text_contains_backward_instruction(self, tmp_path):
        rows = self._get_requests(tmp_path)
        for row in rows:
            assert "backward" in row["prompt_text"].lower()

    def test_prompt_text_contains_final_answer_field(self, tmp_path):
        rows = self._get_requests(tmp_path)
        for row in rows:
            assert "final_answer" in row["prompt_text"]

    def test_request_id_unique(self, tmp_path):
        rows = self._get_requests(tmp_path)
        ids = [r["request_id"] for r in rows]
        assert len(ids) == len(set(ids))

    def test_sha256_matches_prompt(self, tmp_path):
        import hashlib
        rows = self._get_requests(tmp_path)
        for row in rows:
            expected = hashlib.sha256(row["prompt_text"].encode()).hexdigest()
            assert row["prompt_sha256"] == expected

    def test_gold_absent_field_present(self, tmp_path):
        rows = self._get_requests(tmp_path)
        for row in rows:
            assert "gold_absent" in row


# ---------------------------------------------------------------------------
# Prompt audit output
# ---------------------------------------------------------------------------

class TestPromptAuditOutput:
    def test_all_gold_free_in_audit(self, tmp_path):
        cases = [_make_case(f"case_{i:03d}") for i in range(3)]
        result = _run(tmp_path, cases)
        out_dir = Path(result["out_dir"])
        with open(out_dir / "prompt_audit.json") as f:
            audit = json.load(f)
        assert audit["all_gold_free"] is True
        assert audit["violations"] == []

    def test_per_case_audit_entries(self, tmp_path):
        cases = [_make_case(f"case_{i:03d}") for i in range(3)]
        result = _run(tmp_path, cases)
        out_dir = Path(result["out_dir"])
        with open(out_dir / "prompt_audit.json") as f:
            audit = json.load(f)
        assert len(audit["per_case"]) == 3
        assert all("prompt_sha256" in e for e in audit["per_case"])


# ---------------------------------------------------------------------------
# REQUIRED_OUTPUT_FIELDS constant
# ---------------------------------------------------------------------------

class TestRequiredOutputFields:
    def test_has_target_identified(self):
        assert "target_identified" in _REQUIRED_OUTPUT_FIELDS

    def test_has_backward_check_steps(self):
        assert "backward_check_steps" in _REQUIRED_OUTPUT_FIELDS

    def test_has_final_answer(self):
        assert "final_answer" in _REQUIRED_OUTPUT_FIELDS

    def test_has_candidate_pool_review(self):
        assert "candidate_pool_review" in _REQUIRED_OUTPUT_FIELDS

    def test_experiment_id_correct(self):
        assert EXPERIMENT_ID == "backward_from_target_check_live_pilot_v1"
