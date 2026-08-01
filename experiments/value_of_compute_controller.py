"""Value-of-compute controller scaffold (FIX-6 / LoVEC-1).

This module is strictly offline-analysis-safe:
- Runtime policy features are inference-available only.
- Gold/exact/correctness labels are excluded from policy state.
- Oracle helpers that use labels are kept separate and explicitly marked offline.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from experiments import support_aware_selector as sas

REQUIRED_METHODS = (
    "direct_reserve_semantic_frontier_v2",
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
)


def _to_result_metadata(row: dict[str, Any]) -> dict[str, Any]:
    rm = row.get("result_metadata")
    if isinstance(rm, dict):
        return rm
    if isinstance(rm, str):
        import json

        try:
            obj = json.loads(rm)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return {}
    return {}


def _norm(answer: Any) -> str | None:
    return sas._normalize_answer(answer)


def _method_map_from_group(row_or_group: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Normalize input to method->row mapping.

    Accepts either:
    - group mapping: {method_name: row_dict}
    - single row dict (treated as frontier-only group)
    """
    if not isinstance(row_or_group, dict):
        return {}

    # Group form: has any known method as key and dict row as value.
    if any(k in row_or_group for k in REQUIRED_METHODS):
        out: dict[str, dict[str, Any]] = {}
        for k, v in row_or_group.items():
            if k in REQUIRED_METHODS and isinstance(v, dict):
                out[k] = v
        if out:
            return out

    # Single-row fallback.
    method = row_or_group.get("method")
    if isinstance(method, str):
        return {method: row_or_group}
    return {}


def _extract_frontier_answer_clusters(frontier_row: dict[str, Any]) -> list[str]:
    """Extract parseable candidate answer clusters from frontier logs."""
    clusters: Counter[str] = Counter()

    for node in frontier_row.get("final_nodes") or []:
        if not isinstance(node, dict):
            continue
        for key in ("predicted_answer_normalized", "predicted_answer", "trace_extracted_answer"):
            n = _norm(node.get(key))
            if n:
                clusters[n] += 1

    rm = _to_result_metadata(frontier_row)

    # Selector candidate pool often holds canonicalized candidates.
    for cand in rm.get("selector_candidate_pool") or []:
        if not isinstance(cand, dict):
            continue
        for key in ("answer_group", "answer", "canonical_answer"):
            n = _norm(cand.get(key))
            if n:
                clusters[n] += 1

    # Action-trace extracted answers.
    for step in rm.get("action_trace") or []:
        if not isinstance(step, dict):
            continue
        n = _norm(step.get("answer") or step.get("predicted_answer") or step.get("trace_extracted_answer"))
        if n:
            clusters[n] += 1

    # Keep deterministic order: most support first, then lexical.
    ordered = sorted(clusters.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ordered]


def _answer_lengths(state_answer: str | None) -> int | None:
    if state_answer is None:
        return None
    return len(str(state_answer))


