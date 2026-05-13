"""Tests for prepare_relation_verifier_v1_preflight.py (no API)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import prepare_relation_verifier_v1_preflight as preflight


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _selected_case(case_id: str = "openai_gsm8k_1021") -> dict:
    return {
        "case_id": case_id,
        "question": "A simple folding newspaper or tabloid can be made by folding a piece of paper vertically and unfolding. How many pieces of paper would be used in a 32-page tabloid?",
        "requested_target": "number of pieces of paper for a 32-page tabloid",
        "gold_absent": True,
    }


def _topology_row(case_id: str = "openai_gsm8k_1021") -> dict:
    return {
        "case_id": case_id,
        "gold": "8",
        "missing_edge_type": "relation_composition_missing",
        "needed_branch_family": "relation_verifier",
        "tree_topology_label": "near_miss_pool",
        "estimated_steps_from_closest_node_to_gold": 1,
        "label_source": "heuristic_plus_api",
        "prompt_gold_consistency": "consistent",
    }


def _declarative_v2_raw(case_id: str = "openai_gsm8k_1021") -> dict:
    return {
        "case_id": case_id,
        "raw_response": json.dumps(
            {
                "requested_target": "number_of_pieces_of_paper",
                "target_variable": "number_of_pieces_of_paper",
                "target_unit": "piece",
                "process_state": "final",
                "source_facts": ["a 32-page tabloid is made by folding a piece of paper vertically and unfolding"],
                "variables": [
                    {"name": "number_of_pieces_of_paper", "value": None, "unit": "piece", "description": "pieces of paper", "source": "unknown"},
                    {"name": "total_pages", "value": 32, "unit": "page", "description": "total pages", "source": "given"},
                    {"name": "pages_per_piece", "value": 4, "unit": "page", "description": "pages per piece", "source": "given"},
                ],
                "relations": ["the number of pieces of paper is the total number of pages divided by the number of pages per piece"],
                "equations": ["number_of_pieces_of_paper = total_pages / pages_per_piece"],
                "solve_for": "number_of_pieces_of_paper",
                "solution_formula": "total_pages / pages_per_piece",
                "final_answer": 8.0,
                "uncertainty": False,
                "abstain_reason": "",
            }
        ),
    }


def _declarative_v1_raw(case_id: str = "openai_gsm8k_1021") -> dict:
    return {
        "case_id": case_id,
        "raw_response": json.dumps(
            {
                "requested_target": "number of pieces of paper for a 32-page tabloid",
                "source_facts": ["32 pages"],
                "reverse_derivation": [{"step": 1, "description": "Calculate pieces needed", "consistent_with_target": True}],
                "failed_relation": "none",
                "repair_operation": "none",
                "formula_variables": {"pages": {"value": 32, "description": "pages", "unit": "pages"}},
                "solution_formula": "pages / 2",
                "final_answer": 16,
                "confidence": "high",
            }
        ),
    }


def _bftc_raw(case_id: str = "openai_gsm8k_1021") -> dict:
    return {
        "case_id": case_id,
        "raw_response": json.dumps(
            {
                "requested_target": "number of pieces of paper for a 32-page tabloid",
                "source_facts": ["32 pages"],
                "reverse_derivation": [{"step": 1, "description": "Calculate pieces needed", "consistent_with_target": True}],
                "failed_relation": "none",
                "repair_operation": "none",
                "formula_variables": {"pages": {"value": 32, "description": "pages", "unit": "pages"}},
                "solution_formula": "pages / 2",
                "final_answer": 16,
                "confidence": "high",
            }
        ),
    }


class TestNoApiAtImport:
    def test_module_imports_without_provider_clients(self):
        assert preflight.EXPERIMENT_ID == "relation_verifier_v1"

    def test_module_source_has_no_provider_sdk_imports(self):
        source = Path(preflight.__file__).read_text(encoding="utf-8")
        assert "import cohere" not in source
        assert "import openai" not in source


class TestPromptTemplate:
    def test_prompt_contains_required_constraints(self):
        template = preflight._load_prompt_template()
        assert "Do not use any gold answer" in template
        assert "candidate_context_json" in template
        assert "target_relation_correct" in template
        assert "error_type" in template

    def test_rendered_prompt_is_gold_free_and_forbidden_string_free(self):
        rendered = preflight.render_prompt(
            preflight._load_prompt_template(),
            "How many pieces of paper would be used in a 32-page tabloid?",
            "number of pieces of paper for a 32-page tabloid",
            {
                "primary_candidate_source": "declarative_v2",
                "candidate": {"solution_formula": "total_pages / pages_per_piece"},
            },
        )
        audit = preflight.audit_prompt(rendered, "case_1")
        assert audit["gold_free"] is True
        assert audit["forbidden_string_free"] is True
        assert audit["violations"] == []


class TestCliDryRun:
    def test_preflight_generates_provider_requests_and_expected_files(self, tmp_path: Path):
        selected_cases_path = tmp_path / "selected_cases.jsonl"
        topology_path = tmp_path / "topology.jsonl"
        bftc_dir = tmp_path / "bftc"
        v1_dir = tmp_path / "v1"
        v2_dir = tmp_path / "v2"
        out_dir = tmp_path / "out"
        _write_jsonl(selected_cases_path, [_selected_case()])
        _write_jsonl(topology_path, [_topology_row()])
        _write_jsonl(bftc_dir / "raw_responses.jsonl", [_bftc_raw()])
        _write_jsonl(v1_dir / "raw_responses.jsonl", [_declarative_v1_raw()])
        _write_jsonl(v2_dir / "raw_responses.jsonl", [_declarative_v2_raw()])

        manifest = preflight.main(
            [
                "--selected-cases",
                str(selected_cases_path),
                "--bftc-exec-dir",
                str(bftc_dir),
                "--declarative-v1-dir",
                str(v1_dir),
                "--declarative-v2-dir",
                str(v2_dir),
                "--topology-labels",
                str(topology_path),
                "--out-dir",
                str(out_dir),
            ]
        )

        assert manifest["all_prompts_gold_free"] is True
        assert manifest["all_prompts_forbidden_string_free"] is True
        assert manifest["provider_request_count"] == 1
        assert manifest["primary_candidate_sources"]["declarative_v2"] == 1
        assert (out_dir / "manifest.json").exists()
        assert (out_dir / "selected_cases.jsonl").exists()
        assert (out_dir / "provider_requests_dry_run.jsonl").exists()
        assert (out_dir / "prompt_audit.json").exists()
        assert (out_dir / "dry_run_report.md").exists()

        requests = [
            json.loads(line)
            for line in (out_dir / "provider_requests_dry_run.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(requests) == 1
        request = requests[0]
        assert request["dry_run"] is True
        assert request["api_call_made"] is False
        assert request["primary_candidate_source"] == "declarative_v2"
        assert request["topology_metadata"]["missing_edge_type"] == "relation_composition_missing"
        assert request["topology_metadata_in_prompt"] is False
        assert "relation_composition_missing" not in request["prompt_text"]
        assert "candidate_variables" not in request["prompt_text"]  # prompt uses JSON context
        assert "number of pieces of paper for a 32-page tabloid" in request["prompt_text"]

    def test_out_dir_defaults_to_tmp_when_not_supplied(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        selected_cases_path = tmp_path / "selected_cases.jsonl"
        bftc_dir = tmp_path / "bftc"
        v1_dir = tmp_path / "v1"
        v2_dir = tmp_path / "v2"
        _write_jsonl(selected_cases_path, [_selected_case()])
        _write_jsonl(bftc_dir / "raw_responses.jsonl", [_bftc_raw()])
        _write_jsonl(v1_dir / "raw_responses.jsonl", [_declarative_v1_raw()])
        _write_jsonl(v2_dir / "raw_responses.jsonl", [_declarative_v2_raw()])
        auto_out_dir = tmp_path / "auto_out"
        monkeypatch.setattr(preflight, "_default_out_dir", lambda: auto_out_dir)

        manifest = preflight.main(
            [
                "--selected-cases",
                str(selected_cases_path),
                "--bftc-exec-dir",
                str(bftc_dir),
                "--declarative-v1-dir",
                str(v1_dir),
                "--declarative-v2-dir",
                str(v2_dir),
            ]
        )

        assert Path(manifest["out_dir"]) == auto_out_dir
        assert (auto_out_dir / "provider_requests_dry_run.jsonl").exists()

