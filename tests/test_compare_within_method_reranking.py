"""Tests for scripts/compare_within_method_reranking.py"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

from compare_within_method_reranking import (
    aggregate_groups,
    build_groups,
    compute_diagnostics,
    group_stats,
    load_scored,
    main,
    write_diagnostic_csv,
    write_group_details_csv,
    write_reranking_by_budget_method_csv,
    write_reranking_by_method_csv,
)

DIRECT = "direct_reserve_semantic_frontier_v2"
EXTERNAL = "external_l1_max"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_row(
    *,
    example_id="ex0",
    budget=4,
    seed=11,
    method=EXTERNAL,
    proba_ready=0.97,
    exact_match_metadata=1,
) -> dict:
    return {
        "proba_ready": proba_ready,
        "score_ready": proba_ready,
        "predicted_label": int(proba_ready >= 0.5),
        "feature_text": "question: Q | candidate_answer: A",
        "metadata": {
            "example_id": example_id,
            "budget": budget,
            "seed": seed,
            "method": method,
            "exact_match_metadata": exact_match_metadata,
            "gold_answer_metadata": "42",
        },
    }


def _write_jsonl(tmpdir: str, rows: list[dict]) -> pathlib.Path:
    p = pathlib.Path(tmpdir) / "scored.jsonl"
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p


def _make_group_rows(
    *,
    example_id="ex0",
    budget=4,
    method=EXTERNAL,
    seeds=(11, 23, 37),
    probas=(0.97, 0.04, 0.80),
    ems=(1, 0, 1),
) -> list[dict]:
    return [
        _make_row(example_id=example_id, budget=budget, seed=s, method=method,
                  proba_ready=p, exact_match_metadata=e)
        for s, p, e in zip(seeds, probas, ems)
    ]


def _flat(rows: list[dict]) -> list[dict]:
    """Flatten metadata into top-level for load_scored simulation."""
    result = []
    for r in rows:
        fr = dict(r)
        fr.update(r.get("metadata", {}))
        fr["proba_ready"] = float(r.get("proba_ready", 0))
        result.append(fr)
    return result


# ---------------------------------------------------------------------------
# load_scored
# ---------------------------------------------------------------------------

class TestLoadScored(unittest.TestCase):
    def test_flattens_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_jsonl(tmpdir, [_make_row()])
            rows = load_scored(p, "proba_ready", "exact_match_metadata")
        self.assertIn("example_id", rows[0])
        self.assertIn("proba_ready", rows[0])
        self.assertIn("exact_match_metadata", rows[0])

    def test_proba_ready_cast_to_float(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            row = _make_row(proba_ready=0.97)
            row["proba_ready"] = "0.97"  # stored as string
            p = _write_jsonl(tmpdir, [row])
            rows = load_scored(p, "proba_ready", "exact_match_metadata")
        self.assertIsInstance(rows[0]["proba_ready"], float)

    def test_skips_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir) / "s.jsonl"
            p.write_text(json.dumps(_make_row()) + "\n\n")
            rows = load_scored(p, "proba_ready", "exact_match_metadata")
        self.assertEqual(len(rows), 1)

    def test_missing_metadata_handled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            row = {"proba_ready": 0.5, "predicted_label": 1}
            p = _write_jsonl(tmpdir, [row])
            rows = load_scored(p, "proba_ready", "exact_match_metadata")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["proba_ready"], 0.5)


# ---------------------------------------------------------------------------
# build_groups
# ---------------------------------------------------------------------------

class TestBuildGroups(unittest.TestCase):
    def test_groups_by_fields(self):
        rows = _flat(_make_group_rows(example_id="ex0", budget=4, method=EXTERNAL))
        rows += _flat(_make_group_rows(example_id="ex1", budget=4, method=EXTERNAL))
        groups = build_groups(rows, ["example_id", "budget", "method"])
        self.assertEqual(len(groups), 2)
        self.assertTrue(all(len(v) == 3 for v in groups.values()))

    def test_single_group(self):
        rows = _flat(_make_group_rows())
        groups = build_groups(rows, ["example_id", "budget", "method"])
        self.assertEqual(len(groups), 1)

    def test_returns_dict_of_lists(self):
        rows = _flat(_make_group_rows())
        groups = build_groups(rows, ["example_id"])
        self.assertIsInstance(list(groups.values())[0], list)


# ---------------------------------------------------------------------------
# group_stats
# ---------------------------------------------------------------------------

class TestGroupStats(unittest.TestCase):
    def _make_cands(self, probas, ems):
        return [
            {"proba_ready": p, "exact_match_metadata": e, "seed": i}
            for i, (p, e) in enumerate(zip(probas, ems))
        ]

    def test_verifier_max_picks_highest(self):
        cands = self._make_cands([0.04, 0.97, 0.50], [0, 1, 0])
        gs = group_stats(cands, "proba_ready", "exact_match_metadata")
        self.assertEqual(gs["em_verifier_max"], 1)

    def test_anti_verifier_picks_lowest(self):
        cands = self._make_cands([0.04, 0.97, 0.50], [0, 1, 0])
        gs = group_stats(cands, "proba_ready", "exact_match_metadata")
        self.assertEqual(gs["em_anti_verifier"], 0)

    def test_random_expected_is_mean_em(self):
        cands = self._make_cands([0.5, 0.5, 0.5], [1, 0, 1])
        gs = group_stats(cands, "proba_ready", "exact_match_metadata")
        self.assertAlmostEqual(gs["random_expected"], 2 / 3)

    def test_oracle_any_correct(self):
        cands = self._make_cands([0.04, 0.04, 0.04], [0, 0, 1])
        gs = group_stats(cands, "proba_ready", "exact_match_metadata")
        self.assertEqual(gs["oracle_any_correct"], 1)

    def test_oracle_all_wrong(self):
        cands = self._make_cands([0.04, 0.04], [0, 0])
        gs = group_stats(cands, "proba_ready", "exact_match_metadata")
        self.assertEqual(gs["oracle_any_correct"], 0)

    def test_score_spread(self):
        cands = self._make_cands([0.04, 0.97], [0, 1])
        gs = group_stats(cands, "proba_ready", "exact_match_metadata")
        self.assertAlmostEqual(gs["score_spread"], 0.93, places=2)

    def test_tiny_spread(self):
        cands = self._make_cands([0.0390, 0.0391, 0.0392], [0, 1, 0])
        gs = group_stats(cands, "proba_ready", "exact_match_metadata")
        self.assertLess(gs["score_spread"], 0.001)

    def test_n_candidates(self):
        cands = self._make_cands([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], [1]*6)
        gs = group_stats(cands, "proba_ready", "exact_match_metadata")
        self.assertEqual(gs["n_candidates"], 6)


# ---------------------------------------------------------------------------
# aggregate_groups
# ---------------------------------------------------------------------------

class TestAggregateGroups(unittest.TestCase):
    def _make_gstats_and_keys(self, method=EXTERNAL, budget=4, n=6):
        """n groups, alternating correct/wrong for verifier_max."""
        group_fields = ["example_id", "budget", "method"]
        keys = []
        gstats_list = []
        for i in range(n):
            keys.append((f"ex{i}", budget, method))
            em_vm = 1 if i % 2 == 0 else 0
            gstats_list.append({
                "n_candidates": 6,
                "n_with_em": 6,
                "scores": [0.04] * 6,
                "score_min": 0.038,
                "score_max": 0.085,
                "score_spread": 0.047,
                "score_mean": 0.040,
                "score_stdev": 0.003,
                "em_verifier_max": em_vm,
                "em_anti_verifier": 1 - em_vm,
                "em_first_seed": 1,
                "oracle_any_correct": 1,
                "random_expected": 0.5,
                "verifier_max_candidate": {},
                "anti_verifier_candidate": {},
            })
        return gstats_list, keys, group_fields

    def test_overall_n_groups(self):
        gstats, keys, gf = self._make_gstats_and_keys(n=10)
        agg = aggregate_groups(gstats, keys, gf, method_idx=2, budget_idx=1)
        self.assertEqual(agg["overall"]["n_groups"], 10)

    def test_by_method_present(self):
        gstats, keys, gf = self._make_gstats_and_keys()
        agg = aggregate_groups(gstats, keys, gf, method_idx=2, budget_idx=1)
        self.assertIn(EXTERNAL, agg["by_method"])

    def test_verifier_max_accuracy_computed(self):
        gstats, keys, gf = self._make_gstats_and_keys(n=4)
        agg = aggregate_groups(gstats, keys, gf, method_idx=2, budget_idx=1)
        # 2 correct out of 4 (alternating)
        self.assertAlmostEqual(agg["overall"]["verifier_max_accuracy"], 0.5)

    def test_lift_vs_random(self):
        gstats, keys, gf = self._make_gstats_and_keys(n=4)
        agg = aggregate_groups(gstats, keys, gf, method_idx=2, budget_idx=1)
        lift = agg["overall"].get("lift_vs_random")
        # verifier = 0.5, random = 0.5 → lift = 0
        self.assertIsNotNone(lift)

    def test_by_method_budget_keys(self):
        gstats, keys, gf = self._make_gstats_and_keys(n=4, budget=6)
        agg = aggregate_groups(gstats, keys, gf, method_idx=2, budget_idx=1)
        keys_mb = list(agg["by_method_budget"].keys())
        self.assertTrue(any(b == 6 for _, b in keys_mb))


# ---------------------------------------------------------------------------
# compute_diagnostics
# ---------------------------------------------------------------------------

class TestComputeDiagnostics(unittest.TestCase):
    def _gs(self, em_vm, oracle, rnd, spread):
        return {
            "n_candidates": 6,
            "n_with_em": 6,
            "scores": [0.04] * 6,
            "score_min": 0.038,
            "score_max": 0.038 + spread,
            "score_spread": spread,
            "score_mean": 0.040,
            "score_stdev": 0.001,
            "em_verifier_max": em_vm,
            "em_anti_verifier": 0,
            "em_first_seed": 0,
            "oracle_any_correct": oracle,
            "random_expected": rnd,
            "verifier_max_candidate": {},
            "anti_verifier_candidate": {},
        }

    def test_missed_oracle_detected(self):
        # oracle correct, verifier wrong
        gs = [self._gs(em_vm=0, oracle=1, rnd=0.3, spread=0.01)]
        keys = [("ex0", 4, EXTERNAL)]
        gf = ["example_id", "budget", "method"]
        diag = compute_diagnostics(gs, keys, gf, "exact_match_metadata")
        self.assertEqual(len(diag["verifier_missed_oracle"]), 1)

    def test_verifier_wins_low_random(self):
        gs = [self._gs(em_vm=1, oracle=1, rnd=0.3, spread=0.1)]
        keys = [("ex0", 4, EXTERNAL)]
        gf = ["example_id", "budget", "method"]
        diag = compute_diagnostics(gs, keys, gf, "exact_match_metadata")
        self.assertEqual(len(diag["verifier_wins_low_random"]), 1)

    def test_tiny_spread_success(self):
        gs = [self._gs(em_vm=1, oracle=1, rnd=0.5, spread=0.005)]
        keys = [("ex0", 4, DIRECT)]
        gf = ["example_id", "budget", "method"]
        diag = compute_diagnostics(gs, keys, gf, "exact_match_metadata")
        self.assertEqual(len(diag["tiny_spread_success"]), 1)

    def test_no_false_positives(self):
        # oracle wrong, verifier right shouldn't be in missed_oracle
        gs = [self._gs(em_vm=1, oracle=1, rnd=0.9, spread=0.1)]
        keys = [("ex0", 4, EXTERNAL)]
        gf = ["example_id", "budget", "method"]
        diag = compute_diagnostics(gs, keys, gf, "exact_match_metadata")
        self.assertEqual(len(diag["verifier_missed_oracle"]), 0)


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

class TestCsvWriters(unittest.TestCase):
    def test_reranking_by_method_csv(self):
        by_method = {
            EXTERNAL: {"n_groups": 120, "verifier_max_accuracy": 0.78,
                       "random_expected_accuracy": 0.70, "anti_verifier_accuracy": 0.66,
                       "first_seed_accuracy": 0.70, "oracle_ceiling": 1.0,
                       "lift_vs_random": 0.08, "lift_vs_anti_verifier": 0.12,
                       "oracle_gap": 0.22, "mean_score_spread": 0.05,
                       "n_tiny_spread_groups": 0},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir) / "out.csv"
            write_reranking_by_method_csv(by_method, p)
            self.assertTrue(p.exists())
            with open(p) as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertIn("verifier_max_accuracy", rows[0])

    def test_group_details_csv(self):
        gf = ["example_id", "budget", "method"]
        gs = [{
            "n_candidates": 6, "em_verifier_max": 1, "em_anti_verifier": 0,
            "em_first_seed": 1, "oracle_any_correct": 1,
            "random_expected": 0.7, "score_min": 0.04, "score_max": 0.97,
            "score_spread": 0.93, "score_stdev": 0.3,
        }]
        keys = [("ex0", 4, EXTERNAL)]
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir) / "gd.csv"
            write_group_details_csv(gs, keys, gf, p)
            self.assertTrue(p.exists())
            with open(p) as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertIn("example_id", rows[0])

    def test_diagnostic_csv_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir) / "diag.csv"
            write_diagnostic_csv([], p)
            self.assertTrue(p.exists())


# ---------------------------------------------------------------------------
# No forbidden API imports
# ---------------------------------------------------------------------------

class TestNoApiImports(unittest.TestCase):
    def test_no_forbidden_imports(self):
        src = (pathlib.Path(__file__).parent.parent / "scripts" / "compare_within_method_reranking.py").read_text()
        for lib in ["openai", "anthropic", "cohere", "httpx", "requests", "boto3"]:
            self.assertIsNone(
                re.search(rf"^\s*(import|from)\s+{lib}\b", src, re.MULTILINE),
                msg=f"Forbidden import '{lib}' found",
            )


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):
    def _make_scored_file(self, tmpdir: str, n_groups=4, n_seeds=6) -> pathlib.Path:
        rows = []
        for i in range(n_groups):
            for j, seed in enumerate(range(n_seeds)):
                em = 1 if (j + i) % 3 != 0 else 0
                proba = 0.97 - j * 0.15 + (i % 2) * 0.05
                rows.append(_make_row(
                    example_id=f"ex{i}", budget=4, seed=seed * 10 + 11,
                    method=EXTERNAL, proba_ready=max(0.04, proba),
                    exact_match_metadata=em,
                ))
        return _write_jsonl(tmpdir, rows)

    def test_creates_all_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scored_path = self._make_scored_file(tmpdir)
            out = pathlib.Path(tmpdir) / "out"
            rc = main([
                "--scored-jsonl", str(scored_path),
                "--output-dir", str(out),
            ])
            self.assertEqual(rc, 0)
            for fname in ["within_method_reranking_report.md", "metrics.json",
                          "reranking_by_method.csv", "reranking_by_budget_method.csv",
                          "reranking_group_details.csv", "verifier_missed_oracle_cases.csv"]:
                self.assertTrue((out / fname).exists(), f"Missing: {fname}")

    def test_missing_input_returns_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = main([
                "--scored-jsonl", "/nonexistent.jsonl",
                "--output-dir", tmpdir + "/out",
            ])
            self.assertEqual(rc, 1)

    def test_metrics_json_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scored_path = self._make_scored_file(tmpdir)
            out = pathlib.Path(tmpdir) / "out"
            main([
                "--scored-jsonl", str(scored_path),
                "--output-dir", str(out),
            ])
            with open(out / "metrics.json") as f:
                m = json.load(f)
        for k in ["n_rows", "n_groups", "overall", "by_method", "diagnostics"]:
            self.assertIn(k, m)
        self.assertIn("verifier_max_accuracy", m["overall"])

    def test_two_methods(self):
        """Two-method dataset produces by_method entries for each."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rows = []
            for method in [DIRECT, EXTERNAL]:
                for i in range(3):
                    for j, seed in enumerate([11, 23, 37]):
                        proba = 0.04 if method == DIRECT else 0.97 - j * 0.3
                        em = 1 if j == 0 else 0
                        rows.append(_make_row(
                            example_id=f"ex{i}", budget=4, seed=seed,
                            method=method, proba_ready=proba, exact_match_metadata=em,
                        ))
            scored_path = _write_jsonl(tmpdir, rows)
            out = pathlib.Path(tmpdir) / "out"
            main([
                "--scored-jsonl", str(scored_path),
                "--output-dir", str(out),
            ])
            with open(out / "metrics.json") as f:
                m = json.load(f)
        self.assertIn(DIRECT, m["by_method"])
        self.assertIn(EXTERNAL, m["by_method"])

    def test_handles_missing_correct_field_gracefully(self):
        """Rows missing exact_match_metadata should not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rows = []
            for seed in [11, 23, 37]:
                r = _make_row(seed=seed)
                del r["metadata"]["exact_match_metadata"]
                rows.append(r)
            scored_path = _write_jsonl(tmpdir, rows)
            out = pathlib.Path(tmpdir) / "out"
            rc = main([
                "--scored-jsonl", str(scored_path),
                "--output-dir", str(out),
            ])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
