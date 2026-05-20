"""Tests for scripts/apply_frozen_slice_aware_reranking.py"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

from apply_frozen_slice_aware_reranking import (
    aggregate_group_rows,
    baseline_top1_index,
    build_groups,
    choose_index,
    load_rules_csv,
    load_scored,
    main,
    tie_indices,
    validate_and_index_rules,
)


def _mk_row(
    *,
    ex: str,
    budget: int,
    method: str,
    seed: int,
    score: float,
    em: int,
) -> dict:
    return {
        "proba_ready": score,
        "predicted_label": 1 if score >= 0.5 else 0,
        "feature_text": f"q:{ex}",
        "metadata": {
            "example_id": ex,
            "budget": budget,
            "method": method,
            "seed": seed,
            "exact_match_metadata": em,
        },
    }


def _write_jsonl(tmpdir: str, rows: list[dict]) -> pathlib.Path:
    p = pathlib.Path(tmpdir) / "scored.jsonl"
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p


def _write_rule_csv(tmpdir: str, rows: list[dict]) -> pathlib.Path:
    p = pathlib.Path(tmpdir) / "rules.csv"
    cols = [
        "policy_name",
        "method",
        "budget",
        "mode",
        "threshold",
        "tie_policy",
        "source_lift",
    ]
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


class TestLoadAndGroup(unittest.TestCase):
    def test_load_flattens_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_jsonl(tmpdir, [_mk_row(ex="ex0", budget=6, method="mA", seed=11, score=0.9, em=1)])
            rows = load_scored(p, "proba_ready")
        self.assertEqual(len(rows), 1)
        self.assertIn("example_id", rows[0])
        self.assertIn("seed", rows[0])
        self.assertEqual(rows[0]["budget"], 6)

    def test_grouping(self):
        rows = []
        for seed in [11, 23, 37]:
            rows.append({"example_id": "ex0", "budget": 6, "method": "mA", "seed": seed, "proba_ready": 0.1, "exact_match_metadata": 0})
        groups = build_groups(rows, ["example_id", "budget", "method"])
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(next(iter(groups.values()))), 3)


class TestRules(unittest.TestCase):
    def test_load_rule_csv_policy_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rp = _write_rule_csv(
                tmpdir,
                [
                    {"policy_name": "p1", "method": "mA", "budget": "6", "mode": "epsilon", "threshold": "0.01", "tie_policy": "lowest_seed", "source_lift": "0.1"},
                    {"policy_name": "p2", "method": "mA", "budget": "6", "mode": "epsilon", "threshold": "0.01", "tie_policy": "highest_seed", "source_lift": "0.1"},
                ],
            )
            rows = load_rules_csv(rp, "p1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["policy_name"], "p1")

    def test_unsupported_rules_reported(self):
        raw = [
            {"method": "mA", "budget": "6", "mode": "epsilon", "threshold": "0.01", "tie_policy": "lowest_seed"},
            {"method": "mB", "budget": "6", "mode": "epsilon", "threshold": "0.01", "tie_policy": "secondary_score"},
        ]
        indexed, supported, unsupported, dup = validate_and_index_rules(raw)
        self.assertEqual(len(supported), 1)
        self.assertEqual(len(unsupported), 1)
        self.assertEqual(len(indexed), 1)
        self.assertEqual(len(dup), 0)


class TestPolicyMechanics(unittest.TestCase):
    def _cands(self):
        return [
            {"seed": 11, "proba_ready": 0.9000, "exact_match_metadata": 0},
            {"seed": 23, "proba_ready": 0.8995, "exact_match_metadata": 1},
            {"seed": 37, "proba_ready": 0.8000, "exact_match_metadata": 0},
        ]

    def test_baseline_top1(self):
        self.assertEqual(baseline_top1_index(self._cands(), "proba_ready"), 0)

    def test_lowest_seed_epsilon(self):
        c = self._cands()
        b = baseline_top1_index(c, "proba_ready")
        tie = tie_indices(c, "proba_ready", "epsilon", 0.001, b)
        idx = choose_index(c, tie, "lowest_seed", b)
        self.assertEqual(tie, [0, 1])
        self.assertEqual(idx, 0)

    def test_highest_seed_epsilon(self):
        c = self._cands()
        b = baseline_top1_index(c, "proba_ready")
        tie = tie_indices(c, "proba_ready", "epsilon", 0.001, b)
        idx = choose_index(c, tie, "highest_seed", b)
        self.assertEqual(idx, 1)

    def test_median_seed_spread(self):
        c = self._cands()
        b = baseline_top1_index(c, "proba_ready")
        tie = tie_indices(c, "proba_ready", "spread", 0.2, b)
        idx = choose_index(c, tie, "median_seed", b)
        self.assertEqual(tie, [0, 1, 2])
        self.assertEqual(idx, 1)

    def test_verifier_top1_fallback_policy(self):
        c = self._cands()
        b = baseline_top1_index(c, "proba_ready")
        tie = tie_indices(c, "proba_ready", "epsilon", 0.001, b)
        idx = choose_index(c, tie, "verifier_top1", b)
        self.assertEqual(idx, b)


class TestAggregateMetrics(unittest.TestCase):
    def test_recovery_regression_net_gain(self):
        rows = [
            {"baseline_em": 0, "frozen_em": 1, "random_expected": 0.5, "anti_em": 0, "oracle_any_correct": 1, "changed_choice": 1, "recovery": 1, "regression": 0, "slice_has_rule": 1},
            {"baseline_em": 1, "frozen_em": 0, "random_expected": 0.5, "anti_em": 1, "oracle_any_correct": 1, "changed_choice": 1, "recovery": 0, "regression": 1, "slice_has_rule": 1},
        ]
        agg = aggregate_group_rows(rows)
        self.assertEqual(agg["recoveries"], 1)
        self.assertEqual(agg["regressions"], 1)
        self.assertEqual(agg["net_gain"], 0)
        self.assertAlmostEqual(agg["affected_rate"], 1.0)


class TestMainIntegration(unittest.TestCase):
    def _dataset(self) -> list[dict]:
        # ex0 slice mA@6: baseline wrong, highest_seed in epsilon tie recovers
        rows = [
            _mk_row(ex="ex0", budget=6, method="mA", seed=11, score=0.9000, em=0),
            _mk_row(ex="ex0", budget=6, method="mA", seed=23, score=0.8995, em=1),
            _mk_row(ex="ex0", budget=6, method="mA", seed=37, score=0.1000, em=0),
            # ex1 mA@6: baseline right, highest_seed regresses
            _mk_row(ex="ex1", budget=6, method="mA", seed=11, score=0.9100, em=1),
            _mk_row(ex="ex1", budget=6, method="mA", seed=23, score=0.9095, em=0),
            _mk_row(ex="ex1", budget=6, method="mA", seed=37, score=0.2000, em=0),
            # ex2 mB@6: no matching rule
            _mk_row(ex="ex2", budget=6, method="mB", seed=11, score=0.7000, em=1),
            _mk_row(ex="ex2", budget=6, method="mB", seed=23, score=0.4000, em=0),
        ]
        return rows

    def test_no_matching_rule_equals_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scored = _write_jsonl(tmpdir, self._dataset())
            rules = _write_rule_csv(
                tmpdir,
                [{"policy_name": "p", "method": "mZ", "budget": "6", "mode": "epsilon", "threshold": "0.01", "tie_policy": "lowest_seed", "source_lift": "0.1"}],
            )
            out = pathlib.Path(tmpdir) / "out"
            rc = main(["--scored-jsonl", str(scored), "--rule-csv", str(rules), "--output-dir", str(out), "--policy-name", "p"])
            self.assertEqual(rc, 0)
            with open(out / "policy_overall.csv") as f:
                row = next(csv.DictReader(f))
            self.assertAlmostEqual(float(row["frozen_minus_verifier"]), 0.0, places=6)
            self.assertEqual(int(float(row["affected_groups"])), 0)

    def test_outputs_written_and_unmatched_reported(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scored = _write_jsonl(tmpdir, self._dataset())
            rules = _write_rule_csv(
                tmpdir,
                [
                    {"policy_name": "p", "method": "mA", "budget": "6", "mode": "epsilon", "threshold": "0.001", "tie_policy": "highest_seed", "source_lift": "0.1"},
                    {"policy_name": "p", "method": "mUnused", "budget": "6", "mode": "epsilon", "threshold": "0.001", "tie_policy": "lowest_seed", "source_lift": "0.1"},
                ],
            )
            out = pathlib.Path(tmpdir) / "out"
            rc = main(["--scored-jsonl", str(scored), "--rule-csv", str(rules), "--output-dir", str(out), "--policy-name", "p"])
            self.assertEqual(rc, 0)
            expected = [
                "policy_overall.csv",
                "policy_by_method.csv",
                "policy_by_method_budget.csv",
                "affected_groups.csv",
                "frozen_rule_application_report.md",
                "metrics.json",
            ]
            for name in expected:
                self.assertTrue((out / name).exists(), f"missing {name}")

            with open(out / "policy_overall.csv") as f:
                row = next(csv.DictReader(f))
            self.assertEqual(int(float(row["unmatched_rule_slice_count"])), 1)
            self.assertEqual(int(float(row["unmatched_target_slice_count"])), 1)


class TestNoApiImports(unittest.TestCase):
    def test_no_forbidden_imports(self):
        src = (
            pathlib.Path(__file__).parent.parent
            / "scripts"
            / "apply_frozen_slice_aware_reranking.py"
        ).read_text()
        for lib in ["openai", "anthropic", "cohere", "httpx", "requests", "boto3"]:
            self.assertIsNone(
                re.search(rf"^\s*(import|from)\s+{lib}\b", src, re.MULTILINE),
                msg=f"Forbidden import '{lib}' found",
            )


if __name__ == "__main__":
    unittest.main()
