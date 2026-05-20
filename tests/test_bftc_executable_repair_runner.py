"""Tests for run_bftc_executable_repair_v1.py (no API)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import run_bftc_executable_repair_v1 as runner


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


def _provider_request(case_id: str = "gsm8k_0001") -> dict:
    return {
        "request_id": f"req:{case_id}",
        "case_id": case_id,
        "question": "A baker sells 3 cakes for $12 each and spends $8 on supplies. What is the profit?",
        "prompt_text": "QUESTION:\nWhat is the profit?\nReturn JSON with solution_formula and final_answer.",
        "candidate_pool": ["20", "28"],
        "candidate_pool_size": 2,
        "baseline_answer": "20",
        "gold_absent": True,
        "dry_run": True,
        "api_call_made": False,
        "prompt_sha256": "placeholder",
        "max_output_tokens": 2048,
        "required_output_fields": runner._REQUIRED_CANONICAL,
    }


def _valid_response(final_answer: float = 28.0) -> dict:
    return {
        "requested_target": "profit in dollars",
        "source_facts": ["3 cakes sold", "$12 per cake", "$8 supplies cost"],
        "reverse_derivation": [
            {
                "step": 1,
                "description": "Compute revenue then subtract cost.",
                "consistent_with_target": True,
            }
        ],
        "failed_relation": "none",
        "repair_operation": "subtract supplies from revenue",
        "formula_variables": {
            "cakes_sold": {"value": 3, "description": "cakes sold", "unit": "count"},
            "price_per_cake": {"value": 12, "description": "price", "unit": "dollars"},
            "supplies_cost": {"value": 8, "description": "cost", "unit": "dollars"},
        },
        "solution_formula": "(cakes_sold * price_per_cake) - supplies_cost",
        "final_answer": final_answer,
        "confidence": "high",
    }


class TestNoApiAtImport:
    def test_module_imports_without_network_activity(self):
        assert runner.EXPERIMENT_ID == "bftc_executable_repair_v1"


class TestFormulaEvaluator:
    def test_valid_formula_evaluates(self):
        result = runner.eval_formula(
            "(cakes_sold * price_per_cake) - supplies_cost",
            _valid_response()["formula_variables"],
        )
        assert result["eval_ok"] is True
        assert result["value"] == 28.0
        assert result["names_used"] == ["cakes_sold", "price_per_cake", "supplies_cost"]

    def test_unknown_variable_is_rejected(self):
        result = runner.eval_formula("unknown_name + 1", {})
        assert result["eval_ok"] is False
        assert result["error_type"] == "unknown_variable"

    def test_unsafe_ast_is_rejected(self):
        result = runner.eval_formula("__import__('os')", {})
        assert result["eval_ok"] is False
        assert result["error_type"] == "unsafe_call"

    def test_huge_exponent_is_rejected(self):
        result = runner.eval_formula("2 ** 101", {})
        assert result["eval_ok"] is False
        assert result["error_type"] == "huge_exponent"

    def test_round_is_supported(self):
        result = runner.eval_formula("round(value / count, 2)", {"value": 10, "count": 3})
        assert result["eval_ok"] is True
        assert result["value"] == 3.33


class TestResponseParsing:
    def test_formula_variables_and_final_answer_are_parsed(self):
        parsed = runner.parse_bftcx_response(_valid_response())
        assert parsed["schema_ok"] is True
        assert parsed["eval_ok"] is True
        assert parsed["eval_value"] == 28.0
        assert parsed["fa_numeric"] == 28.0
        assert parsed["formula_matches_model_fa"] is True

    def test_formula_mismatch_is_recorded(self):
        parsed = runner.parse_bftcx_response(_valid_response(final_answer=27.0))
        assert parsed["schema_ok"] is True
        assert parsed["eval_ok"] is True
        assert parsed["formula_matches_model_fa"] is False
        assert any(issue.startswith("formula_result_mismatch") for issue in parsed["issues"])


class TestPerCaseProcessing:
    def test_executable_final_answer_is_scored_post_hoc_without_api(self, monkeypatch):
        req = _provider_request()

        def fake_call(*_args, **_kwargs):
            return json.dumps(_valid_response(final_answer=27.0)), {"tokens": 1}

        monkeypatch.setattr(runner, "_call_cohere", fake_call)

        result, calls = runner._process_case(
            req=req,
            gold_labels={"gsm8k_0001": "28"},
            client=object(),
            model="fake-model",
            max_tokens=128,
            temperature=0.0,
            call_index=1,
            dry_run=False,
        )

        assert calls == 1
        assert result["call_ok"] is True
        assert result["formula_matches_model_fa"] is False
        assert result["executable_final_answer"] == 28.0
        assert result["executable_final_answer_source"] == "eval"
        assert result["gold_recovered_model_fa"] is False
        assert result["gold_recovered_executable_fa"] is True

    def test_malformed_model_response_does_not_crash(self, monkeypatch):
        req = _provider_request("gsm8k_bad")

        def fake_call(*_args, **_kwargs):
            return "not json", {"tokens": 1}

        monkeypatch.setattr(runner, "_call_cohere", fake_call)

        result, calls = runner._process_case(
            req=req,
            gold_labels={},
            client=object(),
            model="fake-model",
            max_tokens=128,
            temperature=0.0,
            call_index=1,
            dry_run=False,
        )

        assert calls == 1
        assert result["call_ok"] is True
        assert result["parse_ok"] is False
        assert result["issues"] == ["json_parse_failed:parse_failed"]


class TestDryRunCli:
    def test_dry_run_cli_creates_expected_files_and_issue_summary(self, tmp_path: Path):
        provider_requests_path = tmp_path / "provider_requests_dry_run.jsonl"
        casebook_path = tmp_path / "casebook.csv"
        out_dir = tmp_path / "out"
        _write_jsonl(provider_requests_path, [_provider_request(), _provider_request("gsm8k_0002")])
        _write_casebook(
            casebook_path,
            [
                {"case_id": "gsm8k_0001", "gold_answer": "28"},
                {"case_id": "gsm8k_0002", "gold_answer": "28"},
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
        assert summary["issue_summary"]["dry_run"] == 2
        assert (out_dir / "manifest.json").exists()
        assert (out_dir / "raw_responses.jsonl").exists()
        assert (out_dir / "parsed_responses.jsonl").exists()
        assert (out_dir / "executable_candidate_rows.jsonl").exists()
        assert (out_dir / "pilot_summary.json").exists()
        assert (out_dir / "dry_run_report.md").exists()

        raw_rows = [
            json.loads(line)
            for line in (out_dir / "raw_responses.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(raw_rows) == 2
        assert raw_rows[0]["prompt_text"].startswith("QUESTION:")
        assert raw_rows[0]["raw_response"] is None

