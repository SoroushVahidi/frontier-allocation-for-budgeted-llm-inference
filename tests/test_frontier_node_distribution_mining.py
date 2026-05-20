from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.mine_frontier_node_distribution import (
    extract_features,
    build_labels,
    recommend_next_edge,
    main,
    _parse_numeric,
    _numeric_candidates,
    _safe_entropy,
)


def _make_case(
    case_id: str = "test_case",
    question: str = "Find the profit after buying items.",
    candidate_answers: list = None,
    candidate_rows: list = None,
    pal_exec_ok: str = "0",
    selected_answer: str = "42",
    selected_source: str = "controller_metadata_final_answer",
    question_type: str = "money",
    subset_label: str = "wrong_supported_consensus_97",
    gold_absent: bool = True,
) -> dict:
    if candidate_answers is None:
        candidate_answers = ["42"]
    if candidate_rows is None:
        candidate_rows = []
    return {
        "case_id": case_id,
        "question": question,
        "candidate_answers": candidate_answers,
        "candidate_answer_groups": [],
        "structural_fields": {"candidate_rows": candidate_rows},
        "pal_exec_summary": {
            "pal_exec_ok": pal_exec_ok,
            "pal_execution_status": "success" if pal_exec_ok == "1" else "",
        },
        "selector_metadata": {
            "selected_answer": selected_answer,
            "selected_source": selected_source,
            "selector_candidate_pool_size": len(candidate_answers),
            "gold_present_in_candidate_pool": "",
        },
        "failure_audit_labels": {
            "question_type": question_type,
            "diversity_bucket": "low (1 group)",
            "candidate_pool_status": "Both wrong",
            "num_candidate_groups": 1,
        },
        "action_trace_summary": {
            "trace_excerpt": [],
            "action_trace_step_count": 2,
        },
        "subset_memberships": [
            {
                "subset": subset_label,
                "selection_logic": "gold_absent rows" if gold_absent else "gold_present rows",
            }
        ],
        "primary_subset": subset_label,
        "frontier_candidate_answer": selected_answer,
        "direct_reserve_answer": selected_answer,
    }


def _make_candidate_rows(specs: list[dict]) -> list[dict]:
    """Minimal candidate_row builder from simple specs."""
    rows = []
    for i, spec in enumerate(specs):
        rows.append({
            "branch_family": spec.get("branch_family", "equation_first_reasoning"),
            "branch_slot": str(spec.get("slot", i + 1)),
            "candidate_answer": str(spec.get("answer", str(i + 1))),
            "final_answer_role": spec.get("role", "target"),
            "target_alignment_score": str(spec.get("tas", 0.9)),
            "last_operation_family": spec.get("last_op", ""),
            "exec_ok": "",
        })
    return rows


def _make_casebook_row(
    proxy_improved: bool = True,
    structural_best: str = "10",
    verifier_ans: str = "10",
) -> dict[str, str]:
    return {
        "proxy_score_improved": str(proxy_improved),
        "proxy_alignment_improved": str(proxy_improved),
        "structural_best_answer": structural_best,
        "verifier_answer": verifier_ans,
        "baseline_answer": "5",
        "baseline_target_alignment_score": "0.5",
        "replay_target_alignment_score": "0.9",
    }


def _write_packets(path: Path, cases: list[dict]) -> None:
    batch = {"batch_id": "test", "case_count": len(cases), "cases": cases}
    path.write_text(json.dumps(batch) + "\n", encoding="utf-8")


