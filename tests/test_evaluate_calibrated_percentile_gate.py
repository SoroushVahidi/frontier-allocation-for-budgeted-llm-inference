"""Tests for scripts/evaluate_calibrated_percentile_gate.py"""
from __future__ import annotations

import csv
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

from evaluate_calibrated_percentile_gate import (  # noqa: E402
    Policy,
    _policy_sort_key,
    aggregate_metrics,
    cluster_bootstrap_deltas,
    load_calibrated_rows,
    main,
    should_switch,
    split_dev_holdout,
    tune_policy,
)


def _write_csv(path: pathlib.Path, rows: list[dict]) -> pathlib.Path:
    fields = sorted({k for r in rows for k in r.keys()})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def _row(
    *,
    example_id: str,
    artifact_label: str,
    baseline_correct: int,
    frontier_correct: int,
    baseline_pct: float,
    frontier_pct: float,
    pct_margin: float | None = None,
    z_margin: float = 0.0,
    oracle_recoverable: int = 0,
    regression_risk: int = 0,
    both_wrong: int = 0,
    both_correct: int = 0,
    disagreement: int = 0,
) -> dict:
    return {
        "example_id": example_id,
        "artifact_label": artifact_label,
        "baseline_correct": baseline_correct,
        "frontier_correct": frontier_correct,
        "baseline_proba_ready_pct_within_method": baseline_pct,
        "frontier_proba_ready_pct_within_method": frontier_pct,
        "frontier_minus_baseline_percentile_margin": (
            (frontier_pct - baseline_pct) if pct_margin is None else pct_margin
        ),
        "frontier_minus_baseline_z_margin": z_margin,
        "oracle_recoverable": oracle_recoverable,
        "regression_risk": regression_risk,
        "both_wrong": both_wrong,
        "both_correct": both_correct,
        "disagreement": disagreement,
    }


class TestLoadAndSplit(unittest.TestCase):
    def test_load_rows_and_fallback_group_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "in.csv"
            _write_csv(
                path,
                [
                    _row(
                        example_id="",
                        artifact_label="a1",
                        baseline_correct=1,
                        frontier_correct=0,
                        baseline_pct=0.8,
                        frontier_pct=0.2,
                    )
                ],
            )
            rows, warnings = load_calibrated_rows(
                path=path,
                group_id_col="example_id",
                artifact_col="artifact_label",
                baseline_correct_col="baseline_correct",
                frontier_correct_col="frontier_correct",
                baseline_pct_col="baseline_proba_ready_pct_within_method",
                frontier_pct_col="frontier_proba_ready_pct_within_method",
                percentile_margin_col="frontier_minus_baseline_percentile_margin",
                z_margin_col="frontier_minus_baseline_z_margin",
            )
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["__group_id"].startswith("__row_"))
        self.assertTrue(any("fallback" in w for w in warnings))

    def test_split_dev_holdout(self):
        rows = [
            {"__artifact": "dev_art"},
            {"__artifact": "hold_art"},
            {"__artifact": "dev_art2"},
        ]
        dev, hold = split_dev_holdout(rows, {"hold_art"})
        self.assertEqual(len(dev), 2)
        self.assertEqual(len(hold), 1)


