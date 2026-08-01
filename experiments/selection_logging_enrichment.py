"""Gold-free selection diagnostics for FTA direct-reserve frontier gate (observability only)."""

from __future__ import annotations

from typing import Any, Callable

from experiments.frontier_max_support_tiebreak import normalize_answer_group_key

SELECTION_DIAGNOSTICS_VERSION = "20260706_v1"
SELECTION_LOGGING_RULE_VERSION = "direct_reserve_frontier_gate_v1"
NEAR_TIE_SUPPORT_GAP_THRESHOLD = 1
MAX_ORDERED_GROUPS = 8

# Keys that must never be emitted by this module (offline evaluation / oracle only).
FORBIDDEN_GOLD_DERIVED_KEYS = frozenset(
    {
        "gold_answer",
        "gold_in_tree",
        "is_correct",
        "oracle",
        "correct_answer",
        "d6_bucket",
        "d9_bucket",
    }
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_counts(raw: dict[str, Any] | None) -> dict[str, int]:
    out: dict[str, int] = {}
    if not isinstance(raw, dict):
        return out
    for key, val in raw.items():
        ks = str(key).strip()
        if not ks or ks == "__unknown__":
            continue
        out[ks] = _safe_int(val, 0)
    return out


def _sorted_support_groups(counts: dict[str, int]) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def _derive_selection_rule_name(
    *,
    frontier_override_triggered: bool,
    reserve_used: bool,
    override_reason: str,
    tiebreak_meta: dict[str, Any] | None,
) -> str:
    tb = tiebreak_meta or {}
    if frontier_override_triggered:
        return "frontier_override"
    if bool(tb.get("frontier_tiebreak_triggered")):
        return "frontier_max_support_tiebreak"
    if reserve_used:
        return "direct_reserve_incumbent"
    reason = str(override_reason or "").strip()
    if reason:
        return reason
    return "direct_reserve_frontier_gate_default"


def _find_selected_node(
    *,
    selected_group_key: str,
    selector_candidate_pool: list[dict[str, Any]] | None,
    final_branch_states: list[dict[str, Any]] | None,
) -> tuple[str, str]:
    """Return (node_id, source) for the committed answer group, best-effort."""
    selected_group_key = str(selected_group_key or "").strip() or "__unknown__"

    for collection in (selector_candidate_pool, final_branch_states):
        if not isinstance(collection, list):
            continue
        for row in collection:
            if not isinstance(row, dict):
                continue
            if int(row.get("selected", 0) or 0) == 1:
                node_id = str(row.get("branch_id") or row.get("candidate_id") or "").strip()
                source = str(
                    row.get("source")
                    or row.get("source_id")
                    or row.get("strategy_family")
                    or row.get("source_family")
                    or ""
                ).strip()
                if node_id or source:
                    return node_id, source

    for collection in (selector_candidate_pool, final_branch_states):
        if not isinstance(collection, list):
            continue
        for row in collection:
            if not isinstance(row, dict):
                continue
            pred = str(row.get("predicted_answer") or "").strip()
            group = str(row.get("normalized_answer") or row.get("answer_group") or "").strip()
            if not group and pred:
                group = normalize_answer_group_key(pred) or ""
            if group == selected_group_key:
                node_id = str(row.get("branch_id") or row.get("candidate_id") or "").strip()
                source = str(
                    row.get("source")
                    or row.get("source_id")
                    or row.get("strategy_family")
                    or row.get("source_family")
                    or ""
                ).strip()
                return node_id, source

    return "", ""


def build_selection_logging_enrichment(
    *,
    final_answer_raw: str | None,
    final_answer: str | None,
    answer_group_support_counts: dict[str, Any] | None,
    selector_candidate_pool: list[dict[str, Any]] | None = None,
    final_branch_states: list[dict[str, Any]] | None = None,
    frontier_override_triggered: bool = False,
    reserve_used: bool = False,
    override_reason: str = "",
    tiebreak_meta: dict[str, Any] | None = None,
    method_name: str = "",
    near_tie_gap_threshold: int = NEAR_TIE_SUPPORT_GAP_THRESHOLD,
    normalize_answer_fn: Callable[[str | None], str] | None = None,
) -> dict[str, Any]:
    """Build observability-only metadata; must not change committed answers."""
    norm = normalize_answer_fn or normalize_answer_group_key
    raw_text = str(final_answer_raw if final_answer_raw is not None else final_answer or "").strip()
    normalized_text = str(norm(raw_text) if raw_text else norm(final_answer)).strip() or "__unknown__"
    selected_group_key = normalized_text if normalized_text else "__unknown__"

    counts = _normalize_counts(answer_group_support_counts)
    sorted_groups = _sorted_support_groups(counts)
    answer_group_count = len(sorted_groups)

    top_key = sorted_groups[0][0] if sorted_groups else ""
    top_support = int(sorted_groups[0][1]) if sorted_groups else 0
    second_key = sorted_groups[1][0] if len(sorted_groups) > 1 else ""
    second_support = int(sorted_groups[1][1]) if len(sorted_groups) > 1 else 0
    top_second_gap: int | None = None
    if len(sorted_groups) > 1:
        top_second_gap = int(top_support - second_support)

    selected_support = int(counts.get(selected_group_key, 0))
    selected_rank = 0
    for idx, (group, _support) in enumerate(sorted_groups, start=1):
        if group == selected_group_key:
            selected_rank = idx
            break

    max_support = top_support if sorted_groups else 0
    tie_keys = [group for group, support in sorted_groups if support == max_support and max_support > 0]
    answer_group_support_tie = bool(len(tie_keys) >= 2)
    answer_group_near_tie = bool(
        top_second_gap is not None and top_second_gap <= max(0, int(near_tie_gap_threshold))
    )

    ordered_cap = max(1, int(MAX_ORDERED_GROUPS))
    candidate_group_keys_ordered = [group for group, _ in sorted_groups[:ordered_cap]]
    candidate_group_supports_ordered = [int(support) for _, support in sorted_groups[:ordered_cap]]

    node_id, node_source = _find_selected_node(
        selected_group_key=selected_group_key,
        selector_candidate_pool=selector_candidate_pool,
        final_branch_states=final_branch_states,
    )

    selection_rule_name = _derive_selection_rule_name(
        frontier_override_triggered=bool(frontier_override_triggered),
        reserve_used=bool(reserve_used),
        override_reason=str(override_reason or ""),
        tiebreak_meta=tiebreak_meta,
    )
    rule_version = str(method_name or "").strip() or SELECTION_LOGGING_RULE_VERSION

    answer_group_diagnostics = {
        "answer_group_count": answer_group_count,
        "selected_answer_group_key": selected_group_key,
        "selected_answer_group_support": selected_support,
        "selected_answer_group_rank": selected_rank,
        "top_answer_group_key": top_key,
        "top_answer_group_support": top_support,
        "second_answer_group_key": second_key,
        "second_answer_group_support": second_support,
        "top_second_support_gap": top_second_gap,
        "answer_group_support_tie": answer_group_support_tie,
        "answer_group_near_tie": answer_group_near_tie,
        "answer_group_tie_keys": list(tie_keys),
    }

    out: dict[str, Any] = {
        "selection_diagnostics_version": SELECTION_DIAGNOSTICS_VERSION,
        "answer_group_diagnostics": answer_group_diagnostics,
        "answer_group_count": answer_group_count,
        "selected_answer_group_key": selected_group_key,
        "selected_answer_group_support": selected_support,
        "selected_answer_group_rank": selected_rank,
        "top_answer_group_key": top_key,
        "top_answer_group_support": top_support,
        "second_answer_group_key": second_key,
        "second_answer_group_support": second_support,
        "top_second_support_gap": top_second_gap,
        "answer_group_support_tie": answer_group_support_tie,
        "answer_group_near_tie": answer_group_near_tie,
        "answer_group_tie_keys": list(tie_keys),
        "candidate_group_keys_ordered": candidate_group_keys_ordered,
        "candidate_group_supports_ordered": candidate_group_supports_ordered,
        "selected_final_node_id": node_id,
        "selected_final_node_source": node_source,
        "selected_final_answer_raw": raw_text,
        "selected_final_answer_normalized": selected_group_key,
        "selection_rule_name": selection_rule_name,
        "selection_rule_version": rule_version,
        "selection_behavior_changed": False,
        "selection_logging_only": True,
    }

    for key in out:
        if key in FORBIDDEN_GOLD_DERIVED_KEYS:
            raise ValueError(f"gold-derived key must not appear in selection logging: {key}")

    return out
