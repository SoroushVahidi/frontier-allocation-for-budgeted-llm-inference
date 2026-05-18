"""Tests for scripts/join_verifier_scores_to_failure_features.py."""

from __future__ import annotations

import csv
import json
import pathlib
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

from join_verifier_scores_to_failure_features import flatten_scored_row, main


BASELINE = "external_l1_max"
FRONTIER = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"
ARTIFACT_LABEL = "external_only_loss_collection_pal_vs_l1_round2_20260506T130225Z"


def _feature_row(
    *,
    example_id: str = "openai_gsm8k_1",
    artifact_label: str = ARTIFACT_LABEL,
    baseline_method: str = BASELINE,
    frontier_method: str = FRONTIER,
    budget: str = "6",
    seed: str = "20260501",
    oracle_recoverable: str = "0",
    regression_risk: str = "0",
    both_wrong: str = "0",
    both_correct: str = "0",
    disagreement: str = "0",
) -> dict[str, str]:
    return {
        "artifact_label": artifact_label,
        "source_artifact_path": "outputs/external_only_loss_collection_pal_vs_l1_round2_20260506T130225Z",
        "example_id": example_id,
        "problem_id": "",
        "baseline_method": baseline_method,
        "frontier_method": frontier_method,
        "budget": budget,
        "seed": seed,
        "oracle_recoverable": oracle_recoverable,
        "regression_risk": regression_risk,
        "both_wrong": both_wrong,
        "both_correct": both_correct,
        "disagreement": disagreement,
    }


def _scored_row(
    *,
    example_id: str = "openai_gsm8k_1",
    method: str = BASELINE,
    budget: str = "6",
    seed: str = "20260501",
    proba_ready: float = 0.9,
    predicted_label: int | None = None,
    artifact_label: str = ARTIFACT_LABEL,
) -> dict:
    if predicted_label is None:
        predicted_label = int(proba_ready >= 0.5)
    return {
        "proba_ready": proba_ready,
        "score_ready": proba_ready,
        "predicted_label": predicted_label,
        "feature_text": "question: Q | candidate_answer: 42 | candidate_trace_short: T",
        "metadata": {
            "example_id": example_id,
            "method": method,
            "budget": budget,
            "seed": seed,
            "dataset": "openai/gsm8k",
            "model": "command-a-03-2025",
            "artifact_label": artifact_label,
        },
    }