class TestPoliciesAndMetrics(unittest.TestCase):
    def test_all_policy_families_switch_logic(self):
        row = {
            "__baseline_pct": 0.30,
            "__frontier_pct": 0.80,
            "__pct_margin": 0.50,
            "__z_margin": 0.40,
        }
        self.assertFalse(should_switch(Policy("always_external"), row))
        self.assertTrue(should_switch(Policy("always_frontier"), row))
        self.assertTrue(should_switch(Policy("frontier_pct_threshold", frontier_min=0.70), row))
        self.assertTrue(
            should_switch(
                Policy("external_low_frontier_high", baseline_max=0.35, frontier_min=0.70),
                row,
            )
        )
        self.assertTrue(should_switch(Policy("pct_margin", margin=0.20), row))
        self.assertTrue(
            should_switch(
                Policy("conservative_combo", frontier_min=0.70, baseline_max=0.35, margin=0.20),
                row,
            )
        )
        self.assertTrue(should_switch(Policy("z_margin", z_threshold=0.10), row))

    def test_recovery_regression_missed_and_oracle(self):
        decisions = [
            {
                "baseline_correct": 0,
                "frontier_correct": 1,
                "gated_correct": 1,
                "oracle_top2_correct": 1,
                "did_switch": 1,
                "recovery": 1,
                "regression": 0,
                "missed_recovery": 0,
                "oracle_recoverable": 1,
                "regression_risk": 0,
            },
            {
                "baseline_correct": 1,
                "frontier_correct": 0,
                "gated_correct": 0,
                "oracle_top2_correct": 1,
                "did_switch": 1,
                "recovery": 0,
                "regression": 1,
                "missed_recovery": 0,
                "oracle_recoverable": 0,
                "regression_risk": 1,
            },
            {
                "baseline_correct": 0,
                "frontier_correct": 1,
                "gated_correct": 0,
                "oracle_top2_correct": 1,
                "did_switch": 0,
                "recovery": 0,
                "regression": 0,
                "missed_recovery": 1,
                "oracle_recoverable": 1,
                "regression_risk": 0,
            },
        ]
        m = aggregate_metrics(decisions)
        self.assertEqual(m["recoveries"], 1)
        self.assertEqual(m["regressions"], 1)
        self.assertEqual(m["missed_recoveries"], 1)
        self.assertEqual(m["oracle_recoverable_count"], 2)
        self.assertEqual(m["regression_risk_count"], 1)
        self.assertAlmostEqual(m["oracle_top2_accuracy"], 1.0)


class TestTuningAndTieBreaks(unittest.TestCase):
    def test_tie_break_prefers_family_order(self):
        # All rows have equal baseline/frontier outcome, so best is tied on metrics.
        rows = []
        for i in range(8):
            rows.append(
                {
                    "__group_id": f"g{i}",
                    "__artifact": "dev",
                    "__baseline_correct": 1,
                    "__frontier_correct": 1,
                    "__baseline_pct": 0.6,
                    "__frontier_pct": 0.6,
                    "__pct_margin": 0.0,
                    "__z_margin": 0.0,
                    "__oracle_top2": 1,
                    "__oracle_recoverable": 0,
                    "__regression_risk": 0,
                    "__both_wrong": 0,
                    "__both_correct": 1,
                    "__disagreement": 0,
                }
            )

        class Args:
            frontier_min_start = 0.5
            frontier_min_stop = 0.6
            frontier_min_step = 0.1
            baseline_max_start = 0.05
            baseline_max_stop = 0.10
            baseline_max_step = 0.05
            margin_start = -0.1
            margin_stop = 0.1
            margin_step = 0.1
            z_threshold_start = -0.1
            z_threshold_stop = 0.1
            z_threshold_step = 0.1

        selected, _ = tune_policy(rows, Args())
        self.assertEqual(selected.family, "always_external")

    def test_conservative_signature_order_within_family(self):
        a = {
            "policy": Policy("frontier_pct_threshold", frontier_min=0.90),
            "metrics": {"gated_accuracy": 0.5, "gated_minus_external": 0.0, "switch_rate": 0.5},
        }
        b = {
            "policy": Policy("frontier_pct_threshold", frontier_min=0.60),
            "metrics": {"gated_accuracy": 0.5, "gated_minus_external": 0.0, "switch_rate": 0.5},
        }
        self.assertLess(_policy_sort_key(a), _policy_sort_key(b))


