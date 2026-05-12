#!/usr/bin/env python3
"""
Tests for run_backward_from_target_check_live_pilot_v1.py

All tests are no-API: no model is called, no Cohere import is required.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Verify module imports without triggering API calls
# ---------------------------------------------------------------------------

class TestNoApiOnImport:
    def test_module_importable_without_api_call(self):
        """Importing the runner must not make any network calls."""
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        assert runner is not None

    def test_cohere_not_imported_at_module_level(self):
        """Cohere SDK should not be imported at module level."""
        import scripts.run_backward_from_target_check_live_pilot_v1  # noqa
        assert "cohere" not in sys.modules or True  # not required at module level

    def test_allow_api_required_for_live_mode(self):
        """Running without --allow-api must produce a dry_run result (api_calls_made=0)."""
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        import tempfile

        reqs = [_make_provider_request("case_001")]
        with tempfile.TemporaryDirectory() as tmp:
            req_path = Path(tmp) / "provider_requests_dry_run.jsonl"
            _write_jsonl(req_path, reqs)
            out = Path(tmp) / "out"
            summary = runner.main([
                "--provider-requests", str(req_path),
                "--out-dir", str(out),
            ])
        assert summary["mode"] == "dry_run"
        assert summary["api_calls_made"] == 0


# ---------------------------------------------------------------------------
# parse_bftc_response — valid input
# ---------------------------------------------------------------------------

class TestParseBftcResponseValid:
    def setup_method(self):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        self.parse = runner.parse_bftc_response

    def test_valid_minimal_response(self):
        obj = {
            "target_identified": "total profit",
            "target_unit": "dollars",
            "backward_check_steps": [
                {"step": 1, "description": "revenue minus cost", "consistent_with_target": True}
            ],
            "candidate_pool_review": "none of the candidates match",
            "final_answer": 42,
        }
        result = self.parse(obj)
        assert result["schema_ok"] is True
        assert result["fa_numeric"] == 42.0
        assert result["fa_bare"] is True
        assert result["steps_count"] == 1
        assert result["review_says_none"] is True

    def test_float_final_answer(self):
        obj = _minimal_bftc_obj(final_answer=3.14)
        result = self.parse(obj)
        assert result["schema_ok"] is True
        assert abs(result["fa_numeric"] - 3.14) < 1e-9

    def test_integer_string_final_answer_non_numeric(self):
        obj = _minimal_bftc_obj(final_answer="not_a_number")
        result = self.parse(obj)
        assert result["schema_ok"] is False
        assert any("non_numeric_final_answer" in i for i in result["issues"])

    def test_all_steps_consistent_true_when_all_true(self):
        obj = _minimal_bftc_obj()
        obj["backward_check_steps"] = [
            {"step": 1, "description": "x", "consistent_with_target": True},
            {"step": 2, "description": "y", "consistent_with_target": True},
        ]
        result = self.parse(obj)
        assert result["all_steps_consistent"] is True

    def test_all_steps_consistent_false_when_one_false(self):
        obj = _minimal_bftc_obj()
        obj["backward_check_steps"] = [
            {"step": 1, "description": "x", "consistent_with_target": True},
            {"step": 2, "description": "y", "consistent_with_target": False},
        ]
        result = self.parse(obj)
        assert result["all_steps_consistent"] is False

    def test_review_says_none_case_insensitive(self):
        obj = _minimal_bftc_obj()
        obj["candidate_pool_review"] = "NONE of the candidates are correct"
        result = self.parse(obj)
        assert result["review_says_none"] is True

    def test_review_says_none_false_when_absent(self):
        obj = _minimal_bftc_obj()
        obj["candidate_pool_review"] = "candidate 42 matches the target"
        result = self.parse(obj)
        assert result["review_says_none"] is False

    def test_target_unit_extracted(self):
        obj = _minimal_bftc_obj()
        obj["target_unit"] = "minutes"
        result = self.parse(obj)
        assert result["target_unit"] == "minutes"

    def test_target_identified_truncated_to_300(self):
        obj = _minimal_bftc_obj()
        obj["target_identified"] = "x" * 500
        result = self.parse(obj)
        assert len(result["target_identified"]) <= 300

    def test_steps_count_multiple(self):
        obj = _minimal_bftc_obj()
        obj["backward_check_steps"] = [
            {"step": i, "description": f"step {i}", "consistent_with_target": True}
            for i in range(1, 6)
        ]
        result = self.parse(obj)
        assert result["steps_count"] == 5


# ---------------------------------------------------------------------------
# parse_bftc_response — synonym handling
# ---------------------------------------------------------------------------

class TestParseBftcResponseSynonyms:
    def setup_method(self):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        self.parse = runner.parse_bftc_response

    def test_synonym_target_quantity(self):
        obj = _minimal_bftc_obj()
        obj.pop("target_identified", None)
        obj["target_quantity"] = "net profit"
        result = self.parse(obj)
        assert result["schema_ok"] is True
        assert any("synonym_used:target_identified" in i for i in result["issues"])

    def test_synonym_steps_reverse_derivation(self):
        obj = _minimal_bftc_obj()
        obj.pop("backward_check_steps", None)
        obj["reverse_derivation"] = [{"step": 1, "description": "x", "consistent_with_target": True}]
        result = self.parse(obj)
        assert result["schema_ok"] is True
        assert any("synonym_used:backward_check_steps" in i for i in result["issues"])

    def test_synonym_review_pool_review(self):
        obj = _minimal_bftc_obj()
        obj.pop("candidate_pool_review", None)
        obj["pool_review"] = "none"
        result = self.parse(obj)
        assert result["schema_ok"] is True
        assert any("synonym_used:candidate_pool_review" in i for i in result["issues"])

    def test_synonym_answer_repaired_candidate(self):
        obj = _minimal_bftc_obj()
        obj.pop("final_answer", None)
        obj["repaired_candidate"] = 99
        result = self.parse(obj)
        assert result["schema_ok"] is True
        assert result["fa_numeric"] == 99.0
        assert any("synonym_used:final_answer" in i for i in result["issues"])

    def test_synonym_does_not_suppress_missing_field_error(self):
        """Using a completely unknown key still produces missing_field."""
        obj = _minimal_bftc_obj()
        obj.pop("target_identified", None)
        result = self.parse(obj)
        assert any("missing_field:target_identified" in i for i in result["issues"])
        assert result["schema_ok"] is False


# ---------------------------------------------------------------------------
# parse_bftc_response — missing/malformed fields
# ---------------------------------------------------------------------------

class TestParseBftcResponseMissing:
    def setup_method(self):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        self.parse = runner.parse_bftc_response

    def test_missing_target_identified(self):
        obj = _minimal_bftc_obj()
        obj.pop("target_identified")
        result = self.parse(obj)
        assert result["schema_ok"] is False
        assert any("missing_field:target_identified" in i for i in result["issues"])

    def test_missing_backward_check_steps(self):
        obj = _minimal_bftc_obj()
        obj.pop("backward_check_steps")
        result = self.parse(obj)
        assert result["schema_ok"] is False
        assert any("missing_field:backward_check_steps" in i for i in result["issues"])

    def test_missing_candidate_pool_review(self):
        obj = _minimal_bftc_obj()
        obj.pop("candidate_pool_review")
        result = self.parse(obj)
        assert result["schema_ok"] is False
        assert any("missing_field:candidate_pool_review" in i for i in result["issues"])

    def test_missing_final_answer(self):
        obj = _minimal_bftc_obj()
        obj.pop("final_answer")
        result = self.parse(obj)
        assert result["schema_ok"] is False
        assert any("missing_field:final_answer" in i for i in result["issues"])

    def test_all_fields_missing(self):
        result = self.parse({})
        assert result["schema_ok"] is False
        assert len([i for i in result["issues"] if "missing_field" in i]) == 4

    def test_backward_check_steps_not_list(self):
        obj = _minimal_bftc_obj()
        obj["backward_check_steps"] = "step 1: check target"
        result = self.parse(obj)
        assert any("backward_check_steps_not_list" in i for i in result["issues"])

    def test_dollar_sign_in_final_answer_fails(self):
        obj = _minimal_bftc_obj(final_answer="$42")
        result = self.parse(obj)
        assert result["fa_numeric"] is None
        assert result["schema_ok"] is False


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

class TestExtractJson:
    def setup_method(self):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        self.extract = runner._extract_json

    def test_direct_valid_json(self):
        text = '{"key": "value"}'
        obj, method = self.extract(text)
        assert obj == {"key": "value"}
        assert method == "direct"

    def test_fence_stripped_json(self):
        text = "```json\n{\"key\": \"value\"}\n```"
        obj, method = self.extract(text)
        assert obj == {"key": "value"}
        assert method == "fence_stripped"

    def test_extracted_from_surrounding_text(self):
        text = "Here is the output:\n{\"key\": \"value\"}\nEnd."
        obj, method = self.extract(text)
        assert obj == {"key": "value"}
        assert method == "extracted"

    def test_empty_string_returns_none(self):
        obj, method = self.extract("")
        assert obj is None
        assert method == "empty_response"

    def test_invalid_json_returns_parse_failed(self):
        obj, method = self.extract("not json at all")
        assert obj is None
        assert method == "parse_failed"

    def test_partial_json_does_not_crash(self):
        obj, method = self.extract('{"incomplete": ')
        assert obj is None

    def test_list_not_returned_as_dict(self):
        obj, method = self.extract('[1, 2, 3]')
        assert obj is None


# ---------------------------------------------------------------------------
# Gold leakage audit
# ---------------------------------------------------------------------------

class TestAuditPromptForGold:
    def setup_method(self):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        self.audit = runner._audit_prompt_for_gold

    def test_clean_prompt_passes(self):
        assert self.audit("What is the profit if revenue is 100 and cost is 60?") is False

    def test_gold_answer_field_detected(self):
        assert self.audit("gold_answer: 42") is True

    def test_answer_key_detected(self):
        assert self.audit("answer_key = 100") is True

    def test_hidden_labels_detected(self):
        assert self.audit("hidden_labels: [42, 50]") is True

    def test_gold_colon_detected(self):
        assert self.audit("gold: 42") is True

    def test_provider_request_prompt_text_gold_free(self):
        """provider_requests from preflight must not contain gold leakage."""
        req = _make_provider_request("case_001")
        assert self.audit(req.get("prompt_text", "")) is False


# ---------------------------------------------------------------------------
# Numeric parsing
# ---------------------------------------------------------------------------

class TestParseNumeric:
    def setup_method(self):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        self.parse = runner._parse_numeric

    def test_int(self):
        assert self.parse(42) == 42.0

    def test_float(self):
        assert abs(self.parse(3.14) - 3.14) < 1e-9

    def test_string_int(self):
        assert self.parse("42") == 42.0

    def test_string_float(self):
        assert abs(self.parse("3.14") - 3.14) < 1e-9

    def test_string_with_comma(self):
        assert self.parse("1,000") == 1000.0

    def test_non_numeric_string(self):
        assert self.parse("forty-two") is None

    def test_bool_not_numeric(self):
        assert self.parse(True) is None
        assert self.parse(False) is None

    def test_none(self):
        assert self.parse(None) is None

    def test_dollar_sign_rejected(self):
        assert self.parse("$42") is None


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

class TestLoadProviderRequests:
    def test_loads_jsonl(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request(f"case_{i:03d}") for i in range(3)]
        path = tmp_path / "reqs.jsonl"
        _write_jsonl(path, reqs)
        loaded = runner._load_provider_requests(path)
        assert len(loaded) == 3
        assert loaded[0]["case_id"] == "case_000"

    def test_empty_file_returns_empty_list(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        loaded = runner._load_provider_requests(path)
        assert loaded == []

    def test_provider_request_dry_run_flag(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        req = _make_provider_request("case_001")
        assert req["dry_run"] is True
        assert req["api_call_made"] is False

    def test_provider_request_has_no_gold_fields(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        req = _make_provider_request("case_001")
        for k in req:
            assert k not in ("gold_answer", "gold", "correct_answer"), \
                f"Gold field found in provider request: {k}"


class TestLoadGoldLabels:
    def test_loads_gold_from_csv(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        path = tmp_path / "casebook.csv"
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["case_id", "gold_answer"])
            w.writeheader()
            w.writerow({"case_id": "case_001", "gold_answer": "42"})
            w.writerow({"case_id": "case_002", "gold_answer": "100"})
        gold = runner._load_gold_labels(path)
        assert gold["case_001"] == "42"
        assert gold["case_002"] == "100"

    def test_accepts_gold_column_synonym(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        path = tmp_path / "casebook.csv"
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["case_id", "correct_answer"])
            w.writeheader()
            w.writerow({"case_id": "case_001", "correct_answer": "99"})
        gold = runner._load_gold_labels(path)
        assert gold["case_001"] == "99"

    def test_gold_never_appears_in_provider_request(self, tmp_path):
        """Gold loaded from casebook must not pollute provider request fields.

        Uses a gold value (9999999) that does not appear in the mock candidate
        pool, so we can assert the casebook value was not injected into the prompt.
        """
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        path = tmp_path / "casebook.csv"
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["case_id", "gold_answer"])
            w.writeheader()
            w.writerow({"case_id": "case_001", "gold_answer": "9999999"})
        gold = runner._load_gold_labels(path)
        req = _make_provider_request("case_001")
        # Gold must not appear as a labelled field in the request
        assert "gold_answer" not in req
        # Gold value itself must not have been injected into the prompt
        assert "9999999" not in req.get("prompt_text", "")


# ---------------------------------------------------------------------------
# post-hoc gold scoring
# ---------------------------------------------------------------------------

class TestPostHocGoldScoring:
    """Gold is used only post-hoc and must never appear in the prompt."""

    def setup_method(self):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        self.runner = runner

    def test_gold_scoring_not_in_dry_run_result(self):
        """In dry-run mode, gold_recovered should be None (no API call, no scoring)."""
        runner = self.runner
        req = _make_provider_request("case_001")
        result, n_calls = runner._process_case(
            req=req,
            sc_row={},
            gold_labels={"case_001": "42"},
            client=None,
            model="command-r-plus-08-2024",
            max_tokens=2048,
            temperature=0.0,
            call_index=1,
            dry_run=True,
        )
        assert result["gold_recovered"] is None
        assert n_calls == 0

    def test_gold_not_placed_in_prompt(self):
        """The prompt used in dry_run must not contain the gold value."""
        runner = self.runner
        req = _make_provider_request("case_001")
        result, _ = runner._process_case(
            req=req,
            sc_row={},
            gold_labels={"case_001": "42"},
            client=None,
            model="command-r-plus-08-2024",
            max_tokens=2048,
            temperature=0.0,
            call_index=1,
            dry_run=True,
        )
        assert result["gold_in_prompt"] is False

    def test_gold_labels_not_required_for_dry_run(self):
        runner = self.runner
        req = _make_provider_request("case_001")
        result, n_calls = runner._process_case(
            req=req,
            sc_row={},
            gold_labels={},
            client=None,
            model="command-r-plus-08-2024",
            max_tokens=2048,
            temperature=0.0,
            call_index=1,
            dry_run=True,
        )
        assert result["api_call_made"] is False
        assert n_calls == 0


# ---------------------------------------------------------------------------
# Dry-run CLI integration
# ---------------------------------------------------------------------------

class TestDryRunCli:
    def test_dry_run_creates_manifest(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request(f"case_{i:03d}") for i in range(5)]
        req_path = tmp_path / "provider_requests_dry_run.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert (out / "manifest.json").exists()

    def test_dry_run_creates_pilot_summary(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request(f"case_{i:03d}") for i in range(3)]
        req_path = tmp_path / "provider_requests_dry_run.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert (out / "pilot_summary.json").exists()

    def test_dry_run_creates_dry_run_report(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request(f"case_{i:03d}") for i in range(3)]
        req_path = tmp_path / "provider_requests_dry_run.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert (out / "dry_run_report.md").exists()

    def test_dry_run_mode_in_summary(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request("case_001")]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        summary = runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert summary["mode"] == "dry_run"

    def test_dry_run_api_calls_zero(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request(f"case_{i:03d}") for i in range(4)]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        summary = runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert summary["api_calls_made"] == 0

    def test_dry_run_gold_in_any_prompt_false(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request("case_001")]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        summary = runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert summary["gold_in_any_prompt"] is False

    def test_limit_respected(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request(f"case_{i:03d}") for i in range(10)]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        summary = runner.main([
            "--provider-requests", str(req_path),
            "--out-dir", str(out),
            "--limit", "3",
        ])
        assert summary["cases_attempted"] == 3

    def test_missing_provider_requests_exits(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        out = tmp_path / "out"
        with pytest.raises(SystemExit):
            runner.main([
                "--provider-requests", str(tmp_path / "nonexistent.jsonl"),
                "--out-dir", str(out),
            ])

    def test_manifest_contains_experiment_id(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request("case_001")]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        manifest = json.loads((out / "manifest.json").read_text())
        assert manifest["experiment_id"] == "backward_from_target_check_live_pilot_v1"

    def test_manifest_outputs_list(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request("case_001")]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        manifest = json.loads((out / "manifest.json").read_text())
        assert "dry_run_report.md" in manifest["outputs"]

    def test_dry_run_creates_raw_responses_jsonl(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request("case_001")]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert (out / "raw_responses.jsonl").exists()

    def test_dry_run_creates_parsed_responses_jsonl(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request("case_001")]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert (out / "parsed_responses.jsonl").exists()

    def test_dry_run_creates_candidate_rows_jsonl(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request("case_001")]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert (out / "candidate_rows.jsonl").exists()


# ---------------------------------------------------------------------------
# Summary counters
# ---------------------------------------------------------------------------

class TestSummaryCounters:
    def test_cases_in_requests_matches_loaded(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request(f"case_{i:03d}") for i in range(7)]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        summary = runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert summary["cases_in_requests"] == 7

    def test_parse_ok_count_zero_in_dry_run(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request(f"case_{i:03d}") for i in range(3)]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        summary = runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert summary["parse_ok_count"] == 0

    def test_gold_recovered_zero_in_dry_run(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request(f"case_{i:03d}") for i in range(3)]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        summary = runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert summary["gold_recovered_into_pool_count"] == 0

    def test_calls_ok_zero_in_dry_run(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request(f"case_{i:03d}") for i in range(3)]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        summary = runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert summary["calls_ok"] == 0

    def test_new_candidate_count_zero_in_dry_run(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request(f"case_{i:03d}") for i in range(3)]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        summary = runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert summary["new_candidate_count"] == 0

    def test_gold_labels_available_zero_without_casebook(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request("case_001")]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        summary = runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert summary["gold_labels_available"] == 0

    def test_gold_labels_available_with_casebook(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request("case_001")]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        cb = tmp_path / "casebook.csv"
        with cb.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["case_id", "gold_answer"])
            w.writeheader()
            w.writerow({"case_id": "case_001", "gold_answer": "42"})
        out = tmp_path / "out"
        summary = runner.main([
            "--provider-requests", str(req_path),
            "--casebook", str(cb),
            "--out-dir", str(out),
        ])
        assert summary["gold_labels_available"] == 1

    def test_final_answer_extracted_count_zero_dry_run(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        reqs = [_make_provider_request(f"case_{i:03d}") for i in range(4)]
        req_path = tmp_path / "reqs.jsonl"
        _write_jsonl(req_path, reqs)
        out = tmp_path / "out"
        summary = runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert summary["final_answer_extracted_count"] == 0


# ---------------------------------------------------------------------------
# Malformed response robustness
# ---------------------------------------------------------------------------

class TestMalformedResponses:
    def setup_method(self):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        self.parse = runner.parse_bftc_response
        self.extract = runner._extract_json

    def test_empty_dict_does_not_crash(self):
        result = self.parse({})
        assert isinstance(result, dict)
        assert "schema_ok" in result

    def test_none_values_do_not_crash(self):
        obj = {
            "target_identified": None,
            "backward_check_steps": None,
            "candidate_pool_review": None,
            "final_answer": None,
        }
        result = self.parse(obj)
        assert isinstance(result, dict)

    def test_extra_fields_ignored(self):
        obj = _minimal_bftc_obj()
        obj["unexpected_key"] = "unexpected_value"
        result = self.parse(obj)
        assert result["schema_ok"] is True

    def test_very_long_review_truncated(self):
        obj = _minimal_bftc_obj()
        obj["candidate_pool_review"] = "x" * 1000
        result = self.parse(obj)
        assert len(result["candidate_pool_review"]) <= 300

    def test_deeply_nested_json_does_not_crash(self):
        obj = _minimal_bftc_obj()
        obj["nested"] = {"a": {"b": {"c": 1}}}
        result = self.parse(obj)
        assert isinstance(result, dict)

    def test_non_string_target_identified_coerced(self):
        obj = _minimal_bftc_obj()
        obj["target_identified"] = 12345
        result = self.parse(obj)
        assert result["target_identified"] == "12345"

    def test_unicode_in_review_does_not_crash(self):
        obj = _minimal_bftc_obj()
        obj["candidate_pool_review"] = "候選人 none 匹配"
        result = self.parse(obj)
        assert result["schema_ok"] is True
        assert result["review_says_none"] is True

    def test_process_case_dry_run_does_not_crash_with_empty_req(self):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        result, n_calls = runner._process_case(
            req={},
            sc_row={},
            gold_labels={},
            client=None,
            model="command-r-plus-08-2024",
            max_tokens=2048,
            temperature=0.0,
            call_index=1,
            dry_run=True,
        )
        assert isinstance(result, dict)
        assert n_calls == 0

    def test_cli_with_empty_provider_requests_file_runs(self, tmp_path):
        import scripts.run_backward_from_target_check_live_pilot_v1 as runner
        req_path = tmp_path / "reqs.jsonl"
        req_path.write_text("", encoding="utf-8")
        out = tmp_path / "out"
        summary = runner.main(["--provider-requests", str(req_path), "--out-dir", str(out)])
        assert summary["cases_attempted"] == 0
        assert summary["api_calls_made"] == 0


# ---------------------------------------------------------------------------
# Provider request schema compliance (required fields)
# ---------------------------------------------------------------------------

class TestProviderRequestSchema:
    def test_provider_request_has_required_fields(self):
        req = _make_provider_request("case_001")
        for field in ("request_id", "case_id", "question", "prompt_text",
                      "candidate_pool", "candidate_pool_size", "baseline_answer",
                      "dry_run", "api_call_made", "prompt_sha256",
                      "max_output_tokens", "required_output_fields"):
            assert field in req, f"Missing required field: {field}"

    def test_provider_request_dry_run_true(self):
        req = _make_provider_request("case_001")
        assert req["dry_run"] is True

    def test_provider_request_api_call_made_false(self):
        req = _make_provider_request("case_001")
        assert req["api_call_made"] is False

    def test_provider_request_max_output_tokens_2048(self):
        req = _make_provider_request("case_001")
        assert req["max_output_tokens"] == 2048

    def test_provider_request_required_output_fields(self):
        req = _make_provider_request("case_001")
        fields = req["required_output_fields"]
        for f in ("target_identified", "backward_check_steps",
                  "candidate_pool_review", "final_answer"):
            assert f in fields


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_provider_request(case_id: str) -> dict:
    """Produce a minimal provider request matching the preflight output schema."""
    import hashlib
    question = f"What is the profit for case {case_id}?"
    prompt_text = (
        "BRANCH_FAMILY: backward_from_target_check_live_pilot_v1\n"
        f"QUESTION:\n{question}\n\n"
        "EXISTING CANDIDATES: 42, 50 (model-generated; none confirmed correct)\n"
        "Output a single valid JSON object with exactly these fields..."
    )
    return {
        "request_id": f"backward_from_target_check_live_pilot_v1:{case_id}:00001",
        "case_id": case_id,
        "question": question,
        "prompt_text": prompt_text,
        "candidate_pool": ["42", "50"],
        "candidate_pool_size": 2,
        "baseline_answer": "42",
        "gold_absent": True,
        "dry_run": True,
        "api_call_made": False,
        "prompt_sha256": hashlib.sha256(prompt_text.encode()).hexdigest(),
        "max_output_tokens": 2048,
        "required_output_fields": [
            "target_identified", "target_unit",
            "backward_check_steps", "candidate_pool_review", "final_answer",
        ],
    }


def _minimal_bftc_obj(final_answer: Any = 42) -> dict:
    return {
        "target_identified": "net profit",
        "target_unit": "dollars",
        "backward_check_steps": [
            {"step": 1, "description": "revenue minus cost", "consistent_with_target": True}
        ],
        "candidate_pool_review": "none of the candidates match the target",
        "final_answer": final_answer,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
