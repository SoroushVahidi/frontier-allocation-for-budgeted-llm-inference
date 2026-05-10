from __future__ import annotations

from collections import Counter
import math
from typing import Any

from experiments.data import extract_final_answer, normalize_answer_text
from experiments.frontier_max_support_tiebreak import (
    build_merged_support_histogram_for_tiebreak,
    normalize_answer_group_key,
    pick_answer_text_for_normalized_group,
    resolve_frontier_bias_max_support_tiebreak,
)


def canonicalize_answer(answer_raw: str | None, *, dataset: str) -> str | None:
    """Dataset-safe canonicalization for exact-answer math datasets.

    Keeps logic deterministic and conservative: use shared normalization first,
    then apply small post-normalization numeric cleanup.
    """
    if answer_raw is None:
        return None
    norm = normalize_answer_text(str(answer_raw))
    cand = norm.get("normalized_answer")
    if cand is None:
        return None
    out = str(cand).strip()
    if not out:
        return None

    # Keep AIME answer semantics numeric but normalization-safe (e.g., 055 -> 55).
    if dataset.lower() in {"huggingfaceh4/aime_2024", "aime", "aime_2024"}:
        try:
            return str(int(float(out)))
        except ValueError:
            return out

    # For standard exact numeric datasets, normalize integer-like decimals.
    try:
        f = float(out)
        if f.is_integer():
            return str(int(f))
        return f"{f:.10g}"
    except ValueError:
        return out


def _to_text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


# Histogram mass from non-PAL peers at or above these thresholds blocks PAL takeover.
PAL_STRONG_OVERLAY_PEER_SUPPORT_CONFLICT_MIN = 3
PAL_STRONG_OVERLAY_TIEBREAK_PEER_SUPPORT_CONFLICT_MIN = 2


def _max_histogram_support_excluding_normalized_group(
    combined_group_counts: dict[str, Any], *, normalized_group_key: str
) -> tuple[int, str | None]:
    """Largest integer count among keys whose normalized key differs from ``normalized_group``."""
    best = 0
    best_raw: str | None = None
    if not isinstance(combined_group_counts, dict):
        return 0, None
    for k, v in combined_group_counts.items():
        ks_raw = str(k).strip()
        if not ks_raw or ks_raw == "__unknown__":
            continue
        kn = normalize_answer_group_key(ks_raw)
        if not kn or kn == "__unknown__" or kn == normalized_group_key:
            continue
        try:
            c = int(v or 0)
        except Exception:
            c = 0
        if c > best:
            best, best_raw = c, ks_raw
    return best, best_raw


def _support_for_normalized_histogram_key(combined_group_counts: dict[str, Any], normalized_group_key: str) -> int:
    """Sum counts for histogram keys compatible with normalized ``normalized_group_key``."""
    total = 0
    if not isinstance(combined_group_counts, dict):
        return 0
    for k, v in combined_group_counts.items():
        ks_raw = str(k).strip()
        if not ks_raw:
            continue
        if normalize_answer_group_key(ks_raw) != normalized_group_key:
            continue
        try:
            total += int(v or 0)
        except Exception:
            continue
    return total


def _tiebreak_histogram_support(combined_group_counts: dict[str, Any], tiebreak_selected_raw: str | None) -> int:
    if not tiebreak_selected_raw:
        return 0
    tb = normalize_answer_group_key(str(tiebreak_selected_raw).strip())
    if not tb or tb == "__unknown__":
        return 0
    return _support_for_normalized_histogram_key(combined_group_counts, tb)


def _histogram_counts_by_normalized_group(combined_group_counts: dict[str, Any]) -> dict[str, int]:
    """Merge raw histogram keys onto normalized answer-group keys (same bucketing as tie-break)."""
    out: dict[str, int] = {}
    if not isinstance(combined_group_counts, dict):
        return out
    for k, v in combined_group_counts.items():
        ks_raw = str(k).strip()
        if not ks_raw or ks_raw == "__unknown__":
            continue
        kn = normalize_answer_group_key(ks_raw)
        if not kn or kn == "__unknown__":
            continue
        try:
            c = int(v or 0)
        except Exception:
            c = 0
        out[kn] = out.get(kn, 0) + c
    return out


def _uniform_full_multigroup_tie(counts_by_norm: dict[str, int], *, min_groups: int = 3) -> bool:
    """True when every normalized bucket has the same positive mass and there are at least ``min_groups`` buckets.

    Detects maximal ambiguity (e.g. 3+ answers each with identical support) without picking a global argmax.
    """
    if len(counts_by_norm) < min_groups:
        return False
    vals = list(counts_by_norm.values())
    if not vals:
        return False
    first = vals[0]
    if first <= 0:
        return False
    for x in vals[1:]:
        if x != first:
            return False
    return True


