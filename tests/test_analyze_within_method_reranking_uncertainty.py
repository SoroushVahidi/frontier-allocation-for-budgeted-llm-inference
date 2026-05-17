"""Tests for scripts/analyze_within_method_reranking_uncertainty.py"""
from __future__ import annotations

import csv
import pathlib
import random
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

from analyze_within_method_reranking_uncertainty import (
    _build_cluster_map,
    _resample_rows_cluster,
    bootstrap_distributions,
    ci_from_samples,
    compute_verifier_vs_anti_discordance,
    compute_point_metrics,
    load_group_details,
    main,
    run_analysis,
)


def _write_group_details_csv(tmpdir: str, rows: list[dict]) -> pathlib.Path:
    path = pathlib.Path(tmpdir) / "reranking_group_details.csv"
    cols = [
        "example_id",
        "problem_id",
        "budget",
        "method",
        "n_candidates",
        "em_verifier_max",
        "em_anti_verifier",
        "em_first_seed",
        "oracle_any_correct",
        "random_expected",
        "score_min",
        "score_max",
        "score_spread",
        "score_stdev",
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return path


def _toy_rows() -> list[dict]:
    # 4 groups, 2 methods, mixed outcomes
    return [
        {
            "example_id": "ex1",
            "budget": "6",
            "method": "mA",
            "n_candidates": "6",
            "em_verifier_max": "1",
            "em_anti_verifier": "0",
            "em_first_seed": "0",
            "oracle_any_correct": "1",
            "random_expected": "0.5000",
            "score_min": "0.01",
            "score_max": "0.99",
            "score_spread": "0.98",
            "score_stdev": "0.30",
        },
        {
            "example_id": "ex1",
            "budget": "8",
            "method": "mB",
            "n_candidates": "6",
            "em_verifier_max": "0",
            "em_anti_verifier": "0",
            "em_first_seed": "0",
            "oracle_any_correct": "1",
            "random_expected": "0.1667",
            "score_min": "0.10",
            "score_max": "0.11",
            "score_spread": "0.01",
            "score_stdev": "0.01",
        },
        {
            "example_id": "ex2",
            "budget": "6",
            "method": "mA",
            "n_candidates": "6",
            "em_verifier_max": "1",
            "em_anti_verifier": "1",
            "em_first_seed": "1",
            "oracle_any_correct": "1",
            "random_expected": "1.0000",
            "score_min": "0.20",
            "score_max": "0.30",
            "score_spread": "0.10",
            "score_stdev": "0.03",
        },
        {
            "example_id": "ex3",
            "budget": "6",
            "method": "mB",
            "n_candidates": "6",
            "em_verifier_max": "0",
            "em_anti_verifier": "0",
            "em_first_seed": "1",
            "oracle_any_correct": "0",
            "random_expected": "0.0000",
            "score_min": "0.05",
            "score_max": "0.06",
            "score_spread": "0.01",
            "score_stdev": "0.01",
        },
    ]


class TestLoadGroupDetails(unittest.TestCase):
    def test_loads_and_resolves_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_group_details_csv(tmpdir, _toy_rows())
            rows, cols = load_group_details(
                p,
                cluster_field="example_id",
                method_field="method",
                budget_field="budget",
            )
        self.assertEqual(len(rows), 4)
        self.assertEqual(cols["verifier_max"], "em_verifier_max")
        self.assertEqual(cols["oracle"], "oracle_any_correct")
        self.assertEqual(rows[0]["cluster"], "ex1")
        self.assertEqual(cols["resolved_cluster_field"], "example_id")

    def test_random_expected_numeric(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_group_details_csv(tmpdir, _toy_rows())
            rows, _ = load_group_details(
                p,
                cluster_field="example_id",
                method_field="method",
                budget_field="budget",
            )
        self.assertIsInstance(rows[0]["random_expected"], float)
        self.assertAlmostEqual(rows[0]["random_expected"], 0.5)

    def test_problem_id_fallback_when_example_id_missing(self):
        rows = _toy_rows()
        for row in rows:
            row["problem_id"] = row.pop("example_id")
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir) / "reranking_group_details.csv"
            cols = [
                "problem_id",
                "budget",
                "method",
                "n_candidates",
                "em_verifier_max",
                "em_anti_verifier",
                "em_first_seed",
                "oracle_any_correct",
                "random_expected",
                "score_min",
                "score_max",
                "score_spread",
                "score_stdev",
            ]
            with open(p, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                w.writeheader()
                for row in rows:
                    w.writerow(row)
            loaded, cols = load_group_details(
                p,
                cluster_field="example_id",
                method_field="method",
                budget_field="budget",
            )
        self.assertEqual(len(loaded), 4)
        self.assertEqual(cols["resolved_cluster_field"], "problem_id")


class TestMetricComputation(unittest.TestCase):
    def test_point_metrics(self):
        rows = [
            {"verifier_max": 1.0, "random_expected": 0.5, "anti_verifier": 0.0, "oracle": 1.0},
            {"verifier_max": 0.0, "random_expected": 0.25, "anti_verifier": 0.0, "oracle": 1.0},
        ]
        metrics = compute_point_metrics(rows)
        self.assertAlmostEqual(metrics["verifier_max"], 0.5)
        self.assertAlmostEqual(metrics["random_expected"], 0.375)
        self.assertAlmostEqual(metrics["verifier_minus_random"], 0.125)
        self.assertAlmostEqual(metrics["verifier_minus_anti"], 0.5)
        self.assertAlmostEqual(metrics["oracle_minus_verifier"], 0.5)

    def test_verifier_vs_anti_discordance_counts(self):
        rows = [
            {"verifier_max": 1.0, "anti_verifier": 1.0},
            {"verifier_max": 1.0, "anti_verifier": 0.0},
            {"verifier_max": 0.0, "anti_verifier": 1.0},
            {"verifier_max": 0.0, "anti_verifier": 0.0},
        ]
        d = compute_verifier_vs_anti_discordance(rows)
        self.assertEqual(d["n_groups"], 4)
        self.assertEqual(d["both_correct"], 1)
        self.assertEqual(d["verifier_only_correct"], 1)
        self.assertEqual(d["anti_only_correct"], 1)
        self.assertEqual(d["both_wrong"], 1)


class TestBootstrap(unittest.TestCase):
    def _load_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_group_details_csv(tmpdir, _toy_rows())
            rows, _ = load_group_details(
                p,
                cluster_field="example_id",
                method_field="method",
                budget_field="budget",
            )
        return rows

    def test_paired_bootstrap_reproducible_given_seed(self):
        rows = self._load_rows()
        d1 = bootstrap_distributions(rows, n_bootstrap=50, seed=7)
        d2 = bootstrap_distributions(rows, n_bootstrap=50, seed=7)
        self.assertEqual(d1["paired"]["verifier_max"], d2["paired"]["verifier_max"])
        self.assertEqual(d1["cluster"]["verifier_minus_random"], d2["cluster"]["verifier_minus_random"])

    def test_bootstrap_dimensions(self):
        rows = self._load_rows()
        d = bootstrap_distributions(rows, n_bootstrap=37, seed=7)
        self.assertEqual(len(d["paired"]["verifier_max"]), 37)
        self.assertEqual(len(d["cluster"]["verifier_max"]), 37)

    def test_cluster_bootstrap_resamples_whole_clusters(self):
        rows = self._load_rows()
        cluster_map = _build_cluster_map(rows)
        rng = random.Random(11)
        sampled_rows, sampled_ids = _resample_rows_cluster(cluster_map, rng)

        orig_sizes = {k: len(v) for k, v in cluster_map.items()}
        sampled_cluster_counts = {}
        for cid in sampled_ids:
            sampled_cluster_counts[cid] = sampled_cluster_counts.get(cid, 0) + 1

        sampled_rows_counts = {}
        for r in sampled_rows:
            cid = r["cluster"]
            sampled_rows_counts[cid] = sampled_rows_counts.get(cid, 0) + 1

        for cid, n_selected in sampled_cluster_counts.items():
            self.assertEqual(sampled_rows_counts[cid], n_selected * orig_sizes[cid])

    def test_ci_ordering(self):
        lo, hi = ci_from_samples([0.1, 0.2, 0.3, 0.4, 0.5])
        self.assertLessEqual(lo, hi)


class TestRunAnalysis(unittest.TestCase):
    def test_method_and_method_budget_aggregation_and_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_group_details_csv(tmpdir, _toy_rows())
            out = pathlib.Path(tmpdir) / "out"
            result = run_analysis(
                group_details_csv=p,
                output_dir=out,
                n_bootstrap=120,
                seed=123,
                cluster_field="example_id",
                method_field="method",
                budget_field="budget",
            )

            self.assertIn("mA", result["by_method"])
            self.assertIn("mB", result["by_method"])
            self.assertIn(("mA", "6"), result["by_method_budget"])
            self.assertIn(("mB", "8"), result["by_method_budget"])
            self.assertIn("mA", result["discordance_by_method"])
            self.assertIn(("mA", "6"), result["discordance_by_method_budget"])
            self.assertIn("discordance_verifier_vs_anti", result["metrics_obj"])

            expected_files = [
                "uncertainty_report.md",
                "metrics.json",
                "bootstrap_overall.csv",
                "bootstrap_by_method.csv",
                "bootstrap_by_method_budget.csv",
                "bootstrap_distribution_summary.csv",
            ]
            for fname in expected_files:
                self.assertTrue((out / fname).exists(), msg=f"missing {fname}")

    def test_main_missing_input_returns_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = main(
                [
                    "--group-details-csv",
                    str(pathlib.Path(tmpdir) / "missing.csv"),
                    "--output-dir",
                    str(pathlib.Path(tmpdir) / "out"),
                ]
            )
        self.assertEqual(rc, 1)


class TestNoApiImports(unittest.TestCase):
    def test_no_forbidden_imports(self):
        src = (
            pathlib.Path(__file__).parent.parent
            / "scripts"
            / "analyze_within_method_reranking_uncertainty.py"
        ).read_text()
        for lib in ["openai", "anthropic", "cohere", "httpx", "requests", "boto3"]:
            self.assertIsNone(
                re.search(rf"^\s*(import|from)\s+{lib}\b", src, re.MULTILINE),
                msg=f"Forbidden import '{lib}' found",
            )


if __name__ == "__main__":
    unittest.main()
