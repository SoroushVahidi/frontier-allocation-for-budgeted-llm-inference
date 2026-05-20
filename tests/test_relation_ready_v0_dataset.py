"""Tests for build_relation_ready_v0_dataset.py."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import build_relation_ready_v0_dataset as dataset


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _rv_case_row(case_id: str = "openai_gsm8k_1025", *, false_accept: str = "False") -> dict:
    return {
        "case_id": case_id,
        "topology_label": "arithmetic_precision",
        "verifier_error_type": "none",
        "verifier_target_relation_correct": "True",
        "verifier_target_variable_correct": "True",
        "verifier_source_facts_sufficient": "True",
        "verifier_equations_match_source_facts": "True",
        "verifier_process_state_correct": "True",
        "verifier_unit_scale_correct": "True",
        "verifier_arithmetic_executable": "True",
        "candidate_source": "declarative_v2",
        "prior_exact_any": "True",
        "prior_executable_exact_any": "True",
        "declarative_v1_exact": "False",
        "declarative_v2_exact": "True",
        "bftc_exact": "False",
        "bftc_exec_exact": "True",
        "false_accept": false_accept,
        "false_reject": "False",
        "diagnosis": "accepted",
        "recommended_next_label": "RelationReady",
    }


def _decl_v1_row(case_id: str = "openai_gsm8k_1025") -> dict:
    return {
        "case_id": case_id,
        "topology_label": "arithmetic_precision",
        "topology_tree_label": "precision",
        "prompt_gold_consistency": "consistent",
        "gold": "23",
        "final_answer": "",
        "executable_final_answer": "",
        "final_exact": "False",
        "executable_exact": "False",
        "json_parse_ok": "True",
        "relation_present": "True",
        "equation_present": "True",
        "target_solve_for_match": "True",
        "formula_eval_ok": "False",
        "schema_issues": "",
        "unknown_relation_variable_count": "0",
        "unknown_equation_variable_count": "0",
        "unknown_relation_variable_false_positive_validation_artifact": "False",
        "relaxed_relation_schema_ok": "True",
        "equation_strict_ok": "True",
        "formula_strict_ok": "False",
        "is_new_declarative_candidate": "False",
        "matches_baseline_pool": "True",
        "near_miss_under_20pct": "False",
        "diagnosis": "no exact recovery",
        "recommended_fix_category": "equation_generation_failure",
    }


def _decl_v2_row(case_id: str = "openai_gsm8k_1025", *, prompt_gold_consistency: str = "consistent") -> dict:
    return {
        "case_id": case_id,
        "topology_label": "arithmetic_precision",
        "topology_tree_label": "precision",
        "prompt_gold_consistency": prompt_gold_consistency,
        "gold": "23",
        "v1_fix_category": "equation_generation_failure",
        "v1_final_exact": "False",
        "v1_executable_exact": "False",
        "v2_schema_ok": "True",
        "v2_formula_eval_ok": "True",
        "v2_target_solve_for_match": "True",
        "v2_solve_for_declared": "True",
        "v2_numeric_variable_value_ok": "True",
        "v2_final_answer": "23",
        "v2_executable_answer": "23",
        "normalized_executable_answer": "23",
        "primary_label": "exact_recovered",
        "mechanically_fixable_offline": "False",
        "normalization_note": "",
        "comparison_note": "exact",
    }


def _bftc_row(case_id: str = "openai_gsm8k_1025") -> dict:
    return {
        "case_id": case_id,
        "qtype": "arithmetic",
        "gold": "23.0",
        "fa": "22.0",
        "rel_err": "0.04",
        "is_new": "False",
        "all_consistent": "True",
        "target_correct": "True",
        "error_category": "near_miss",
        "subpattern": "",
        "failed_relation": "",
        "repair_operation": "",
        "deterministic_repair_possible": "False",
        "diagnosis": "near miss",
        "near_miss": "True",
    }


def _bftc_exec_row(case_id: str = "openai_gsm8k_1025") -> dict:
    return {
        "case_id": case_id,
        "question_type": "arithmetic",
        "question": "Q?",
        "gold": "23.0",
        "bftc_only_final_answer": "22.0",
        "bftc_only_abs_error": "1.0",
        "bftc_only_rel_error": "0.04",
        "bftc_only_recovered": "False",
        "bftc_only_prev_category": "near_miss",
        "bftc_only_target_identified": "target",
        "bftc_only_all_steps_consistent": "True",
        "model_final_answer": "22.0",
        "model_final_abs_error": "1.0",
        "model_final_recovered": "False",
        "solution_formula": "x+y",
        "formula_variables_json": "{}",
        "formula_result_mismatched_model_final_answer": "False",
        "formula_eval_ok": "True",
        "formula_eval_error_type": "",
        "executable_final_answer": "23.0",
        "executable_abs_error": "0.0",
        "executable_rel_error": "0.0",
        "executable_recovered": "True",
        "executable_result_new_vs_prior_pool": "True",
        "fixed_or_worsened_vs_bftc_only": "fixed",
        "fixed_or_worsened_vs_model_final": "fixed",
        "gold_value_in_formula_variables": "False",
        "variable_close_to_gold": "False",
        "closest_formula_variable_name": "",
        "closest_formula_variable_value": "",
        "primary_category": "fixed",
        "failure_axis": "arithmetic",
        "formula_variables_assessment": "",
        "prompt_gold_consistency": "consistent",
        "minimal_fix": "",
        "diagnosis": "fixed by formula",
    }


def _topology_row(case_id: str = "openai_gsm8k_1025", *, prompt_gold_consistency: str = "consistent") -> dict:
    return {
        "case_id": case_id,
        "question": "Q?",
        "gold": "23",
        "baseline_selected_answer": "22",
        "all_explored_numeric_candidates": ["22", "23"],
        "candidate_provenance": [],
        "closest_numeric_candidate_to_gold": "23",
        "numeric_distance_to_gold": 0.0,
        "relative_distance_to_gold": 0.0,
        "candidate_cluster_structure": {},
        "closest_semantic_candidate": {},
        "missing_edge_type": "arithmetic_precision",
        "missing_edge_description": "precision",
        "estimated_steps_from_closest_node_to_gold": 0,
        "needed_branch_family": "repair",
        "tree_topology_label": "precision",
        "existing_information_sufficient": True,
        "deterministic_local_repair_possible": True,
        "new_model_generation_edge_needed": False,
        "confidence": 0.9,
        "label_source": "heuristic",
        "prompt_gold_consistency": prompt_gold_consistency,
        "heuristic_rationale": "",
        "api_rationale": "",
    }


class TestHelpers:
    def test_normalize_case_id_equivalence(self):
        assert dataset._normalize_case_id("openai_gsm8k_1025") == "gsm8k_1025"
        assert dataset._normalize_case_id("gsm8k_1025") == "gsm8k_1025"

    def test_prompt_gold_inconsistent_forces_false_label(self):
        row = {"prompt_gold_inconsistent_flag": True, "relation_verifier_false_accept": False, "first_error_axis": "no_issue", "exact_final_answer_posthoc": True, "exact_executable_answer_posthoc": True, "relation_verifier_accept": True}
        label, source, confidence = dataset._derive_relation_ready_label(row)
        assert label is False
        assert source == "conservative_blocker"
        assert confidence == "high"

    def test_relation_verifier_false_accept_forces_false_label(self):
        row = {"prompt_gold_inconsistent_flag": False, "relation_verifier_false_accept": True, "first_error_axis": "no_issue", "exact_final_answer_posthoc": True, "exact_executable_answer_posthoc": True, "relation_verifier_accept": True}
        label, _, _ = dataset._derive_relation_ready_label(row)
        assert label is False

    def test_exact_executable_candidate_can_be_true_label_if_no_blocker(self):
        row = {"prompt_gold_inconsistent_flag": False, "relation_verifier_false_accept": False, "first_error_axis": "no_issue", "exact_final_answer_posthoc": False, "exact_executable_answer_posthoc": True, "relation_verifier_accept": None}
        label, source, confidence = dataset._derive_relation_ready_label(row)
        assert label is True
        assert source == "posthoc_exact_no_blocker"
        assert confidence == "medium"

    def test_module_imports_without_api_clients(self):
        first_lines = "\n".join(Path(dataset.__file__).read_text(encoding="utf-8").splitlines()[:50])
        assert "import cohere" not in first_lines
        assert "import openai" not in first_lines


class TestDatasetBuild:
    def test_build_from_minimal_fake_artifacts(self, tmp_path: Path):
        out_dir = tmp_path / "out"
        paths = {
            "rv_case": tmp_path / "rv_case.csv",
            "rv_rows": tmp_path / "rv_rows.jsonl",
            "rv_summary": tmp_path / "rv_summary.json",
            "d1": tmp_path / "d1.csv",
            "d2": tmp_path / "d2.csv",
            "bftc": tmp_path / "bftc.csv",
            "bftc_exec": tmp_path / "bftc_exec.csv",
            "topology": tmp_path / "topology.jsonl",
            "casebook": tmp_path / "casebook.csv",
        }
        _write_csv(paths["rv_case"], list(_rv_case_row().keys()), [_rv_case_row()])
        _write_jsonl(paths["rv_rows"], [{"case_id": "openai_gsm8k_1025", "primary_candidate_source": "declarative_v2", "extraction_source": "response.text"}])
        paths["rv_summary"].write_text(json.dumps({"false_accepts": 0}), encoding="utf-8")
        _write_csv(paths["d1"], list(_decl_v1_row().keys()), [_decl_v1_row()])
        _write_csv(paths["d2"], list(_decl_v2_row().keys()), [_decl_v2_row()])
        _write_csv(paths["bftc"], list(_bftc_row().keys()), [_bftc_row()])
        _write_csv(paths["bftc_exec"], list(_bftc_exec_row().keys()), [_bftc_exec_row()])
        _write_jsonl(paths["topology"], [_topology_row()])
        _write_csv(paths["casebook"], ["case_id", "gold"], [{"case_id": "gsm8k_1025", "gold": "23"}])

        summary = dataset.main(
            [
                "--relation-verifier-case-analysis",
                str(paths["rv_case"]),
                "--relation-verifier-false-accept-summary",
                str(paths["rv_summary"]),
                "--relation-verifier-rows",
                str(paths["rv_rows"]),
                "--declarative-v1-case-analysis",
                str(paths["d1"]),
                "--declarative-v2-case-analysis",
                str(paths["d2"]),
                "--bftc-case-analysis",
                str(paths["bftc"]),
                "--bftc-executable-case-analysis",
                str(paths["bftc_exec"]),
                "--topology-rows",
                str(paths["topology"]),
                "--casebook",
                str(paths["casebook"]),
                "--out-dir",
                str(out_dir),
            ]
        )

        assert summary["row_count"] == 5
        assert (out_dir / "relation_ready_rows.jsonl").exists()
        assert (out_dir / "relation_ready_rows.csv").exists()
        assert (out_dir / "relation_ready_summary.json").exists()
        assert (out_dir / "relation_ready_report.md").exists()

        rows = [json.loads(line) for line in (out_dir / "relation_ready_rows.jsonl").read_text(encoding="utf-8").splitlines()]
        d2_row = next(row for row in rows if row["candidate_source"] == "declarative_v2")
        assert d2_row["normalized_case_id"] == "gsm8k_1025"
        assert d2_row["relation_ready_label"] is True
        assert d2_row["exact_executable_answer_posthoc"] is True

    def test_missing_optional_files_do_not_crash(self, tmp_path: Path):
        out_dir = tmp_path / "out_missing"
        d2 = tmp_path / "d2.csv"
        topology = tmp_path / "topology.jsonl"
        casebook = tmp_path / "casebook.csv"
        _write_csv(d2, list(_decl_v2_row().keys()), [_decl_v2_row()])
        _write_jsonl(topology, [_topology_row()])
        _write_csv(casebook, ["case_id", "gold"], [{"case_id": "openai_gsm8k_1025", "gold": "23"}])

        summary = dataset.main(
            [
                "--relation-verifier-case-analysis",
                str(tmp_path / "missing_rv.csv"),
                "--relation-verifier-false-accept-summary",
                str(tmp_path / "missing_summary.json"),
                "--relation-verifier-rows",
                str(tmp_path / "missing_rows.jsonl"),
                "--declarative-v1-case-analysis",
                str(tmp_path / "missing_d1.csv"),
                "--declarative-v2-case-analysis",
                str(d2),
                "--bftc-case-analysis",
                str(tmp_path / "missing_bftc.csv"),
                "--bftc-executable-case-analysis",
                str(tmp_path / "missing_bftc_exec.csv"),
                "--topology-rows",
                str(topology),
                "--casebook",
                str(casebook),
                "--out-dir",
                str(out_dir),
            ]
        )

        assert summary["row_count"] == 1
        assert summary["warnings"]
        assert any("missing_optional_file:" in item for item in summary["warnings"])
