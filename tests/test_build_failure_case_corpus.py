from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    p = ROOT / "scripts" / "build_failure_case_corpus.py"
    spec = importlib.util.spec_from_file_location("build_failure_case_corpus", p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_failure_case_corpus_minimal_fixture(tmp_path: Path) -> None:
    mod = _load_module()
    fx = ROOT / "tests" / "fixtures" / "failure_case_corpus_minimal"
    out = tmp_path / "out"
    summary = mod.build_corpus(
        paired_casebook_csv=fx / "paired_casebook.csv",
        pal_results_jsonl=fx / "pal_results.jsonl",
        external_results_jsonl=fx / "external_l1_results.jsonl",
        path_coverage_csv=fx / "path_coverage.csv",
        atlas_anchor_csv=fx / "atlas_anchor.csv",
        selector_sensitivity_csv=fx / "selector_sensitivity.csv",
        broad_anchor_csv=None,
        conservative_anchor_csv=None,
        isolated_anchor_csv=None,
        output_dir=out,
    )
    assert summary["failure_cases_collected"] == 2
    assert summary["outcome_buckets"]["external_only"] == 1
    assert summary["outcome_buckets"]["both_wrong"] == 1
    assert (out / "failure_cases.jsonl").is_file()
    assert (out / "failure_cases.csv").is_file()
    assert (out / "feature_summary.json").is_file()
    assert (out / "pattern_seed_report.md").is_file()
    assert (out / "case_index.md").is_file()
    manifest = summary["manifest"]
    assert "created_at" in summary["meta"]
    assert manifest["row_counts_loaded"]["paired_casebook_rows"] == 2
    assert manifest["corpus_row_count"] == 2


def test_stage_priority_prefers_gold_absent_flag(tmp_path: Path) -> None:
    mod = _load_module()
    d = tmp_path / "fx1"
    d.mkdir()
    (d / "paired_casebook.csv").write_text(
        "example_id,question,gold_answer,pal_exact\n"
        "ex1,What is 2+2?,4,0\n",
        encoding="utf-8",
    )
    (d / "pal_results.jsonl").write_text(
        json.dumps({"example_id": "ex1", "result_metadata": {"selector_candidate_pool": [{"predicted_answer": "3"}]}})
        + "\n",
        encoding="utf-8",
    )
    (d / "path_coverage.csv").write_text(
        "example_id,gold_in_selector_pool,gold_in_trace_candidates,gold_in_execution_output,gold_absent_everywhere_detectable\n"
        "ex1,1,0,0,1\n",
        encoding="utf-8",
    )
    out = tmp_path / "out1"
    mod.build_corpus(
        paired_casebook_csv=d / "paired_casebook.csv",
        pal_results_jsonl=d / "pal_results.jsonl",
        external_results_jsonl=None,
        path_coverage_csv=d / "path_coverage.csv",
        atlas_anchor_csv=None,
        selector_sensitivity_csv=None,
        broad_anchor_csv=None,
        conservative_anchor_csv=None,
        isolated_anchor_csv=None,
        output_dir=out,
    )
    rows = [json.loads(x) for x in (out / "failure_cases.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert rows[0]["feature_tags"]["failure_stage_classification"] == "gold_absent_everywhere_detectable"


def test_mixed_answer_fields_count_toward_diversity(tmp_path: Path) -> None:
    mod = _load_module()
    d = tmp_path / "fx2"
    d.mkdir()
    (d / "paired_casebook.csv").write_text(
        "example_id,question,gold_answer,pal_exact\n"
        "ex1,Find total of 1 and 1,2,0\n",
        encoding="utf-8",
    )
    pal_row = {
        "example_id": "ex1",
        "result_metadata": {
            "selector_candidate_pool": [
                {"answer": "2"},
                {"extracted_answer": "3"},
                {"final_answer": "4"},
            ]
        },
    }
    (d / "pal_results.jsonl").write_text(json.dumps(pal_row) + "\n", encoding="utf-8")
    out = tmp_path / "out2"
    mod.build_corpus(
        paired_casebook_csv=d / "paired_casebook.csv",
        pal_results_jsonl=d / "pal_results.jsonl",
        external_results_jsonl=None,
        path_coverage_csv=None,
        atlas_anchor_csv=None,
        selector_sensitivity_csv=None,
        broad_anchor_csv=None,
        conservative_anchor_csv=None,
        isolated_anchor_csv=None,
        output_dir=out,
    )
    rows = [json.loads(x) for x in (out / "failure_cases.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert rows[0]["feature_tags"]["our_candidate_diversity"] == 3


def test_external_exact_fallback_and_missing_optional_inputs(tmp_path: Path) -> None:
    mod = _load_module()
    d = tmp_path / "fx3"
    d.mkdir()
    (d / "paired_casebook.csv").write_text(
        "example_id,question,gold_answer,pal_final_answer,pal_exact\n"
        "ex1,If 10/2 then answer?,5,4,0\n",
        encoding="utf-8",
    )
    (d / "pal_results.jsonl").write_text(
        json.dumps({"example_id": "ex1", "result_metadata": {"selector_candidate_pool": [{"predicted_answer": "4"}]}})
        + "\n",
        encoding="utf-8",
    )
    (d / "external_l1_results.jsonl").write_text(
        json.dumps({"example_id": "ex1", "final_answer_raw": "5", "result_metadata": {}}) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "out3"
    summary = mod.build_corpus(
        paired_casebook_csv=d / "paired_casebook.csv",
        pal_results_jsonl=d / "pal_results.jsonl",
        external_results_jsonl=d / "external_l1_results.jsonl",
        path_coverage_csv=d / "missing.csv",
        atlas_anchor_csv=d / "missing2.csv",
        selector_sensitivity_csv=d / "missing3.csv",
        broad_anchor_csv=None,
        conservative_anchor_csv=None,
        isolated_anchor_csv=None,
        output_dir=out,
    )
    assert summary["outcome_buckets"]["external_only"] == 1
    with (out / "failure_cases.csv").open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["outcome_bucket"] == "external_only"
