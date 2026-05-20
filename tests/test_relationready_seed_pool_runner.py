from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import extract_relationready_seed_pool as seed_pool  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _rows() -> list[dict]:
    return [
        {
            "case_id": "openai_gsm8k_1",
            "normalized_case_id": "gsm8k_1",
            "candidate_id": "cand_1",
            "candidate_source": "declarative_v2",
            "candidate_formula": "a + b + 12",
            "relation_ready_label": True,
            "relation_ready_source": "posthoc_exact_no_blocker",
            "prompt_gold_inconsistent_flag": False,
            "split": "train",
        },
        {
            "case_id": "openai_gsm8k_2",
            "normalized_case_id": "gsm8k_2",
            "candidate_id": "cand_2",
            "candidate_source": "declarative_v2",
            "candidate_formula": "x + y",
            "relation_ready_label": True,
            "relation_ready_source": "posthoc_exact_no_blocker",
            "prompt_gold_inconsistent_flag": False,
            "split": "eval_holdout",
        },
        {
            "case_id": "openai_gsm8k_3",
            "normalized_case_id": "gsm8k_3",
            "candidate_id": "cand_3",
            "candidate_source": "declarative_v1",
            "solution_formula": "c - d",
            "relation_ready_label": "true",
            "relation_ready_source": "posthoc_exact_no_blocker",
            "prompt_gold_inconsistent_flag": True,
            "split": "train",
        },
        {
            "case_id": "openai_gsm8k_4",
            "normalized_case_id": "gsm8k_4",
            "candidate_id": "cand_4",
            "candidate_source": "bftc_only",
            "candidate_formula": "n / 2",
            "relation_ready_label": False,
            "relation_ready_source": "conservative_blocker",
            "prompt_gold_inconsistent_flag": False,
            "split": "train",
        },
    ]


def test_seed_pool_extracts_clean_positive_rows(tmp_path: Path):
    seed_path = tmp_path / "seed.jsonl"
    out_dir = tmp_path / "seed_pool"
    _write_jsonl(seed_path, _rows())

    summary = seed_pool.main(["--input", str(seed_path), "--out-dir", str(out_dir)])

    assert summary["selected_row_count"] == 1
    assert summary["skipped_reason_counts"]["disallowed_split"] == 1
    assert summary["skipped_reason_counts"]["prompt_gold_inconsistent"] == 1
    assert summary["skipped_reason_counts"]["not_positive"] == 1
    rows = [json.loads(line) for line in (out_dir / "seed_rows.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["candidate_id"] == "cand_1"
    assert row["candidate_formula"] == "a + b + 12"
    assert row["relation_ready_label"] is True
    assert row["seed_status"] == "selected_clean_positive"


def test_seed_pool_is_deterministic(tmp_path: Path):
    seed_path = tmp_path / "seed.jsonl"
    _write_jsonl(seed_path, _rows())
    out_a = tmp_path / "seed_pool_a"
    out_b = tmp_path / "seed_pool_b"

    summary_a = seed_pool.main(["--input", str(seed_path), "--out-dir", str(out_a)])
    summary_b = seed_pool.main(["--input", str(seed_path), "--out-dir", str(out_b)])

    assert summary_a == summary_b
    assert (out_a / "seed_rows.jsonl").read_text(encoding="utf-8") == (
        out_b / "seed_rows.jsonl"
    ).read_text(encoding="utf-8")


def test_seed_pool_can_exclude_case_ids(tmp_path: Path):
    seed_path = tmp_path / "seed.jsonl"
    _write_jsonl(seed_path, _rows())
    out_dir = tmp_path / "seed_pool"
    summary = seed_pool.main(
        [
            "--input",
            str(seed_path),
            "--out-dir",
            str(out_dir),
            "--exclude-case-ids",
            "gsm8k_1",
        ]
    )

    assert summary["selected_row_count"] == 0
    assert summary["skipped_reason_counts"]["excluded_case_id"] == 1


def test_seed_pool_source_contains_no_model_imports_or_eval():
    source = Path(seed_pool.__file__).read_text(encoding="utf-8").lower()
    assert "eval(" not in source
    assert "import openai" not in source
    assert "import cohere" not in source

