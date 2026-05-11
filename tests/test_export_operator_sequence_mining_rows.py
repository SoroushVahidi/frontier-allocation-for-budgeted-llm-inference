from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from scripts import export_operator_sequence_mining_rows as exporter


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "export_operator_sequence_mining_rows.py"


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _fixture_rows() -> list[dict[str, object]]:
    return [
        {
            "provider": "cohere",
            "model": "command-a",
            "dataset": "openai/gsm8k",
            "seed": 7,
            "budget": 4,
            "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
            "example_id": "ex-action-trace",
            "exact_match": 1,
            "gold_in_tree": 1,
            "failure_tag": "correct",
            "final_answer_source": "repair_layer",
            "gold_answer": "8",
            "gold_answer_canonical": "8",
            "selected_answer_canonical": "8",
            "final_answer_canonical": "8",
            "result_metadata": {
                "answer_group_support_counts": {"8": 2, "7": 1},
                "action_trace": [
                    {
                        "branch_id": "b0",
                        "parent_branch_id": None,
                        "branch_depth": 1,
                        "action": "expand",
                        "strategy_family": "direct_formula_family",
                        "reasoning_text": "step one",
                        "response_text": "{\"answer\":\"7\"}",
                        "predicted_answer": "7",
                        "predicted_answer_normalized": "7",
                        "group_key": "7",
                    },
                    {
                        "branch_id": "b1",
                        "parent_branch_id": "b0",
                        "branch_depth": 2,
                        "action": "expand",
                        "strategy_family": "pal_seed",
                        "reasoning_text": "step two",
                        "response_text": "{\"answer\":\"8\"}",
                        "predicted_answer": "8",
                        "predicted_answer_normalized": "8",
                        "group_key": "8",
                    },
                ],
            },
        },
        {
            "provider": "cohere",
            "model": "command-a",
            "dataset": "openai/gsm8k",
            "seed": 8,
            "budget": 4,
            "method": "external_l1_max",
            "example_id": "ex-final-nodes",
            "exact_match": 1,
            "gold_in_tree": 1,
            "failure_tag": "correct",
            "final_answer_source": "controller_metadata_final_answer",
            "gold_answer": "11",
            "gold_answer_canonical": "11",
            "selected_answer_canonical": "11",
            "final_answer_canonical": "11",
            "final_nodes": [
                {
                    "branch_id": "fn0",
                    "predicted_answer": "11",
                    "predicted_answer_normalized": "11",
                    "reasoning_text": "final node",
                    "source_metadata": "pal_seed",
                }
            ],
        },
        {
            "provider": "cohere",
            "model": "command-a",
            "dataset": "openai/gsm8k",
            "seed": 9,
            "budget": 4,
            "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
            "example_id": "ex-singleton",
            "exact_match": 0,
            "gold_in_tree": 0,
            "failure_tag": "correct answer absent from explored tree",
            "final_answer_source": "repair_layer",
            "gold_answer": "5",
            "gold_answer_canonical": "5",
            "selected_answer_canonical": "4",
            "final_answer_canonical": "4",
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


def test_dry_run_does_not_write_output(tmp_path: Path) -> None:
    input_path = tmp_path / "per_example_records.jsonl"
    _write_jsonl(input_path, _fixture_rows())
    output_dir = tmp_path / "exported"

    result = _run_script(["--input", str(input_path), "--dry-run", "--output-dir", str(output_dir)])

    assert result.returncode == 0, result.stderr
    assert not output_dir.exists()
    assert "candidate_rows" in result.stdout
    assert "available_trace_fields" in result.stdout


def test_exported_rows_contain_feature_and_label_separation(tmp_path: Path) -> None:
    input_path = tmp_path / "per_example_records.jsonl"
    _write_jsonl(input_path, _fixture_rows())
    output_dir = tmp_path / "exported"

    result = _run_script(["--input", str(input_path), "--output-dir", str(output_dir), "--timestamp", "20260511T000000Z"])
    assert result.returncode == 0, result.stderr

    rows_path = output_dir / "path_prefix_rows.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 4

    for row in rows:
        feature_keys = {key for key in row if key.startswith("feature_")}
        label_keys = {key for key in row if key.startswith("label_")}
        assert feature_keys
        assert label_keys
        assert feature_keys.isdisjoint(label_keys)
        for key in feature_keys:
            lowered = key.lower()
            assert "gold" not in lowered
            assert "is_correct" not in lowered
            assert "exact" not in lowered
            assert "label" not in lowered


def test_summary_counts_match_exported_rows(tmp_path: Path) -> None:
    input_path = tmp_path / "per_example_records.jsonl"
    _write_jsonl(input_path, _fixture_rows())
    output_dir = tmp_path / "exported"

    result = _run_script(["--input", str(input_path), "--output-dir", str(output_dir), "--timestamp", "20260511T000000Z"])
    assert result.returncode == 0, result.stderr

    rows_path = output_dir / "path_prefix_rows.jsonl"
    summary_path = output_dir / "summary.json"
    rows = [line for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary["exported_rows"] == len(rows)
    assert summary["candidate_rows"] == len(rows)
    assert summary["source_resolutions"][0]["row_count"] == len(rows)


def test_missing_input_path_fails_clearly(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jsonl"
    result = _run_script(["--input", str(missing), "--dry-run"])
    assert result.returncode != 0
    assert "Missing input artifact" in result.stderr


def test_script_has_no_api_client_imports_and_uses_helpers() -> None:
    source_path = Path(exporter.__file__)
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
    assert "build_path_prefix_row" in source
    assert "def answer_entropy" not in source
    assert "def operator_ngrams" not in source
