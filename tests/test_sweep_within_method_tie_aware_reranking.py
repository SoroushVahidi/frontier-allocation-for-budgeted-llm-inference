"""Tests for scripts/sweep_within_method_tie_aware_reranking.py"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

from sweep_within_method_tie_aware_reranking import (
    aggregate_binary,
    baseline_top1_index,
    build_groups,
    choose_tie_breaker_index,
    detect_secondary_score_field,
    load_scored,
    main,
    tie_set_indices,
)

DIRECT = "direct_reserve_semantic_frontier_v2"
EXTERNAL = "external_l1_max"


def _make_row(
    *,
    example_id: str,
    budget: int,
    method: str,
    seed: int,
    score: float,
    em: int,
    with_secondary: bool = False,
) -> dict:
    row = {
        "proba_ready": score,
        "predicted_label": 1 if score >= 0.5 else 0,
        "feature_text": f"question: Q | candidate_answer: A{seed} | candidate_trace_short: T{seed}",
        "metadata": {
            "example_id": example_id,
            "budget": budget,
            "method": method,
            "seed": seed,
            "exact_match_metadata": em,
        },
    }
    if with_secondary:
        row["metadata"]["frontier_score"] = float(seed)
    return row


def _write_jsonl(tmpdir: str, rows: list[dict]) -> pathlib.Path:
    p = pathlib.Path(tmpdir) / "scored.jsonl"
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p


class TestLoadAndGroup(unittest.TestCase):
    def test_load_flattens_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_jsonl(
                tmpdir,
                [_make_row(example_id="ex0", budget=4, method=DIRECT, seed=11, score=0.5, em=1)],
            )
            rows = load_scored(p, "proba_ready")
        self.assertEqual(len(rows), 1)
        self.assertIn("example_id", rows[0])
        self.assertIn("seed", rows[0])
        self.assertIn("proba_ready", rows[0])

    def test_build_groups(self):
        rows = []
        for ex in ["ex0", "ex1"]:
            for seed in [11, 23]:
                rows.append(
                    {
                        "example_id": ex,
                        "budget": 4,
                        "method": DIRECT,
                        "seed": seed,
                        "proba_ready": 0.1 * seed,
                        "exact_match_metadata": 0,
                    }
                )
        groups = build_groups(rows, ["example_id", "budget", "method"])
        self.assertEqual(len(groups), 2)
        self.assertTrue(all(len(v) == 2 for v in groups.values()))


class TestTieSetsAndPolicy(unittest.TestCase):
    def _cands(self):
        return [
            {"seed": 11, "proba_ready": 0.9000, "exact_match_metadata": 0, "frontier_score": 1.0},
            {"seed": 23, "proba_ready": 0.8995, "exact_match_metadata": 1, "frontier_score": 9.0},
            {"seed": 37, "proba_ready": 0.8000, "exact_match_metadata": 0, "frontier_score": 3.0},
        ]

    def test_baseline_top1(self):
        idx = baseline_top1_index(self._cands(), "proba_ready")
        self.assertEqual(idx, 0)

    def test_tie_set_epsilon(self):
        tie, spread = tie_set_indices(self._cands(), "proba_ready", "epsilon", 0.001)
        self.assertEqual(tie, [0, 1])
        self.assertGreater(spread, 0.0)

    def test_tie_set_spread(self):
        tie, _ = tie_set_indices(self._cands(), "proba_ready", "spread", 0.2)
        self.assertEqual(tie, [0, 1, 2])

    def test_lowest_highest_median(self):
        tie = [0, 1, 2]
        c = self._cands()
        self.assertEqual(choose_tie_breaker_index(c, tie, "lowest_seed", None), 0)
        self.assertEqual(choose_tie_breaker_index(c, tie, "highest_seed", None), 2)
        self.assertEqual(choose_tie_breaker_index(c, tie, "median_seed", None), 1)

    def test_secondary_score(self):
        tie = [0, 1, 2]
        idx = choose_tie_breaker_index(self._cands(), tie, "secondary_score", "frontier_score")
        self.assertEqual(idx, 1)

    def test_secondary_score_missing_graceful(self):
        tie = [0, 1]
        idx = choose_tie_breaker_index(self._cands(), tie, "secondary_score", None)
        self.assertIsNone(idx)


class TestAggregateBinary(unittest.TestCase):
    def test_recovery_regression_counts(self):
        rows = [
            {
                "policy_em": 1,
                "baseline_em": 0,
                "tie_activated": 1,
                "changed_choice": 1,
                "recovery": 1,
                "regression": 0,
                "missed_oracle_group": 1,
                "recovery_on_missed_oracle": 1,
                "tie_set_size": 2,
            },
            {
                "policy_em": 0,
                "baseline_em": 1,
                "tie_activated": 1,
                "changed_choice": 1,
                "recovery": 0,
                "regression": 1,
                "missed_oracle_group": 0,
                "recovery_on_missed_oracle": 0,
                "tie_set_size": 2,
            },
        ]
        agg = aggregate_binary(rows)
        self.assertEqual(agg["recoveries"], 1)
        self.assertEqual(agg["regressions"], 1)
        self.assertEqual(agg["net_gain"], 0)
        self.assertAlmostEqual(agg["affected_pct"], 1.0)


class TestMainIntegration(unittest.TestCase):
    def _dataset(self, with_secondary: bool = False) -> list[dict]:
        rows = []
        # direct: tie-aware can recover some groups
        rows += [
            _make_row(example_id="ex0", budget=8, method=DIRECT, seed=11, score=0.9000, em=0, with_secondary=with_secondary),
            _make_row(example_id="ex0", budget=8, method=DIRECT, seed=23, score=0.8995, em=1, with_secondary=with_secondary),
            _make_row(example_id="ex0", budget=8, method=DIRECT, seed=37, score=0.8000, em=0, with_secondary=with_secondary),
            _make_row(example_id="ex1", budget=8, method=DIRECT, seed=11, score=0.7000, em=1, with_secondary=with_secondary),
            _make_row(example_id="ex1", budget=8, method=DIRECT, seed=23, score=0.6997, em=0, with_secondary=with_secondary),
            _make_row(example_id="ex1", budget=8, method=DIRECT, seed=37, score=0.1000, em=0, with_secondary=with_secondary),
        ]
        # external: mostly stable
        rows += [
            _make_row(example_id="ex2", budget=4, method=EXTERNAL, seed=11, score=0.9500, em=1, with_secondary=with_secondary),
            _make_row(example_id="ex2", budget=4, method=EXTERNAL, seed=23, score=0.9499, em=0, with_secondary=with_secondary),
            _make_row(example_id="ex2", budget=4, method=EXTERNAL, seed=37, score=0.3000, em=0, with_secondary=with_secondary),
            _make_row(example_id="ex3", budget=4, method=EXTERNAL, seed=11, score=0.9100, em=0, with_secondary=with_secondary),
            _make_row(example_id="ex3", budget=4, method=EXTERNAL, seed=23, score=0.9097, em=1, with_secondary=with_secondary),
            _make_row(example_id="ex3", budget=4, method=EXTERNAL, seed=37, score=0.1000, em=0, with_secondary=with_secondary),
        ]
        return rows

    def test_detect_secondary_score_field(self):
        rows = load_scored(_write_jsonl(tempfile.gettempdir(), self._dataset(with_secondary=True)), "proba_ready")
        self.assertEqual(detect_secondary_score_field(rows), "frontier_score")

    def test_outputs_written_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_jsonl(tmpdir, self._dataset(with_secondary=False))
            out = pathlib.Path(tmpdir) / "out"
            rc = main(["--scored-jsonl", str(p), "--output-dir", str(out)])
            self.assertEqual(rc, 0)
            for name in [
                "tie_aware_sweep_report.md",
                "metrics.json",
                "sweep_overall.csv",
                "sweep_by_method.csv",
                "sweep_by_method_budget.csv",
                "tie_set_size_distribution.csv",
                "affected_groups.csv",
            ]:
                self.assertTrue((out / name).exists(), f"missing {name}")
            with open(out / "metrics.json") as f:
                m = json.load(f)
            self.assertIn("best_non_oracle_overall", m)
            self.assertIsNone(m["secondary_score_field"])
            self.assertGreater(m["n_secondary_score_configs_skipped"], 0)

    def test_recovery_and_regression_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_jsonl(tmpdir, self._dataset(with_secondary=False))
            out = pathlib.Path(tmpdir) / "out"
            main(["--scored-jsonl", str(p), "--output-dir", str(out)])
            with open(out / "sweep_overall.csv") as f:
                rows = list(csv.DictReader(f))
            non_oracle = [r for r in rows if r["is_oracle_diagnostic"] == "0"]
            has_recovery = any(int(float(r["recoveries"])) > 0 for r in non_oracle)
            has_regression = any(int(float(r["regressions"])) > 0 for r in non_oracle)
            self.assertTrue(has_recovery)
            self.assertTrue(has_regression)


class TestNoApiImports(unittest.TestCase):
    def test_no_forbidden_imports(self):
        src = (
            pathlib.Path(__file__).parent.parent / "scripts" / "sweep_within_method_tie_aware_reranking.py"
        ).read_text()
        for lib in ["openai", "anthropic", "cohere", "httpx", "requests", "boto3"]:
            self.assertIsNone(
                re.search(rf"^\s*(import|from)\s+{lib}\b", src, re.MULTILINE),
                msg=f"Forbidden import '{lib}' found",
            )


if __name__ == "__main__":
    unittest.main()
