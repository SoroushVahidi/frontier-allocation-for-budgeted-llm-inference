"""Tests for scripts/compare_allocation_policies.py"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

from compare_allocation_policies import (
    build_groups,
    load_scored,
    method_entanglement_diagnostics,
    pairwise_policy_comparison,
    per_method_accuracy,
    per_method_budget_accuracy,
    write_accuracy_by_budget_csv,
    write_policy_pairwise_csv,
    write_score_bins_by_method_csv,
    main,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DIRECT = "direct_reserve_semantic_frontier_v2"
EXTERNAL = "external_l1_max"


def _make_row(
    *,
    example_id="ex0",
    budget=4,
    seed=11,
    method=DIRECT,
    proba_ready=0.04,
    exact_match_metadata=1,
) -> dict:
    return {
        "feature_text": f"question: Q | candidate_trace_short: T",
        "proba_ready": proba_ready,
        "score_ready": proba_ready,
        "predicted_label": int(proba_ready >= 0.5),
        "metadata": {
            "example_id": example_id,
            "budget": budget,
            "seed": seed,
            "method": method,
            "dataset": "gsm8k",
            "exact_match_metadata": exact_match_metadata,
            "gold_answer_metadata": "42",
        },
    }


def _write_scored_jsonl(tmpdir: str, rows: list[dict]) -> pathlib.Path:
    p = pathlib.Path(tmpdir) / "scored_candidates.jsonl"
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p


def _make_pair(example_id="ex0", budget=4, seed=11, em_direct=1, em_external=1,
               proba_direct=0.04, proba_external=0.97) -> list[dict]:
    return [
        _make_row(example_id=example_id, budget=budget, seed=seed,
                  method=DIRECT, proba_ready=proba_direct, exact_match_metadata=em_direct),
        _make_row(example_id=example_id, budget=budget, seed=seed,
                  method=EXTERNAL, proba_ready=proba_external, exact_match_metadata=em_external),
    ]


def _make_dataset(n_problems=4, budgets=(4, 6), seeds=(11, 21)) -> list[dict]:
    rows = []
    for p in range(n_problems):
        for b in budgets:
            for s in seeds:
                em_d = 1 if p % 2 == 0 else 0
                em_e = 1 if p % 3 != 1 else 0
                rows += _make_pair(
                    example_id=f"ex{p}", budget=b, seed=s,
                    em_direct=em_d, em_external=em_e,
                    proba_direct=0.04, proba_external=0.97,
                )
    return rows


# ---------------------------------------------------------------------------
# load_scored
# ---------------------------------------------------------------------------

class TestLoadScored(unittest.TestCase):
    def test_loads_rows_and_flattens_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_scored_jsonl(tmpdir, [_make_row()])
            rows = load_scored(p, "proba_ready", "exact_match_metadata")
        self.assertEqual(len(rows), 1)
        self.assertIn("example_id", rows[0])
        self.assertIn("proba_ready", rows[0])
        self.assertIn("exact_match_metadata", rows[0])

    def test_proba_ready_is_float(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Store as string (as produced by the scoring script)
            row = _make_row(proba_ready=0.97)
            row["proba_ready"] = "0.97"
            p = _write_scored_jsonl(tmpdir, [row])
            rows = load_scored(p, "proba_ready", "exact_match_metadata")
        self.assertIsInstance(rows[0]["proba_ready"], float)

    def test_skips_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir) / "s.jsonl"
            with open(p, "w") as f:
                f.write(json.dumps(_make_row()) + "\n\n")
            rows = load_scored(p, "proba_ready", "exact_match_metadata")
        self.assertEqual(len(rows), 1)


# ---------------------------------------------------------------------------
# per_method_accuracy
# ---------------------------------------------------------------------------

class TestPerMethodAccuracy(unittest.TestCase):
    def test_computes_accuracy_per_method(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_scored_jsonl(tmpdir, _make_dataset())
            rows = load_scored(p, "proba_ready", "exact_match_metadata")
        result = per_method_accuracy(rows, "method", "exact_match_metadata")
        self.assertIn(DIRECT, result)
        self.assertIn(EXTERNAL, result)
        self.assertGreaterEqual(result[DIRECT]["accuracy"], 0.0)
        self.assertLessEqual(result[DIRECT]["accuracy"], 1.0)

    def test_n_sums_to_total(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_scored_jsonl(tmpdir, _make_dataset())
            rows = load_scored(p, "proba_ready", "exact_match_metadata")
        result = per_method_accuracy(rows, "method", "exact_match_metadata")
        total = sum(d["n"] for d in result.values())
        self.assertEqual(total, len(rows))


# ---------------------------------------------------------------------------
# per_method_budget_accuracy
# ---------------------------------------------------------------------------

class TestPerMethodBudgetAccuracy(unittest.TestCase):
    def test_returns_one_entry_per_method_budget_pair(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_scored_jsonl(tmpdir, _make_dataset(budgets=(4, 6)))
            rows = load_scored(p, "proba_ready", "exact_match_metadata")
        result = per_method_budget_accuracy(rows, "method", "budget", "exact_match_metadata")
        # 2 methods × 2 budgets = 4 entries
        self.assertEqual(len(result), 4)

    def test_accuracy_in_valid_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_scored_jsonl(tmpdir, _make_dataset())
            rows = load_scored(p, "proba_ready", "exact_match_metadata")
        result = per_method_budget_accuracy(rows, "method", "budget", "exact_match_metadata")
        for d in result.values():
            self.assertGreaterEqual(d["accuracy"], 0.0)
            self.assertLessEqual(d["accuracy"], 1.0)


# ---------------------------------------------------------------------------
# build_groups
# ---------------------------------------------------------------------------

class TestBuildGroups(unittest.TestCase):
    def test_groups_by_fields(self):
        rows = _make_dataset(n_problems=2, budgets=(4,), seeds=(11,))
        flat_rows = []
        for r in rows:
            fr = dict(r)
            fr.update(r.get("metadata", {}))
            flat_rows.append(fr)
        groups = build_groups(flat_rows, ["example_id", "budget", "seed"])
        # 2 problems × 1 budget × 1 seed = 2 groups, each with 2 candidates
        self.assertEqual(len(groups), 2)
        self.assertTrue(all(len(v) == 2 for v in groups.values()))

    def test_returns_dict_of_lists(self):
        rows = [_make_row()]
        # flatten
        r = dict(rows[0])
        r.update(rows[0].get("metadata", {}))
        groups = build_groups([r], ["example_id"])
        self.assertEqual(len(groups), 1)
        self.assertIsInstance(list(groups.values())[0], list)


# ---------------------------------------------------------------------------
# pairwise_policy_comparison
# ---------------------------------------------------------------------------

class TestPairwisePolicyComparison(unittest.TestCase):
    def _make_groups_and_rows(self, pairs):
        rows = []
        for pair in pairs:
            rows += pair
        # flatten metadata
        flat = []
        for r in rows:
            fr = dict(r)
            fr.update(r.get("metadata", {}))
            flat.append(fr)
        groups = build_groups(flat, ["example_id", "budget", "seed"])
        return groups, flat

    def test_verifier_picks_max_score(self):
        pairs = [
            _make_pair("ex0", 4, 11, em_direct=0, em_external=1,
                       proba_direct=0.04, proba_external=0.97),
        ]
        groups, rows = self._make_groups_and_rows(pairs)
        result = pairwise_policy_comparison(
            groups, "proba_ready", "exact_match_metadata", "method", "budget",
            DIRECT, EXTERNAL,
        )
        # verifier should pick external (higher score), which is correct
        self.assertEqual(result["overall"]["verifier_guided"]["accuracy"], 1.0)

    def test_verifier_picks_wrong_when_low_score_correct(self):
        pairs = [
            _make_pair("ex0", 4, 11, em_direct=1, em_external=0,
                       proba_direct=0.04, proba_external=0.97),
        ]
        groups, rows = self._make_groups_and_rows(pairs)
        result = pairwise_policy_comparison(
            groups, "proba_ready", "exact_match_metadata", "method", "budget",
            DIRECT, EXTERNAL,
        )
        # verifier picks external (high score) but external is wrong
        self.assertEqual(result["overall"]["verifier_guided"]["accuracy"], 0.0)

    def test_disagree_count_correct(self):
        # 2 pairs: one where both agree, one where they disagree
        pairs = [
            _make_pair("ex0", 4, 11, em_direct=1, em_external=1),  # agree
            _make_pair("ex1", 4, 11, em_direct=0, em_external=1),  # disagree
        ]
        groups, _ = self._make_groups_and_rows(pairs)
        result = pairwise_policy_comparison(
            groups, "proba_ready", "exact_match_metadata", "method", "budget",
            DIRECT, EXTERNAL,
        )
        self.assertEqual(result["disagreement"]["n_disagree"], 1)

    def test_budget_breakdown_present(self):
        pairs = [
            _make_pair("ex0", 4, 11),
            _make_pair("ex0", 6, 11),
        ]
        groups, _ = self._make_groups_and_rows(pairs)
        result = pairwise_policy_comparison(
            groups, "proba_ready", "exact_match_metadata", "method", "budget",
            DIRECT, EXTERNAL,
        )
        self.assertIn("by_budget", result)
        self.assertGreaterEqual(len(result["by_budget"]), 2)

    def test_verifier_method_choice_tracked(self):
        pairs = [_make_pair("ex0", 4, 11, proba_external=0.97, proba_direct=0.04)]
        groups, _ = self._make_groups_and_rows(pairs)
        result = pairwise_policy_comparison(
            groups, "proba_ready", "exact_match_metadata", "method", "budget",
            DIRECT, EXTERNAL,
        )
        choices = result["verifier_method_choice"]
        # verifier should have chosen external (higher score)
        self.assertEqual(choices.get(EXTERNAL, 0), 1)
        self.assertEqual(choices.get(DIRECT, 0), 0)


# ---------------------------------------------------------------------------
# method_entanglement_diagnostics
# ---------------------------------------------------------------------------

class TestMethodEntanglementDiagnostics(unittest.TestCase):
    def _make_flat_rows(self):
        rows = []
        for r in _make_dataset():
            fr = dict(r)
            fr.update(r.get("metadata", {}))
            rows.append(fr)
        return rows

    def test_returns_entry_per_method(self):
        rows = self._make_flat_rows()
        result = method_entanglement_diagnostics(rows, "proba_ready", "exact_match_metadata", "method")
        self.assertIn(DIRECT, result)
        self.assertIn(EXTERNAL, result)

    def test_detects_entanglement_when_methods_fully_separated(self):
        # direct always low, external always high
        rows = self._make_flat_rows()
        result = method_entanglement_diagnostics(rows, "proba_ready", "exact_match_metadata", "method")
        # direct_reserve mean = 0.04 -> n_above_0_5 = 0 -> sep_a = 0%
        # external mean = 0.97 -> n_above_0_5 = all -> sep_b = 100%
        ent = result["__entanglement__"]
        self.assertTrue(ent["entangled"])
        self.assertIn("WARNING", ent["note"])

    def test_bins_sum_to_total(self):
        rows = self._make_flat_rows()
        result = method_entanglement_diagnostics(rows, "proba_ready", "exact_match_metadata", "method")
        for m, s in result.items():
            if m.startswith("__"):
                continue
            bin_sum = sum(b["n"] for b in s["bins"])
            self.assertEqual(bin_sum, s["n"])

    def test_no_entanglement_with_mixed_scores(self):
        # Scores interleaved: direct 0.5, external 0.5
        rows = []
        for i in range(10):
            rows.append({
                "example_id": f"ex{i}", "budget": 4, "seed": 11,
                "method": DIRECT, "proba_ready": 0.5,
                "exact_match_metadata": 1,
            })
            rows.append({
                "example_id": f"ex{i}", "budget": 4, "seed": 11,
                "method": EXTERNAL, "proba_ready": 0.5,
                "exact_match_metadata": 1,
            })
        result = method_entanglement_diagnostics(rows, "proba_ready", "exact_match_metadata", "method")
        ent = result["__entanglement__"]
        self.assertFalse(ent["entangled"])


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

class TestCsvWriters(unittest.TestCase):
    def test_accuracy_by_budget_csv(self):
        by_budget = {
            "4": {"n": 10, "direct_reserve_accuracy": 0.6,
                  "external_l1_max_accuracy": 0.7, "verifier_guided_accuracy": 0.7},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir) / "out.csv"
            write_accuracy_by_budget_csv(by_budget, p)
            self.assertTrue(p.exists())
            with open(p) as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertIn("budget", rows[0])

    def test_policy_pairwise_csv(self):
        overall = {
            "direct_reserve": {"n": 100, "accuracy": 0.6},
            "external_l1_max": {"n": 100, "accuracy": 0.72},
            "verifier_guided": {"n": 100, "accuracy": 0.72},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir) / "pw.csv"
            write_policy_pairwise_csv(overall, p)
            self.assertTrue(p.exists())
            with open(p) as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 3)
        policies = [r["policy"] for r in rows]
        self.assertIn("verifier_guided", policies)

    def test_score_bins_csv(self):
        ent = {
            DIRECT: {"bins": [{"bin": "[0.0,0.2]", "n": 100, "accuracy": 0.6}]},
            EXTERNAL: {"bins": [{"bin": "[0.8,1.0]", "n": 90, "accuracy": 0.74}]},
            "__entanglement__": {"entangled": True, "note": "WARNING"},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir) / "bins.csv"
            write_score_bins_by_method_csv(ent, p)
            self.assertTrue(p.exists())
            with open(p) as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):
    def test_main_creates_all_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rows = _make_dataset(n_problems=4, budgets=(4,), seeds=(11,))
            scored_path = _write_scored_jsonl(tmpdir, rows)
            out = pathlib.Path(tmpdir) / "out"
            rc = main([
                "--scored-jsonl", str(scored_path),
                "--output-dir", str(out),
                "--mode", "report",
            ])
            self.assertEqual(rc, 0)
            for fname in ["policy_comparison_report.md", "metrics.json",
                          "accuracy_by_budget.csv", "policy_pairwise_accuracy.csv",
                          "score_bins_by_method.csv"]:
                self.assertTrue((out / fname).exists(), f"Missing: {fname}")

    def test_main_missing_input_returns_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = main([
                "--scored-jsonl", "/nonexistent/scored.jsonl",
                "--output-dir", tmpdir + "/out",
            ])
            self.assertEqual(rc, 1)

    def test_metrics_json_has_expected_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rows = _make_dataset(n_problems=3, budgets=(4,), seeds=(11,))
            scored_path = _write_scored_jsonl(tmpdir, rows)
            out = pathlib.Path(tmpdir) / "out"
            main([
                "--scored-jsonl", str(scored_path),
                "--output-dir", str(out),
            ])
            with open(out / "metrics.json") as f:
                m = json.load(f)
        for k in ["n_rows", "n_groups", "pairwise_accuracy", "disagreement"]:
            self.assertIn(k, m)
        self.assertIn("verifier_guided", m["pairwise_accuracy"])

    def test_handles_missing_hybrid_score_gracefully(self):
        """Script should work even with no 'original_score' or hybrid column."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rows = _make_dataset(n_problems=2, budgets=(4,), seeds=(11,))
            scored_path = _write_scored_jsonl(tmpdir, rows)
            out = pathlib.Path(tmpdir) / "out"
            # No error expected
            rc = main([
                "--scored-jsonl", str(scored_path),
                "--output-dir", str(out),
            ])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
