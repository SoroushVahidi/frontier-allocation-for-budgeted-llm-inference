"""Tests for scripts/collect_baseline_gated_loss_cases.py"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

from collect_baseline_gated_loss_cases import (
    assign_placeholder_labels,
    assign_required_labels,
    collect_cases,
    compute_metrics,
    load_group_decisions,
    load_raw_index,
    load_scored_index,
    main,
)

BASELINE = "external_l1_max"
FRONTIER = "direct_reserve_semantic_frontier_v2"


def _make_group_decision_row(
    *,
    split: str,
    example_id: str,
    budget: int,
    selected_method: str,
    did_switch: int,
    external_score: float,
    direct_score: float,
    external_seed: int,
    direct_seed: int,
    external_correct: int,
    direct_correct: int,
    gated_correct: int,
) -> dict[str, str]:
    return {
        "split": split,
        "group_id": example_id,
        "budget": str(budget),
        "selected_method": selected_method,
        "did_switch": str(did_switch),
        "external_top_score": str(external_score),
        "direct_top_score": str(direct_score),
        "score_margin_direct_minus_external": str(direct_score - external_score),
        "external_top_seed": str(external_seed),
        "direct_top_seed": str(direct_seed),
        "external_top_correct": str(external_correct),
        "direct_top_correct": str(direct_correct),
        "gated_correct": str(gated_correct),
        "random_expected_external": "0.5",
        "random_expected_direct": "0.5",
        "oracle_top2_correct": str(int(external_correct == 1 or direct_correct == 1)),
        "recovery": str(int(external_correct == 0 and gated_correct == 1)),
        "regression": str(int(external_correct == 1 and gated_correct == 0)),
        "net_gain": str(int(external_correct == 0 and gated_correct == 1) - int(external_correct == 1 and gated_correct == 0)),
    }


def _make_scored_row(
    *,
    example_id: str,
    budget: int,
    method: str,
    seed: int,
    proba_ready: float,
    exact_match: int,
    answer: str,
    trace: str,
    row_index: int,
) -> dict:
    return {
        "row_index": row_index,
        "proba_ready": proba_ready,
        "score_ready": proba_ready,
        "predicted_label": int(proba_ready >= 0.5),
        "feature_text": (
            f"question: Q-{example_id} | candidate_answer: {answer} | "
            f"candidate_trace_short: {trace} | candidate_source: {method}"
        ),
        "metadata": {
            "example_id": example_id,
            "budget": budget,
            "method": method,
            "seed": seed,
            "exact_match_metadata": exact_match,
            "gold_answer_metadata": f"gold-{example_id}",
        },
    }


def _write_group_decisions_csv(path: pathlib.Path, rows: list[dict[str, str]]) -> None:
    cols = [
        "split",
        "group_id",
        "budget",
        "selected_method",
        "did_switch",
        "external_top_score",
        "direct_top_score",
        "score_margin_direct_minus_external",
        "external_top_seed",
        "direct_top_seed",
        "external_top_correct",
        "direct_top_correct",
        "gated_correct",
        "random_expected_external",
        "random_expected_direct",
        "oracle_top2_correct",
        "recovery",
        "regression",
        "net_gain",
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _write_jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


class TestLabelAssignment(unittest.TestCase):
    def test_assign_required_labels_main_cases(self):
        both_correct = assign_required_labels(
            {
                "baseline_correct": 1,
                "frontier_correct": 1,
                "gated_correct": 1,
                "switch_flag": 0,
            }
        )
        self.assertIn("both_correct", both_correct)
        self.assertIn("gate_neutral_stay", both_correct)

        both_wrong = assign_required_labels(
            {
                "baseline_correct": 0,
                "frontier_correct": 0,
                "gated_correct": 0,
                "switch_flag": 0,
            }
        )
        self.assertIn("both_wrong", both_wrong)

        regression = assign_required_labels(
            {
                "baseline_correct": 1,
                "frontier_correct": 0,
                "gated_correct": 0,
                "switch_flag": 1,
            }
        )
        self.assertIn("baseline_correct_frontier_wrong", regression)
        self.assertIn("gate_regression", regression)

        missed = assign_required_labels(
            {
                "baseline_correct": 0,
                "frontier_correct": 1,
                "gated_correct": 0,
                "switch_flag": 0,
            }
        )
        self.assertIn("baseline_wrong_frontier_correct", missed)
        self.assertIn("gate_missed_recovery", missed)
        self.assertIn("oracle_recoverable", missed)

        recovery = assign_required_labels(
            {
                "baseline_correct": 0,
                "frontier_correct": 1,
                "gated_correct": 1,
                "switch_flag": 1,
            }
        )
        self.assertIn("gate_recovery", recovery)
        self.assertIn("gate_safe_switch", recovery)

    def test_assign_placeholder_labels(self):
        case = {
            "baseline_correct": 0,
            "frontier_correct": 1,
            "switch_flag": 0,
            "oracle_correct": 1,
            "parsing_or_canonicalization_suspect": 0,
            "required_labels": ["baseline_wrong_frontier_correct", "gate_missed_recovery"],
            "gated_correct": 0,
        }
        labels = assign_placeholder_labels(case)
        self.assertIn("selector_miss", labels)
        self.assertIn("verifier_or_gate_miss", labels)

        pool_miss = {
            "baseline_correct": 0,
            "frontier_correct": 0,
            "switch_flag": 0,
            "oracle_correct": 0,
            "parsing_or_canonicalization_suspect": 0,
            "required_labels": ["both_wrong"],
            "gated_correct": 0,
        }
        labels2 = assign_placeholder_labels(pool_miss)
        self.assertIn("candidate_pool_miss", labels2)


class TestLoadingAndJoin(unittest.TestCase):
    def test_load_group_decisions_auto_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir) / "group_decisions.csv"
            rows = [
                _make_group_decision_row(
                    split="dev",
                    example_id="ex0",
                    budget=6,
                    selected_method=BASELINE,
                    did_switch=0,
                    external_score=0.9,
                    direct_score=0.1,
                    external_seed=11,
                    direct_seed=11,
                    external_correct=1,
                    direct_correct=0,
                    gated_correct=1,
                ),
                _make_group_decision_row(
                    split="validation",
                    example_id="ex1",
                    budget=6,
                    selected_method=BASELINE,
                    did_switch=0,
                    external_score=0.8,
                    direct_score=0.2,
                    external_seed=11,
                    direct_seed=11,
                    external_correct=0,
                    direct_correct=1,
                    gated_correct=0,
                ),
            ]
            _write_group_decisions_csv(p, rows)

            loaded = load_group_decisions(p, split="auto")
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["split"], "validation")

    def test_extract_selected_candidate_fields_and_optional_raw_join(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            scored = root / "scored.jsonl"
            raw = root / "raw.jsonl"

            scored_rows = [
                _make_scored_row(
                    example_id="ex1",
                    budget=6,
                    method=BASELINE,
                    seed=11,
                    proba_ready=0.9,
                    exact_match=0,
                    answer="A-baseline",
                    trace="trace-baseline",
                    row_index=1,
                ),
                _make_scored_row(
                    example_id="ex1",
                    budget=6,
                    method=FRONTIER,
                    seed=23,
                    proba_ready=0.2,
                    exact_match=1,
                    answer="A-frontier",
                    trace="trace-frontier",
                    row_index=2,
                ),
            ]
            _write_jsonl(scored, scored_rows)

            raw_rows = [
                {
                    "metadata": {
                        "example_id": "ex1",
                        "budget": 6,
                        "method": BASELINE,
                        "seed": 11,
                    },
                    "status": "ok",
                    "error": "",
                }
            ]
            _write_jsonl(raw, raw_rows)

            scored_index, _ = load_scored_index(scored, score_field="proba_ready")
            raw_index = load_raw_index(raw)

            decisions = [
                _make_group_decision_row(
                    split="validation",
                    example_id="ex1",
                    budget=6,
                    selected_method=BASELINE,
                    did_switch=0,
                    external_score=0.9,
                    direct_score=0.2,
                    external_seed=11,
                    direct_seed=23,
                    external_correct=0,
                    direct_correct=1,
                    gated_correct=0,
                )
            ]

            cases = collect_cases(
                decisions,
                scored_index=scored_index,
                raw_index=raw_index,
                scored_jsonl_path=scored,
                baseline_method=BASELINE,
                frontier_method=FRONTIER,
                score_field="proba_ready",
                group_id_field="example_id",
                budget_field="budget",
                max_trace_chars=800,
            )

            self.assertEqual(len(cases), 1)
            c = cases[0]
            self.assertEqual(c["baseline_answer"], "A-baseline")
            self.assertEqual(c["frontier_answer"], "A-frontier")
            self.assertIn("trace-baseline", c["baseline_trace_snippet"])
            self.assertEqual(c["baseline_raw_status"], "ok")
            self.assertIn("gate_missed_recovery", c["required_labels"])


class TestEndToEndOutputs(unittest.TestCase):
    def test_outputs_created_and_metrics_consistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            group_csv = root / "group_decisions.csv"
            scored = root / "scored.jsonl"
            out = root / "out"

            # 4 validation groups, covering key categories.
            decisions = [
                # missed recovery
                _make_group_decision_row(
                    split="validation",
                    example_id="ex_missed",
                    budget=6,
                    selected_method=BASELINE,
                    did_switch=0,
                    external_score=0.9,
                    direct_score=0.2,
                    external_seed=11,
                    direct_seed=23,
                    external_correct=0,
                    direct_correct=1,
                    gated_correct=0,
                ),
                # regression
                _make_group_decision_row(
                    split="validation",
                    example_id="ex_reg",
                    budget=6,
                    selected_method=FRONTIER,
                    did_switch=1,
                    external_score=0.8,
                    direct_score=0.1,
                    external_seed=11,
                    direct_seed=23,
                    external_correct=1,
                    direct_correct=0,
                    gated_correct=0,
                ),
                # both correct
                _make_group_decision_row(
                    split="validation",
                    example_id="ex_bothc",
                    budget=6,
                    selected_method=BASELINE,
                    did_switch=0,
                    external_score=0.7,
                    direct_score=0.6,
                    external_seed=11,
                    direct_seed=23,
                    external_correct=1,
                    direct_correct=1,
                    gated_correct=1,
                ),
                # both wrong
                _make_group_decision_row(
                    split="validation",
                    example_id="ex_bothw",
                    budget=6,
                    selected_method=BASELINE,
                    did_switch=0,
                    external_score=0.6,
                    direct_score=0.5,
                    external_seed=11,
                    direct_seed=23,
                    external_correct=0,
                    direct_correct=0,
                    gated_correct=0,
                ),
            ]
            _write_group_decisions_csv(group_csv, decisions)

            scored_rows = []
            for ex in ["ex_missed", "ex_reg", "ex_bothc", "ex_bothw"]:
                scored_rows.append(
                    _make_scored_row(
                        example_id=ex,
                        budget=6,
                        method=BASELINE,
                        seed=11,
                        proba_ready=0.9,
                        exact_match=1 if ex == "ex_bothc" else 0,
                        answer=f"ans-{ex}-b",
                        trace=f"trace-{ex}-b",
                        row_index=len(scored_rows) + 1,
                    )
                )
                scored_rows.append(
                    _make_scored_row(
                        example_id=ex,
                        budget=6,
                        method=FRONTIER,
                        seed=23,
                        proba_ready=0.1,
                        exact_match=1 if ex in {"ex_missed", "ex_bothc"} else 0,
                        answer=f"ans-{ex}-f",
                        trace=f"trace-{ex}-f",
                        row_index=len(scored_rows) + 1,
                    )
                )
            _write_jsonl(scored, scored_rows)

            rc = main(
                [
                    "--group-decisions-csv",
                    str(group_csv),
                    "--scored-jsonl",
                    str(scored),
                    "--output-dir",
                    str(out),
                ]
            )
            self.assertEqual(rc, 0)

            expected = [
                "loss_case_report.md",
                "loss_case_metrics.json",
                "case_diagnostics.csv",
                "missed_recoveries.csv",
                "regressions.csv",
                "switch_cases.csv",
                "oracle_recoverable_cases.csv",
                "manual_review_cases.csv",
            ]
            for name in expected:
                self.assertTrue((out / name).exists(), msg=f"missing {name}")

            metrics = json.loads((out / "loss_case_metrics.json").read_text())
            m = metrics["metrics"]
            self.assertEqual(m["n_groups"], 4)
            self.assertEqual(m["recoveries"], 0)
            self.assertEqual(m["regressions"], 1)
            self.assertEqual(m["direct_opportunities"], 1)
            self.assertEqual(m["missed_opportunities"], 1)

            with open(out / "missed_recoveries.csv", newline="") as f:
                miss_rows = list(csv.DictReader(f))
            self.assertEqual(len(miss_rows), 1)
            self.assertEqual(miss_rows[0]["example_id"], "ex_missed")

            with open(out / "regressions.csv", newline="") as f:
                reg_rows = list(csv.DictReader(f))
            self.assertEqual(len(reg_rows), 1)
            self.assertEqual(reg_rows[0]["example_id"], "ex_reg")


class TestSafety(unittest.TestCase):
    def test_no_forbidden_imports(self):
        src = (
            pathlib.Path(__file__).parent.parent
            / "scripts"
            / "collect_baseline_gated_loss_cases.py"
        ).read_text()

        for lib in ["openai", "anthropic", "cohere", "requests", "httpx", "boto3"]:
            self.assertIsNone(
                re.search(rf"^\s*(import|from)\s+{lib}\b", src, re.MULTILINE),
                msg=f"Forbidden import '{lib}' found",
            )


if __name__ == "__main__":
    unittest.main()
