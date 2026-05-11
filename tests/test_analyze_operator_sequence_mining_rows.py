from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from scripts import analyze_operator_sequence_mining_rows as analyzer


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "analyze_operator_sequence_mining_rows.py"


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _fixture_rows() -> list[dict[str, object]]:
    return [
        {
            "node_id": "n1",
            "parent_id": None,
            "feature_operator_sequence": ["direct_l1_anchor"],
            "feature_operator_sequence_key": "direct_l1_anchor",
            "feature_answer_entropy": 0.2,
            "feature_support_margin": 3,
            "feature_is_answer_outlier": False,
            "feature_current_answer_group_support": 4,
            "feature_current_answer_group_share": 0.8,
            "feature_operator_ngram_counts": {"n1:direct_l1_anchor": 1},
            "label_terminal_quality": 1.0,
            "label_best_descendant_quality": 1.0,
            "label_gold_in_subtree": True,
        },
        {
            "node_id": "n2",
            "parent_id": "n1",
            "feature_operator_sequence": ["direct_l1_anchor", "PAL/code_reasoning"],
            "feature_operator_sequence_key": "direct_l1_anchor->PAL/code_reasoning",
            "feature_answer_entropy": 1.1,
            "feature_support_margin": 1,
            "feature_is_answer_outlier": True,
            "feature_current_answer_group_support": 1,
            "feature_current_answer_group_share": 0.2,
            "feature_operator_ngram_counts": {
                "n1:direct_l1_anchor": 1,
                "n1:PAL/code_reasoning": 1,
                "n2:direct_l1_anchor->PAL/code_reasoning": 1,
            },
            "label_terminal_quality": 0.0,
            "label_best_descendant_quality": 0.5,
            "label_gold_in_subtree": False,
        },
        {
            "node_id": "n3",
            "parent_id": "n2",
            "feature_operator_sequence": ["direct_l1_anchor", "PAL/code_reasoning"],
            "feature_operator_sequence_key": "direct_l1_anchor->PAL/code_reasoning",
            "feature_answer_entropy": 0.9,
            "feature_support_margin": 2,
            "feature_is_answer_outlier": False,
            "feature_current_answer_group_support": 2,
            "feature_current_answer_group_share": 0.5,
            "feature_operator_ngram_counts": {
                "n1:direct_l1_anchor": 1,
                "n1:PAL/code_reasoning": 1,
                "n2:direct_l1_anchor->PAL/code_reasoning": 1,
            },
            "label_terminal_quality": 0.25,
            "label_best_descendant_quality": 0.75,
            "label_gold_in_subtree": True,
        },
    ]


def _run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_analyzer_summary_and_aggregation(tmp_path: Path) -> None:
    input_dir = tmp_path / "export"
    input_dir.mkdir(parents=True)
    _write_jsonl(input_dir / "path_prefix_rows.jsonl", _fixture_rows())
    (input_dir / "summary.json").write_text(
        json.dumps({"source_selection": {"row_type": "action_trace_pseudo_path"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "analysis"
    result = _run_script(["--input", str(input_dir), "--output-dir", str(output_dir), "--timestamp", "20260511T000000Z"])

    assert result.returncode == 0, result.stderr
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))

    assert summary["row_count"] == 3
    assert "feature_operator_sequence_key" in summary["feature_field_names"]
    assert "label_best_descendant_quality" in summary["label_field_names"]
    assert summary["best_descendant_quality_distribution"][0]["count"] == 1
    assert summary["gold_in_subtree_distribution"][0]["count"] == 2
    assert summary["top_operator_sequences"][0]["operator_sequence_key"] == "direct_l1_anchor->PAL/code_reasoning"
    assert summary["top_operator_sequences"][0]["count"] == 2
    assert summary["top_operator_sequences"][0]["mean_quality"] == 0.625
    assert summary["top_ngrams"][0]["ngram"] == "n1:direct_l1_anchor"
    assert summary["bucket_summaries"][0]["count"] == 1
    assert summary["source_row_type"] == "action_trace_pseudo_path"


def test_report_and_csv_files_written(tmp_path: Path) -> None:
    input_dir = tmp_path / "export"
    input_dir.mkdir(parents=True)
    _write_jsonl(input_dir / "path_prefix_rows.jsonl", _fixture_rows())
    (input_dir / "summary.json").write_text(
        json.dumps({"source_selection": {"row_type": "action_trace_pseudo_path"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "analysis"
    result = _run_script(["--input", str(input_dir), "--output-dir", str(output_dir), "--timestamp", "20260511T000000Z"])

    assert result.returncode == 0, result.stderr
    assert (output_dir / "operator_sequence_signal_report.md").is_file()
    assert (output_dir / "operator_sequence_quality_table.csv").is_file()
    assert (output_dir / "ngram_quality_table.csv").is_file()
    report = (output_dir / "operator_sequence_signal_report.md").read_text(encoding="utf-8").lower()
    assert "baseline" not in report
    assert "superiority" not in report
    assert "outperform" not in report


def test_missing_input_path_fails_clearly(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    result = _run_script(["--input", str(missing), "--output-dir", str(tmp_path / "analysis")])
    assert result.returncode != 0
    assert "Missing input path" in result.stderr


def test_script_has_no_api_client_imports_and_uses_helpers() -> None:
    source_path = Path(analyzer.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])

    forbidden = {"openai", "cohere", "anthropic", "requests", "google"}
    assert imported_modules.isdisjoint(forbidden)
    assert "export_operator_sequence_mining_rows" in source
    assert "operator_sequence_signal_report.md" in source
    assert "baseline" not in source.lower()
    assert "superiority" not in source.lower()


def test_analyzer_can_export_from_source_path(tmp_path: Path) -> None:
    source_file = tmp_path / "source.jsonl"
    _write_jsonl(
        source_file,
        [
            {
                "provider": "cohere",
                "model": "command-a",
                "dataset": "openai/gsm8k",
                "seed": 1,
                "budget": 4,
                "method": "demo",
                "example_id": "ex-1",
                "exact_match": 1,
                "gold_in_tree": 1,
                "failure_tag": "correct",
                "final_answer_source": "repair_layer",
                "gold_answer": "2",
                "gold_answer_canonical": "2",
                "selected_answer_canonical": "2",
                "final_answer_canonical": "2",
                "result_metadata": {
                    "answer_group_support_counts": {"2": 2},
                    "action_trace": [
                        {
                            "branch_id": "b0",
                            "branch_depth": 1,
                            "action": "expand",
                            "strategy_family": "direct_formula_family",
                            "predicted_answer": "2",
                            "predicted_answer_normalized": "2",
                        }
                    ],
                },
            }
        ],
    )

    output_dir = tmp_path / "analysis"
    result = _run_script(["--input", str(source_file), "--output-dir", str(output_dir)])

    assert result.returncode == 0, result.stderr
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["row_count"] >= 1