def extract_lovec_state_features(row_or_group: dict[str, Any]) -> dict[str, Any]:
    """Extract inference-available LoVEC state features.

    Forbidden runtime-label fields (gold/exact/correctness/example_id/artifact path)
    are intentionally excluded.
    """
    method_map = _method_map_from_group(row_or_group)
    frontier_row = method_map.get("direct_reserve_semantic_frontier_v2", {})
    rm = _to_result_metadata(frontier_row)

    ext_answers = {
        "external_l1_max": method_map.get("external_l1_max", {}).get("final_answer_canonical"),
        "external_s1_budget_forcing": method_map.get("external_s1_budget_forcing", {}).get("final_answer_canonical"),
        "external_tale_prompt_budgeting": method_map.get("external_tale_prompt_budgeting", {}).get("final_answer_canonical"),
    }

    fix24_row = (
        sas.apply_combined_fix24_to_row(frontier_row, external_answers=ext_answers)
        if frontier_row
        else {}
    )

    base_policy_answer = _norm(fix24_row.get("combined24_answer_canonical"))
    tale_answer = _norm(ext_answers.get("external_tale_prompt_budgeting"))
    l1_answer = _norm(ext_answers.get("external_l1_max"))
    s1_answer = _norm(ext_answers.get("external_s1_budget_forcing"))
    frontier_answer = _norm(
        frontier_row.get("final_answer_canonical")
        or frontier_row.get("selected_answer_canonical")
    )

    sig = sas.external_agreement_signature(ext_answers)
    all_externals_agree = sig == "l1=s1=tale"
    tale_isolated = sas.is_tale_isolated(ext_answers)
    frontier_agrees_l1_s1 = bool(frontier_answer and l1_answer and s1_answer and frontier_answer == l1_answer == s1_answer)
    frontier_agrees_any_external = bool(
        frontier_answer and any(frontier_answer == a for a in (l1_answer, s1_answer, tale_answer) if a)
    )

    unique_external_answer_count = len({a for a in (l1_answer, s1_answer, tale_answer) if a})
    override_reason = str(rm.get("override_reason", "") or "")
    support_margin_raw = rm.get("support_margin")
    try:
        support_margin = float(support_margin_raw) if support_margin_raw is not None else None
    except (TypeError, ValueError):
        support_margin = None

    candidate_count = rm.get("candidate_pool_answer_group_count")
    if candidate_count is None:
        candidate_count = rm.get("selector_candidate_answer_group_count")
    try:
        candidate_count = int(candidate_count) if candidate_count is not None else None
    except (TypeError, ValueError):
        candidate_count = None

    final_nodes = frontier_row.get("final_nodes")
    final_node_count = len(final_nodes) if isinstance(final_nodes, list) else None

    node_expansion_order = frontier_row.get("node_expansion_order")
    if not isinstance(node_expansion_order, list):
        node_expansion_order = rm.get("node_expansion_order")
    node_expansion_order_len = len(node_expansion_order) if isinstance(node_expansion_order, list) else None

    action_trace = rm.get("action_trace")
    action_trace_len = len(action_trace) if isinstance(action_trace, list) else None

    answer_clusters = _extract_frontier_answer_clusters(frontier_row)
    answer_diversity_cluster_count = len(answer_clusters)

    pr = frontier_row.get("promotion_review_record")
    trace_length_chars = None
    if isinstance(pr, dict):
        candidate_trace = pr.get("candidate_trace")
        if isinstance(candidate_trace, str):
            trace_length_chars = len(candidate_trace)
    if trace_length_chars is None and isinstance(action_trace, list):
        trace_length_chars = sum(
            len(str(step.get("reasoning_text", "")))
            for step in action_trace
            if isinstance(step, dict)
        ) or None

    calibrated_percentile = None
    if isinstance(pr, dict):
        calibrated_percentile = pr.get("calibrated_percentile")
    if calibrated_percentile is None:
        calibrated_percentile = rm.get("calibrated_percentile")
    try:
        calibrated_percentile = float(calibrated_percentile) if calibrated_percentile is not None else None
    except (TypeError, ValueError):
        calibrated_percentile = None

    low_depth_flag = sas.is_low_depth_risk(rm)
    weak_search_flag = bool(
        low_depth_flag
        or (candidate_count is not None and candidate_count <= 2)
        or (final_node_count is not None and final_node_count <= 3)
    )

    state = {
        "base_policy": sas.COMBINED_FIX24_POLICY_NAME,
        "base_policy_answer_canonical": base_policy_answer,
        "tale_answer_canonical": tale_answer,
        "l1_answer_canonical": l1_answer,
        "s1_answer_canonical": s1_answer,
        "frontier_answer_canonical": frontier_answer,
        "external_agreement_signature": sig,
        "all_externals_agree": all_externals_agree,
        "tale_isolated": tale_isolated,
        "frontier_agrees_l1_s1": frontier_agrees_l1_s1,
        "frontier_agrees_any_external": frontier_agrees_any_external,
        "unique_external_answer_count": unique_external_answer_count,
        "base_policy_differs_from_tale": bool(base_policy_answer and tale_answer and base_policy_answer != tale_answer),
        "override_reason": override_reason,
        "low_depth_flag": low_depth_flag,
        "weak_search_flag": weak_search_flag,
        "support_margin": support_margin,
        "direct_frontier_agree_flag": bool(rm.get("direct_frontier_agree") or override_reason == "direct_frontier_agree"),
        "candidate_count": candidate_count,
        "final_node_count": final_node_count,
        "node_expansion_order_len": node_expansion_order_len,
        "action_trace_len": action_trace_len,
        "answer_diversity_cluster_count": answer_diversity_cluster_count,
        "trace_length_chars": trace_length_chars,
        "answer_length_chars": _answer_lengths(base_policy_answer),
        "input_tokens": frontier_row.get("input_tokens"),
        "output_tokens": frontier_row.get("output_tokens"),
        "total_tokens": frontier_row.get("total_tokens"),
        "estimated_cost_usd": frontier_row.get("estimated_cost_usd"),
        "cohere_logical_api_calls": frontier_row.get("cohere_logical_api_calls"),
        "latency_seconds": frontier_row.get("latency_seconds"),
        "retry_attempts": frontier_row.get("retry_attempts"),
        "calibrated_percentile": calibrated_percentile,
        # Helpful internal trace for action construction.
        "_frontier_answer_clusters": answer_clusters,
    }
    return state


