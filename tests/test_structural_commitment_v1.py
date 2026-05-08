"""Structural commitment v1 — gold-free extensions on Track B (fixtures only)."""

from __future__ import annotations

import inspect

import pytest

from experiments.controllers import DirectReserveFrontierGateController
from experiments.output_layer_repair import decide_structural_commitment_v1, decide_track_b_overlay_commitment_gate

from tests.test_track_b_overlay_commitment_gate import (
    _counts_from_fixture,
    _load,
    _pal_flat_from_fixture,
    _tb_meta_from_fixture,
)


def test_structural_commit_signature_has_no_gold_parameters() -> None:
    sig = inspect.signature(decide_structural_commitment_v1)
    assert "gold" not in str(sig).lower()


def test_controller_structural_defaults_disabled() -> None:
    sig = inspect.signature(DirectReserveFrontierGateController.__init__)
    assert sig.parameters["enable_structural_commitment_v1"].default is False


def test_structural_matches_track_b_on_fixture_anchors() -> None:
    for case_id in ("openai_gsm8k_1087", "openai_gsm8k_1279"):
        row = _load(case_id)
        ov = dict(row.get("overlay_tiebreak_summary") or {})
        tb = decide_track_b_overlay_commitment_gate(
            combined_group_counts_base=_counts_from_fixture(row),
            tiebreak_meta=_tb_meta_from_fixture(row),
            pal_execution_flat=_pal_flat_from_fixture(row),
            overlay_tiebreak_summary=ov,
        )
        st = decide_structural_commitment_v1(
            combined_group_counts_base=_counts_from_fixture(row),
            tiebreak_meta=_tb_meta_from_fixture(row),
            pal_execution_flat=_pal_flat_from_fixture(row),
            overlay_tiebreak_summary=ov,
            direct_reserve_answer_raw=str(row.get("direct_reserve_answer") or "").strip() or None,
        )
        assert tb["should_override"] is True
        assert st["should_override"] is tb["should_override"]
        assert st["reason"] == tb["reason"]
        assert st["commitment_policy_layer"] == "track_b"


@pytest.mark.parametrize(
    "case_id,expect_override",
    [
        ("openai_gsm8k_1083", False),
        ("openai_gsm8k_1085", False),
        ("openai_gsm8k_1087", True),
        ("openai_gsm8k_1095", False),
        ("openai_gsm8k_1124", True),
        ("openai_gsm8k_1279", True),
    ],
)
def test_structural_fixture_roundtrip(case_id: str, expect_override: bool) -> None:
    row = _load(case_id)
    ov = dict(row.get("overlay_tiebreak_summary") or {})
    st = decide_structural_commitment_v1(
        combined_group_counts_base=_counts_from_fixture(row),
        tiebreak_meta=_tb_meta_from_fixture(row),
        pal_execution_flat=_pal_flat_from_fixture(row),
        overlay_tiebreak_summary=ov,
        direct_reserve_answer_raw=str(row.get("direct_reserve_answer") or "").strip() or None,
    )
    assert st["should_override"] is expect_override


def test_fixture_1124_dr_equal_histogram_realign() -> None:
    row = _load("openai_gsm8k_1124")
    ov = dict(row.get("overlay_tiebreak_summary") or {})
    tb = decide_track_b_overlay_commitment_gate(
        combined_group_counts_base=_counts_from_fixture(row),
        tiebreak_meta=_tb_meta_from_fixture(row),
        pal_execution_flat=_pal_flat_from_fixture(row),
        overlay_tiebreak_summary=ov,
    )
    assert tb["should_override"] is False
    assert tb["abstain_reason"] == "pal_stdout_already_matches_tiebreak_group"

    st = decide_structural_commitment_v1(
        combined_group_counts_base=_counts_from_fixture(row),
        tiebreak_meta=_tb_meta_from_fixture(row),
        pal_execution_flat=_pal_flat_from_fixture(row),
        overlay_tiebreak_summary=ov,
        direct_reserve_answer_raw=str(row.get("direct_reserve_answer") or "").strip(),
    )
    assert st["should_override"] is True
    assert st["commitment_policy_layer"] == "structural_frontier_realign_dr"
    assert st["recommended_answer"] == "45"


def test_rule_b_abstains_when_direct_reserve_missing() -> None:
    row = _load("openai_gsm8k_1124")
    ov = dict(row.get("overlay_tiebreak_summary") or {})
    st = decide_structural_commitment_v1(
        combined_group_counts_base=_counts_from_fixture(row),
        tiebreak_meta=_tb_meta_from_fixture(row),
        pal_execution_flat=_pal_flat_from_fixture(row),
        overlay_tiebreak_summary=ov,
        direct_reserve_answer_raw=None,
    )
    assert st["should_override"] is False
    assert st["commitment_policy_layer"] in ("none", "")


def test_rule_a_abstains_uniform_multigroup_tie_stdout_off_histogram() -> None:
    st = decide_structural_commitment_v1(
        combined_group_counts_base={"4": 1, "2": 1, "2.5": 1},
        tiebreak_meta={
            "frontier_tiebreak_triggered": False,
            "frontier_tiebreak_selected_group": "",
            "frontier_tiebreak_previous_group": "",
            "frontier_tiebreak_reason": "replay",
        },
        pal_execution_flat={"pal_candidate_answer": "5", "pal_json_answer": "2"},
        overlay_tiebreak_summary={"pal_overlay_previous_answer": "2"},
        direct_reserve_answer_raw=None,
    )
    assert st["should_override"] is False
    assert st["reason"] == "abstain_structural_A_uniform_multigroup_tie_stdout_off_histogram"


def test_offline_shape_1290_structural_still_track_b_override() -> None:
    st = decide_structural_commitment_v1(
        combined_group_counts_base={"6600": 1, "6400": 1},
        tiebreak_meta={
            "frontier_tiebreak_triggered": True,
            "frontier_tiebreak_selected_group": "6600",
            "frontier_tiebreak_previous_group": "",
            "frontier_tiebreak_reason": "replay",
        },
        pal_execution_flat={"pal_candidate_answer": "2200", "pal_json_answer": "6600"},
        overlay_tiebreak_summary={"pal_overlay_previous_answer": "6600"},
        direct_reserve_answer_raw="9999",
    )
    assert st["should_override"] is True
    assert st["commitment_policy_layer"] == "track_b"