def decide_track_b_overlay_commitment_gate(
    *,
    combined_group_counts_base: dict[str, Any],
    tiebreak_meta: dict[str, Any],
    pal_execution_flat: dict[str, Any],
    overlay_tiebreak_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Narrow gold-free commitment gate for Track B (overlay / tie-break vs PAL stdout).

    Pure function: no API, no filesystem, no mutation of inputs. Decides whether to
    replace the surfaced PAL executable channel with the tie-break / overlay-consistent
    numeric when **narrow structural preconditions** hold.

    This is **not** global histogram maximum-support selection, not DR-finalization, and not PAL-exec-only priority.

    Returns a structured dict:
      - ``should_override``: whether caller should replace ``final_answer``
      - ``recommended_answer``: literal answer text when inferable without gold (else ``None``)
      - ``recommended_normalized_group``: normalized bucket key for ``pick_answer_text_for_normalized_group``
      - ``recommended_source``: short tag for telemetry
      - ``reason``: primary outcome tag
      - ``signals_used``: list of signal keys consulted
      - ``abstain_reason``: non-empty when ``should_override`` is False
    """
    signals_used: list[str] = []
    abstain_reason = ""

    def _out(
        *,
        should_override: bool,
        recommended_answer: str | None,
        recommended_normalized_group: str | None,
        recommended_source: str,
        reason: str,
        abstain: str | None,
    ) -> dict[str, Any]:
        return {
            "should_override": bool(should_override),
            "recommended_answer": recommended_answer,
            "recommended_normalized_group": recommended_normalized_group,
            "recommended_source": str(recommended_source),
            "reason": str(reason),
            "signals_used": list(signals_used),
            "abstain_reason": abstain or "",
        }

    if not isinstance(tiebreak_meta, dict):
        return _out(
            should_override=False,
            recommended_answer=None,
            recommended_normalized_group=None,
            recommended_source="none",
            reason="abstain_invalid_tiebreak_meta",
            abstain="invalid_tiebreak_meta",
        )

    if not bool(tiebreak_meta.get("frontier_tiebreak_triggered")):
        signals_used.append("frontier_tiebreak_triggered=false")
        return _out(
            should_override=False,
            recommended_answer=None,
            recommended_normalized_group=None,
            recommended_source="none",
            reason="abstain_no_tiebreak",
            abstain="tiebreak_not_triggered",
        )

    tb_raw = _to_text(tiebreak_meta.get("frontier_tiebreak_selected_group"))
    if not tb_raw:
        signals_used.append("missing_frontier_tiebreak_selected_group")
        return _out(
            should_override=False,
            recommended_answer=None,
            recommended_normalized_group=None,
            recommended_source="none",
            reason="abstain_missing_tiebreak_group",
            abstain="missing_tiebreak_selected_group",
        )

    tb_n = normalize_answer_group_key(str(tb_raw).strip())
    signals_used.append("frontier_tiebreak_selected_group")
    if not tb_n or tb_n == "__unknown__":
        return _out(
            should_override=False,
            recommended_answer=None,
            recommended_normalized_group=None,
            recommended_source="none",
            reason="abstain_bad_normalized_tiebreak_group",
            abstain="tiebreak_group_normalizes_empty",
        )

    px = pal_execution_flat if isinstance(pal_execution_flat, dict) else {}
    pal_out = _to_text(px.get("pal_candidate_answer"))
    pal_out_n = normalize_answer_group_key(str(pal_out).strip()) if pal_out else ""
    signals_used.append("pal_candidate_answer")
    pal_json_raw = _to_text(px.get("pal_json_answer"))
    pal_json_n = normalize_answer_group_key(str(pal_json_raw).strip()) if pal_json_raw else ""
    if pal_json_raw:
        signals_used.append("pal_json_answer")

    sup_tb = _support_for_normalized_histogram_key(
        combined_group_counts_base if isinstance(combined_group_counts_base, dict) else {},
        tb_n,
    )
    signals_used.append("histogram_support_for_tiebreak_group")

    if sup_tb < 1:
        abstain_reason = "insufficient_histogram_support_for_tiebreak_group"
        return _out(
            should_override=False,
            recommended_answer=None,
            recommended_normalized_group=tb_n,
            recommended_source="none",
            reason="abstain_low_support",
            abstain=abstain_reason,
        )

    if not pal_out_n or pal_out_n == "__unknown__":
        abstain_reason = "missing_or_unknown_pal_executable_stdout_group"
        return _out(
            should_override=False,
            recommended_answer=None,
            recommended_normalized_group=tb_n,
            recommended_source="none",
            reason="abstain_missing_pal_stdout_group",
            abstain=abstain_reason,
        )

    if pal_out_n == tb_n:
        abstain_reason = "pal_stdout_already_matches_tiebreak_group"
        return _out(
            should_override=False,
            recommended_answer=None,
            recommended_normalized_group=tb_n,
            recommended_source="none",
            reason="abstain_stdout_aligned",
            abstain=abstain_reason,
        )

    # --- Overlay-summary alignment (compact replay snapshots; no gold) ---
    if isinstance(overlay_tiebreak_summary, dict):
        op_prev = _to_text(overlay_tiebreak_summary.get("pal_overlay_previous_answer"))
        if op_prev:
            signals_used.append("overlay_pal_overlay_previous_answer")
            op_n = normalize_answer_group_key(str(op_prev).strip())
            if op_n and op_n != "__unknown__" and op_n == tb_n:
                combined_norm = _histogram_counts_by_normalized_group(
                    combined_group_counts_base if isinstance(combined_group_counts_base, dict) else {}
                )
                uniform_high_ambiguity = _uniform_full_multigroup_tie(combined_norm, min_groups=3)
                sup_pal_stdout = _support_for_normalized_histogram_key(
                    combined_group_counts_base if isinstance(combined_group_counts_base, dict) else {},
                    pal_out_n,
                )
                signals_used.append("histogram_uniform_multigroup_tie")
                signals_used.append("pal_stdout_histogram_mass")
                # Triple (or more) full ties among peers + executable stdout off the merged histogram
                # are too ambiguous for overlay-only commitment (offline replay showed systematic harm).
                # Keep overlay when PAL stdout still lands on an on-manifold peer (competitive branch mass).
                if uniform_high_ambiguity and sup_pal_stdout < 1:
                    return _out(
                        should_override=False,
                        recommended_answer=None,
                        recommended_normalized_group=tb_n,
                        recommended_source="none",
                        reason="abstain_overlay_ambiguous_multipeer_tie_stdout_off_histogram",
                        abstain="uniform_multigroup_tie_and_pal_stdout_off_manifold",
                    )

                # --- NEW: Strong PAL / Equal Support Guard ---
                # If PAL is strong or has equal/higher support than the tie-break group,
                # do not override with the overlay.
                is_strong_pal = bool(px.get("pal_candidate_is_strong"))
                if is_strong_pal and sup_pal_stdout >= 1:
                    return _out(
                        should_override=False,
                        recommended_answer=None,
                        recommended_normalized_group=tb_n,
                        recommended_source="none",
                        reason="abstain_overlay_vs_strong_supported_pal",
                        abstain="strong_pal_with_histogram_support",
                    )

                if sup_pal_stdout >= sup_tb:
                    return _out(
                        should_override=False,
                        recommended_answer=None,
                        recommended_normalized_group=tb_n,
                        recommended_source="none",
                        reason="abstain_overlay_vs_equal_support_pal",
                        abstain="pal_stdout_has_equal_or_higher_support_than_tiebreak",
                    )

                return _out(
                    should_override=True,
                    recommended_answer=str(op_prev).strip(),
                    recommended_normalized_group=tb_n,
                    recommended_source="overlay_prior_matches_tiebreak",
                    reason="override_overlay_prior_matches_tiebreak_conflicts_with_pal_stdout",
                    abstain=None,
                )

    # --- PAL JSON aligns with tie-break selection but executable stdout differs ---
    if pal_json_n and pal_json_n != "__unknown__" and pal_json_n == tb_n and pal_out_n != tb_n:
        signals_used.append("pal_json_aligns_with_tiebreak")
        return _out(
            should_override=True,
            recommended_answer=None,
            recommended_normalized_group=tb_n,
            recommended_source="pal_json_agrees_with_tiebreak",
            reason="override_pal_json_matches_tiebreak_conflicts_with_stdout",
            abstain=None,
        )

    abstain_reason = "no_track_b_alignment_channel_met"
    return _out(
        should_override=False,
        recommended_answer=None,
        recommended_normalized_group=tb_n,
        recommended_source="none",
        reason="abstain_no_alignment",
        abstain=abstain_reason,
    )


def decide_structural_commitment_v1(
    *,
    combined_group_counts_base: dict[str, Any],
    tiebreak_meta: dict[str, Any],
    pal_execution_flat: dict[str, Any],
    overlay_tiebreak_summary: dict[str, Any] | None = None,
    direct_reserve_answer_raw: str | None = None,
) -> dict[str, Any]:
    """Conservative structural commitment (v1) extending Track B without gold.

    Runs :func:`decide_track_b_overlay_commitment_gate` first. If it overrides, returns that
    decision with ``commitment_policy_layer=\"track_b\"``.

    Otherwise applies **narrow** offline-validated extensions:

    - **Rule A (overlay, no frontier tie-break):** when tie-break did not fire, overlay prior
      disagrees with executable stdout, **PAL JSON or normalized DR matches the overlay bucket**,
      and the merged histogram has **at least two supported peers** and overlay mass is not beaten by
      a competing normalized bucket — allow override to overlay text. Uniform ≥3-way ties with stdout
      off-manifold still abstain (Track B-style).
    - **Rule B (DR realign, histogram tie only):** when Track B abstained because PAL stdout
      already matched the tie-break bucket, but direct-reserve final differs and shares **exact**
      histogram mass with the tie-break bucket — prefer the direct-reserve answer (trusted DR leaf).

    Abstains on uniform multigroup ambiguity (mirrors Track B) and when metadata is incomplete.
    """
    tb = decide_track_b_overlay_commitment_gate(
        combined_group_counts_base=combined_group_counts_base,
        tiebreak_meta=tiebreak_meta,
        pal_execution_flat=pal_execution_flat,
        overlay_tiebreak_summary=overlay_tiebreak_summary,
    )
    out = dict(tb)
    out["commitment_policy_layer"] = "track_b" if tb.get("should_override") else "none"
    if tb.get("should_override"):
        return out

    if not isinstance(tiebreak_meta, dict):
        return out

    combined = combined_group_counts_base if isinstance(combined_group_counts_base, dict) else {}
    px = pal_execution_flat if isinstance(pal_execution_flat, dict) else {}
    pal_out = _to_text(px.get("pal_candidate_answer"))
    if not pal_out and isinstance(px.get("pal_execution_result"), dict):
        er = px.get("pal_execution_result")
        if isinstance(er, dict):
            pal_out = _to_text(er.get("pal_answer_normalized") or er.get("pal_answer_raw"))
    pal_out_n = normalize_answer_group_key(str(pal_out).strip()) if pal_out else ""

    ov = overlay_tiebreak_summary if isinstance(overlay_tiebreak_summary, dict) else {}
    op_prev = _to_text(ov.get("pal_overlay_previous_answer"))

    pal_json_raw = _to_text(px.get("pal_json_answer"))
    pal_json_n = normalize_answer_group_key(str(pal_json_raw).strip()) if pal_json_raw else ""
    dr_gate = _to_text(direct_reserve_answer_raw)
    dr_n_gate = normalize_answer_group_key(str(dr_gate).strip()) if dr_gate else ""

    # ----- Rule A: overlay prior vs executable stdout (no tie-break) -----
    if (
        not bool(tiebreak_meta.get("frontier_tiebreak_triggered"))
        and op_prev
        and pal_out_n
        and pal_out_n != "__unknown__"
    ):
        op_n = normalize_answer_group_key(str(op_prev).strip())
        if op_n and op_n != "__unknown__" and op_n != pal_out_n:
            combined_norm_pre = _histogram_counts_by_normalized_group(combined)
            if sum(1 for c in combined_norm_pre.values() if int(c) > 0) < 2:
                pass
            else:
                trusted_overlay = (
                    (pal_json_n and pal_json_n != "__unknown__" and pal_json_n == op_n)
                    or (dr_n_gate and dr_n_gate != "__unknown__" and dr_n_gate == op_n)
                )
                if trusted_overlay:
                    sup_op = _support_for_normalized_histogram_key(combined, op_n)
                    if sup_op >= 1:
                        max_peer, _peer_raw = _max_histogram_support_excluding_normalized_group(
                            combined, normalized_group_key=op_n
                        )
                        if sup_op >= int(max_peer):
                            combined_norm = _histogram_counts_by_normalized_group(combined)
                            uniform_high_ambiguity = _uniform_full_multigroup_tie(combined_norm, min_groups=3)
                            sup_pal_stdout = _support_for_normalized_histogram_key(combined, pal_out_n)
                            if uniform_high_ambiguity and sup_pal_stdout < 1:
                                out.update(
                                    {
                                        "should_override": False,
                                        "commitment_policy_layer": "none",
                                        "reason": "abstain_structural_A_uniform_multigroup_tie_stdout_off_histogram",
                                        "abstain_reason": "structural_v1_rule_a_ambiguous_uniform_tie",
                                        "recommended_answer": None,
                                        "recommended_normalized_group": None,
                                        "recommended_source": "none",
                                    }
                                )
                                return out
                            out.update(
                                {
                                    "should_override": True,
                                    "recommended_answer": str(op_prev).strip(),
                                    "recommended_normalized_group": op_n,
                                    "recommended_source": "structural_v1_overlay_no_tiebreak",
                                    "reason": "override_structural_v1_overlay_prior_vs_executable_stdout",
                                    "abstain_reason": "",
                                    "commitment_policy_layer": "structural_overlay_no_tiebreak",
                                }
                            )
                            sigs = list(tb.get("signals_used") or [])
                            sigs.append("structural_rule_A_overlay_no_tiebreak")
                            sigs.append("structural_rule_A_trusted_overlay_backing")
                            out["signals_used"] = sigs
                            return out

    # ----- Rule B: equal-support DR realignment (stdout aligned with tie-break) -----
    if (
        bool(tiebreak_meta.get("frontier_tiebreak_triggered"))
        and tb.get("abstain_reason") == "pal_stdout_already_matches_tiebreak_group"
        and pal_out_n
        and pal_out_n != "__unknown__"
    ):
        tb_raw = _to_text(tiebreak_meta.get("frontier_tiebreak_selected_group"))
        tb_n = normalize_answer_group_key(str(tb_raw).strip()) if tb_raw else ""
        if tb_n and pal_out_n == tb_n:
            dr_raw = _to_text(direct_reserve_answer_raw)
            if dr_raw:
                dr_n = normalize_answer_group_key(str(dr_raw).strip())
                if dr_n and dr_n != "__unknown__" and dr_n != tb_n:
                    sup_tb = _support_for_normalized_histogram_key(combined, tb_n)
                    sup_dr = _support_for_normalized_histogram_key(combined, dr_n)
                    # --- Rule B: DR realignment (only if DR has STRICTLY HIGHER support) ---
                    if sup_dr > sup_tb:
                        out.update(
                            {
                                "should_override": True,
                                "recommended_answer": str(dr_raw).strip(),
                                "recommended_normalized_group": dr_n,
                                "recommended_source": "structural_v1_frontier_realign_dr_strict_higher_support",
                                "reason": "override_structural_v1_dr_realign_higher_histogram_to_tiebreak_peer",
                                "abstain_reason": "",
                                "commitment_policy_layer": "structural_frontier_realign_dr",
                            }
                        )
                        sigs = list(tb.get("signals_used") or [])
                        sigs.append("structural_rule_B_dr_equal_support_realign")
                        out["signals_used"] = sigs
                        return out

    return out


def decide_pal_strong_overlay_promotion(
    *,
    combined_group_counts_base: dict[str, Any],
    pal_answer_raw: str | None,
    incumbent_final_answer_raw: str | None,
    frontier_weak: bool,
    tiebreak_triggered: bool,
    tiebreak_selected_group_raw: str | None,
    strong_pal: bool,
    pal_score: float,
    peer_conflict_min_support: int = PAL_STRONG_OVERLAY_PEER_SUPPORT_CONFLICT_MIN,
    tiebreak_conflict_min_support: int = PAL_STRONG_OVERLAY_TIEBREAK_PEER_SUPPORT_CONFLICT_MIN,
) -> tuple[bool, str, dict[str, Any]]:
    """Gold-free PAL takeover decision shared by live controller overlays and residual integration replay.

    Return ``(promote, reason, diagnostics)``.
    ``reason`` is either a promotion tag or a blocking tag matching ``PALOverlayReason`` wording.
    """
    pal_raw = _to_text(pal_answer_raw) or ""
    pal_g = normalize_answer_group_key(pal_raw)
    if not pal_g or pal_g == "__unknown__":
        return False, "blocked_missing_pal_group", {}

    diag: dict[str, Any] = {
        "pal_normalized_group_key": pal_g,
        "peer_conflict_min_support": int(peer_conflict_min_support),
        "tiebreak_conflict_min_support": int(tiebreak_conflict_min_support),
    }

    combined = combined_group_counts_base if isinstance(combined_group_counts_base, dict) else {}
    group_support = _support_for_normalized_histogram_key(combined, pal_g)
    diag["pal_histogram_support_sum"] = int(group_support)

    max_peer, peer_g = _max_histogram_support_excluding_normalized_group(combined, normalized_group_key=pal_g)
    diag["max_non_pal_histogram_support"], diag["max_non_pal_histogram_group_raw"] = max_peer, peer_g

    frontier_conflict = bool(max_peer >= int(peer_conflict_min_support) and int(group_support) == 0)

    tb_sup = _tiebreak_histogram_support(combined, tiebreak_selected_group_raw)
    diag["tiebreak_selected_group_histogram_support"] = int(tb_sup)
    if bool(tiebreak_triggered):
        tb_g = normalize_answer_group_key(str(tiebreak_selected_group_raw or "").strip())
        if tb_g not in {"", "__unknown__"} and tb_g != pal_g:
            if tb_sup >= int(tiebreak_conflict_min_support):
                frontier_conflict = True
                diag["tiebreak_conflict_escalated"] = True

    diag["pal_frontier_conflict"] = bool(frontier_conflict)
    incumbent_raw = _to_text(incumbent_final_answer_raw) or ""
    final_g = normalize_answer_group_key(incumbent_raw) if incumbent_raw else ""
    agrees_supported = bool(group_support >= 1)
    final_is_weak_fallback = bool(final_g in {"", "__unknown__", "0", "1"})

    if not strong_pal:
        return False, "blocked_non_strong_pal_candidate", diag
    if frontier_conflict:
        return False, "blocked_frontier_tiebreak_conflict", diag
    if agrees_supported:
        return True, "agrees_with_supported_group", diag
    if frontier_weak and final_is_weak_fallback:
        return True, "replace_weak_fallback_under_weak_frontier", diag
    if frontier_weak and float(pal_score) >= 0.75:
        return True, "weak_frontier_plus_high_pal_score", diag

    displaces = (
        not agrees_supported
        and final_g != pal_g
        and not frontier_conflict
    )
    if displaces:
        return True, "pal_strong_executable_displaces_non_histogram_supported_commit", diag

    return False, "blocked_policy_conditions_not_met", diag


def _extract_flat_pal_execution(metadata: dict[str, Any]) -> dict[str, Any]:
    """Normalize controller ``pal_execution`` dict for integration logic."""
    md = metadata or {}
    px = md.get("pal_execution")
    if isinstance(px, dict):
        return px
    return {}


def apply_pal_residual_strong_integration_fix(
    metadata: dict[str, Any],
    repaired: dict[str, Any],
    *,
    dataset: str,
    enabled: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Optional evaluator-time integration: align surfaced answer with strong executed PAL after commit.

    Gold-free: relies only on ``metadata`` parity fields captured at runtime plus ``repaired``
    surfaced controller commit. Mirrors :func:`decide_pal_strong_overlay_promotion` for offline bundles
    collected before controller overlay tweaks shipped.
    """
    sidecar: dict[str, Any] = {
        "pal_integration_fix_triggered": False,
        "pal_integration_fix_reason": "",
        "pal_integration_previous_answer": None,
        "pal_integration_selected_answer": None,
        "pal_integration_blocked_reason": "",
        "pal_integration_conflict_answer": None,
        "pal_integration_frontier_conflict": False,
    }
    out = dict(repaired)
    if not enabled:
        sidecar["pal_integration_fix_reason"] = "disabled"
        return out, sidecar

    md = dict(metadata or {})
    if md.get("external_baseline_family"):
        sidecar["pal_integration_fix_reason"] = "skipped_external_baseline_family"
        return out, sidecar

    pal_px = _extract_flat_pal_execution(md)
    pal_already = md.get("pal_overlay") if isinstance(md.get("pal_overlay"), dict) else {}
    if isinstance(pal_already, dict) and bool(pal_already.get("pal_overlay_applied")):
        sidecar["pal_integration_fix_reason"] = "skipped_pal_overlay_already_applied"
        return out, sidecar

    # Track B gate already committed metadata["final_answer"]; do not re-run PAL promotion at evaluator time.
    if isinstance(pal_already, dict) and bool(pal_already.get("track_b_gate_override_applied")):
        sidecar["pal_integration_fix_reason"] = "skipped_track_b_gate_override_applied"
        sidecar["pal_integration_skipped_reason"] = "track_b_gate_override_applied"
        return out, sidecar

    strong_pal = int(pal_px.get("pal_candidate_is_strong", 0) or 0) == 1
    exec_ok = int(pal_px.get("pal_exec_ok", 0) or 0) == 1
    parse_ok = int(pal_px.get("pal_parse_ok", 0) or 0) == 1
    safety_ok = int(pal_px.get("pal_safety_ok", 0) or 0) == 1

    if not strong_pal or not exec_ok or not parse_ok or not safety_ok:
        sidecar["pal_integration_blocked_reason"] = (
            "blocked_pal_gate_not_exec_or_not_strong" if enabled else ""
        )
        sidecar["pal_integration_fix_reason"] = "skipped_pal_integration_gates_failed"
        return out, sidecar

    exec_res = pal_px.get("pal_execution_result")
    ans_raw = _to_text(pal_px.get("pal_candidate_answer"))
    if ans_raw is None and isinstance(exec_res, dict):
        ans_raw = _to_text(exec_res.get("pal_answer_normalized") or exec_res.get("pal_answer_raw"))
    if ans_raw is None:
        sidecar["pal_integration_fix_reason"] = "skipped_missing_pal_candidate_answer"
        return out, sidecar

    combined = md.get("answer_group_support_counts")
    frontier_support = md.get("frontier_support")
    try:
        fs_int = int(frontier_support or 0)
    except Exception:
        fs_int = 0
    frontier_result_is_none = md.get("frontier_result") is None
    frontier_weak = bool(frontier_result_is_none or fs_int <= 1)

    pal_score_s = pal_px.get("pal_score")
    try:
        pal_score = float(pal_score_s or 0.0)
    except Exception:
        pal_score = 0.0

    incumbent_commit = _to_text(md.get("final_answer"))

    promote, sel_reason, diag = decide_pal_strong_overlay_promotion(
        combined_group_counts_base=dict(combined) if isinstance(combined, dict) else {},
        pal_answer_raw=ans_raw,
        incumbent_final_answer_raw=incumbent_commit,
        frontier_weak=frontier_weak,
        tiebreak_triggered=bool(md.get("frontier_tiebreak_triggered")),
        tiebreak_selected_group_raw=str(md.get("frontier_tiebreak_selected_group") or "").strip(),
        strong_pal=True,
        pal_score=pal_score,
    )

    pal_can_before = canonicalize_answer(ans_raw, dataset=dataset)
    surf_raw = _to_text(out.get("surfaced_final_answer_raw"))
    surf_can = canonicalize_answer(surf_raw, dataset=dataset) if surf_raw else None

    sidecar.update(
        {
            "pal_integration_frontier_conflict": bool(diag.get("pal_frontier_conflict")),
            "pal_integration_conflict_answer": diag.get("max_non_pal_histogram_group_raw"),
        }
    )

    if not promote:
        sidecar["pal_integration_blocked_reason"] = str(sel_reason or "")
        sidecar["pal_integration_fix_reason"] = (
            sel_reason if str(sel_reason).startswith("blocked") else "not_promoted_other"
        )
        return out, sidecar

    if surf_can == pal_can_before and _to_text(out.get("surfaced_final_answer_raw")) == ans_raw:
        sidecar["pal_integration_fix_reason"] = "skipped_already_surfaced_pal_exact"
        return out, sidecar

    merged_counts: dict[str, Any] | None = None
    if isinstance(combined, dict):
        merged_counts = dict(combined)

    ans_can_merge = canonicalize_answer(ans_raw, dataset=dataset)
    if merged_counts is not None and ans_can_merge is not None:
        bumped = False
        for k in list(merged_counts.keys()):
            if normalize_answer_group_key(str(k)) == normalize_answer_group_key(str(ans_can_merge)):
                try:
                    merged_counts[k] = int(merged_counts[k] or 0) + 1
                    bumped = True
                    break
                except Exception:
                    continue
        if not bumped:
            merged_counts[str(ans_can_merge)] = int(merged_counts.get(str(ans_can_merge), 0) or 0) + 1
        sidecar["pal_integration_merged_answer_group_support_counts"] = merged_counts

    prev_surf = surf_raw or incumbent_commit or ""
    out["surfaced_final_answer_raw"] = ans_raw
    out["surfaced_final_answer_canonical"] = canonicalize_answer(ans_raw, dataset=dataset)
    out["chosen_final_node_answer_raw"] = ans_raw
    out["chosen_final_node_answer_canonical"] = canonicalize_answer(ans_raw, dataset=dataset)
    out["final_answer_source"] = "pal_residual_strong_integration_fix"
    out["repair_answer_raw"] = out.get("repair_answer_raw")
    sidecar.update(
        {
            "pal_integration_fix_triggered": True,
            "pal_integration_fix_reason": str(sel_reason),
            "pal_integration_previous_answer": prev_surf,
            "pal_integration_selected_answer": ans_raw,
            "pal_integration_blocked_reason": "",
        }
    )
    return out, sidecar


def effective_answer_raw_from_node(node: dict[str, Any], *, dataset: str) -> str | None:
    """Gold-free: best-effort answer string from a runner ``final_nodes`` row (API-free).

    Preference: explicit ``predicted_answer`` > ``trace_extracted_answer`` >
    ``extract_final_answer(reasoning_text)``. The ``dataset`` parameter is reserved for
    future dataset-aware extraction hooks.
    """
    _ = dataset  # reserved for dataset-specific extraction policy extensions
    pa = _to_text(node.get("predicted_answer"))
    if pa is not None:
        return pa
    ta = _to_text(node.get("trace_extracted_answer"))
    if ta is not None:
        return ta
    rt = _to_text(node.get("reasoning_text"))
    if rt:
        ext = _to_text(extract_final_answer(rt))
        if ext is not None:
            return ext
    nl_raw = _to_text(node.get("numeric_leaf_value"))
    nl_st = str(node.get("numeric_leaf_status") or "").strip().lower()
    if nl_raw and nl_st in {"final", "provisional", "equation_progress"}:
        return nl_raw
    return None


def augment_final_nodes_with_metadata_frontier(
    final_nodes: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    """Append frontier-weighted nodes when the live registry snapshot omits them (gold-free).

    Sources (in order): ``selector_candidate_pool`` rows, then ``frontier_metadata.action_trace``
    expand events. Does not remove or rewrite existing registry rows.

    Selector pool rows patch existing ``branch_id`` nodes in place when a more authoritative PAL
    candidate is present while preserving merged diverse-root/direct-hybrid pool semantics via the
    ``direct_hybrid_seed`` sentinel.
    """
    out: list[dict[str, Any]] = list(final_nodes)
    pool_rows = metadata.get("selector_candidate_pool") or []
    has_direct_hybrid = any(
        isinstance(r, dict) and str(r.get("source_metadata") or "").strip() == "direct_hybrid_seed" for r in pool_rows
    )
    existing: set[str] = {str(n.get("branch_id") or "") for n in out if n.get("branch_id")}
    existing_idx: dict[str, int] = {
        str(n.get("branch_id") or ""): i for i, n in enumerate(out) if isinstance(n, dict) and str(n.get("branch_id") or "")
    }

    for row in pool_rows:
        if not isinstance(row, dict):
            continue
        bid = str(row.get("branch_id") or row.get("candidate_id") or "").strip()
        if not bid:
            continue
        if bid in existing:
            idx = existing_idx.get(bid)
            pred = row.get("predicted_answer")
            trace = str(row.get("reasoning_text") or row.get("trace") or "")
            sm = str(row.get("source_metadata") or "").strip()
            if idx is not None and isinstance(out[idx], dict):
                if pred is not None and str(pred).strip():
                    out[idx]["predicted_answer"] = pred
                if trace and not str(out[idx].get("reasoning_text") or "").strip():
                    out[idx]["reasoning_text"] = trace
                if sm:
                    out[idx]["source_metadata"] = sm
            continue
        existing.add(bid)
        existing_idx[bid] = len(out)
        pred = row.get("predicted_answer")
        trace = str(row.get("reasoning_text") or row.get("trace") or "")
        sm = str(row.get("source_metadata") or "").strip()
        out.append(
            {
                "branch_id": bid,
                "predicted_answer": pred,
                "reasoning_text": trace,
                "score": float(row.get("branch_score", 0.5) or 0.5),
                "trace_extracted_answer": None,
                "expand_answer_extraction_sources": [],
                "verify_answer_extraction_sources": [],
                "source_metadata": sm if sm else "selector_candidate_pool",
            }
        )

    if not bool(metadata.get("frontier_executed")) and not has_direct_hybrid:
        return out

    fm = metadata.get("frontier_metadata") or {}
    at = fm.get("action_trace") or []
    for i, ev in enumerate(at):
        if not isinstance(ev, dict):
            continue
        if str(ev.get("action") or "").strip().lower() != "expand":
            continue
        bid = str(ev.get("branch_id") or "").strip() or f"frontier_expand_{i}"
        uniq = bid
        suffix = 0
        while uniq in existing:
            suffix += 1
            uniq = f"{bid}__{suffix}"
        existing.add(uniq)
        rt = str(ev.get("response_text") or ev.get("reasoning_text") or "")
        ea = ev.get("extracted_answer")
        ea_s = str(ea).strip() if ea is not None else ""
        out.append(
            {
                "branch_id": uniq,
                "predicted_answer": ea_s if ea_s else None,
                "reasoning_text": rt,
                "score": 0.5,
                "trace_extracted_answer": ea_s if ea_s else None,
                "expand_answer_extraction_sources": [],
                "verify_answer_extraction_sources": [],
                "source_metadata": "frontier_action_trace",
            }
        )
    return out


def resolve_selected_group_hint_from_metadata(metadata: dict[str, Any], *, dataset: str) -> str | None:
    """Resolve ``selected_group_hint`` for ``choose_repair_answer`` across controller families (gold-free)."""
    _ = dataset  # reserved for future dataset-specific hint shaping
    sg = _to_text(metadata.get("selected_group"))
    if sg and sg != "__unknown__":
        return sg
    fa = _to_text(metadata.get("final_answer"))
    if fa:
        return fa
    raw = metadata.get("answer_group_support_counts") or {}
    if isinstance(raw, dict) and raw:
        best: str | None = None
        best_cnt = -1
        for k, v in raw.items():
            try:
                c = int(v)
            except Exception:
                c = 0
            ks = str(k).strip()
            if not ks or ks == "__unknown__":
                continue
            if c > best_cnt:
                best, best_cnt = ks, c
        if best is not None:
            return best
    return _to_text(metadata.get("frontier_candidate_answer"))


def gold_in_tree_from_nodes(final_nodes: list[dict[str, Any]], gold_answer: str, *, dataset: str) -> int:
    """Whether gold appears in any node's effective answer (registry + metadata-augmented)."""
    gold_can = canonicalize_answer(gold_answer, dataset=dataset)
    if gold_can is None:
        return 0
    for n in final_nodes:
        raw = effective_answer_raw_from_node(n, dataset=dataset)
        if raw and canonicalize_answer(raw, dataset=dataset) == gold_can:
            return 1
    return 0


def deterministic_extract_answer(
    *,
    chosen_node_answer_raw: str | None,
    chosen_branch_reasoning_text: str | None,
) -> tuple[str | None, str]:
    """Deterministic extraction policy after node selection.

    Preference order: explicit branch-local answer > extracted-from-branch-text.
    """
    direct = _to_text(chosen_node_answer_raw)
    extracted = _to_text(extract_final_answer(chosen_branch_reasoning_text or "")) if _to_text(chosen_branch_reasoning_text) else None
    if direct is not None:
        return direct, "branch_local_answer_preferred"
    if extracted is not None:
        return extracted, "extracted_from_branch_reasoning_text"
    return None, "no_extractable_answer"


def classify_mismatch_subtype(row: dict[str, Any]) -> str:
    if row.get("canonical_answer_matches_ground_truth") and not row.get("surface_was_correct"):
        return "canonical_match_surface_mismatch"
    if row.get("chosen_node_vs_surface_mismatch"):
        return "chosen_node_vs_surface_mismatch"
    if row.get("chosen_node_vs_extraction_mismatch"):
        return "chosen_node_vs_extraction_mismatch"
    if row.get("extraction_vs_surface_mismatch"):
        return "extraction_vs_surface_mismatch"
    if row.get("canonicalization_changed_answer"):
        return "canonicalization_mismatch"
    if row.get("rescue_applied"):
        return "answer_level_rescue"
    return "unresolved_other"


def apply_controller_committed_surfacing_for_evaluation(
    metadata: dict[str, Any],
    repaired: dict[str, Any],
    *,
    dataset: str,
) -> dict[str, Any]:
    """Prefer ``metadata['final_answer']`` for evaluated surfacing when the controller committed it.

    Gold-free: uses only runtime controller metadata, never evaluation labels.
    """
    out = dict(repaired)
    repair_raw = out.get("surfaced_final_answer_raw")
    out["repair_answer_raw"] = repair_raw
    ctrl_raw = _to_text((metadata or {}).get("final_answer"))
    out["controller_final_answer_raw"] = ctrl_raw if ctrl_raw else None

    if ctrl_raw:
        can = canonicalize_answer(ctrl_raw, dataset=dataset)
        out["surfaced_final_answer_raw"] = ctrl_raw
        out["surfaced_final_answer_canonical"] = can
        out["chosen_final_node_answer_raw"] = ctrl_raw
        out["chosen_final_node_answer_canonical"] = can
        out["final_answer_source"] = "controller_metadata_final_answer"
        return out

    if _to_text(out.get("surfaced_final_answer_raw")):
        out["final_answer_source"] = "repair_layer"
    else:
        out["final_answer_source"] = "fallback"
    return out


_FINALITY_EXPAND_SOURCES = frozenset({"api_json_final_answer", "api_json_answer"})


def node_has_expand_finality_marking(node: dict[str, Any]) -> bool:
    """Gold-free: JSON field-backed extraction counts as stronger commitment than reasoning fallback."""
    for key in ("expand_answer_extraction_sources", "verify_answer_extraction_sources"):
        for s in node.get(key) or []:
            if str(s) in _FINALITY_EXPAND_SOURCES:
                return True
    return False


def _has_reliable_frontier_answer_group_counts(metadata: dict[str, Any]) -> bool:
    fg = metadata.get("frontier_answer_group_counts") or {}
    if not isinstance(fg, dict) or not fg:
        return False
    try:
        return sum(int(v or 0) for v in fg.values()) > 0
    except Exception:
        return False


def _weak_singleton_canonical(canonical: str | None) -> bool:
    return canonical is not None and str(canonical).strip() in {"0", "1"}


def _distinct_numeric_canonicals_in_nodes(final_nodes: list[dict[str, Any]], *, dataset: str) -> set[str]:
    out: set[str] = set()
    for n in final_nodes:
        raw = effective_answer_raw_from_node(n, dataset=dataset)
        if raw is None:
            continue
        ck = canonicalize_answer(raw, dataset=dataset)
        if ck is not None:
            out.add(str(ck))
    return out


def surface_answer_has_evidence(
    *,
    surfaced_raw: str | None,
    surfaced_canonical: str | None,
    metadata: dict[str, Any],
    final_nodes: list[dict[str, Any]],
    dataset: str,
) -> bool:
    """Runtime-legal support: group counts, selected_group, tiebreak group, or finality-marked node match."""
    md = metadata or {}
    if md.get("external_baseline_family"):
        return True
    nk = normalize_answer_group_key(str(surfaced_raw or surfaced_canonical or "")).strip()
    if not nk or nk == "__unknown__":
        return False
    ag = md.get("answer_group_support_counts") or {}
    if isinstance(ag, dict):
        try:
            if int(ag.get(nk, 0) or 0) >= 1:
                return True
        except Exception:
            pass
    fg = md.get("frontier_answer_group_counts") or {}
    if isinstance(fg, dict):
        try:
            if int(fg.get(nk, 0) or 0) >= 1:
                return True
        except Exception:
            pass
    sg = md.get("selected_group")
    if sg is not None and normalize_answer_group_key(str(sg)) == nk:
        return True
    if md.get("frontier_tiebreak_triggered"):
        tbg = md.get("frontier_tiebreak_selected_group")
        if tbg is not None and normalize_answer_group_key(str(tbg)) == nk:
            return True
    target_can = surfaced_canonical
    if target_can is None and surfaced_raw:
        target_can = canonicalize_answer(surfaced_raw, dataset=dataset)
    if target_can is not None:
        for n in final_nodes:
            if canonicalize_answer(effective_answer_raw_from_node(n, dataset=dataset), dataset=dataset) == target_can:
                if node_has_expand_finality_marking(n):
                    return True
    return False


def interim_total_likely_mistaken(
    *,
    surfaced_canonical: str | None,
    surfaced_raw: str | None,
    metadata: dict[str, Any],
    final_nodes: list[dict[str, Any]],
    dataset: str,
) -> bool:
    """Conservative interim detector (gold-free): singleton merged support with alternate numerics elsewhere."""
    md = metadata or {}
    if surfaced_canonical is None and surfaced_raw:
        surfaced_canonical = canonicalize_answer(surfaced_raw, dataset=dataset)
    if surfaced_canonical is None:
        return False
    nk = normalize_answer_group_key(str(surfaced_raw or surfaced_canonical or "")).strip()
    if not nk:
        return False
    for n in final_nodes:
        if canonicalize_answer(effective_answer_raw_from_node(n, dataset=dataset), dataset=dataset) == surfaced_canonical:
            if node_has_expand_finality_marking(n):
                return False
    ag = md.get("answer_group_support_counts") or {}
    direct_trace = list(md.get("direct_reserve_attempts") or [])
    final_s = md.get("final_answer")
    if final_s is not None:
        final_s = str(final_s).strip() or None
    merged = build_merged_support_histogram_for_tiebreak(
        dict(ag) if isinstance(ag, dict) else {},
        final_answer=final_s,
        direct_trace=direct_trace,
    )
    try:
        mc = int(merged.get(nk, 0) or 0)
    except Exception:
        mc = 0
    if mc != 1:
        return False
    dist = _distinct_numeric_canonicals_in_nodes(final_nodes, dataset=dataset)
    return len(dist) >= 2


def choose_completion_answer_deterministic(
    *,
    metadata: dict[str, Any],
    final_nodes: list[dict[str, Any]],
    dataset: str,
    previous_surface_key_hint: str | None,
) -> tuple[str | None, str]:
    """Highest-support group with frontier tiebreak on ties; else best scored finality-marked node."""
    md = metadata or {}
    ag = md.get("answer_group_support_counts") or {}
    direct_trace = list(md.get("direct_reserve_attempts") or [])
    final_s = md.get("final_answer")
    if final_s is not None:
        final_s = str(final_s).strip() or None
    merged: dict[str, int] = build_merged_support_histogram_for_tiebreak(
        dict(ag) if isinstance(ag, dict) else {},
        final_answer=final_s,
        direct_trace=direct_trace,
    )
    if merged:
        max_v = max(int(v) for v in merged.values())
        tied = [
            str(g).strip()
            for g, v in merged.items()
            if str(g).strip() not in {"", "__unknown__"} and int(v) == int(max_v)
        ]
        chosen_g: str | None = None
        if len(tied) == 1:
            chosen_g = tied[0]
        else:
            fg_counts = dict(md.get("frontier_answer_group_counts") or {})
            dc_counts = dict(md.get("direct_answer_group_counts") or {})
            cg, _tm = resolve_frontier_bias_max_support_tiebreak(
                merged,
                fg_counts,
                dc_counts,
                previous_group_key=str(previous_surface_key_hint or tied[0] if tied else "__unknown__"),
            )
            if cg is not None:
                chosen_g = str(cg).strip()
            elif tied:

                def _fc(g: str) -> int:
                    try:
                        return int(fg_counts.get(g, 0) or 0)
                    except Exception:
                        return 0

                def _dc(g: str) -> int:
                    try:
                        return int(dc_counts.get(g, 0) or 0)
                    except Exception:
                        return 0

                chosen_g = sorted(tied, key=lambda g: (-_fc(g), -_dc(g), g))[0]
        if chosen_g:
            da_list: list[str | None] = []
            dr = md.get("direct_reserve_answer")
            if dr is not None:
                da_list.append(str(dr))
            txt = pick_answer_text_for_normalized_group(
                chosen_g,
                direct_answers=da_list,
                incumbent_answer=str(dr).strip() if dr is not None else None,
                frontier_answer=md.get("frontier_candidate_answer"),
                frontier_metadata=dict(md.get("frontier_candidate_metadata") or md.get("frontier_metadata") or {}),
                selector_candidate_pool=list(md.get("selector_candidate_pool") or []),
            )
            if txt and str(txt).strip():
                return str(txt).strip(), "completion_histogram_or_tiebreak"

    best_raw: str | None = None
    best_score = -1e18
    for n in final_nodes:
        if not node_has_expand_finality_marking(n):
            continue
        raw = effective_answer_raw_from_node(n, dataset=dataset)
        if raw is None:
            continue
        try:
            sc = float(n.get("score", 0.0) or 0.0)
        except Exception:
            sc = 0.0
        if sc > best_score:
            best_score = sc
            best_raw = raw
    if best_raw:
        return str(best_raw).strip(), "completion_finality_marked_node"
    return None, ""


def apply_finalization_guard_surfacing(
    metadata: dict[str, Any],
    repaired: dict[str, Any],
    *,
    final_nodes: list[dict[str, Any]],
    dataset: str,
    enabled: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Post-commit surfacing guard (gold-free). Does not call APIs."""
    sidecar: dict[str, Any] = {
        "finalguard_enabled": bool(enabled),
        "finalguard_triggered": False,
        "finalguard_previous_answer": None,
        "finalguard_selected_answer": None,
        "finalguard_reason": "disabled",
        "finalguard_answer_source": "",
    }
    if not enabled:
        return dict(repaired), sidecar

    md = dict(metadata or {})
    if md.get("external_baseline_family"):
        sidecar.update(
            {
                "finalguard_triggered": False,
                "finalguard_reason": "skipped_external_baseline_family",
                "finalguard_answer_source": "skipped_external_baseline",
            }
        )
        return dict(repaired), sidecar

    out = dict(repaired)
    prev_raw = _to_text(out.get("surfaced_final_answer_raw"))
    prev_can = canonicalize_answer(prev_raw, dataset=dataset) if prev_raw else None
    sidecar["finalguard_previous_answer"] = prev_can
    src = str(out.get("final_answer_source") or "")

    ev = surface_answer_has_evidence(
        surfaced_raw=prev_raw,
        surfaced_canonical=prev_can,
        metadata=md,
        final_nodes=final_nodes,
        dataset=dataset,
    )
    weak = _weak_singleton_canonical(prev_can)
    rel_fc = _has_reliable_frontier_answer_group_counts(md)
    interim = interim_total_likely_mistaken(
        surfaced_canonical=prev_can,
        surfaced_raw=prev_raw,
        metadata=md,
        final_nodes=final_nodes,
        dataset=dataset,
    )

    should_override = False
    reason = "keep_supported_commit"
    if src == "repair_layer" and weak and not rel_fc:
        should_override = True
        reason = "repair_weak_singleton_without_frontier_counts"
    elif interim:
        should_override = True
        reason = "interim_singleton_with_alternate_numeric_leaves"
    elif not ev and prev_can is not None and (
        weak or src == "repair_layer" or src == "controller_metadata_final_answer"
    ):
        should_override = True
        reason = "unsupported_surface_completion_attempt"

    if not should_override:
        sidecar.update(
            {
                "finalguard_triggered": False,
                "finalguard_reason": reason,
                "finalguard_answer_source": "kept_original",
                "finalguard_selected_answer": prev_can,
            }
        )
        return out, sidecar

    sidecar["finalguard_triggered"] = True
    prev_key = normalize_answer_group_key(str(prev_raw or prev_can or ""))
    cand_raw, cand_src = choose_completion_answer_deterministic(
        metadata=md,
        final_nodes=final_nodes,
        dataset=dataset,
        previous_surface_key_hint=prev_key or None,
    )
    cand_can = canonicalize_answer(cand_raw, dataset=dataset) if cand_raw else None

    if cand_raw is None or not str(cand_raw).strip():
        sidecar.update(
            {
                "finalguard_reason": reason + "_no_runtime_alternative_kept_fallback",
                "finalguard_answer_source": "kept_fallback_no_alternative",
                "finalguard_selected_answer": prev_can,
            }
        )
        return out, sidecar

    if cand_can == prev_can and str(cand_raw).strip() == str(prev_raw or "").strip():
        sidecar.update(
            {
                "finalguard_reason": reason + "_completion_unchanged",
                "finalguard_answer_source": "kept_original",
                "finalguard_selected_answer": prev_can,
            }
        )
        return out, sidecar

    out["surfaced_final_answer_raw"] = cand_raw
    out["surfaced_final_answer_canonical"] = cand_can
    out["chosen_final_node_answer_raw"] = cand_raw
    out["chosen_final_node_answer_canonical"] = cand_can
    out["final_answer_source"] = "finalguard_adjusted"
    sidecar.update(
        {
            "finalguard_selected_answer": cand_can,
            "finalguard_reason": reason + "_applied_completion",
            "finalguard_answer_source": cand_src,
        }
    )
    return out, sidecar


def choose_repair_answer(
    *,
    final_nodes: list[dict[str, Any]],
    selected_group_hint: str | None,
    dataset: str,
    enable_rescue: bool = True,
    policy_mode: str = "current_selection_control",
) -> dict[str, Any]:
    done_nodes = [n for n in final_nodes if effective_answer_raw_from_node(n, dataset=dataset) is not None]
    selected_group = _to_text(selected_group_hint)

    def _group_nodes(nodes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for n in nodes:
            raw_eff = effective_answer_raw_from_node(n, dataset=dataset)
            ck = canonicalize_answer(raw_eff, dataset=dataset) if raw_eff is not None else None
            if ck is None:
                continue
            out.setdefault(ck, []).append(n)
        return out

    def _pick_group_support_only(groups: dict[str, list[dict[str, Any]]]) -> str | None:
        if not groups:
            return None
        ranked = sorted(
            groups.items(),
            key=lambda kv: (
                len(kv[1]),
                sum(float(x.get("score", 0.0)) for x in kv[1]) / max(1, len(kv[1])),
                max(float(x.get("score", 0.0)) for x in kv[1]),
            ),
            reverse=True,
        )
        return ranked[0][0]

    def _pick_group_support_plus_score(groups: dict[str, list[dict[str, Any]]], *, calibrated: bool = False) -> str | None:
        if not groups:
            return None
        scores = [float(n.get("score", 0.0)) for members in groups.values() for n in members]
        if not scores:
            return _pick_group_support_only(groups)
        mn, mx = min(scores), max(scores)
        mean = sum(scores) / len(scores)
        var = sum((s - mean) ** 2 for s in scores) / max(1, len(scores))
        std = math.sqrt(max(var, 1e-12))

        def _norm(s: float) -> float:
            if calibrated:
                z = (s - mean) / std
                return 1.0 / (1.0 + math.exp(-z))
            if mx <= mn + 1e-12:
                return 0.5
            return (s - mn) / (mx - mn)

        total_nodes = sum(len(v) for v in groups.values())
        group_rows: list[tuple[str, float, int, float, float]] = []
        for gk, members in groups.items():
            support = len(members) / max(1, total_nodes)
            max_score = max(_norm(float(x.get("score", 0.0))) for x in members)
            mean_score = sum(_norm(float(x.get("score", 0.0))) for x in members) / max(1, len(members))
            if calibrated:
                group_score = 0.55 * support + 0.45 * mean_score
            else:
                group_score = 0.65 * support + 0.35 * max_score
            group_rows.append((gk, group_score, len(members), mean_score, max_score))
        group_rows.sort(key=lambda x: x[1], reverse=True)

        # Tie-break cleanup: near-tie prefers robust multi-branch support.
        if calibrated and len(group_rows) > 1 and abs(group_rows[0][1] - group_rows[1][1]) <= 0.03:
            top = sorted(group_rows[:2], key=lambda x: (x[2], x[3], x[4]), reverse=True)[0]
            return top[0]
        return group_rows[0][0]

    chosen: dict[str, Any] | None = None
    groups = _group_nodes(done_nodes)
    policy = str(policy_mode or "current_selection_control")
    winning_group: str | None = None
    if policy == "answer_group_support_only":
        winning_group = _pick_group_support_only(groups)
    elif policy == "answer_group_support_plus_node_score":
        winning_group = _pick_group_support_plus_score(groups, calibrated=False)
    elif policy == "answer_group_support_plus_calibrated_score":
        winning_group = _pick_group_support_plus_score(groups, calibrated=True)
    elif policy == "answer_group_support_plus_score_plus_tiebreak_cleanup":
        winning_group = _pick_group_support_plus_score(groups, calibrated=True)
    else:
        if selected_group is not None:
            sg_can = canonicalize_answer(selected_group, dataset=dataset)
            cands = [
                n
                for n in done_nodes
                if canonicalize_answer(effective_answer_raw_from_node(n, dataset=dataset), dataset=dataset) == sg_can
            ]
            if cands:
                chosen = max(cands, key=lambda n: float(n.get("score", 0.0)))
        if chosen is None and done_nodes:
            chosen = max(done_nodes, key=lambda n: float(n.get("score", 0.0)))
            winning_group = canonicalize_answer(effective_answer_raw_from_node(chosen, dataset=dataset), dataset=dataset)

    if chosen is None and winning_group is not None:
        members = groups.get(winning_group, [])
        if members:
            chosen = max(members, key=lambda n: float(n.get("score", 0.0)))

    chosen_id = _to_text(chosen.get("branch_id")) if chosen else None
    chosen_raw = effective_answer_raw_from_node(chosen, dataset=dataset) if chosen else None
    chosen_canonical = canonicalize_answer(chosen_raw, dataset=dataset)
    reasoning_text = _to_text(chosen.get("reasoning_text")) if chosen else None

    extracted_raw, extraction_source = deterministic_extract_answer(
        chosen_node_answer_raw=chosen_raw,
        chosen_branch_reasoning_text=reasoning_text,
    )
    extracted_canonical = canonicalize_answer(extracted_raw, dataset=dataset)

    surfaced_raw = extracted_raw
    surfaced_canonical = extracted_canonical
    rescue_applied = False
    rescue_detail: dict[str, Any] = {"applied": False, "reason": "disabled_or_not_triggered"}

    if enable_rescue and done_nodes:
        canon_rows = []
        for n in done_nodes:
            ans_raw = effective_answer_raw_from_node(n, dataset=dataset)
            ans_can = canonicalize_answer(ans_raw, dataset=dataset)
            if ans_can is not None:
                canon_rows.append((ans_can, float(n.get("score", 0.0)), _to_text(n.get("branch_id"))))
        counts = Counter([c for c, _, _ in canon_rows])
        if counts:
            support_sorted = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
            top_ans, top_cnt = support_sorted[0]
            second_cnt = support_sorted[1][1] if len(support_sorted) > 1 else 0
            if top_cnt >= 2 and (top_cnt - second_cnt) >= 1:
                if surfaced_canonical != top_ans:
                    rescue_applied = True
                    surfaced_canonical = top_ans
                    surfaced_raw = top_ans
                    rescue_detail = {
                        "applied": True,
                        "reason": "high_support_canonical_consensus",
                        "top_support_count": int(top_cnt),
                        "second_support_count": int(second_cnt),
                        "candidate_supports": dict(counts),
                    }

    return {
        "selection_policy_mode": policy,
        "selected_group_hint": selected_group,
        "selected_group_after_policy": winning_group,
        "chosen_final_node_id": chosen_id,
        "chosen_final_node_answer_raw": chosen_raw,
        "chosen_final_node_answer_canonical": chosen_canonical,
        "extracted_final_answer_raw": extracted_raw,
        "extracted_final_answer_canonical": extracted_canonical,
        "surfaced_final_answer_raw": surfaced_raw,
        "surfaced_final_answer_canonical": surfaced_canonical,
        "extraction_source": extraction_source,
        "rescue_applied": rescue_applied,
        "rescue_detail": rescue_detail,
    }
