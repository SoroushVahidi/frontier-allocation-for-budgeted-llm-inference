"""Evaluator layering for Track B vs PAL residual integration (gold-free metadata fixtures)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.output_layer_repair import (
    apply_controller_committed_surfacing_for_evaluation,
    apply_pal_residual_strong_integration_fix,
    canonicalize_answer,
    choose_repair_answer,
    resolve_selected_group_hint_from_metadata,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_98_JSONL = (
    REPO_ROOT
    / "outputs"
    / "cohere_track_b_ab_pilot_30case_20260507T204409Z"
    / "cohere_real_model_cost_normalized_validation_live_run_20260507T204409Z"
    / "per_example_records.jsonl"
)

DATASET = "openai/gsm8k"


def _pal_promotion_like_case98_metadata(*, track_b_override: bool) -> dict:
    """Minimal metadata mirroring pilot Track-B row shape (PAL can promote over incumbent via integration)."""
    pal_overlay: dict = {
        "pal_overlay_applied": False,
        "track_b_gate_override_applied": track_b_override,
    }
    return {
        "final_answer": "57",
        "selected_group": "57",
        "frontier_result": None,
        "frontier_support": 1,
        "frontier_tiebreak_triggered": True,
        "frontier_tiebreak_selected_group": "57",
        "answer_group_support_counts": {"57": 1, "126": 1, "93": 1},
        "pal_overlay": pal_overlay,
        "pal_execution": {
            "pal_candidate_is_strong": 1,
            "pal_exec_ok": 1,
            "pal_parse_ok": 1,
            "pal_safety_ok": 1,
            "pal_candidate_answer": "93",
            "pal_score": 0.9,
        },
    }


def _run_eval_chain(metadata: dict, *, enable_integration: bool = True) -> tuple[dict, dict]:
    hint = resolve_selected_group_hint_from_metadata(metadata, dataset=DATASET) or metadata.get("selected_group")
    repaired = choose_repair_answer(
        final_nodes=[],
        selected_group_hint=hint,
        dataset=DATASET,
        enable_rescue=True,
    )
    repaired = apply_controller_committed_surfacing_for_evaluation(metadata, repaired, dataset=DATASET)
    return apply_pal_residual_strong_integration_fix(
        metadata,
        repaired,
        dataset=DATASET,
        enabled=enable_integration,
    )


def test_track_b_override_skips_residual_integration_and_preserves_commitment() -> None:
    md = _pal_promotion_like_case98_metadata(track_b_override=True)
    out, side = _run_eval_chain(md)
    assert out["surfaced_final_answer_raw"] == "57"
    assert side["pal_integration_fix_reason"] == "skipped_track_b_gate_override_applied"
    assert side["pal_integration_skipped_reason"] == "track_b_gate_override_applied"
    assert side["pal_integration_fix_triggered"] is False


def test_without_track_b_override_residual_integration_unchanged_promotes_pal() -> None:
    md = _pal_promotion_like_case98_metadata(track_b_override=False)
    out, side = _run_eval_chain(md)
    assert side["pal_integration_fix_triggered"] is True
    assert out["surfaced_final_answer_raw"] == "93"
    assert side["pal_integration_selected_answer"] == "93"
    assert out["final_answer_source"] == "pal_residual_strong_integration_fix"


def test_pal_overlay_applied_at_controller_still_skips_integration_first() -> None:
    md = _pal_promotion_like_case98_metadata(track_b_override=True)
    md["pal_overlay"]["pal_overlay_applied"] = True
    md["pal_overlay"]["track_b_gate_override_applied"] = False
    out, side = _run_eval_chain(md)
    assert side["pal_integration_fix_reason"] == "skipped_pal_overlay_already_applied"
    assert "pal_integration_skipped_reason" not in side or side.get("pal_integration_skipped_reason") in (
        None,
        "",
    )


def test_track_b_skip_records_reason_in_sidecar() -> None:
    md = _pal_promotion_like_case98_metadata(track_b_override=True)
    _, side = _run_eval_chain(md)
    assert side.get("pal_integration_skipped_reason") == "track_b_gate_override_applied"


@pytest.mark.skipif(not CASE_98_JSONL.is_file(), reason="archived pilot JSONL not present")
def test_archived_openai_gsm8k_98_respects_controller_commit_under_fixed_evaluator() -> None:
    row = None
    target_method = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_track_b_commitment_v1"
    for line in CASE_98_JSONL.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("example_id") == "openai_gsm8k_98" and rec.get("method") == target_method:
            row = rec
            break
    assert row is not None
    md = dict(row.get("result_metadata") or {})
    hint = resolve_selected_group_hint_from_metadata(md, dataset=DATASET) or md.get("selected_group")
    repaired = choose_repair_answer(
        final_nodes=list(row.get("final_nodes") or []),
        selected_group_hint=hint,
        dataset=DATASET,
        enable_rescue=True,
    )
    repaired = apply_controller_committed_surfacing_for_evaluation(md, repaired, dataset=DATASET)
    out, side = apply_pal_residual_strong_integration_fix(
        md,
        repaired,
        dataset=DATASET,
        enabled=True,
    )
    ctrl = str(md.get("final_answer") or "").strip()
    gold = str(row.get("gold_answer") or "").strip()
    assert side["pal_integration_fix_reason"] == "skipped_track_b_gate_override_applied"
    assert out["surfaced_final_answer_raw"] == ctrl == "57"
    # Honest accounting vs gold (75): commitment stays wrong; previously scored 93 via integration (also wrong).
    gold_can = canonicalize_answer(gold, dataset=DATASET)
    surf_can = canonicalize_answer(out["surfaced_final_answer_raw"], dataset=DATASET)
    assert gold_can is not None and surf_can is not None
    assert surf_can != gold_can