class TestBootstrapAndErrors(unittest.TestCase):
    def test_cluster_bootstrap_shapes(self):
        decisions = []
        for i in range(5):
            decisions.append(
                {
                    "group_id": f"g{i}",
                    "baseline_correct": i % 2,
                    "frontier_correct": 1 - (i % 2),
                    "gated_correct": i % 2,
                    "oracle_top2_correct": 1,
                    "did_switch": 0,
                    "recovery": 0,
                    "regression": 0,
                    "missed_recovery": 1 - (i % 2),
                    "oracle_recoverable": 1 - (i % 2),
                    "regression_risk": i % 2,
                }
            )
        out = cluster_bootstrap_deltas(decisions, n_bootstrap=25, seed=7)
        self.assertEqual(len(out["rows"]), 25)
        self.assertIn("gated_minus_external", out["ci"])
        self.assertIn("always_frontier_minus_external", out["ci"])

    def test_missing_required_feature_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "bad.csv"
            _write_csv(path, [{"example_id": "x1", "artifact_label": "a"}])
            with self.assertRaises(ValueError):
                load_calibrated_rows(
                    path=path,
                    group_id_col="example_id",
                    artifact_col="artifact_label",
                    baseline_correct_col="baseline_correct",
                    frontier_correct_col="frontier_correct",
                    baseline_pct_col="baseline_proba_ready_pct_within_method",
                    frontier_pct_col="frontier_proba_ready_pct_within_method",
                    percentile_margin_col="frontier_minus_baseline_percentile_margin",
                    z_margin_col="frontier_minus_baseline_z_margin",
                )


class TestMainAndOutputs(unittest.TestCase):
    def test_main_creates_required_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            in_csv = root / "cal.csv"
            out = root / "out"
            rows = []
            for i in range(18):
                art = "holdout_a" if i < 6 else "dev_a"
                b_ok = 1 if i % 3 != 0 else 0
                f_ok = 1 if i % 4 != 0 else 0
                bp = 0.70 if b_ok else 0.20
                fp = 0.75 if f_ok else 0.25
                rows.append(
                    _row(
                        example_id=f"ex{i}",
                        artifact_label=art,
                        baseline_correct=b_ok,
                        frontier_correct=f_ok,
                        baseline_pct=bp,
                        frontier_pct=fp,
                        z_margin=(fp - bp),
                        oracle_recoverable=int(b_ok == 0 and f_ok == 1),
                        regression_risk=int(b_ok == 1 and f_ok == 0),
                        both_wrong=int(b_ok == 0 and f_ok == 0),
                        both_correct=int(b_ok == 1 and f_ok == 1),
                        disagreement=int(b_ok != f_ok),
                    )
                )
            _write_csv(in_csv, rows)

            code = main(
                [
                    "--calibrated-features-csv",
                    str(in_csv),
                    "--output-dir",
                    str(out),
                    "--holdout-artifact",
                    "holdout_a",
                    "--n-bootstrap",
                    "40",
                    "--seed",
                    "7",
                ]
            )
            self.assertEqual(code, 0)

            required = {
                "calibrated_gate_report.md",
                "selected_policy.json",
                "dev_gate_search_results.csv",
                "holdout_metrics.csv",
                "all_artifacts_metrics.csv",
                "by_artifact_metrics.csv",
                "by_target_metrics.csv",
                "group_decisions.csv",
                "bootstrap_deltas.csv",
                "metrics.json",
            }
            produced = {p.name for p in out.iterdir() if p.is_file()}
            self.assertTrue(required.issubset(produced))

    def test_script_has_no_provider_api_imports(self):
        script = pathlib.Path(__file__).parent.parent / "scripts" / "evaluate_calibrated_percentile_gate.py"
        text = script.read_text(encoding="utf-8").lower()
        forbidden = [
            "import openai",
            "from openai import",
            "import cohere",
            "from cohere import",
            "import anthropic",
            "from anthropic import",
            "import requests",
            "from requests import",
            "import httpx",
            "from httpx import",
        ]
        for tok in forbidden:
            self.assertNotIn(tok, text)


if __name__ == "__main__":
    unittest.main()
