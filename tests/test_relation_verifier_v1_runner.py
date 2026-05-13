"""Tests for run_relation_verifier_v1.py (no API)."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import run_relation_verifier_v1 as runner


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _write_casebook(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "gold_answer"])
        writer.writeheader()
        writer.writerows(rows)


def _provider_request(case_id: str = "openai_gsm8k_1021") -> dict:
    return {
        "request_id": f"req:{case_id}",
        "case_id": case_id,
        "question": "How many pieces of paper would be used in a 32-page tabloid?",
        "requested_target": "number of pieces of paper for a 32-page tabloid",
        "prompt_text": "QUESTION:\nHow many pieces of paper would be used in a 32-page tabloid?\nREQUESTED_TARGET:\nnumber of pieces of paper for a 32-page tabloid\nCANDIDATE_CONTEXT:\n{\"primary_candidate_source\": \"declarative_v2\", \"candidate\": {\"solution_formula\": \"total_pages / pages_per_piece\"}}",
        "candidate_sources": ["declarative_v2", "declarative_v1", "bftc_executable"],
        "primary_candidate_source": "declarative_v2",
        "topology_metadata": {"missing_edge_type": "relation_composition_missing"},
        "dry_run": True,
        "api_call_made": False,
        "prompt_sha256": "placeholder",
        "max_output_tokens": 1024,
        "required_output_fields": runner._REQUIRED_FIELDS,
    }


def _valid_response() -> dict:
    return {
        "target_relation_correct": True,
        "target_variable_correct": True,
        "source_facts_sufficient": True,
        "equations_match_source_facts": True,
        "process_state_correct": True,
        "unit_scale_correct": True,
        "arithmetic_executable": True,
        "error_type": "none",
        "failed_relation": "",
        "repair_hint": "",
        "confidence": 0.95,
    }


class _FakeCohereClient:
    def __init__(self, response_obj):
        self.response_obj = response_obj
        self.calls: list[dict] = []

    def chat(self, *, model: str, message: str, max_tokens: int, temperature: float):
        self.calls.append(
            {
                "model": model,
                "message": message,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        return self.response_obj


class _MessageWithContent:
    def __init__(self, content):
        self.content = content


class _BlockWithText:
    def __init__(self, text: str):
        self.text = text


class _ResponseWithText:
    def __init__(self, text: str):
        self.text = text
        self.usage = {"input_tokens": 1}


class _ResponseWithMessage:
    def __init__(self, message):
        self.message = message
        self.usage = {"input_tokens": 1}


class _ResponseWithGenerations:
    def __init__(self, text: str):
        self.generations = [type("Generation", (), {"text": text})()]
        self.usage = {"input_tokens": 1}


class _ResponseWithNestedResponse:
    def __init__(self, text: str):
        self.response = type("NestedResponse", (), {"text": text})()
        self.usage = {"input_tokens": 1}


class TestNoApiAtImport:
    def test_module_imports_without_network_activity(self):
        assert runner.EXPERIMENT_ID == "relation_verifier_v1"
        first_lines = "\n".join(Path(runner.__file__).read_text(encoding="utf-8").splitlines()[:40])
        assert "import cohere" not in first_lines


class TestValidation:
    def test_valid_response_parses(self):
        parsed = runner.parse_relation_verifier_response(_valid_response())
        assert parsed["schema_ok"] is True
        assert parsed["error_type"] == "none"
        assert parsed["confidence"] == 0.95
        assert parsed["target_relation_correct"] is True

    def test_rejects_malformed_json_gracefully(self):
        obj, method = runner._extract_json("not json")
        assert obj is None
        assert method == "parse_failed"

    def test_extract_cohere_text_from_response_text(self):
        text, source, issue = runner._extract_cohere_text(_ResponseWithText('{"ok": true}'))
        assert text == '{"ok": true}'
        assert source == "response.text"
        assert issue is None

    def test_extract_cohere_text_from_message(self):
        response = _ResponseWithMessage(_MessageWithContent([_BlockWithText('{"ok": true}')]))
        text, source, issue = runner._extract_cohere_text(response)
        assert text == '{"ok": true}'
        assert source == "response.message.content"
        assert issue is None

    def test_extract_cohere_text_from_generations(self):
        text, source, issue = runner._extract_cohere_text(_ResponseWithGenerations('{"ok": true}'))
        assert text == '{"ok": true}'
        assert source == "response.generations[0].text"
        assert issue is None

    def test_extract_cohere_text_from_dict_text(self):
        text, source, issue = runner._extract_cohere_text({"text": '{"ok": true}'})
        assert text == '{"ok": true}'
        assert source == "response.text"
        assert issue is None

    def test_extract_cohere_text_from_dict_message_content(self):
        response = {"message": {"content": [{"text": '{"ok": true}'}]}}
        text, source, issue = runner._extract_cohere_text(response)
        assert text == '{"ok": true}'
        assert source == "response.message.content"
        assert issue is None

    def test_extract_cohere_text_from_content_list(self):
        response = {"content": [{"text": '{"ok": true}'}]}
        text, source, issue = runner._extract_cohere_text(response)
        assert text == '{"ok": true}'
        assert source == "response.content"
        assert issue is None

    def test_extract_cohere_text_from_message_string(self):
        response = _ResponseWithMessage('{"ok": true}')
        text, source, issue = runner._extract_cohere_text(response)
        assert text == '{"ok": true}'
        assert source == "response.message"
        assert issue is None

    def test_extract_cohere_text_from_dict_generations(self):
        response = {"generations": [{"text": '{"ok": true}'}]}
        text, source, issue = runner._extract_cohere_text(response)
        assert text == '{"ok": true}'
        assert source == "dict.generations[0].text"
        assert issue is None

    def test_extract_cohere_text_empty_response_sets_issue(self):
        text, source, issue = runner._extract_cohere_text({})
        assert text == ""
        assert source == "unavailable"
        assert issue == "no_text_found"

    def test_call_cohere_uses_message_parameter_and_extracts_text(self):
        client = _FakeCohereClient(_ResponseWithText('{"ok": true}'))
        text, usage, diagnostics = runner._call_cohere(client, "command-r-plus-08-2024", "prompt text", 256, 0.0)
        assert text == '{"ok": true}'
        assert client.calls == [
            {
                "model": "command-r-plus-08-2024",
                "message": "prompt text",
                "max_tokens": 256,
                "temperature": 0.0,
            }
        ]
        assert isinstance(usage, dict)
        assert diagnostics["extraction_source"] == "response.text"
        assert diagnostics["extraction_issue"] is None
        assert diagnostics["response_type"] == "_ResponseWithText"

    def test_call_cohere_extracts_text_from_nested_response(self):
        client = _FakeCohereClient(_ResponseWithNestedResponse('{"ok": true}'))
        text, _, diagnostics = runner._call_cohere(client, "command-r-plus-08-2024", "prompt text", 256, 0.0)
        assert text == '{"ok": true}'
        assert diagnostics["extraction_source"] == "response.response.text"

    def test_schema_validation_catches_missing_fields(self):
        parsed = runner.parse_relation_verifier_response(
            {
                "target_relation_correct": True,
                "target_variable_correct": True,
                "source_facts_sufficient": True,
                "equations_match_source_facts": True,
                "process_state_correct": True,
                "unit_scale_correct": True,
                "arithmetic_executable": True,
                "error_type": "none",
                "failed_relation": "",
                "repair_hint": "",
            }
        )
        assert parsed["schema_ok"] is False
        assert "missing_field:confidence" in parsed["issues"]


class TestDryRunCli:
    def test_dry_run_cli_creates_expected_files_and_issue_summary(self, tmp_path: Path):
        provider_requests_path = tmp_path / "provider_requests_dry_run.jsonl"
        casebook_path = tmp_path / "casebook.csv"
        out_dir = tmp_path / "out"
        _write_jsonl(provider_requests_path, [_provider_request(), _provider_request("openai_gsm8k_1025")])
        _write_casebook(
            casebook_path,
            [
                {"case_id": "openai_gsm8k_1021", "gold_answer": "8"},
                {"case_id": "openai_gsm8k_1025", "gold_answer": "23"},
            ],
        )

        summary = runner.main(
            [
                "--provider-requests",
                str(provider_requests_path),
                "--casebook",
                str(casebook_path),
                "--out-dir",
                str(out_dir),
            ]
        )

        assert summary["mode"] == "dry_run"
        assert summary["calls_attempted"] == 0
        assert summary["calls_succeeded"] == 0
        assert summary["json_parse_ok_count"] == 0
        assert summary["schema_ok_count"] == 0
        assert summary["issue_summary"]["dry_run"] == 2
        assert (out_dir / "manifest.json").exists()
        assert (out_dir / "raw_responses.jsonl").exists()
        assert (out_dir / "parsed_responses.jsonl").exists()
        assert (out_dir / "relation_verifier_rows.jsonl").exists()
        assert (out_dir / "pilot_summary.json").exists()
        assert (out_dir / "dry_run_report.md").exists()

    def test_issue_summary_counters_include_requested_categories(self):
        results = [
            {"issues": ["wrong_relation", "format_error"]},
            {"issues": ["wrong_target_variable", "uncertain"]},
        ]
        args = argparse.Namespace(
            allow_api=False,
            model="fake-model",
            provider_requests=Path("/tmp/provider_requests.jsonl"),
            casebook=None,
            out_dir=Path("/tmp/out"),
        )
        summary = runner._summarize_results(
            results=results,
            n_loaded=2,
            total_api_calls=0,
            args=args,
            gold_labels={},
            gold_in_any_prompt=False,
            report_name="dry_run_report.md",
        )
        assert summary["issue_summary"]["wrong_relation"] == 1
        assert summary["issue_summary"]["wrong_target_variable"] == 1
        assert summary["issue_summary"]["format_error"] == 1
        assert summary["issue_summary"]["uncertain"] == 1

    def test_casebook_lookup_normalizes_openai_prefix_in_either_direction(self, tmp_path: Path):
        provider_requests_path = tmp_path / "provider_requests_dry_run.jsonl"
        casebook_path = tmp_path / "casebook.csv"
        out_dir = tmp_path / "out"
        _write_jsonl(
            provider_requests_path,
            [
                _provider_request("openai_gsm8k_1021"),
                _provider_request("gsm8k_1025"),
                _provider_request("openai_gsm8k_1027"),
            ],
        )
        _write_casebook(
            casebook_path,
            [
                {"case_id": "gsm8k_1021", "gold_answer": "8"},
                {"case_id": "openai_gsm8k_1025", "gold_answer": "23"},
                {"case_id": "openai_gsm8k_1027", "gold_answer": "11"},
            ],
        )

        summary = runner.main(
            [
                "--provider-requests",
                str(provider_requests_path),
                "--casebook",
                str(casebook_path),
                "--out-dir",
                str(out_dir),
            ]
        )

        rows = [
            json.loads(line)
            for line in (out_dir / "relation_verifier_rows.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert summary["gold_label_available_count"] == 3
        assert summary["gold_label_coverage"] == "3/3"
        assert {row["case_id"] for row in rows} == {"openai_gsm8k_1021", "gsm8k_1025", "openai_gsm8k_1027"}
        assert [row["gold_label_available"] for row in rows] == [True, True, True]
        assert rows[0]["casebook_match_id"] == "gsm8k_1021"
        assert rows[1]["casebook_match_id"] == "openai_gsm8k_1025"
        assert rows[2]["casebook_match_id"] == "openai_gsm8k_1027"
        assert all("gold_answer" not in row["prompt_text"] for row in rows)
        assert all("answer_key" not in row["prompt_text"] for row in rows)
        assert all("hidden label" not in row["prompt_text"].lower() for row in rows)

    def test_process_case_records_extraction_diagnostics_when_call_returns_empty_text(self):
        class _EmptyResponse:
            text = ""
            usage = {"input_tokens": 1}

        result, api_calls = runner._process_case(
            req=_provider_request(),
            gold_labels={"openai_gsm8k_1021": "8"},
            client=_FakeCohereClient(_EmptyResponse()),
            model="command-r-plus-08-2024",
            max_tokens=256,
            temperature=0.0,
            call_index=1,
            dry_run=False,
        )
        assert api_calls == 1
        assert result["call_ok"] is True
        assert result["raw_response"] == ""
        assert result["response_type"] == "_EmptyResponse"
        assert result["extraction_source"] == "unavailable"
        assert result["extraction_issue"] == "empty_text:response.text"
        assert result["issues"] == ["json_parse_failed:empty_response"]
        assert "prompt text" not in (result["response_repr"] or "").lower()
