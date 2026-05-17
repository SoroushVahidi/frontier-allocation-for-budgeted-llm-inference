"""Tests for scripts/compare_baseline_gated_hybrid_allocator.py"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

from compare_baseline_gated_hybrid_allocator import (
    GatePolicy,
    _policy_sort_key,
    build_groups,
    ci_from_samples,
    cluster_bootstrap_deltas,
    evaluate_gate_policy,
    gate_should_switch,
    load_scored_candidates,
    main,
    select_verifier_top_candidate,
    tune_gate_on_dev,
)

DIRECT = "direct_reserve_semantic_frontier_v2"
EXTERNAL = "external_l1_max"


def _make_row(
    *,
    example_id: str,
    budget: int,
    seed: int,
    method: str,
    proba_ready: float,
    exact_match_metadata: int,
) -> dict:
    return {
        "proba_ready": proba_ready,
        "predicted_label": int(proba_ready >= 0.5),
        "metadata": {
            "example_id": example_id,
            "budget": budget,
            "seed": seed,
            "method": method,
            "exact_match_metadata": exact_match_metadata,
        },
    }


def _write_jsonl(path: pathlib.Path, rows: list[dict]) -> pathlib.Path:
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return path


def _two_method_group(
    *,
    example_id: str,
    budget: int,
    external_scores: tuple[float, ...],
    external_ems: tuple[int, ...],
    direct_scores: tuple[float, ...],
    direct_ems: tuple[int, ...],
    seeds: tuple[int, ...] = (11, 23, 37),
) -> list[dict]:
    rows: list[dict] = []
    for s, p, em in zip(seeds, external_scores, external_ems):
        rows.append(
            _make_row(
                example_id=example_id,
                budget=budget,
                seed=s,
                method=EXTERNAL,
                proba_ready=p,
                exact_match_metadata=em,
            )
        )
    for s, p, em in zip(seeds, direct_scores, direct_ems):
        rows.append(
            _make_row(
                example_id=example_id,
                budget=budget,
                seed=s,
                method=DIRECT,
                proba_ready=p,
                exact_match_metadata=em,
            )
        )
    return rows


class TestLoadAndGrouping(unittest.TestCase):
    def test_load_scored_candidates_flattens_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "scored.jsonl"
            _write_jsonl(
                path,
                [
                    _make_row(
                        example_id="ex0",
                        budget=6,
                        seed=11,
                        method=EXTERNAL,
                        proba_ready=0.77,
                        exact_match_metadata=1,
                    )
                ],
            )
            rows = load_scored_candidates(path, score_field="proba_ready", correct_field="exact_match_metadata")

        self.assertEqual(len(rows), 1)
        self.assertIn("example_id", rows[0])
        self.assertIn("budget", rows[0])
        self.assertIsInstance(rows[0]["proba_ready"], float)
        self.assertEqual(rows[0]["exact_match_metadata"], 1)

    def test_build_groups_example_budget(self):
        rows = []
        rows.extend(_two_method_group(example_id="ex0", budget=6, external_scores=(0.2,), external_ems=(0,), direct_scores=(0.3,), direct_ems=(1,), seeds=(11,)))
        rows.extend(_two_method_group(example_id="ex1", budget=6, external_scores=(0.8,), external_ems=(1,), direct_scores=(0.4,), direct_ems=(0,), seeds=(11,)))
        flat = []
        for raw in rows:
            merged = dict(raw.get("metadata", {}))
            merged["proba_ready"] = raw["proba_ready"]
            merged["exact_match_metadata"] = raw["metadata"]["exact_match_metadata"]
            flat.append(merged)

        groups = build_groups(flat, group_id_field="example_id", budget_field="budget")
        self.assertEqual(len(groups), 2)
        self.assertTrue(all(len(v) == 2 for v in groups.values()))


class TestTopSelectionAndGates(unittest.TestCase):
    def test_select_verifier_top_candidate_by_score(self):
        cands = [
            {"proba_ready": 0.2, "seed": 11, "exact_match_metadata": 1},
            {"proba_ready": 0.9, "seed": 23, "exact_match_metadata": 0},
            {"proba_ready": 0.5, "seed": 37, "exact_match_metadata": 1},
        ]
        top = select_verifier_top_candidate(cands, score_field="proba_ready", seed_field="seed")
        self.assertEqual(top["seed"], 23)

    def test_all_gate_families(self):
        external = 0.4
        direct = 0.8

        self.assertFalse(gate_should_switch(GatePolicy("always_external"), external_score=external, direct_score=direct))
        self.assertTrue(gate_should_switch(GatePolicy("always_direct"), external_score=external, direct_score=direct))
        self.assertTrue(
            gate_should_switch(
                GatePolicy("verifier_margin", margin=0.2),
                external_score=external,
                direct_score=direct,
            )
        )
        self.assertTrue(
            gate_should_switch(
                GatePolicy("direct_threshold", threshold=0.7),
                external_score=external,
                direct_score=direct,
            )
        )
        self.assertTrue(
            gate_should_switch(
                GatePolicy("external_low_confidence", threshold=0.5),
                external_score=external,
                direct_score=direct,
            )
        )
        self.assertTrue(
            gate_should_switch(
                GatePolicy("margin_and_external_low", margin=0.2, external_threshold=0.5),
                external_score=external,
                direct_score=direct,
            )
        )


class TestEvaluationMetrics(unittest.TestCase):
    def _eval(self, rows: list[dict], policy: GatePolicy) -> dict:
        flat = []
        for raw in rows:
            merged = dict(raw.get("metadata", {}))
            merged["proba_ready"] = raw["proba_ready"]
            merged["exact_match_metadata"] = raw["metadata"]["exact_match_metadata"]
            flat.append(merged)
        return evaluate_gate_policy(
            flat,
            baseline_method=EXTERNAL,
            frontier_method=DIRECT,
            score_field="proba_ready",
            correct_field="exact_match_metadata",
            method_field="method",
            budget_field="budget",
            seed_field="seed",
            group_id_field="example_id",
            policy=policy,
        )

    def test_recovery_regression_net_gain(self):
        # ex0 recovery under always_direct; ex1 regression.
        rows = []
        rows.extend(_two_method_group(example_id="ex0", budget=6, external_scores=(0.8,), external_ems=(0,), direct_scores=(0.9,), direct_ems=(1,), seeds=(11,)))
        rows.extend(_two_method_group(example_id="ex1", budget=6, external_scores=(0.9,), external_ems=(1,), direct_scores=(0.8,), direct_ems=(0,), seeds=(11,)))

        out = self._eval(rows, GatePolicy("always_direct"))
        ov = out["overall"]

        self.assertEqual(ov["recoveries"], 1)
        self.assertEqual(ov["regressions"], 1)
        self.assertEqual(ov["net_gain"], 0)

    def test_missing_method_groups_reported_and_skipped(self):
        rows = []
        rows.extend(_two_method_group(example_id="ex0", budget=6, external_scores=(0.8,), external_ems=(1,), direct_scores=(0.3,), direct_ems=(0,), seeds=(11,)))
        rows.append(
            _make_row(
                example_id="ex_missing",
                budget=6,
                seed=11,
                method=EXTERNAL,
                proba_ready=0.7,
                exact_match_metadata=1,
            )
        )

        out = self._eval(rows, GatePolicy("always_external"))
        self.assertEqual(out["n_total_groups"], 2)
        self.assertEqual(out["n_skipped_missing_method"], 1)
        self.assertEqual(out["overall"]["n_groups"], 1)


class TestTuningAndTieBreaks(unittest.TestCase):
    def _dev_rows_for_tuning(self) -> list[dict]:
        rows = []
        # ex1: both correct
        rows.extend(_two_method_group(example_id="ex1", budget=6, external_scores=(0.9,), external_ems=(1,), direct_scores=(0.95,), direct_ems=(1,), seeds=(11,)))
        # ex2: external correct, direct wrong
        rows.extend(_two_method_group(example_id="ex2", budget=6, external_scores=(0.85,), external_ems=(1,), direct_scores=(0.80,), direct_ems=(0,), seeds=(11,)))
        # ex3: external wrong, direct correct with strong margin
        rows.extend(_two_method_group(example_id="ex3", budget=6, external_scores=(0.30,), external_ems=(0,), direct_scores=(0.75,), direct_ems=(1,), seeds=(11,)))
        flat = []
        for raw in rows:
            merged = dict(raw["metadata"])
            merged["proba_ready"] = raw["proba_ready"]
            merged["exact_match_metadata"] = raw["metadata"]["exact_match_metadata"]
            flat.append(merged)
        return flat

    def test_tune_gate_on_dev_and_freeze_on_validation_via_main(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            dev_path = root / "dev.jsonl"
            val_path = root / "val.jsonl"
            out_dir = root / "out"

            dev_rows = []
            dev_rows.extend(_two_method_group(example_id="ex1", budget=6, external_scores=(0.9, 0.2), external_ems=(1, 0), direct_scores=(0.95, 0.3), direct_ems=(1, 0), seeds=(11, 23)))
            dev_rows.extend(_two_method_group(example_id="ex2", budget=6, external_scores=(0.85, 0.1), external_ems=(1, 0), direct_scores=(0.80, 0.2), direct_ems=(0, 0), seeds=(11, 23)))
            dev_rows.extend(_two_method_group(example_id="ex3", budget=6, external_scores=(0.30, 0.1), external_ems=(0, 0), direct_scores=(0.75, 0.2), direct_ems=(1, 0), seeds=(11, 23)))

            val_rows = []
            val_rows.extend(_two_method_group(example_id="vx1", budget=6, external_scores=(0.9,), external_ems=(1,), direct_scores=(0.95,), direct_ems=(1,), seeds=(11,)))
            val_rows.extend(_two_method_group(example_id="vx2", budget=6, external_scores=(0.2,), external_ems=(0,), direct_scores=(0.7,), direct_ems=(1,), seeds=(11,)))
            val_rows.extend(_two_method_group(example_id="vx3", budget=6, external_scores=(0.8,), external_ems=(1,), direct_scores=(0.6,), direct_ems=(0,), seeds=(11,)))

            _write_jsonl(dev_path, dev_rows)
            _write_jsonl(val_path, val_rows)

            rc = main(
                [
                    "--dev-scored-jsonl",
                    str(dev_path),
                    "--validation-scored-jsonl",
                    str(val_path),
                    "--output-dir",
                    str(out_dir),
                    "--gate-family",
                    "verifier_margin",
                    "--margin-min",
                    "-0.5",
                    "--margin-max",
                    "0.6",
                    "--margin-step",
                    "0.1",
                    "--n-bootstrap",
                    "30",
                    "--seed",
                    "9",
                ]
            )
            self.assertEqual(rc, 0)

            metrics = json.loads((out_dir / "metrics.json").read_text())
            self.assertEqual(metrics["mode"], "tune_dev_eval_validation")
            self.assertEqual(metrics["selected_policy"]["family"], "verifier_margin")
            self.assertIn("validation_overall", metrics)

            expected = [
                "hybrid_allocator_report.md",
                "metrics.json",
                "policy_overall.csv",
                "policy_by_budget.csv",
                "group_decisions.csv",
                "gate_search_results.csv",
                "bootstrap_deltas.csv",
            ]
            for name in expected:
                self.assertTrue((out_dir / name).exists(), msg=f"missing {name}")

    def test_tie_break_prefers_fewer_switches_before_family_simplicity(self):
        c_more_switch_simple = {
            "gate_family": "always_direct",
            "margin": None,
            "threshold": None,
            "external_threshold": None,
            "dev_gated_accuracy": 0.8,
            "dev_switch_count": 10,
        }
        c_fewer_switch_less_simple = {
            "gate_family": "direct_threshold",
            "margin": None,
            "threshold": 1.0,
            "external_threshold": None,
            "dev_gated_accuracy": 0.8,
            "dev_switch_count": 2,
        }
        ranked = sorted([c_more_switch_simple, c_fewer_switch_less_simple], key=_policy_sort_key)
        self.assertEqual(ranked[0]["gate_family"], "direct_threshold")

    def test_tie_break_prefers_simpler_family(self):
        a = {
            "gate_family": "always_direct",
            "margin": None,
            "threshold": None,
            "external_threshold": None,
            "dev_gated_accuracy": 0.7,
            "dev_switch_count": 3,
        }
        b = {
            "gate_family": "verifier_margin",
            "margin": 0.2,
            "threshold": None,
            "external_threshold": None,
            "dev_gated_accuracy": 0.7,
            "dev_switch_count": 3,
        }
        ranked = sorted([b, a], key=_policy_sort_key)
        self.assertEqual(ranked[0]["gate_family"], "always_direct")

    def test_tie_break_prefers_conservative_thresholds(self):
        a = {
            "gate_family": "verifier_margin",
            "margin": 0.1,
            "threshold": None,
            "external_threshold": None,
            "dev_gated_accuracy": 0.8,
            "dev_switch_count": 4,
        }
        b = {
            "gate_family": "verifier_margin",
            "margin": 0.3,
            "threshold": None,
            "external_threshold": None,
            "dev_gated_accuracy": 0.8,
            "dev_switch_count": 4,
        }
        ranked = sorted([a, b], key=_policy_sort_key)
        self.assertEqual(ranked[0]["margin"], 0.3)

    def test_tune_gate_returns_policy(self):
        rows = self._dev_rows_for_tuning()

        class Args:
            gate_family = "verifier_margin"
            margin_min = -0.2
            margin_max = 0.4
            margin_step = 0.1
            threshold_min = 0.0
            threshold_max = 1.0
            threshold_step = 0.1
            external_threshold_min = 0.0
            external_threshold_max = 1.0
            external_threshold_step = 0.1
            baseline_method = EXTERNAL
            frontier_method = DIRECT
            score_field = "proba_ready"
            correct_field = "exact_match_metadata"
            method_field = "method"
            budget_field = "budget"
            seed_field = "seed"
            group_id_field = "example_id"

        tuned = tune_gate_on_dev(rows, args=Args())
        self.assertEqual(tuned["selected_policy"].family, "verifier_margin")
        self.assertGreater(len(tuned["search_rows"]), 1)


class TestBootstrapAndNoApi(unittest.TestCase):
    def test_cluster_bootstrap_basic_output(self):
        decisions = [
            {
                "group_id": "ex1",
                "external_top_correct": 0,
                "direct_top_correct": 1,
                "gated_correct": 1,
                "oracle_top2_correct": 1,
                "did_switch": 1,
                "recovery": 1,
                "regression": 0,
                "net_gain": 1,
                "random_expected_external": 0.0,
                "random_expected_direct": 1.0,
            },
            {
                "group_id": "ex2",
                "external_top_correct": 1,
                "direct_top_correct": 0,
                "gated_correct": 1,
                "oracle_top2_correct": 1,
                "did_switch": 0,
                "recovery": 0,
                "regression": 0,
                "net_gain": 0,
                "random_expected_external": 1.0,
                "random_expected_direct": 0.0,
            },
        ]

        boot = cluster_bootstrap_deltas(decisions, n_bootstrap=25, seed=7)
        self.assertEqual(len(boot["rows"]), 25)
        ci = boot["ci"]
        self.assertIn("gated_minus_external", ci)
        self.assertIn("lower", ci["gated_minus_external"])

    def test_ci_from_samples_ordering(self):
        lo, hi = ci_from_samples([0.1, 0.2, 0.3, 0.4])
        self.assertLessEqual(lo, hi)

    def test_no_forbidden_imports_or_calls(self):
        src = (
            pathlib.Path(__file__).parent.parent
            / "scripts"
            / "compare_baseline_gated_hybrid_allocator.py"
        ).read_text()

        for lib in ["openai", "anthropic", "cohere", "requests", "httpx", "boto3"]:
            self.assertIsNone(
                re.search(rf"^\s*(import|from)\s+{lib}\b", src, re.MULTILINE),
                msg=f"Forbidden import '{lib}' found",
            )
            self.assertNotIn(f"{lib}.", src)


if __name__ == "__main__":
    unittest.main()
