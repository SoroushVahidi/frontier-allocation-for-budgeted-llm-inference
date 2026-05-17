from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.run_cohere_real_model_cost_normalized_validation import maybe_compute_disjointness_preflight


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_runner_preflight_detects_metadata_example_id_overlap(tmp_path: Path) -> None:
    selected = tmp_path / "exact_cases.jsonl"
    prior = tmp_path / "prior_scored.jsonl"
    proof = tmp_path / "disjointness_proof.json"

    _write_jsonl(
        selected,
        [
            {
                "example_id": "openai_gsm8k_0",
                "question": "Q overlap",
                "gold_answer": "42",
                "gold_answer_canonical": "42",
            }
        ],
    )
    _write_jsonl(
        prior,
        [
            {
                "feature_text": "question: Q overlap | candidate_answer: 42 | candidate_trace_short: x",
                "metadata": {"example_id": "openai_gsm8k_0"},
            }
        ],
    )

    args = argparse.Namespace(
        exact_cases_jsonl=str(selected),
        disjointness_prior_jsonl=[str(prior)],
        disjointness_prior_label=["prior_40_scored"],
        disjointness_proof_json=str(proof),
        allow_disjointness_overlap=False,
    )

    try:
        maybe_compute_disjointness_preflight(args=args, out_dir=tmp_path)
        raise AssertionError("expected overlap failure")
    except RuntimeError as exc:
        assert "overlap detected" in str(exc).lower()

    payload = json.loads(proof.read_text(encoding="utf-8"))
    assert payload["overlap_example_ids_with_prior"] == 1
    assert payload["source_counts"]["prior_40_scored"]["unique_example_ids"] == 1


def test_runner_preflight_can_allow_overlap_for_diagnostics(tmp_path: Path) -> None:
    selected = tmp_path / "exact_cases.jsonl"
    prior = tmp_path / "prior_scored.jsonl"

    _write_jsonl(
        selected,
        [
            {
                "example_id": "openai_gsm8k_0",
                "question": "Q overlap",
                "gold_answer": "42",
                "gold_answer_canonical": "42",
            }
        ],
    )
    _write_jsonl(
        prior,
        [
            {
                "feature_text": "question: Q overlap | candidate_answer: 42 | candidate_trace_short: x",
                "metadata": {"example_id": "openai_gsm8k_0"},
            }
        ],
    )

    args = argparse.Namespace(
        exact_cases_jsonl=str(selected),
        disjointness_prior_jsonl=[str(prior)],
        disjointness_prior_label=["prior_40_scored"],
        disjointness_proof_json="",
        allow_disjointness_overlap=True,
    )

    proof_path = maybe_compute_disjointness_preflight(args=args, out_dir=tmp_path)
    assert proof_path is not None
    payload = json.loads(Path(proof_path).read_text(encoding="utf-8"))
    assert payload["overlap_example_ids_with_prior"] == 1
