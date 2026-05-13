from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import generate_relationready_corruption_pool as runner  # noqa: E402
from scripts import qa_relationready_corruption_pool as qa  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _seed_rows() -> list[dict]:
    return [
        {
            "case_id": "openai_gsm8k_1",
            "normalized_case_id": "gsm8k_1",
            "candidate_id": "cand_1",
            "candidate_source": "gold_derived_smoke",
            "candidate_formula": "a + b + 12",
            "relation_ready_label": "ready",
            "first_error_axis": "none",
        },
        {
            "case_id": "openai_gsm8k_2",
            "normalized_case_id": "gsm8k_2",
            "candidate_id": "cand_2",
            "candidate_source": "gold_derived_smoke",
            "solution_formula": "x / 12",
            "prompt_gold_inconsistent_flag": True,
            "relation_ready_label": "ready",
            "first_error_axis": "none",
        },
    ]


def test_runner_creates_expected_files_and_rows(tmp_path: Path):
    seed_path = tmp_path / "seed.jsonl"
    out_dir = tmp_path / "pool"
    _write_jsonl(seed_path, _seed_rows())

    summary = runner.main(
        [
            "--input",
            str(seed_path),
            "--out-dir",
            str(out_dir),
            "--max-per-row",
            "5",
        ]
    )

    assert summary["row_count"] >= 1
    assert summary["skipped_prompt_gold_inconsistent_count"] == 1
    assert (out_dir / "corruption_pool_rows.jsonl").exists()
    assert (out_dir / "corruption_pool_rows.csv").exists()
    assert (out_dir / "corruption_pool_summary.json").exists()
    assert (out_dir / "corruption_pool_report.md").exists()

    rows = [json.loads(line) for line in (out_dir / "corruption_pool_rows.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows
    assert all(row["synthetic_negative"] is True for row in rows)
    assert all(row["relation_ready_label"] == "not_ready" for row in rows)
    assert all(row["candidate_source"] == "synthetic_corrupt" for row in rows)
    assert all(row["parent_candidate_id"] == "cand_1" for row in rows)
    assert all(row["corruption_operator"] in runner.OPERATOR_ALIASES for row in rows)


def test_runner_is_deterministic(tmp_path: Path):
    seed_path = tmp_path / "seed.jsonl"
    out_a = tmp_path / "pool_a"
    out_b = tmp_path / "pool_b"
    _write_jsonl(seed_path, [_seed_rows()[0]])

    summary_a = runner.main(["--input", str(seed_path), "--out-dir", str(out_a), "--max-per-row", "5", "--seed", "7"])
    summary_b = runner.main(["--input", str(seed_path), "--out-dir", str(out_b), "--max-per-row", "5", "--seed", "7"])

    assert summary_a == summary_b
    rows_a = (out_a / "corruption_pool_rows.jsonl").read_text(encoding="utf-8")
    rows_b = (out_b / "corruption_pool_rows.jsonl").read_text(encoding="utf-8")
    assert rows_a == rows_b


def test_qa_catches_unchanged_formula_and_missing_labels(tmp_path: Path):
    rows = [
        {
            "case_id": "c1",
            "normalized_case_id": "c1",
            "parent_candidate_id": "cand_1",
            "candidate_id": "cand_1:var_rebind_swap:0",
            "candidate_source": "synthetic_corrupt",
            "corruption_operator": "var_rebind_swap",
            "corruption_status": "generated",
            "synthetic_negative": True,
            "relation_ready_label": "not_ready",
            "first_error_axis": "wrong_target_variable",
            "label_source": "synthetic_corruption",
            "label_confidence": "high",
            "original_formula": "a + b",
            "corrupted_formula": "a + b",
            "qa_trivial_flag": False,
            "qa_broken_formula_flag": False,
            "qa_notes": "",
        },
        {
            "case_id": "c2",
            "normalized_case_id": "c2",
            "candidate_id": "cand_2:relation_delete:0",
            "candidate_source": "synthetic_corrupt",
            "corruption_status": "generated",
            "synthetic_negative": True,
            "relation_ready_label": "not_ready",
            "first_error_axis": "wrong_relation",
            "label_source": "synthetic_corruption",
            "label_confidence": "high",
            "original_formula": "a + b",
            "corrupted_formula": "a +",
            "qa_trivial_flag": False,
            "qa_broken_formula_flag": False,
            "qa_notes": "",
        },
        {
            "case_id": "c3",
            "normalized_case_id": "c3",
            "candidate_id": "cand_3:relation_delete:0",
            "candidate_source": "synthetic_corrupt",
            "corruption_status": "generated",
            "synthetic_negative": True,
            "relation_ready_label": "not_ready",
            "first_error_axis": "wrong_relation",
            "label_source": "synthetic_corruption",
            "label_confidence": "high",
            "original_formula": "a + b",
            "corrupted_formula": "a",
            "qa_trivial_flag": False,
            "qa_broken_formula_flag": False,
            "qa_notes": "",
            "prompt_gold_inconsistent_flag": True,
        },
    ]
    checked, summary = qa.qa_rows(rows)
    assert summary["row_count"] == 3
    assert summary["trivial_formula_count"] == 1
    assert summary["broken_formula_count"] == 1
    assert summary["prompt_gold_inconsistent_not_for_training_count"] == 1
    assert checked[0]["qa_pass"] is False
    assert checked[0]["qa_trivial_flag"] is True
    assert checked[1]["qa_pass"] is False
    assert checked[1]["qa_broken_formula_flag"] is True
    assert checked[2]["training_eligibility"] == "not_for_training"


def test_no_eval_and_no_model_imports_in_new_scripts():
    runner_source = Path(runner.__file__).read_text(encoding="utf-8")
    qa_source = Path(qa.__file__).read_text(encoding="utf-8")
    assert "eval(" not in runner_source
    assert "eval(" not in qa_source
    assert "import openai" not in runner_source.lower()
    assert "import cohere" not in runner_source.lower()
    assert "import openai" not in qa_source.lower()
    assert "import cohere" not in qa_source.lower()


def test_cli_parsing_accepts_operator_list():
    args = runner.parse_args(
        [
            "--input",
            "/tmp/seed.jsonl",
            "--operators",
            "var_rebind_swap,unit_scale",
            "--max-per-row",
            "2",
        ]
    )
    assert args.operators == ["var_rebind_swap", "unit_scale"]
