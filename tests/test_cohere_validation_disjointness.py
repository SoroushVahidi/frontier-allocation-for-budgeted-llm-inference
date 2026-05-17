from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.compute_cohere_validation_disjointness import (
    collect_ids_questions,
    compute_disjointness,
    extract_example_id,
    extract_question,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_extract_example_id_top_level() -> None:
    row = {"example_id": "openai_gsm8k_0", "question": "Q"}
    assert extract_example_id(row) == "openai_gsm8k_0"


def test_extract_example_id_metadata_nested() -> None:
    row = {"metadata": {"example_id": "openai_gsm8k_1"}}
    assert extract_example_id(row) == "openai_gsm8k_1"


def test_extract_question_from_feature_text() -> None:
    row = {
        "feature_text": (
            "question: John has 3 apples and eats 1. How many left? | "
            "candidate_answer: 2 | candidate_trace_short: short"
        ),
        "metadata": {"example_id": "openai_gsm8k_2"},
    }
    assert extract_question(row) == "John has 3 apples and eats 1. How many left?"


def test_collect_ids_questions_mixed_schema(tmp_path: Path) -> None:
    path = tmp_path / "mixed.jsonl"
    _write_jsonl(
        path,
        [
            {"example_id": "e0", "question": "Q0"},
            {"metadata": {"example_id": "e1", "question": "Q1"}},
            {
                "metadata": {"example_id": "e2"},
                "feature_text": "question: Q2 | candidate_answer: A2 | candidate_trace_short: T2",
            },
        ],
    )

    ids, questions, summary = collect_ids_questions(path)
    assert ids == {"e0", "e1", "e2"}
    assert questions == {"Q0", "Q1", "Q2"}
    assert summary.rows == 3
    assert summary.unique_example_ids == 3
    assert summary.unique_questions == 3


def test_scored_candidates_metadata_example_id_extraction(tmp_path: Path) -> None:
    selected = tmp_path / "selected.jsonl"
    prior = tmp_path / "prior_scored.jsonl"

    _write_jsonl(
        selected,
        [
            {"example_id": "openai_gsm8k_0", "question": "Q overlap"},
            {"example_id": "openai_gsm8k_9", "question": "Q unique"},
        ],
    )
    _write_jsonl(
        prior,
        [
            {
                "feature_text": "question: Q overlap | candidate_answer: 42 | candidate_trace_short: x",
                "metadata": {"example_id": "openai_gsm8k_0"},
            },
            {
                "feature_text": "question: Q other | candidate_answer: 5 | candidate_trace_short: y",
                "metadata": {"example_id": "openai_gsm8k_1"},
            },
        ],
    )

    proof = compute_disjointness(
        selected_cases_jsonl=selected,
        prior_jsonls=[prior],
        source_labels=["prior_40_scored"],
    )

    assert proof["source_counts"]["prior_40_scored"]["unique_example_ids"] == 2
    assert proof["overlap_example_ids_with_prior"] == 1
    assert "openai_gsm8k_0" in proof["overlap_example_ids_preview"]


def test_cli_fail_on_overlap(tmp_path: Path) -> None:
    selected = tmp_path / "selected.jsonl"
    prior = tmp_path / "prior.jsonl"
    out = tmp_path / "proof.json"

    _write_jsonl(selected, [{"example_id": "openai_gsm8k_0", "question": "Q"}])
    _write_jsonl(prior, [{"metadata": {"example_id": "openai_gsm8k_0"}, "feature_text": "question: Q | candidate_answer: 1"}])

    res = subprocess.run(
        [
            sys.executable,
            "scripts/compute_cohere_validation_disjointness.py",
            "--selected-cases-jsonl",
            str(selected),
            "--prior-jsonl",
            str(prior),
            "--prior-label",
            "prior",
            "--output-json",
            str(out),
            "--fail-on-overlap",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )

    assert res.returncode == 2
    proof = json.loads(out.read_text(encoding="utf-8"))
    assert proof["overlap_example_ids_with_prior"] == 1


def test_script_has_no_provider_api_imports() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "compute_cohere_validation_disjointness.py"
    txt = script_path.read_text(encoding="utf-8").lower()
    assert "import cohere" not in txt
    assert "from cohere" not in txt
    assert "import openai" not in txt
    assert "from openai" not in txt
