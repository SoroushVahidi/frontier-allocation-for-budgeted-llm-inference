"""Unit tests for Track B overlay/commitment gate (gold-free; uses fixtures only)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from experiments.controllers import DirectReserveFrontierGateController
from experiments.output_layer_repair import decide_track_b_overlay_commitment_gate

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "present_not_selected_replay"


def _load(case_id: str) -> dict:
    p = FIXTURE_DIR / f"{case_id}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _tb_meta_from_fixture(row: dict) -> dict:
    ots = row.get("overlay_tiebreak_summary") or {}
    return {
        "frontier_tiebreak_triggered": bool(ots.get("frontier_tiebreak_triggered")),
        "frontier_tiebreak_selected_group": str(ots.get("frontier_tiebreak_selected_group") or ""),
        "frontier_tiebreak_previous_group": "",
        "frontier_tiebreak_reason": "fixture",
    }


def _pal_flat_from_fixture(row: dict) -> dict:
    px = row.get("pal_execution_summary") or {}
    return {
        "pal_candidate_answer": str(px.get("pal_candidate_answer") or ""),
        "pal_json_answer": str(px.get("pal_json_answer") or ""),
    }


def _counts_from_fixture(row: dict) -> dict:
    return dict(row.get("answer_group_histogram") or {})


def test_gate_signature_has_no_gold_parameters() -> None:
    sig = inspect.signature(decide_track_b_overlay_commitment_gate)
    assert "gold" not in str(sig).lower()
    assert "exact_match" not in str(sig).lower()


def test_direct_reserve_frontier_gate_controller_track_b_defaults_disabled() -> None:
    sig = inspect.signature(DirectReserveFrontierGateController.__init__)
    assert sig.parameters["enable_track_b_overlay_commitment_gate"].default is False


def test_fixture_1087_overlay_positive_override() -> None:
    row = _load("openai_gsm8k_1087")
    out = decide_track_b_overlay_commitment_gate(
        combined_group_counts_base=_counts_from_fixture(row),
        tiebreak_meta=_tb_meta_from_fixture(row),
        pal_execution_flat=_pal_flat_from_fixture(row),
        overlay_tiebreak_summary=dict(row.get("overlay_tiebreak_summary") or {}),
    )
    assert out["should_override"] is True
    assert out["recommended_answer"] == "6"
    assert out["reason"].startswith("override_")


def test_fixture_1279_overlay_positive_override() -> None:
    row = _load("openai_gsm8k_1279")
    out = decide_track_b_overlay_commitment_gate(
        combined_group_counts_base=_counts_from_fixture(row),
        tiebreak_meta=_tb_meta_from_fixture(row),
        pal_execution_flat=_pal_flat_from_fixture(row),
        overlay_tiebreak_summary=dict(row.get("overlay_tiebreak_summary") or {}),
    )
    assert out["should_override"] is True
    assert out["recommended_answer"] == "24"


def test_fixture_1083_histogram_skew_abstains_no_tiebreak() -> None:
    """Naive max-support would hit wrong mass; gate abstains without tie-break trigger."""
    row = _load("openai_gsm8k_1083")
    out = decide_track_b_overlay_commitment_gate(
        combined_group_counts_base=_counts_from_fixture(row),
        tiebreak_meta=_tb_meta_from_fixture(row),
        pal_execution_flat=_pal_flat_from_fixture(row),
        overlay_tiebreak_summary=dict(row.get("overlay_tiebreak_summary") or {}),
    )
    assert out["should_override"] is False
    assert out["abstain_reason"] == "tiebreak_not_triggered"


def test_fixture_1124_abstains_no_stdout_conflict_dr_peer_case() -> None:
    """Tie-break/PAL stdout agree on peer — gate must not invent DR-heavy finals."""
    row = _load("openai_gsm8k_1124")
    out = decide_track_b_overlay_commitment_gate(
        combined_group_counts_base=_counts_from_fixture(row),
        tiebreak_meta=_tb_meta_from_fixture(row),
        pal_execution_flat=_pal_flat_from_fixture(row),
        overlay_tiebreak_summary=dict(row.get("overlay_tiebreak_summary") or {}),
    )
    assert out["should_override"] is False
    assert out["abstain_reason"] == "pal_stdout_already_matches_tiebreak_group"


def test_fixture_1095_abstains_missing_executable_stdout() -> None:
    """PAL exec-only / empty stdout cannot drive commitment override."""
    row = _load("openai_gsm8k_1095")
    out = decide_track_b_overlay_commitment_gate(
        combined_group_counts_base=_counts_from_fixture(row),
        tiebreak_meta=_tb_meta_from_fixture(row),
        pal_execution_flat=_pal_flat_from_fixture(row),
        overlay_tiebreak_summary=dict(row.get("overlay_tiebreak_summary") or {}),
    )
    assert out["should_override"] is False
    assert out["abstain_reason"] == "missing_or_unknown_pal_executable_stdout_group"


def test_gate_has_no_histogram_argmax_logic() -> None:
    src = inspect.getsource(decide_track_b_overlay_commitment_gate)
    assert "max(" not in src
    assert "argmax" not in src.lower()


def test_empty_tiebreak_abstains() -> None:
    out = decide_track_b_overlay_commitment_gate(
        combined_group_counts_base={"6": 1},
        tiebreak_meta={},
        pal_execution_flat={"pal_candidate_answer": "-66", "pal_json_answer": "12"},
        overlay_tiebreak_summary=None,
    )
    assert out["should_override"] is False


def test_offline_replay_shape_triple_tie_stdout_off_histogram_abstains_overlay() -> None:
    """Harm cases 1299 / 1307 / 1291: uniform ≥3-way tie + PAL stdout not on histogram."""
    out = decide_track_b_overlay_commitment_gate(
        combined_group_counts_base={"4": 1, "2": 1, "2.5": 1},
        tiebreak_meta={
            "frontier_tiebreak_triggered": True,
            "frontier_tiebreak_selected_group": "2",
            "frontier_tiebreak_previous_group": "",
            "frontier_tiebreak_reason": "replay",
        },
        pal_execution_flat={"pal_candidate_answer": "5", "pal_json_answer": "5"},
        overlay_tiebreak_summary={"pal_overlay_previous_answer": "2"},
    )
    assert out["should_override"] is False
    assert out["reason"] == "abstain_overlay_ambiguous_multipeer_tie_stdout_off_histogram"


def test_offline_replay_shape_1290_two_way_tie_pal_json_override_still_works() -> None:
    """Fix case 1290: two-peer histogram — overlay allowed; pal_json also agrees with tb."""
    out = decide_track_b_overlay_commitment_gate(
        combined_group_counts_base={"6600": 1, "6400": 1},
        tiebreak_meta={
            "frontier_tiebreak_triggered": True,
            "frontier_tiebreak_selected_group": "6600",
            "frontier_tiebreak_previous_group": "",
            "frontier_tiebreak_reason": "replay",
        },
        pal_execution_flat={"pal_candidate_answer": "2200", "pal_json_answer": "6600"},
        overlay_tiebreak_summary={"pal_overlay_previous_answer": "6600"},
    )
    assert out["should_override"] is True
    assert out["recommended_normalized_group"] == "6600"


def test_offline_replay_shape_triple_tie_stdout_on_manifold_overrides_like_1279() -> None:
    """Fix case 1279: triple tie but executable stdout maps to a histogram peer (mass ≥1)."""
    out = decide_track_b_overlay_commitment_gate(
        combined_group_counts_base={"24": 1, "30": 1, "12": 1},
        tiebreak_meta={
            "frontier_tiebreak_triggered": True,
            "frontier_tiebreak_selected_group": "24",
            "frontier_tiebreak_previous_group": "",
            "frontier_tiebreak_reason": "replay",
        },
        pal_execution_flat={"pal_candidate_answer": "30", "pal_json_answer": "34"},
        overlay_tiebreak_summary={"pal_overlay_previous_answer": "24"},
    )
    assert out["should_override"] is True
    assert out["recommended_answer"] == "24"


@pytest.mark.parametrize(
    "case_id,expect_override",
    [
        ("openai_gsm8k_1083", False),
        ("openai_gsm8k_1085", False),
        ("openai_gsm8k_1087", True),
        ("openai_gsm8k_1095", False),
        ("openai_gsm8k_1124", False),
        ("openai_gsm8k_1279", True),
    ],
)
def test_all_six_fixture_roundtrip(case_id: str, expect_override: bool) -> None:
    row = _load(case_id)
    out = decide_track_b_overlay_commitment_gate(
        combined_group_counts_base=_counts_from_fixture(row),
        tiebreak_meta=_tb_meta_from_fixture(row),
        pal_execution_flat=_pal_flat_from_fixture(row),
        overlay_tiebreak_summary=dict(row.get("overlay_tiebreak_summary") or {}),
    )
    assert out["should_override"] is expect_override