def _write_feature_csv(path: pathlib.Path, rows: list[dict[str, str]]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_scored_jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _read_csv(path: pathlib.Path) -> list[dict[str, str]]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


class TestFlattening(unittest.TestCase):
    def test_flatten_scored_row_extracts_metadata_and_candidate_answer(self):
        raw = _scored_row()
        flat = flatten_scored_row(raw, score_field="proba_ready")
        self.assertEqual(flat["example_id"], "openai_gsm8k_1")
        self.assertEqual(flat["method"], BASELINE)
        self.assertEqual(flat["candidate_answer"], "42")
        self.assertIsInstance(flat["proba_ready"], float)


class TestJoinScript(unittest.TestCase):
    def _run(self, feature_rows: list[dict[str, str]], scored_rows: list[dict], extra_args: list[str] | None = None):
        extra_args = extra_args or []
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        tmp = pathlib.Path(tmpdir)
        feature_csv = tmp / "features.csv"
        scored_jsonl = tmp / "scored.jsonl"
        out_dir = tmp / "out"
        _write_feature_csv(feature_csv, feature_rows)
        _write_scored_jsonl(scored_jsonl, scored_rows)
        rc = main(
            [
                "--feature-table-csv",
                str(feature_csv),
                "--scored-candidates-jsonl",
                str(scored_jsonl),
                "--output-dir",
                str(out_dir),
                "--artifact-label",
                ARTIFACT_LABEL,
                "--artifact-path",
                "outputs/external_only_loss_collection_pal_vs_l1_round2_20260506T130225Z",
            ]
            + extra_args
        )
        self.assertEqual(rc, 0)
        return out_dir

    def test_exact_key_join(self):
        out_dir = self._run(
            [_feature_row()],
            [
                _scored_row(method=BASELINE, proba_ready=0.95),
                _scored_row(method=FRONTIER, proba_ready=0.40),
            ],
        )
        joined = _read_csv(out_dir / "joined_failure_pattern_features.csv")
        self.assertEqual(joined[0]["verifier_join_status"], "matched_both")
        self.assertAlmostEqual(float(joined[0]["baseline_proba_ready_max"]), 0.95, places=6)
        self.assertAlmostEqual(float(joined[0]["frontier_proba_ready_max"]), 0.40, places=6)

    def test_fallback_key_join_when_budget_seed_missing(self):
        out_dir = self._run(
            [_feature_row(budget="", seed="")],
            [
                _scored_row(method=BASELINE, budget="6", seed="20260501", proba_ready=0.70),
                _scored_row(method=FRONTIER, budget="6", seed="20260501", proba_ready=0.60),
            ],
        )
        diag = _read_csv(out_dir / "join_match_diagnostics.csv")[0]
        self.assertEqual(diag["baseline_join_key_used"], "artifact_label+example_id+method")
        self.assertEqual(diag["frontier_join_key_used"], "artifact_label+example_id+method")
        joined = _read_csv(out_dir / "joined_failure_pattern_features.csv")[0]
        self.assertEqual(joined["verifier_join_status"], "matched_both")

    def test_duplicate_match_aggregation_top2_gap_and_std(self):
        out_dir = self._run(
            [_feature_row()],
            [
                _scored_row(method=BASELINE, proba_ready=0.80, predicted_label=1),
                _scored_row(method=BASELINE, proba_ready=0.60, predicted_label=0),
                _scored_row(method=FRONTIER, proba_ready=0.70, predicted_label=1),
            ],
        )
        joined = _read_csv(out_dir / "joined_failure_pattern_features.csv")[0]
        self.assertEqual(joined["baseline_scored_candidate_count"], "2")
        self.assertEqual(joined["baseline_predicted_ready_count"], "1")
        self.assertAlmostEqual(float(joined["baseline_proba_ready_mean"]), 0.70, places=6)
        self.assertAlmostEqual(float(joined["baseline_proba_ready_top2_gap"]), 0.20, places=6)
        self.assertAlmostEqual(float(joined["baseline_proba_ready_std"]), 0.141421, places=5)
        self.assertEqual(joined["verifier_join_match_count_baseline"], "2")

    def test_unmatched_rows_and_unmatched_scored_candidates_exported(self):
        out_dir = self._run(
            [_feature_row(example_id="openai_gsm8k_missing")],
            [_scored_row(example_id="openai_gsm8k_other", method=BASELINE, proba_ready=0.3)],
        )
        joined = _read_csv(out_dir / "joined_failure_pattern_features.csv")[0]
        self.assertEqual(joined["verifier_join_status"], "unmatched")
        unmatched_feature = _read_csv(out_dir / "unmatched_feature_rows.csv")
        unmatched_scored = _read_csv(out_dir / "unmatched_scored_candidates.csv")
        self.assertEqual(len(unmatched_feature), 1)
        self.assertEqual(len(unmatched_scored), 1)

    def test_fuzzy_method_matching_reported(self):
        fuzzy_frontier = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4"
        out_dir = self._run(
            [_feature_row(frontier_method=fuzzy_frontier)],
            [
                _scored_row(method=BASELINE, proba_ready=0.30),
                _scored_row(method=FRONTIER, proba_ready=0.80),
            ],
        )
        diag = _read_csv(out_dir / "join_match_diagnostics.csv")[0]
        self.assertEqual(diag["frontier_method_match_mode"], "fuzzy")
        metrics = json.loads((out_dir / "verifier_join_metrics.json").read_text())
        self.assertGreaterEqual(metrics["fuzzy_method_match_count"], 1)
        self.assertTrue(any("Fuzzy method matching" in x for x in metrics["limitations"]))

    def test_output_files_created(self):
        out_dir = self._run(
            [_feature_row()],
            [
                _scored_row(method=BASELINE, proba_ready=0.91),
                _scored_row(method=FRONTIER, proba_ready=0.22),
            ],
        )
        expected = {
            "joined_failure_pattern_features.csv",
            "verifier_join_report.md",
            "verifier_join_metrics.json",
            "join_match_diagnostics.csv",
            "unmatched_feature_rows.csv",
            "unmatched_scored_candidates.csv",
            "verifier_score_feature_summary.csv",
        }
        existing = {p.name for p in out_dir.iterdir()}
        self.assertTrue(expected.issubset(existing))


class TestNoApiImports(unittest.TestCase):
    def test_no_forbidden_provider_imports(self):
        src_path = pathlib.Path(__file__).parent.parent / "scripts" / "join_verifier_scores_to_failure_features.py"
        src = src_path.read_text()
        forbidden = ["openai", "anthropic", "cohere", "httpx", "requests", "boto3"]
        for lib in forbidden:
            self.assertIsNone(
                re.search(rf"^\s*(import|from)\s+{lib}\b", src, re.MULTILINE),
                msg=f"Forbidden import '{lib}' found in script",
            )


if __name__ == "__main__":
    unittest.main()