def available_lovec_actions(group: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Compute observable action availability from existing logs only."""
    method_map = _method_map_from_group(group)
    state = extract_lovec_state_features(method_map)
    base = state.get("base_policy_answer_canonical")

    ext_answers = {
        "external_l1_max": method_map.get("external_l1_max", {}).get("final_answer_canonical"),
        "external_s1_budget_forcing": method_map.get("external_s1_budget_forcing", {}).get("final_answer_canonical"),
        "external_tale_prompt_budgeting": method_map.get("external_tale_prompt_budgeting", {}).get("final_answer_canonical"),
    }

    majority_ans, majority_meta = sas.select_external_majority(ext_answers)
    majority_ans = _norm(majority_ans)

    frontier_alts = [a for a in state.get("_frontier_answer_clusters", []) if a and a != base]

    ext_vals = [_norm(ext_answers[m]) for m in REQUIRED_METHODS[1:]]
    ext_vals = [v for v in ext_vals if v]
    ext_counts = Counter(ext_vals)
    ext_alt_order = [
        ans
        for ans, _ in sorted(ext_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        if ans != base
    ]

    actions: dict[str, dict[str, Any]] = {
        "stop_fix24": {
            "available": bool(base),
            "candidate_answer": base,
            "reason": "base_policy_default",
        },
        "stop_tale": {
            "available": bool(state.get("tale_answer_canonical")),
            "candidate_answer": state.get("tale_answer_canonical"),
            "reason": "tale_observed",
        },
        "stop_external_consensus": {
            "available": bool(majority_ans),
            "candidate_answer": majority_ans,
            "reason": str(majority_meta.get("reason", "no_majority")) if isinstance(majority_meta, dict) else "no_majority",
        },
        "logged_frontier_alternative_proxy": {
            "available": bool(frontier_alts),
            "candidate_answer": frontier_alts[0] if frontier_alts else None,
            "reason": "frontier_alternative_in_logs" if frontier_alts else "no_frontier_alternative_in_logs",
        },
        "logged_external_alternative_proxy": {
            "available": bool(ext_alt_order),
            "candidate_answer": ext_alt_order[0] if ext_alt_order else None,
            "reason": "external_alternative_in_logs" if ext_alt_order else "no_external_alternative_in_logs",
        },
    }

    non_default = any(
        actions[name]["available"]
        for name in ("logged_frontier_alternative_proxy", "logged_external_alternative_proxy")
    )
    actions["no_observable_extra_action"] = {
        "available": not non_default,
        "candidate_answer": base,
        "reason": "no_logged_alternative_available" if not non_default else "logged_alternatives_available",
    }
    return actions


def choose_lovec_action_v1(
    state: dict[str, Any],
    available_actions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Choose LoVEC-1 action.

    Current version is a conservative scaffold:
    - Default to FIX-2+FIX-4 answer.
    - Do not switch to proxy alternatives until extra-action payoff is validated
      on disjoint pilot data.
    """
    base = state.get("base_policy_answer_canonical")
    stop_fix24 = available_actions.get("stop_fix24", {})
    if stop_fix24.get("available") and base:
        return {
            "chosen_action": "stop_fix24",
            "chosen_answer": base,
            "action_changed": False,
            "reason": "skeleton_default_fix24",
        }

    if available_actions.get("stop_tale", {}).get("available"):
        return {
            "chosen_action": "stop_tale",
            "chosen_answer": available_actions["stop_tale"].get("candidate_answer"),
            "action_changed": True,
            "reason": "fallback_tale_missing_fix24",
        }

    return {
        "chosen_action": "no_observable_extra_action",
        "chosen_answer": base,
        "action_changed": False,
        "reason": "no_safe_observable_action",
    }


def apply_lovec1_controller(group: dict[str, Any]) -> dict[str, Any]:
    """Apply LoVEC-1 controller to one method-group record."""
    method_map = _method_map_from_group(group)
    state = extract_lovec_state_features(method_map)
    actions = available_lovec_actions(method_map)
    choice = choose_lovec_action_v1(state, actions)

    return {
        "lovec_policy": "lovec1_skeleton_fix24_default_v1",
        "lovec_policy_version": "1.0",
        "lovec_answer_canonical": _norm(choice.get("chosen_answer")),
        "lovec_action": choice.get("chosen_action"),
        "lovec_action_changed": bool(choice.get("action_changed")),
        "lovec_reason": choice.get("reason"),
        "state": state,
        "available_actions": actions,
    }


def observable_action_answer_table(group: dict[str, Any]) -> dict[str, str | None]:
    """Return observable action->answer table (label-free)."""
    actions = available_lovec_actions(group)
    return {
        name: _norm(meta.get("candidate_answer")) if meta.get("available") else None
        for name, meta in actions.items()
        if name != "no_observable_extra_action"
    }


def choose_oracle_observable_action_offline(
    group: dict[str, Any],
    gold_answer: Any,
) -> dict[str, Any]:
    """Offline-only oracle among observable actions.

    Uses gold label only for analysis/evaluation. Never call this in runtime policy.
    """
    gold = _norm(gold_answer)
    table = observable_action_answer_table(group)

    best_action = None
    best_answer = None
    best_correct = False
    for action_name in (
        "stop_fix24",
        "stop_tale",
        "stop_external_consensus",
        "logged_frontier_alternative_proxy",
        "logged_external_alternative_proxy",
    ):
        ans = table.get(action_name)
        if not ans:
            continue
        corr = bool(gold and ans == gold)
        if corr:
            best_action = action_name
            best_answer = ans
            best_correct = True
            break
        if best_action is None:
            best_action = action_name
            best_answer = ans

    return {
        "oracle_action": best_action,
        "oracle_answer_canonical": best_answer,
        "oracle_correct": best_correct,
        "gold_answer_canonical": gold,
    }
