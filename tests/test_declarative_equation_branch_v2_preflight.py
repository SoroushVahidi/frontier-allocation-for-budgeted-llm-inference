"""Tests for prepare_declarative_equation_branch_v2_preflight.py (no API)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import prepare_declarative_equation_branch_v2_preflight as preflight


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


def _prior_v1_row(case_id: str = "gsm8k_0001") -> dict:
    return {
        "case_id": case_id,
        "requested_target": "profit in dollars",
        "target_variable": "profit_dollars",
        "target_unit": "dollars",
        "process_state": "final",
        "solution_formula": "(cakes_sold * price_per_cake) - supplies_cost",
        "final_answer": 28.0,
        "schema_ok": False,
        "issue_summary": {"unknown_equation_variable": 1},
    }


class TestNoApiAtImport:
    def test_module_imports_without_api_clients(self):
        assert preflight.EXPERIMENT_ID == "declarative_equation_branch_v2"

    def test_module_source_has_no_provider_sdk_imports(self):
        source = Path(preflight.__file__).read_text(encoding="utf-8")
        assert "import cohere" not in source
        assert "import openai" not in source


class TestPromptTemplate:
    def test_prompt_contains_required_constraints(self):
        template = preflight._load_prompt_template()
        assert "relations are prose-only semantic statements" in template
        assert "equations are the only place for algebraic equalities" in template
        assert "variable.value must be a JSON number or null" in template
        assert '"source": "<given|derived|unknown>"' in template

    def test_rendered_prompt_is_gold_free_and_forbidden_string_free(self):
        rendered = preflight.render_prompt(
            preflight._load_prompt_template(),
            "What is 6 * 7?",
            "41, 43 (model-generated only; none are confirmed correct)",
        )
        audit = preflight.audit_prompt(rendered, "case_1")
        assert audit["gold_free"] is True
        assert audit["forbidden_string_free"] is True
        assert audit["violations"] == []


class TestCliDryRun:
    def test_preflight_generates_provider_requests_and_expected_files(self, tmp_path: Path):
        selected_cases_path = tmp_path / "selected_cases.jsonl"
        topology_path = tmp_path / "topology.jsonl"
        prior_v1_path = tmp_path / "prior_v1.jsonl"
        out_dir = tmp_path / "out"
        _write_jsonl(selected_cases_path, [_selected_case()])
        _write_jsonl(topology_path, [_topology_row()])
        _write_jsonl(prior_v1_path, [_prior_v1_row()])

        manifest = preflight.main(
            [
                "--selected-cases",
                str(selected_cases_path),
                "--topology-labels",
                str(topology_path),
                "--prior-v1-output",
                str(prior_v1_path),
                "--out-dir",
                str(out_dir),
            ]
        )

        assert manifest["all_prompts_gold_free"] is True
        assert manifest["all_prompts_forbidden_string_free"] is True
        assert manifest["topology_labels_input"] == str(topology_path)
        assert manifest["prior_v1_output_input"] == str(prior_v1_path)
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
        assert request["prior_v1_metadata"]["target_variable"] == "profit_dollars"
        assert request["topology_metadata_in_prompt"] is False
        assert request["prior_v1_metadata_in_prompt"] is False
        assert "final_after_process" not in request["prompt_text"]
        assert "profit_dollars" not in request["prompt_text"]

    def test_out_dir_defaults_to_tmp_when_not_supplied(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        selected_cases_path = tmp_path / "selected_cases.jsonl"
        _write_jsonl(selected_cases_path, [_selected_case()])
        auto_out_dir = tmp_path / "auto_out"
        monkeypatch.setattr(preflight, "_default_out_dir", lambda: auto_out_dir)

        manifest = preflight.main(["--selected-cases", str(selected_cases_path)])

        assert Path(manifest["out_dir"]) == auto_out_dir
        assert (auto_out_dir / "provider_requests_dry_run.jsonl").exists()
