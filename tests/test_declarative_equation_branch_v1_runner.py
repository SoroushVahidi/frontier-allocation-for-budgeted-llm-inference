"""Tests for run_declarative_equation_branch_v1.py (no API)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import run_declarative_equation_branch_v1 as runner


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
        "prompt_text": "QUESTION:\nWhat is the profit?\nReturn JSON with process_state, relations, equations, solution_formula, final_answer, and uncertainty.",
        "candidate_pool": ["20", "28"],
        "candidate_pool_size": 2,
        "baseline_answer": "20",
        "gold_absent": True,
        "dry_run": True,
        "api_call_made": False,
        "prompt_sha256": "placeholder",
        "max_output_tokens": 2048,
        "required_output_fields": runner._REQUIRED_FIELDS,
    }


def _valid_response(final_answer: float = 28.0, uncertainty: bool = False) -> dict:
    return {
        "requested_target": "profit in dollars",
        "target_variable": "profit_dollars",
        "target_unit": "dollars",
        "process_state": "final",
        "source_facts": ["3 cakes sold", "$12 per cake", "$8 on supplies"],
        "variables": [
            {"name": "cakes_sold", "description": "cakes sold", "unit": "count", "value": 3},
            {"name": "price_per_cake", "description": "price per cake", "unit": "dollars", "value": 12},
            {"name": "supplies_cost", "description": "supplies cost", "unit": "dollars", "value": 8},
            {"name": "revenue_dollars", "description": "revenue", "unit": "dollars", "value": None},
            {"name": "profit_dollars", "description": "profit", "unit": "dollars", "value": None},
        ],
        "relations": [
            "revenue_dollars = cakes_sold * price_per_cake",
            "profit_dollars = revenue_dollars - supplies_cost",
        ],
        "equations": [
            "revenue_dollars = cakes_sold * price_per_cake",
            "profit_dollars = revenue_dollars - supplies_cost",
        ],
        "equation_rationale": "Profit is revenue minus supplies cost.",
        "solve_for": "profit_dollars",
        "solution_formula": "(cakes_sold * price_per_cake) - supplies_cost",
        "final_answer": final_answer,
        "uncertainty": uncertainty,
        "abstain_reason": "" if not uncertainty else "ambiguous relation",
    }


class TestNoApiAtImport:
    def test_module_imports_without_network_activity(self):
        assert runner.EXPERIMENT_ID == "declarative_equation_branch_v1"
        first_lines = "\n".join(Path(runner.__file__).read_text(encoding="utf-8").splitlines()[:40])
        assert "import cohere" not in first_lines


class TestValidation:
    def test_valid_response_parses_and_evaluates(self):
        parsed = runner.parse_declarative_response(_valid_response())
        assert parsed["schema_ok"] is True
        assert parsed["relation_present"] is True
        assert parsed["equation_present"] is True
        assert parsed["formula_eval_ok"] is True
        assert parsed["formula_eval_value"] == 28.0
        assert parsed["target_variable_solve_for_match"] is True
        assert parsed["formula_matches_final_answer"] is True

    def test_target_variable_mismatch_is_flagged(self):
        response = _valid_response()
        response["solve_for"] = "revenue_dollars"
        parsed = runner.parse_declarative_response(response)
        assert parsed["schema_ok"] is False
        assert "target_variable_solve_for_mismatch" in parsed["issues"]

    def test_unknown_variable_in_equation_is_flagged(self):
        response = _valid_response()
        response["equations"] = ["profit_dollars = revenue_dollars - missing_cost"]
        parsed = runner.parse_declarative_response(response)
        assert parsed["schema_ok"] is False
        assert "missing_cost" in parsed["unknown_equation_vars"]

    def test_unknown_variable_in_relation_is_flagged(self):
        response = _valid_response()
        response["relations"] = ["profit_dollars = revenue_dollars - hidden_fee"]
        parsed = runner.parse_declarative_response(response)
        assert parsed["schema_ok"] is False
        assert "hidden_fee" in parsed["unknown_relation_vars"]

    def test_formula_unknown_variable_is_flagged(self):
        response = _valid_response()
        response["solution_formula"] = "revenue_dollars - hidden_fee"
        parsed = runner.parse_declarative_response(response)
        assert parsed["schema_ok"] is False
        assert parsed["formula_eval_error_type"] == "unknown_variable"

    def test_invalid_process_state_is_flagged(self):
        response = _valid_response()
        response["process_state"] = "later"
        parsed = runner.parse_declarative_response(response)
        assert parsed["schema_ok"] is False
        assert any(issue.startswith("invalid_process_state:") for issue in parsed["issues"])

    def test_uncertainty_requires_bool(self):
        response = _valid_response()
        response["uncertainty"] = "low"
        parsed = runner.parse_declarative_response(response)
        assert parsed["schema_ok"] is False
        assert "uncertainty_not_bool" in parsed["issues"]


class TestPerCaseProcessing:
    def test_post_hoc_gold_scoring_uses_local_eval_not_prompt(self, monkeypatch):
        def fake_call(*_args, **_kwargs):
            return json.dumps(_valid_response(final_answer=27.0)), {"tokens": 1}

        monkeypatch.setattr(runner, "_call_cohere", fake_call)

        result, calls = runner._process_case(
            req=_provider_request(),
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
        assert result["formula_eval_ok"] is True
        assert result["formula_matches_final_answer"] is False
        assert result["executable_final_answer"] == 28.0
        assert result["gold_recovered_final_answer"] is False
        assert result["gold_recovered_executable_answer"] is True
        assert result["gold_in_prompt"] is False

    def test_malformed_response_does_not_crash(self, monkeypatch):
        monkeypatch.setattr(runner, "_call_cohere", lambda *_args, **_kwargs: ("not json", {"tokens": 1}))
        result, calls = runner._process_case(
            req=_provider_request("gsm8k_bad"),
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
        assert summary["relation_present_count"] == 0
        assert summary["target_solve_for_match_count"] == 0
        assert summary["issue_summary"]["dry_run"] == 2
        assert (out_dir / "manifest.json").exists()
        assert (out_dir / "raw_responses.jsonl").exists()
        assert (out_dir / "parsed_responses.jsonl").exists()
        assert (out_dir / "declarative_candidate_rows.jsonl").exists()
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
