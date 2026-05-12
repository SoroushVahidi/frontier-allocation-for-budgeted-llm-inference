"""Tests for prepare_declarative_equation_branch_v1_preflight.py (no API)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import prepare_declarative_equation_branch_v1_preflight as preflight


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
        "fa_numeric": 28.0,
        "candidate_pool_review": "check whether profit instead of revenue is requested",
    }


def _prior_exec_row(case_id: str = "gsm8k_0001") -> dict:
    return {
        "case_id": case_id,
        "requested_target": "profit in dollars",
        "failed_relation": "revenue was used as the target",
        "repair_operation": "subtract supplies from revenue",
        "solution_formula": "(cakes_sold * price_per_cake) - supplies_cost",
        "executable_final_answer": 28.0,
    }


def _topology_row(case_id: str = "gsm8k_0001") -> dict:
    return {
        "case_id": case_id,
        "gold": "28",
        "missing_edge_type": "final_after_process",
        "needed_branch_family": "backward_from_target_check",
        "tree_topology_label": "near_miss_pool",
        "estimated_steps_from_closest_node_to_gold": 1,
        "label_source": "heuristic_plus_api",
        "prompt_gold_consistency": "consistent",
    }


class TestNoApiAtImport:
    def test_module_imports_without_api_clients(self):
        assert preflight.EXPERIMENT_ID == "declarative_equation_branch_v1"

    def test_module_source_has_no_provider_sdk_imports(self):
        source = Path(preflight.__file__).read_text(encoding="utf-8")
        assert "import cohere" not in source
        assert "import openai" not in source


class TestPromptTemplate:
    def test_prompt_contains_required_constraints(self):
        template = preflight._load_prompt_template()
        assert "target_variable and solve_for must be identical strings" in template
        assert "process_state must be one of" in template
        assert "relations must describe how quantities compose" in template
        assert '"uncertainty": <true or false>' in template

    def test_rendered_prompt_is_gold_free(self):
        rendered = preflight.render_prompt(
            preflight._load_prompt_template(),
            "What is 6 * 7?",
            "41, 43 (model-generated only; none are confirmed correct)",
            "",
        )
        audit = preflight.audit_prompt(rendered, "case_1")
        assert audit["gold_free"] is True
        assert audit["violations"] == []

    def test_rendered_prompt_includes_prior_context(self):
        rendered = preflight.render_prompt(
            preflight._load_prompt_template(),
            "What is 6 * 7?",
            "41, 43 (model-generated only; none are confirmed correct)",
            preflight._build_prior_context(_prior_bftc_row(), _prior_exec_row()),
        )
        assert "PRIOR BFTC CONTEXT" in rendered
        assert "PRIOR EXECUTABLE-REPAIR CONTEXT" in rendered
        assert "solution_formula" in rendered


class TestCliDryRun:
    def test_preflight_generates_provider_requests_and_expected_files(self, tmp_path: Path):
        selected_cases_path = tmp_path / "selected_cases.jsonl"
        prior_bftc_path = tmp_path / "parsed_bftc.jsonl"
        prior_exec_path = tmp_path / "parsed_exec.jsonl"
        topology_path = tmp_path / "topology.jsonl"
        out_dir = tmp_path / "out"
        _write_jsonl(selected_cases_path, [_selected_case()])
        _write_jsonl(prior_bftc_path, [_prior_bftc_row()])
        _write_jsonl(prior_exec_path, [_prior_exec_row()])
        _write_jsonl(topology_path, [_topology_row()])

        manifest = preflight.main(
            [
                "--selected-cases",
                str(selected_cases_path),
                "--prior-bftc-output",
                str(prior_bftc_path),
                "--prior-executable-output",
                str(prior_exec_path),
                "--topology-labels",
                str(topology_path),
                "--out-dir",
                str(out_dir),
            ]
        )

        assert manifest["all_prompts_gold_free"] is True
        assert manifest["topology_labels_input"] == str(topology_path)
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
        assert request["required_output_fields"] == preflight._REQUIRED_OUTPUT_FIELDS
        assert request["topology_metadata"]["missing_edge_type"] == "final_after_process"
        assert request["topology_metadata_in_prompt"] is False
        assert "gold_answer" not in request["prompt_text"].lower()

    def test_out_dir_defaults_to_tmp_when_not_supplied(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        selected_cases_path = tmp_path / "selected_cases.jsonl"
        _write_jsonl(selected_cases_path, [_selected_case()])
        auto_out_dir = tmp_path / "auto_out"
        monkeypatch.setattr(preflight, "_default_out_dir", lambda: auto_out_dir)

        manifest = preflight.main(["--selected-cases", str(selected_cases_path)])

        assert Path(manifest["out_dir"]) == auto_out_dir
        assert (auto_out_dir / "provider_requests_dry_run.jsonl").exists()
