"""Promotion-review logging schema helpers for failure/runtime-cap cases.

Offline/local utility only. This module defines:
1) A canonical schema field set for promotion-grade case review records.
2) A builder that normalizes records and can inject explicit empty/unavailable markers
   for runtime/incomplete frontier failures.
3) A validator that reports review sufficiency (`yes`/`partial`/`no`) and runtime
   failure reviewability.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

EXPLICIT_EMPTY_MARKER = "__explicit_empty__"
EXPLICIT_UNAVAILABLE_MARKER = "__explicit_unavailable__"
EXPLICIT_NOT_SCORED_YET_MARKER = "__not_scored_yet__"
EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER = "__unavailable_not_recorded__"
EXPLICIT_NOT_APPLICABLE_MARKER = "__not_applicable__"

FAILURE_STATUSES = {"failed", "runtime_cap", "timeout", "parse_failed"}

OFFLINE_EVAL_ONLY_FIELDS = {"exact_match", "gold_answer"}

REQUIRED_IDENTITY_FIELDS = [
    "run_id",
    "artifact_label",
    "dataset",
    "provider",
    "model",
    "method",
    "budget",
    "seed",
]

PROMOTION_REVIEW_FIELDS = [
    # Identity
    "run_id",
    "artifact_label",
    "example_id",
    "problem_id",
    "dataset",
    "provider",
    "model",
    "method",
    "budget",
    "seed",
    # Problem/input
    "problem_text",
    "question",
    "prompt_template_id",
    "prompt_text",
    "prompt_pointer",
    "prompt_hash",
    # Candidate/output
    "candidate_answer",
    "candidate_trace",
    "candidate_answer_canonical",
    "parse_success",
    "parser_status",
    "parser_error",
    # Failure/runtime
    "status",
    "runtime_cap_reached",
    "error_type",
    "error_message",
    "partial_answer_present",
    "partial_trace_present",
    # Discovery/frontier
    "discovery_tree",
    "discovery_tree_pointer",
    "node_expansion_order",
    "final_nodes",
    "selected_node_id",
    "prune_or_selection_reasons",
    "candidate_pool_summary",
    "candidate_pool_pointer",
    # Cost
    "call_count",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "estimated_cost",
    "latency_seconds",
    "cost_timeline",
    "cost_timeline_pointer",
    # Scoring/gate
    "verifier_scores",
    "verifier_scores_pointer",
    "raw_proba_ready",
    "calibrated_percentile",
    "gate_features",
    "gate_decision",
    "policy_family",
    "policy_thresholds",
    # Offline eval metadata only
    "exact_match",
    "gold_answer",
    "offline_eval_only",
]


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def _is_explicit_marker(value: Any) -> bool:
    return str(value) in {
        EXPLICIT_EMPTY_MARKER,
        EXPLICIT_UNAVAILABLE_MARKER,
        EXPLICIT_NOT_SCORED_YET_MARKER,
        EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER,
        EXPLICIT_NOT_APPLICABLE_MARKER,
    }


def _present_or_explicit(value: Any) -> bool:
    return _is_present(value) or _is_explicit_marker(value)


def build_promotion_review_record(
    raw_record: Mapping[str, Any],
    *,
    fill_explicit_failure_state: bool = True,
) -> dict[str, Any]:
    """Build a normalized promotion-review record from a raw mapping."""
    out: dict[str, Any] = {k: raw_record.get(k) for k in PROMOTION_REVIEW_FIELDS}
    for k, v in raw_record.items():
        if k not in out:
            out[k] = v

    status = str(out.get("status") or "").strip().lower()
    runtime_cap_reached = bool(out.get("runtime_cap_reached"))
    is_failure = (status in FAILURE_STATUSES) or runtime_cap_reached

    if fill_explicit_failure_state and is_failure:
        if not _is_present(out.get("candidate_answer")):
            out["candidate_answer"] = EXPLICIT_EMPTY_MARKER
        if not _is_present(out.get("candidate_trace")):
            out["candidate_trace"] = EXPLICIT_EMPTY_MARKER
        if not _is_present(out.get("node_expansion_order")):
            out["node_expansion_order"] = EXPLICIT_UNAVAILABLE_MARKER
        if not _is_present(out.get("prune_or_selection_reasons")):
            out["prune_or_selection_reasons"] = EXPLICIT_UNAVAILABLE_MARKER
        if out.get("partial_answer_present") is None:
            out["partial_answer_present"] = False
        if out.get("partial_trace_present") is None:
            out["partial_trace_present"] = False

    if out.get("offline_eval_only") is None:
        out["offline_eval_only"] = bool(
            _is_present(out.get("exact_match")) or _is_present(out.get("gold_answer"))
        )

    return out


def validate_promotion_review_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate promotion-review sufficiency for a record."""
    missing_required: list[str] = []
    missing_critical: list[str] = []
    notes: list[str] = []

    def require(field: str, *, critical: bool = False) -> None:
        if not _is_present(record.get(field)):
            missing_required.append(field)
            if critical:
                missing_critical.append(field)

    # Identity
    for f in REQUIRED_IDENTITY_FIELDS:
        require(f, critical=True)

    # Required identity alternative
    if not (_is_present(record.get("example_id")) or _is_present(record.get("problem_id"))):
        missing_required.append("example_id_or_problem_id")
        missing_critical.append("example_id_or_problem_id")

    # Problem/input
    if not (_is_present(record.get("problem_text")) or _is_present(record.get("question"))):
        missing_required.append("problem_text_or_question")
        missing_critical.append("problem_text_or_question")
    if not (
        _is_present(record.get("prompt_text"))
        or _is_present(record.get("prompt_pointer"))
        or _is_present(record.get("prompt_hash"))
    ):
        missing_required.append("prompt_text_or_pointer_or_hash")

    # Candidate/output
    if not _present_or_explicit(record.get("candidate_answer")):
        missing_required.append("candidate_answer_or_explicit_empty")
        missing_critical.append("candidate_answer_or_explicit_empty")
    if not _present_or_explicit(record.get("candidate_trace")):
        missing_required.append("candidate_trace_or_explicit_empty")
        missing_critical.append("candidate_trace_or_explicit_empty")

    # Failure/runtime fields
    require("status", critical=True)
    require("runtime_cap_reached")
    status = str(record.get("status") or "").strip().lower()
    runtime_failure = bool(record.get("runtime_cap_reached")) or status in FAILURE_STATUSES
    if runtime_failure and not (_is_present(record.get("error_type")) or _is_present(record.get("error_message"))):
        missing_required.append("error_type_or_error_message")

    # Discovery/frontier
    if not (_is_present(record.get("discovery_tree")) or _is_present(record.get("discovery_tree_pointer"))):
        missing_required.append("discovery_tree_or_pointer")
        missing_critical.append("discovery_tree_or_pointer")
    if not _present_or_explicit(record.get("node_expansion_order")):
        missing_required.append("node_expansion_order_or_unavailable")
        missing_critical.append("node_expansion_order_or_unavailable")
    if not _present_or_explicit(record.get("prune_or_selection_reasons")):
        missing_required.append("prune_or_selection_reasons_or_unavailable")
        missing_critical.append("prune_or_selection_reasons_or_unavailable")
    if not (_is_present(record.get("candidate_pool_summary")) or _is_present(record.get("candidate_pool_pointer"))):
        missing_required.append("candidate_pool_summary_or_pointer")

    # Cost
    require("call_count")
    if not (
        _is_present(record.get("prompt_tokens"))
        or _is_present(record.get("completion_tokens"))
        or _is_present(record.get("total_tokens"))
    ):
        missing_required.append("tokens_any")
    if not (
        _is_present(record.get("estimated_cost"))
        or _is_present(record.get("latency_seconds"))
        or _is_present(record.get("cost_timeline"))
        or _is_present(record.get("cost_timeline_pointer"))
    ):
        missing_required.append("cost_or_latency_or_timeline")

    # Scoring/gate
    if not (_is_present(record.get("verifier_scores")) or _is_present(record.get("verifier_scores_pointer"))):
        missing_required.append("verifier_scores_or_pointer")
    if not (_is_present(record.get("raw_proba_ready")) or _is_present(record.get("calibrated_percentile"))):
        missing_required.append("raw_or_calibrated_score")
    require("gate_decision")
    require("policy_family")

    # Offline-only flags
    offline_present = sorted(f for f in OFFLINE_EVAL_ONLY_FIELDS if _is_present(record.get(f)))
    offline_flagged = bool(record.get("offline_eval_only")) if offline_present else True
    if offline_present and not offline_flagged:
        notes.append("offline_eval_fields_present_but_not_flagged_offline_eval_only")

    # Runtime failure reviewability
    runtime_failure_reviewable = True
    if runtime_failure:
        has_error = _is_present(record.get("error_type")) or _is_present(record.get("error_message"))
        has_answer = _present_or_explicit(record.get("candidate_answer"))
        has_trace = _present_or_explicit(record.get("candidate_trace"))
        has_node_order = _present_or_explicit(record.get("node_expansion_order"))
        has_prune = _present_or_explicit(record.get("prune_or_selection_reasons"))
        has_cost = _is_present(record.get("call_count")) and (
            _is_present(record.get("total_tokens"))
            or _is_present(record.get("estimated_cost"))
            or _is_present(record.get("latency_seconds"))
        )
        runtime_failure_reviewable = all([has_error, has_answer, has_trace, has_node_order, has_prune, has_cost])
        if not runtime_failure_reviewable:
            notes.append("runtime_failure_not_reviewable_due_to_missing_failure_state")

    # Sufficiency level
    if missing_required:
        notes.append("record_missing_required_fields")
    if missing_critical:
        notes.append("record_missing_critical_fields")

    if runtime_failure and not runtime_failure_reviewable:
        enough = "no"
    elif not missing_required and not missing_critical:
        enough = "yes"
    elif len(missing_critical) <= 2 and len(missing_required) <= 8:
        enough = "partial"
    else:
        enough = "no"

    return {
        "enough_for_promotion_review": enough,
        "missing_required_fields": sorted(set(missing_required)),
        "missing_critical_fields": sorted(set(missing_critical)),
        "notes": notes,
        "runtime_failure_reviewable": "yes" if runtime_failure_reviewable else "no",
        "offline_eval_only_fields_present": offline_present,
        "offline_eval_only_fields_flagged": offline_flagged,
    }