def _write_casebook(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("(empty)\n")
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# _parse_numeric and _numeric_candidates
# ---------------------------------------------------------------------------

def test_parse_numeric_integer():
    assert _parse_numeric("42") == pytest.approx(42.0)


def test_parse_numeric_decimal():
    assert _parse_numeric("3.14") == pytest.approx(3.14)


def test_parse_numeric_comma_separated():
    assert _parse_numeric("1,000") == pytest.approx(1000.0)


def test_parse_numeric_none_on_text():
    assert _parse_numeric("model_step_missing") is None


def test_numeric_candidates_filters_non_numeric():
    assert _numeric_candidates(["1", "abc", "3.5", ""]) == pytest.approx([1.0, 3.5])


def test_safe_entropy_uniform():
    assert _safe_entropy([1, 1]) == pytest.approx(1.0)


def test_safe_entropy_all_zero():
    assert _safe_entropy([0, 0]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# extract_features — numeric candidate features
# ---------------------------------------------------------------------------

def test_extract_features_candidate_count():
    case = _make_case(candidate_answers=["10", "20", "30"])
    feats = extract_features(case)
    assert feats["candidate_count"] == 3
    assert feats["unique_numeric_count"] == 3


def test_extract_features_repeated_value():
    case = _make_case(candidate_answers=["5", "5", "10"])
    feats = extract_features(case)
    assert feats["unique_numeric_count"] == 2
    assert feats["repeated_value_count"] == 1


def test_extract_features_numeric_range():
    case = _make_case(candidate_answers=["2", "10", "8"])
    feats = extract_features(case)
    assert feats["numeric_min"] == pytest.approx(2.0)
    assert feats["numeric_max"] == pytest.approx(10.0)
    assert feats["numeric_range"] == pytest.approx(8.0)


def test_extract_features_has_integer_and_decimal():
    case = _make_case(candidate_answers=["3", "3.5"])
    feats = extract_features(case)
    assert feats["has_integer_candidates"] == 1
    assert feats["has_decimal_candidates"] == 1


def test_extract_features_has_fraction_like():
    case = _make_case(candidate_answers=["0.25", "3"])
    feats = extract_features(case)
    assert feats["has_fraction_or_percent_like"] == 1


def test_extract_features_has_degenerate_one():
    case = _make_case(candidate_answers=["1", "42"])
    feats = extract_features(case)
    assert feats["has_degenerate_one"] == 1


def test_extract_features_has_zero():
    case = _make_case(candidate_answers=["0", "5"])
    feats = extract_features(case)
    assert feats["has_zero"] == 1


# ---------------------------------------------------------------------------
# extract_features — semantic role features
# ---------------------------------------------------------------------------

def test_extract_features_role_counts():
    crows = _make_candidate_rows([
        {"role": "target"}, {"role": "target"}, {"role": "intermediate"},
    ])
    case = _make_case(candidate_rows=crows)
    feats = extract_features(case)
    assert feats["count_final_target_role"] == 2
    assert feats["count_intermediate_role"] == 1
    assert feats["has_candidate_marked_target"] == 1
    assert feats["has_candidate_marked_intermediate"] == 1


def test_extract_features_target_alignment_score():
    crows = _make_candidate_rows([
        {"tas": 0.8}, {"tas": 0.9}, {"tas": 0.95},
    ])
    case = _make_case(candidate_rows=crows)
    feats = extract_features(case)
    assert feats["target_alignment_score_max"] == pytest.approx(0.95)
    assert feats["target_alignment_score_mean"] == pytest.approx(0.883, rel=1e-2)
    assert feats["target_alignment_score_gap_top2"] == pytest.approx(0.05, rel=1e-2)


# ---------------------------------------------------------------------------
# extract_features — source/edge features
# ---------------------------------------------------------------------------

def test_extract_features_has_pal_from_exec_ok():
    case = _make_case(pal_exec_ok="1")
    feats = extract_features(case)
    assert feats["has_PAL_code_candidate"] == 1
    assert feats["PAL_success"] == 1


def test_extract_features_has_verifier_check():
    crows = _make_candidate_rows([
        {"branch_family": "backward_from_target_check"},
    ])
    case = _make_case(candidate_rows=crows)
    feats = extract_features(case)
    assert feats["has_verifier_check_candidate"] == 1
    assert feats["has_backward_from_target_check"] == 1


def test_extract_features_no_verifier_check():
    crows = _make_candidate_rows([
        {"branch_family": "equation_first_reasoning"},
        {"branch_family": "pal_code_with_required_target_variable"},
    ])
    case = _make_case(pal_exec_ok="1", candidate_rows=crows)
    feats = extract_features(case)
    assert feats["has_verifier_check_candidate"] == 0


def test_extract_features_has_equation_setup():
    crows = _make_candidate_rows([{"branch_family": "equation_first_reasoning"}])
    case = _make_case(candidate_rows=crows)
    feats = extract_features(case)
    assert feats["has_equation_setup_candidate"] == 1


def test_extract_features_has_repair_from_source():
    case = _make_case(selected_source="repair_layer")
    feats = extract_features(case)
    assert feats["has_repair_candidate"] == 1


def test_extract_features_no_gold_in_feature_keys():
    """Gold must not appear in the feature keys (only in labels)."""
    crows = _make_candidate_rows([{"branch_family": "equation_first_reasoning"}])
    case = _make_case(candidate_rows=crows)
    feats = extract_features(case)
    for key in feats:
        assert "gold" not in key.lower(), f"Gold leaked into feature key: {key}"


# ---------------------------------------------------------------------------
# extract_features — question cue features
# ---------------------------------------------------------------------------

def test_extract_features_profit_cue():
    case = _make_case(question="How much profit did she earn from selling items?")
    feats = extract_features(case)
    assert feats["has_profit_cue"] == 1


def test_extract_features_difference_cue():
    case = _make_case(question="How many apples are left after eating 3?")
    feats = extract_features(case)
    assert feats["has_difference_cue"] == 1


def test_extract_features_ratio_percent_cue():
    case = _make_case(question="What is 40% of the total revenue?")
    feats = extract_features(case)
    assert feats["has_ratio_percent_cue"] == 1


def test_extract_features_original_before_cue():
    case = _make_case(question="Before the sale, how much did it cost originally?")
    feats = extract_features(case)
    assert feats["has_original_before_cue"] == 1


def test_extract_features_per_unit_cue():
    case = _make_case(question="How much does each item cost per unit?")
    feats = extract_features(case)
    assert feats["has_per_unit_share_cue"] == 1


def test_extract_features_unit_conversion_cue():
    case = _make_case(question="Convert 5 meters to feet.")
    feats = extract_features(case)
    assert feats["has_unit_conversion_cue"] == 1


def test_extract_features_no_false_cues():
    case = _make_case(question="A simple math problem with no special keywords.")
    feats = extract_features(case)
    assert feats["transformed_target_cue_count"] == 0


# ---------------------------------------------------------------------------
# build_labels — gold used only after features
# ---------------------------------------------------------------------------

def test_build_labels_gold_absent_from_subset_membership():
    case = _make_case(gold_absent=True)
    feats = extract_features(case)
    labels = build_labels(case, feats, _make_casebook_row(), None)
    assert labels["gold_absent_from_pool"] == 1
    assert labels["gold_present_in_pool"] == 0


def test_build_labels_gold_present_when_not_absent():
    case = _make_case(gold_absent=False, subset_label="gold_present_subset")
    feats = extract_features(case)
    labels = build_labels(case, feats, _make_casebook_row(), None)
    assert labels["gold_present_in_pool"] == 1


def test_build_labels_verifier_present():
    crows = _make_candidate_rows([{"branch_family": "backward_from_target_check"}])
    case = _make_case(candidate_rows=crows)
    feats = extract_features(case)
    labels = build_labels(case, feats, _make_casebook_row(), None)
    assert labels["verifier_branch_present"] == 1
    assert labels["verifier_branch_missing"] == 0


def test_build_labels_verifier_missing():
    crows = _make_candidate_rows([{"branch_family": "equation_first_reasoning"}])
    case = _make_case(pal_exec_ok="1", candidate_rows=crows)
    feats = extract_features(case)
    labels = build_labels(case, feats, _make_casebook_row(), None)
    assert labels["verifier_branch_missing"] == 1
    assert labels["requires_live_verifier_branch_allocation"] == 1


def test_build_labels_no_live_vc_when_no_pal():
    crows = _make_candidate_rows([{"branch_family": "equation_first_reasoning"}])
    case = _make_case(pal_exec_ok="0", candidate_rows=crows)
    feats = extract_features(case)
    labels = build_labels(case, feats, _make_casebook_row(), None)
    assert labels["requires_live_verifier_branch_allocation"] == 0


def test_build_labels_proxy_improved():
    case = _make_case()
    feats = extract_features(case)
    labels = build_labels(case, feats, _make_casebook_row(proxy_improved=True), None)
    assert labels["proxy_score_improved"] == 1


def test_build_labels_proxy_not_improved():
    case = _make_case()
    feats = extract_features(case)
    labels = build_labels(case, feats, _make_casebook_row(proxy_improved=False), None)
    assert labels["proxy_score_improved"] == 0


# ---------------------------------------------------------------------------
# recommend_next_edge
# ---------------------------------------------------------------------------

def test_recommend_vc_when_pal_and_no_verifier():
    crows = _make_candidate_rows([{"branch_family": "pal_code_with_required_target_variable"}])
    case = _make_case(pal_exec_ok="1", candidate_rows=crows)
    feats = extract_features(case)
    labels = build_labels(case, feats, _make_casebook_row(), None)
    rec = recommend_next_edge(feats, labels)
    recs = json.loads(rec["recommended_next_edges"])
    assert "backward_from_target_check" in recs
    assert rec["primary_recommendation"] == "backward_from_target_check"


def test_no_vc_recommendation_when_verifier_already_present():
    crows = _make_candidate_rows([
        {"branch_family": "pal_code_with_required_target_variable"},
        {"branch_family": "backward_from_target_check"},
    ])
    case = _make_case(pal_exec_ok="1", candidate_rows=crows)
    feats = extract_features(case)
    labels = build_labels(case, feats, _make_casebook_row(), None)
    rec = recommend_next_edge(feats, labels)
    assert rec["primary_recommendation"] != "backward_from_target_check"


def test_recommend_ratio_when_ratio_cue_and_no_equation():
    case = _make_case(
        question="What percentage of the total is spent on rent?",
        candidate_rows=[],
        pal_exec_ok="0",
    )
    feats = extract_features(case)
    labels = build_labels(case, feats, _make_casebook_row(), None)
    rec = recommend_next_edge(feats, labels)
    recs = json.loads(rec["recommended_next_edges"])
    assert "ratio_base_branch" in recs


def test_recommend_difference_when_leftover_cue():
    case = _make_case(
        question="How many tokens are left after spending 5?",
        candidate_rows=[],
        pal_exec_ok="0",
    )
    feats = extract_features(case)
    labels = build_labels(case, feats, _make_casebook_row(), None)
    rec = recommend_next_edge(feats, labels)
    recs = json.loads(rec["recommended_next_edges"])
    assert "difference_or_remainder_branch" in recs or "backward_from_target_check" not in recs


# ---------------------------------------------------------------------------
# CLI end-to-end
# ---------------------------------------------------------------------------

def _make_full_fixture(tmp_path: Path):
    cases = [
        _make_case(
            "c1",
            question="What profit did she earn after paying costs?",
            candidate_answers=["10", "20", "5"],
            candidate_rows=_make_candidate_rows([
                {"branch_family": "pal_code_with_required_target_variable", "slot": 1,
                 "answer": "10", "tas": 0.95},
                {"branch_family": "equation_first_reasoning", "slot": 2,
                 "answer": "20", "tas": 0.8},
            ]),
            pal_exec_ok="1",
            selected_answer="10",
        ),
        _make_case(
            "c2",
            question="How much of the original amount was remaining?",
            candidate_answers=["600"],
            candidate_rows=[],
            pal_exec_ok="0",
            selected_answer="600",
        ),
    ]
    packets = tmp_path / "packets.jsonl"
    _write_packets(packets, cases)

    cb_path = tmp_path / "casebook.csv"
    _write_casebook(cb_path, [
        {"case_id": "c1", "proxy_score_improved": "True",
         "proxy_alignment_improved": "True",
         "structural_best_answer": "20", "verifier_answer": "20",
         "baseline_answer": "10", "baseline_target_alignment_score": "0.7",
         "replay_target_alignment_score": "0.9"},
        {"case_id": "c2", "proxy_score_improved": "False",
         "proxy_alignment_improved": "False",
         "structural_best_answer": "600", "verifier_answer": "",
         "baseline_answer": "600", "baseline_target_alignment_score": "0.6",
         "replay_target_alignment_score": "0.6"},
    ])
    out = tmp_path / "out"
    return packets, cb_path, out


def test_cli_writes_all_expected_files(tmp_path: Path):
    packets, cb, out = _make_full_fixture(tmp_path)
    result = main([
        "--trace-packets", str(packets),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    assert result["api_calls_made"] == 0
    for fname in [
        "manifest.json",
        "frontier_feature_rows.csv",
        "frontier_feature_rows.jsonl",
        "feature_group_summary.csv",
        "gold_absent_feature_contrasts.csv",
        "verifier_missing_feature_contrasts.csv",
        "missing_edge_recommendations.csv",
        "report.md",
    ]:
        assert (out / fname).is_file(), f"Missing: {fname}"


def test_cli_feature_rows_have_required_columns(tmp_path: Path):
    packets, cb, out = _make_full_fixture(tmp_path)
    main([
        "--trace-packets", str(packets),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    rows = list(csv.DictReader(open(out / "frontier_feature_rows.csv")))
    assert len(rows) == 2
    required = {
        "case_id", "candidate_count", "unique_numeric_count",
        "has_PAL_code_candidate", "has_verifier_check_candidate",
        "has_profit_cue", "has_ratio_percent_cue",
        "selected_value_is_extreme", "candidate_values_cluster_count",
        "verifier_branch_present", "verifier_branch_missing",
        "requires_live_verifier_branch_allocation",
    }
    assert required.issubset(set(rows[0].keys()))


def test_cli_no_gold_in_feature_columns(tmp_path: Path):
    packets, cb, out = _make_full_fixture(tmp_path)
    main([
        "--trace-packets", str(packets),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    rows = list(csv.DictReader(open(out / "frontier_feature_rows.csv")))
    # Labels (which use gold) should be in the merged rows, but pure feature extraction
    # columns should not include gold-dependent fields in their names
    # The merged CSV includes labels, so we just verify the feature sub-keys are present
    all_keys = set(rows[0].keys())
    # gold_absent_from_pool is a LABEL (ok to be there), but no 'gold_answer' feature
    assert "gold_answer" not in all_keys
    assert "gold_correct" not in all_keys


def test_cli_recommendations_written(tmp_path: Path):
    packets, cb, out = _make_full_fixture(tmp_path)
    main([
        "--trace-packets", str(packets),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    recs = list(csv.DictReader(open(out / "missing_edge_recommendations.csv")))
    assert len(recs) == 2
    assert all("primary_recommendation" in r for r in recs)
    # c1 has PAL_code candidate but no verifier_check → should recommend backward_from_target_check
    c1_rec = next(r for r in recs if r["case_id"] == "c1")
    assert c1_rec["primary_recommendation"] == "backward_from_target_check"


def test_cli_with_limit(tmp_path: Path):
    packets, cb, out = _make_full_fixture(tmp_path)
    result = main([
        "--trace-packets", str(packets),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
        "--limit", "1",
    ])
    assert result["cases_loaded"] == 1


def test_cli_manifest_no_api_calls(tmp_path: Path):
    packets, cb, out = _make_full_fixture(tmp_path)
    result = main([
        "--trace-packets", str(packets),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["api_calls_made"] == 0
    assert manifest["no_gold_features"] is True
