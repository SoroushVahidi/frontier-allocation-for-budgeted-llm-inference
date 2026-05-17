"""Tests for scripts/score_verifier_on_frontier_candidates.py"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

from score_verifier_on_frontier_candidates import (
    GOLD_FIELDS,
    SAFE_FEATURE_COLS,
    TRACE_MAX_CHARS,
    _detect_schema,
    _extract_per_example_record,
    _extract_training_format,
    _extract_unified_candidate_trace,
    build_feature_text,
    check_leakage,
    extract_candidates,
    main,
)


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

def _make_per_example_row(*, exact_match=1, gold_answer="42", method="frontier_v2", budget=4) -> dict:
    return {
        "question": "How many apples?",
        "final_nodes": [{"reasoning_text": "There are 5 trees with 8 apples each.", "branch_id": "b0"}],
        "final_answer_canonical": "40",
        "example_id": "openai_gsm8k_0",
        "budget": budget,
        "method": method,
        "model": "cohere-cmd-r",
        "dataset": "gsm8k",
        "seed": 42,
        "exact_match": exact_match,
        "gold_answer": gold_answer,
        "gold_answer_canonical": gold_answer,
        "gold_in_tree": True,
    }


def _make_unified_row() -> dict:
    return {
        "example_id": "openai_gsm8k_1",
        "budget": "4",
        "verifier_input": {
            "problem_statement": "How fast does John run?",
            "candidates_for_verifier": [
                {
                    "candidate_id": "cand_0",
                    "source_family": "frontier",
                    "final_answer": "10",
                    "normalized_answer": "10",
                    "trace_text": "John runs 60 miles in 3 days at 10 mph.",
                }
            ],
        },
    }


def _make_training_row(*, label=1) -> dict:
    return {
        "feature_text": "question: How many apples? | candidate_answer: 40 | candidate_trace_short: 5*8=40",
        "label": label,
        "row_id": "rrseed_abc123",
        "problem_id": "openai/gsm8k::openai_gsm8k_0::42::4",
    }


# ---------------------------------------------------------------------------
# Schema detection
# ---------------------------------------------------------------------------

class TestDetectSchema(unittest.TestCase):
    def test_per_example_records(self):
        self.assertEqual(_detect_schema(_make_per_example_row()), "per_example_records")

    def test_unified_candidate_trace(self):
        self.assertEqual(_detect_schema(_make_unified_row()), "unified_candidate_trace")

    def test_training_format(self):
        self.assertEqual(_detect_schema(_make_training_row()), "training_format")

    def test_fallback_is_per_example(self):
        self.assertEqual(_detect_schema({"question": "x"}), "per_example_records")


# ---------------------------------------------------------------------------
# Feature extraction — per_example_records
# ---------------------------------------------------------------------------

class TestExtractPerExampleRecord(unittest.TestCase):
    def test_returns_one_record(self):
        recs = _extract_per_example_record(_make_per_example_row())
        self.assertEqual(len(recs), 1)

    def test_question_in_feature_fields(self):
        rec = _extract_per_example_record(_make_per_example_row())[0]
        self.assertEqual(rec["feature_fields"]["question"], "How many apples?")

    def test_trace_from_final_nodes(self):
        rec = _extract_per_example_record(_make_per_example_row())[0]
        self.assertIn("apples", rec["feature_fields"]["candidate_trace_short"])

    def test_trace_truncated_to_max_chars(self):
        long_trace = "x" * (TRACE_MAX_CHARS + 100)
        row = _make_per_example_row()
        row["final_nodes"] = [{"reasoning_text": long_trace}]
        rec = _extract_per_example_record(row)[0]
        self.assertEqual(len(rec["feature_fields"]["candidate_trace_short"]), TRACE_MAX_CHARS)

    def test_candidate_answer_from_final_answer_canonical(self):
        rec = _extract_per_example_record(_make_per_example_row())[0]
        self.assertEqual(rec["feature_fields"]["candidate_answer"], "40")

    def test_gold_answer_only_in_metadata(self):
        rec = _extract_per_example_record(_make_per_example_row(gold_answer="999"))[0]
        ff = rec["feature_fields"]
        for v in ff.values():
            self.assertNotIn("999", str(v))
        self.assertEqual(rec["metadata"]["gold_answer_metadata"], "999")

    def test_exact_match_only_in_metadata(self):
        rec = _extract_per_example_record(_make_per_example_row(exact_match=1))[0]
        ff_str = " ".join(str(v) for v in rec["feature_fields"].values())
        self.assertNotIn("exact_match", ff_str)
        self.assertEqual(rec["metadata"]["exact_match_metadata"], 1)

    def test_empty_final_nodes(self):
        row = _make_per_example_row()
        row["final_nodes"] = []
        rec = _extract_per_example_record(row)[0]
        self.assertEqual(rec["feature_fields"]["candidate_trace_short"], "")


# ---------------------------------------------------------------------------
# Feature extraction — unified_candidate_trace
# ---------------------------------------------------------------------------

class TestExtractUnifiedCandidateTrace(unittest.TestCase):
    def test_returns_one_record_per_candidate(self):
        recs = _extract_unified_candidate_trace(_make_unified_row())
        self.assertEqual(len(recs), 1)

    def test_question_from_problem_statement(self):
        rec = _extract_unified_candidate_trace(_make_unified_row())[0]
        self.assertEqual(rec["feature_fields"]["question"], "How fast does John run?")

    def test_trace_from_trace_text(self):
        rec = _extract_unified_candidate_trace(_make_unified_row())[0]
        self.assertIn("60 miles", rec["feature_fields"]["candidate_trace_short"])

    def test_candidate_id_in_metadata(self):
        rec = _extract_unified_candidate_trace(_make_unified_row())[0]
        self.assertEqual(rec["metadata"]["candidate_id"], "cand_0")

    def test_empty_candidates(self):
        row = _make_unified_row()
        row["verifier_input"]["candidates_for_verifier"] = []
        recs = _extract_unified_candidate_trace(row)
        self.assertEqual(recs, [])


# ---------------------------------------------------------------------------
# Feature extraction — training format
# ---------------------------------------------------------------------------

class TestExtractTrainingFormat(unittest.TestCase):
    def test_preserves_feature_text(self):
        rec = _extract_training_format(_make_training_row())[0]
        self.assertIn("How many apples?", rec["feature_text"])

    def test_label_in_metadata_only(self):
        rec = _extract_training_format(_make_training_row(label=1))[0]
        self.assertEqual(rec["metadata"]["label_metadata"], 1)
        self.assertNotIn("label", rec.get("feature_text", ""))


# ---------------------------------------------------------------------------
# build_feature_text and leakage check
# ---------------------------------------------------------------------------

class TestBuildFeatureText(unittest.TestCase):
    def test_includes_non_empty_fields(self):
        ft = build_feature_text({"question": "Q?", "candidate_answer": "A", "candidate_trace_short": "T"})
        self.assertIn("question: Q?", ft)
        self.assertIn("candidate_answer: A", ft)
        self.assertIn("candidate_trace_short: T", ft)

    def test_excludes_empty_fields(self):
        ft = build_feature_text({"question": "Q?", "target_phrase": "", "candidate_answer": "A"})
        self.assertNotIn("target_phrase", ft)

    def test_uses_pipe_separator(self):
        ft = build_feature_text({"question": "Q?", "candidate_answer": "A"})
        self.assertIn(" | ", ft)

    def test_field_order_matches_safe_cols(self):
        ft = build_feature_text({"question": "Q?", "candidate_answer": "A", "candidate_trace_short": "T"})
        q_pos = ft.index("question:")
        a_pos = ft.index("candidate_answer:")
        t_pos = ft.index("candidate_trace_short:")
        self.assertLess(q_pos, a_pos)
        self.assertLess(a_pos, t_pos)


class TestCheckLeakage(unittest.TestCase):
    def test_no_leakage_clean_text(self):
        self.assertEqual(check_leakage("question: Q | candidate_answer: 40 | candidate_trace_short: trace"), [])

    def test_detects_gold_answer_field_name(self):
        violations = check_leakage("question: Q | gold_answer: 42")
        self.assertIn("gold_answer", violations)

    def test_detects_exact_match_field_name(self):
        violations = check_leakage("exact_match: 1 | question: Q")
        self.assertIn("exact_match", violations)

    def test_detects_is_correct(self):
        violations = check_leakage("is_correct: true | question: Q")
        self.assertIn("is_correct", violations)


# ---------------------------------------------------------------------------
# extract_candidates integration
# ---------------------------------------------------------------------------

class TestExtractCandidates(unittest.TestCase):
    def test_per_example_schema(self):
        rows = [_make_per_example_row() for _ in range(3)]
        cands, schema = extract_candidates(rows)
        self.assertEqual(schema, "per_example_records")
        self.assertEqual(len(cands), 3)
        for c in cands:
            self.assertIn("feature_text", c)

    def test_training_format_schema(self):
        rows = [_make_training_row(label=i % 2) for i in range(4)]
        cands, schema = extract_candidates(rows)
        self.assertEqual(schema, "training_format")
        self.assertEqual(len(cands), 4)

    def test_empty_input(self):
        cands, schema = extract_candidates([])
        self.assertEqual(cands, [])
        self.assertEqual(schema, "unknown")

    def test_gold_not_in_feature_text(self):
        rows = [_make_per_example_row(gold_answer="SECRET999")]
        cands, _ = extract_candidates(rows)
        self.assertNotIn("SECRET999", cands[0]["feature_text"])


# ---------------------------------------------------------------------------
# No forbidden API imports in script source
# ---------------------------------------------------------------------------

class TestNoApiImports(unittest.TestCase):
    def test_no_forbidden_imports(self):
        src_path = pathlib.Path(__file__).parent.parent / "scripts" / "score_verifier_on_frontier_candidates.py"
        src = src_path.read_text()
        forbidden = ["openai", "anthropic", "cohere", "httpx", "requests", "boto3"]
        for lib in forbidden:
            self.assertIsNone(
                re.search(rf"^\s*(import|from)\s+{lib}\b", src, re.MULTILINE),
                msg=f"Forbidden import '{lib}' found in script",
            )


# ---------------------------------------------------------------------------
# dry_run mode — no model loading
# ---------------------------------------------------------------------------

class TestDryRunMode(unittest.TestCase):
    def test_dry_run_creates_manifest_and_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rows_path = pathlib.Path(tmpdir) / "input.jsonl"
            with open(rows_path, "w") as f:
                for _ in range(3):
                    f.write(json.dumps(_make_per_example_row()) + "\n")

            rc = main([
                "--input-jsonl", str(rows_path),
                "--output-dir", tmpdir + "/out",
                "--mode", "dry_run",
                "--dry-run-rows", "2",
            ])
            self.assertEqual(rc, 0)
            out = pathlib.Path(tmpdir) / "out"
            self.assertTrue((out / "run_manifest.json").exists())
            self.assertTrue((out / "scoring_report.md").exists())
            # scored_candidates.jsonl should NOT be written in dry_run
            self.assertFalse((out / "scored_candidates.jsonl").exists())

    def test_dry_run_no_model_loaded(self):
        """dry_run must not call sentence_transformers or sklearn at all."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rows_path = pathlib.Path(tmpdir) / "input.jsonl"
            with open(rows_path, "w") as f:
                f.write(json.dumps(_make_per_example_row()) + "\n")

            with patch("score_verifier_on_frontier_candidates._load_sentence_transformer") as mock_st:
                rc = main([
                    "--input-jsonl", str(rows_path),
                    "--output-dir", tmpdir + "/out",
                    "--mode", "dry_run",
                ])
                mock_st.assert_not_called()
            self.assertEqual(rc, 0)

    def test_dry_run_leakage_fail_returns_2(self):
        """If a gold field appears in feature_text, dry_run must return exit code 2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rows_path = pathlib.Path(tmpdir) / "input.jsonl"
            # Inject a row where feature_text would be pre-built with a gold field name
            bad_row = _make_training_row()
            bad_row["feature_text"] = "question: Q | exact_match: 1 | candidate_answer: 40"
            with open(rows_path, "w") as f:
                f.write(json.dumps(bad_row) + "\n")

            rc = main([
                "--input-jsonl", str(rows_path),
                "--output-dir", tmpdir + "/out",
                "--mode", "dry_run",
                "--dry-run-rows", "1",
            ])
            self.assertEqual(rc, 2)

    def test_missing_input_file_returns_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = main([
                "--input-jsonl", "/nonexistent/path.jsonl",
                "--output-dir", tmpdir + "/out",
                "--mode", "dry_run",
            ])
            self.assertEqual(rc, 1)


# ---------------------------------------------------------------------------
# score mode — mocked model
# ---------------------------------------------------------------------------

class TestScoreMode(unittest.TestCase):
    def _make_mock_model(self):
        import numpy as np

        mock_st = MagicMock()
        # encode returns fake embeddings
        mock_st.encode.return_value = [[0.1, 0.2]] * 100

        mock_clf = MagicMock()
        mock_clf.classes_ = [0, 1]
        mock_clf.predict_proba.return_value = [[0.3, 0.7]] * 100
        mock_clf.fit.return_value = mock_clf

        return mock_st, mock_clf

    def test_score_mode_creates_all_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rows_path = pathlib.Path(tmpdir) / "input.jsonl"
            train_path = pathlib.Path(tmpdir) / "train.jsonl"

            with open(rows_path, "w") as f:
                for _ in range(5):
                    f.write(json.dumps(_make_per_example_row()) + "\n")
            with open(train_path, "w") as f:
                for label in [0, 0, 1, 0, 1]:
                    f.write(json.dumps(_make_training_row(label=label)) + "\n")

            mock_st, mock_clf = self._make_mock_model()

            with (
                patch("score_verifier_on_frontier_candidates._load_sentence_transformer", return_value=mock_st),
                patch("score_verifier_on_frontier_candidates._fit_lr_head", return_value=mock_clf),
                patch("pathlib.Path.exists", return_value=True),
            ):
                rc = main([
                    "--input-jsonl", str(rows_path),
                    "--output-dir", tmpdir + "/out",
                    "--model-dir", "fake/checkpoint",
                    "--train-jsonl", str(train_path),
                    "--mode", "score",
                ])

            self.assertEqual(rc, 0)
            out = pathlib.Path(tmpdir) / "out"
            self.assertTrue((out / "scored_candidates.jsonl").exists())
            self.assertTrue((out / "scoring_report.md").exists())
            self.assertTrue((out / "run_manifest.json").exists())

    def test_scored_candidates_have_proba_ready(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rows_path = pathlib.Path(tmpdir) / "input.jsonl"
            train_path = pathlib.Path(tmpdir) / "train.jsonl"

            with open(rows_path, "w") as f:
                for _ in range(3):
                    f.write(json.dumps(_make_per_example_row()) + "\n")
            with open(train_path, "w") as f:
                for label in [0, 1, 0]:
                    f.write(json.dumps(_make_training_row(label=label)) + "\n")

            mock_st, mock_clf = self._make_mock_model()

            with (
                patch("score_verifier_on_frontier_candidates._load_sentence_transformer", return_value=mock_st),
                patch("score_verifier_on_frontier_candidates._fit_lr_head", return_value=mock_clf),
                patch("pathlib.Path.exists", return_value=True),
            ):
                main([
                    "--input-jsonl", str(rows_path),
                    "--output-dir", tmpdir + "/out",
                    "--model-dir", "fake/checkpoint",
                    "--train-jsonl", str(train_path),
                    "--mode", "score",
                ])

            out = pathlib.Path(tmpdir) / "out"
            with open(out / "scored_candidates.jsonl") as f:
                scored = [json.loads(l) for l in f]
            self.assertEqual(len(scored), 3)
            for row in scored:
                self.assertIn("proba_ready", row)
                self.assertGreaterEqual(row["proba_ready"], 0.0)
                self.assertLessEqual(row["proba_ready"], 1.0)
                self.assertNotIn("gold_answer", row.get("feature_text", ""))
                self.assertNotIn("exact_match", row.get("feature_text", ""))

    def test_scored_gold_metadata_preserved(self):
        """Gold metadata must appear in output metadata, not in feature_text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rows_path = pathlib.Path(tmpdir) / "input.jsonl"
            train_path = pathlib.Path(tmpdir) / "train.jsonl"

            with open(rows_path, "w") as f:
                f.write(json.dumps(_make_per_example_row(exact_match=1, gold_answer="GOLD_VAL")) + "\n")
            with open(train_path, "w") as f:
                for label in [0, 1]:
                    f.write(json.dumps(_make_training_row(label=label)) + "\n")

            mock_st, mock_clf = self._make_mock_model()

            with (
                patch("score_verifier_on_frontier_candidates._load_sentence_transformer", return_value=mock_st),
                patch("score_verifier_on_frontier_candidates._fit_lr_head", return_value=mock_clf),
                patch("pathlib.Path.exists", return_value=True),
            ):
                main([
                    "--input-jsonl", str(rows_path),
                    "--output-dir", tmpdir + "/out",
                    "--model-dir", "fake/checkpoint",
                    "--train-jsonl", str(train_path),
                    "--mode", "score",
                ])

            out = pathlib.Path(tmpdir) / "out"
            with open(out / "scored_candidates.jsonl") as f:
                row = json.loads(f.readline())

            # Gold must NOT be in feature_text
            self.assertNotIn("GOLD_VAL", row["feature_text"])
            self.assertNotIn("exact_match", row["feature_text"])
            # Gold MUST be in metadata
            self.assertEqual(row["metadata"]["exact_match_metadata"], 1)
            self.assertEqual(row["metadata"]["gold_answer_metadata"], "GOLD_VAL")

    def test_multiple_input_files(self):
        """Score mode should handle multiple --input-jsonl files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = pathlib.Path(tmpdir) / "a.jsonl"
            p2 = pathlib.Path(tmpdir) / "b.jsonl"
            train_path = pathlib.Path(tmpdir) / "train.jsonl"

            with open(p1, "w") as f:
                for _ in range(2):
                    f.write(json.dumps(_make_per_example_row()) + "\n")
            with open(p2, "w") as f:
                for _ in range(3):
                    f.write(json.dumps(_make_per_example_row()) + "\n")
            with open(train_path, "w") as f:
                for label in [0, 1, 0]:
                    f.write(json.dumps(_make_training_row(label=label)) + "\n")

            mock_st, mock_clf = self._make_mock_model()

            with (
                patch("score_verifier_on_frontier_candidates._load_sentence_transformer", return_value=mock_st),
                patch("score_verifier_on_frontier_candidates._fit_lr_head", return_value=mock_clf),
                patch("pathlib.Path.exists", return_value=True),
            ):
                rc = main([
                    "--input-jsonl", str(p1),
                    "--input-jsonl", str(p2),
                    "--output-dir", tmpdir + "/out",
                    "--model-dir", "fake/checkpoint",
                    "--train-jsonl", str(train_path),
                    "--mode", "score",
                ])
            self.assertEqual(rc, 0)

            out = pathlib.Path(tmpdir) / "out"
            with open(out / "scored_candidates.jsonl") as f:
                rows = [json.loads(l) for l in f]
            self.assertEqual(len(rows), 5)


if __name__ == "__main__":
    unittest.main()
