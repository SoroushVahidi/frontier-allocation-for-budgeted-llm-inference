"""Tests for prepare_bftc_executable_repair_v1_preflight.py (no API)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import prepare_bftc_executable_repair_v1_preflight as preflight


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _selected_case(case_id: str = "gsm8k_0001") -> dict:
    return {
        "case_id": case_id,
        "question": "A baker sells 3 cakes for $12 each and spends $8 on supplies. What is the profit?",
        "candidate_pool": ["20", "28"],
        "baseline_answer": "20",
        "gold_absent": True,
    }


def _prior_bftc_row(case_id: str = "gsm8k_0001") -> dict:
    return {
        "case_id": case_id,
        "target_identified": "profit in dollars",
        "steps_count": 3,
        "candidate_pool_review": "none of the prior candidates match the requested target",
        "fa_numeric": 28.0,
    }


class TestNoApiAtImport:
    def test_module_imports_without_api_clients(self):
        assert preflight.EXPERIMENT_ID == "bftc_executable_repair_v1"

    def test_module_source_has_no_api_sdk_imports(self):
        import inspect

        source = inspect.getsource(preflight)
        assert "import cohere" not in source
        assert "import openai" not in source
        assert "cerebras.cloud" not in source


class TestPromptTemplate:
    def test_prompt_mentions_solution_formula_contract(self):
        template = preflight._load_prompt_template()
        assert "solution_formula" in template
        assert "formula_variables" in template
        assert "final_answer" in template
        assert "No code block." in template

    def test_rendered_prompt_is_gold_free(self):
        template = preflight._load_prompt_template()
        rendered = preflight.render_prompt(
            template,
            "What is 6 * 7?",
            "41, 43 (model-generated from prior branches; none are confirmed correct)",
            "",
        )
        audit = preflight.audit_prompt(rendered, "case_1")
        assert audit["gold_free"] is True
        assert audit["violations"] == []

    def test_rendered_prompt_includes_prior_bftc_context_when_available(self):
        template = preflight._load_prompt_template()
        rendered = preflight.render_prompt(
            template,
            "What is 6 * 7?",
            "41, 43 (model-generated from prior branches; none are confirmed correct)",
            preflight._build_prior_bftc_context(_prior_bftc_row()),
        )
        assert "PRIOR BFTC RESPONSE" in rendered
        assert "prior_final_answer: 28.0" in rendered


class TestCliDryRun:
    def test_dry_run_generates_provider_requests_and_expected_files(self, tmp_path: Path):
        selected_cases_path = tmp_path / "selected_cases.jsonl"
        prior_bftc_path = tmp_path / "parsed_responses.jsonl"
        out_dir = tmp_path / "out"
        _write_jsonl(selected_cases_path, [_selected_case()])
        _write_jsonl(prior_bftc_path, [_prior_bftc_row()])

        manifest = preflight.main(
            [
                "--selected-cases",
                str(selected_cases_path),
                "--prior-bftc-output",
                str(prior_bftc_path),
                "--out-dir",
                str(out_dir),
            ]
        )

        assert manifest["all_prompts_gold_free"] is True
        assert manifest["has_prior_bftc_context"] is True
        assert (out_dir / "manifest.json").exists()
        assert (out_dir / "selected_cases.jsonl").exists()
        assert (out_dir / "provider_requests_dry_run.jsonl").exists()
        assert (out_dir / "prompt_audit.json").exists()
        assert (out_dir / "dry_run_report.md").exists()

        provider_requests = [
            json.loads(line)
            for line in (out_dir / "provider_requests_dry_run.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(provider_requests) == 1
        request = provider_requests[0]
        assert request["dry_run"] is True
        assert request["api_call_made"] is False
        assert request["required_output_fields"] == preflight._REQUIRED_OUTPUT_FIELDS
        assert "solution_formula" in request["prompt_text"]
        assert "PRIOR BFTC RESPONSE" in request["prompt_text"]

    def test_out_dir_defaults_to_tmp_when_not_supplied(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        selected_cases_path = tmp_path / "selected_cases.jsonl"
        _write_jsonl(selected_cases_path, [_selected_case()])

        auto_out_dir = tmp_path / "auto_out"
        monkeypatch.setattr(preflight, "_default_out_dir", lambda: auto_out_dir)

        manifest = preflight.main(
            [
                "--selected-cases",
                str(selected_cases_path),
            ]
        )

        assert Path(manifest["out_dir"]) == auto_out_dir
        assert (auto_out_dir / "provider_requests_dry_run.jsonl").exists()

