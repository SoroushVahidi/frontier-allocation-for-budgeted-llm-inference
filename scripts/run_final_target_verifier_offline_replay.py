#!/usr/bin/env python3
"""Offline replay for final-target binding checks on rich trace packets.

This is gold-free in the selection path and does not call any external API.
It replays a deterministic candidate-pool re-rank using the existing
final-target verifier and structural target features, then reports proxy
improvement metrics on the same rich packets used for pattern mining.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.final_target_verifier import final_target_verifier_features, select_with_final_target_verifier_v1
from experiments.selector_error_features import build_structural_target_feature_row
from experiments.frontier_max_support_tiebreak import normalize_answer_group_key


DEFAULT_TRACE_PACKETS = Path("/tmp/codex_pattern_mining_wrong_consensus_97_packets/trace_packets.jsonl")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "final_target_verifier_offline_replay_latest"
CALIBRATED_V1_ALLOWED_TARGET_TYPES = {"difference", "rate", "remaining", "total", "ratio_part"}
CALIBRATED_V1_ALLOWED_SOURCES = {"our_candidate", "retry_candidate"}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        text = _stringify(value)
        if not text:
            return default
        return float(text)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        text = _stringify(value)
        if not text:
            return default
        return int(float(text))
    except Exception:
        return default


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return _stringify(value)


def _maybe_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str):
        return {}
    text = value.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _jsonable(row.get(k)) if isinstance(row.get(k), (dict, list)) else row.get(k, "") for k in fieldnames})


def _norm_answer(text: Any) -> str:
    return normalize_answer_group_key(_stringify(text))


def _case_trace_excerpt(case: dict[str, Any]) -> str:
    summary = case.get("action_trace_summary") or {}
    excerpt = summary.get("trace_excerpt") or []
    if not isinstance(excerpt, list):
        return ""
    parts: list[str] = []
    for item in excerpt:
        if not isinstance(item, dict):
            continue
        text = _stringify(item.get("reasoning_text") or item.get("extracted_answer") or "")
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _question_target_type(question: str, verifier_features: dict[str, Any]) -> str:
    if verifier_features.get("asks_difference"):
        return "difference"
    if verifier_features.get("asks_remaining"):
        return "remaining"
    if verifier_features.get("asks_ratio_part"):
        return "ratio_part"
    if verifier_features.get("asks_average_target"):
        return "average"
    if verifier_features.get("asks_total"):
        return "total"
    if verifier_features.get("asks_state_value"):
        return "entity_value"
    q = (question or "").lower()
    if any(tok in q for tok in (" per ", " mph", "/hour", "rate")):
        return "rate"
    return "entity_value"


def _looks_transformed_target_case(question: str, action_summary: dict[str, Any], verifier_features: dict[str, Any]) -> bool:
    q = (question or "").lower()
    cues = (
        verifier_features.get("asks_difference"),
        verifier_features.get("asks_remaining"),
        verifier_features.get("asks_ratio_part"),
        verifier_features.get("asks_total"),
        verifier_features.get("asks_average_target"),
        verifier_features.get("ratio_partition_risk"),
        verifier_features.get("percent_base_denominator_risk"),
        verifier_features.get("state_update_risk"),
    )
    if any(bool(cue) for cue in cues):
        return True
    return any(
        tok in q
        for tok in (
            "profit",
            "left over",
            "leftover",
            "difference",
            "remaining",
            "original",
            "before",
            "after",
            "convert",
            "percent",
            "percentage",
            "ratio",
            "per ",
            "how many more",
        )
    ) or "target" in _stringify(action_summary.get("latest_method_failure_tag")).lower()


def _case_focus_tag(question: str, selector_metadata: dict[str, Any], action_summary: dict[str, Any], verifier_features: dict[str, Any]) -> str:
    selected_source = _stringify(selector_metadata.get("selected_source"))
    baseline = _norm_answer(selector_metadata.get("selected_answer"))
    if selected_source == "repair_layer" and baseline == "1":
        return "repair_layer_collapse_to_1"
    if _looks_transformed_target_case(question, action_summary, verifier_features):
        return "mistargeted_final_transformation"
    return "other"


def _best_structural_row(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = case.get("structural_fields", {}).get("candidate_rows", [])
    best_by_answer: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return best_by_answer
    for row in rows:
        if not isinstance(row, dict):
            continue
        ans = _norm_answer(row.get("candidate_answer"))
        if not ans:
            continue
        current = best_by_answer.get(ans)
        score = _safe_float(row.get("structural_selector_score"), 0.0)
        if current is None or score > _safe_float(current.get("structural_selector_score"), 0.0):
            best_by_answer[ans] = dict(row)
    return best_by_answer


def _support_map(case: dict[str, Any]) -> dict[str, float]:
    support: dict[str, float] = {}
    groups = case.get("candidate_answer_groups") or []
    if isinstance(groups, list):
        for row in groups:
            if not isinstance(row, dict):
                continue
            ans = _norm_answer(row.get("candidate_answer"))
            if not ans:
                continue
            support[ans] = max(support.get(ans, 0.0), _safe_float(row.get("support_count"), 0.0))
    support_counts = case.get("answer_group_support_counts") or {}
    if isinstance(support_counts, dict):
        for ans, count in support_counts.items():
            ansn = _norm_answer(ans)
            if not ansn:
                continue
            support[ansn] = max(support.get(ansn, 0.0), _safe_float(count, 0.0))
    return support


def _candidate_source(candidate_answer: str, baseline: str, direct: str, frontier: str) -> str:
    if candidate_answer == _norm_answer(direct):
        return "retry_candidate"
    if candidate_answer == _norm_answer(frontier):
        return "our_candidate"
    if candidate_answer == _norm_answer(baseline):
        return "baseline_candidate"
    return "pal_candidate"


def _infer_candidate_role(
    *,
    candidate_answer: str,
    baseline: str,
    selected_source: str,
    row: dict[str, Any] | None,
    action_summary: dict[str, Any],
    transformed_focus: bool,
) -> str:
    if row:
        role = _stringify(row.get("final_answer_role") or row.get("candidate_role") or row.get("role"))
        if role in {"target", "intermediate"}:
            return role
    if candidate_answer == baseline and selected_source == "repair_layer":
        return "intermediate"
    if candidate_answer == baseline and transformed_focus and selected_source in {"repair_layer", "controller_metadata_final_answer"}:
        return "intermediate"
    if candidate_answer == "1" and selected_source == "repair_layer":
        return "intermediate"
    if "premature intermediate answer" in _stringify(action_summary.get("latest_method_failure_tag")).lower():
        return "intermediate" if candidate_answer == baseline else "target"
    return "target"


def _candidate_trace_and_code(case: dict[str, Any], row: dict[str, Any] | None) -> tuple[str, str]:
    case_trace = _case_trace_excerpt(case)
    if row:
        trace = _stringify(row.get("candidate_trace") or row.get("reasoning_text") or row.get("trace"))
        code = _stringify(row.get("candidate_code") or row.get("code"))
        return (trace or case_trace, code)
    return case_trace, ""


def _build_candidate_pool(case: dict[str, Any]) -> list[dict[str, Any]]:
    question = _stringify(case.get("question"))
    baseline = _norm_answer(case.get("model_final_prediction") or case.get("selector_metadata", {}).get("selected_answer"))
    direct = _norm_answer(case.get("direct_reserve_answer"))
    frontier = _norm_answer(case.get("frontier_candidate_answer"))
    selected_source = _stringify(case.get("selector_metadata", {}).get("selected_source"))
    action_summary = case.get("action_trace_summary") or {}
    verifier_features = final_target_verifier_features(question, candidate_answer_text=baseline, candidate_trace=_case_trace_excerpt(case))
    transformed_focus = _looks_transformed_target_case(question, action_summary, verifier_features)
    question_target_type = _question_target_type(question, verifier_features)
    structural_rows = _best_structural_row(case)
    support = _support_map(case)

    candidate_keys: list[str] = []
    for text in (baseline, direct, frontier):
        if text and text not in candidate_keys:
            candidate_keys.append(text)
    for item in case.get("candidate_answers") or []:
        text = _norm_answer(item)
        if text and text not in candidate_keys:
            candidate_keys.append(text)
    groups = case.get("candidate_answer_groups") or []
    if isinstance(groups, list):
        for row in groups:
            if not isinstance(row, dict):
                continue
            ans = _norm_answer(row.get("candidate_answer"))
            if ans and ans not in candidate_keys:
                candidate_keys.append(ans)

    if not candidate_keys and baseline:
        candidate_keys.append(baseline)

    candidates: list[dict[str, Any]] = []
    for candidate_answer in candidate_keys:
        row = structural_rows.get(candidate_answer)
        trace_text, code_text = _candidate_trace_and_code(case, row)
        support_count = max(
            support.get(candidate_answer, 0.0),
            _safe_float(row.get("support_count"), 0.0) if row else 0.0,
        )
        execution_metadata: dict[str, Any] = {}
        if row:
            ledger_proxy = _maybe_json_dict(row.get("entity_unit_ledger_proxy"))
            execution_metadata = {
                "final_answer_role": _stringify(row.get("final_answer_role")),
                "candidate_role": _stringify(row.get("candidate_role")),
                "source_family": _stringify(row.get("source_family")),
                "target_entity": _stringify(ledger_proxy.get("target_entity")),
                "target_unit": _stringify(ledger_proxy.get("target_unit")),
                "unit_consistency_status": _stringify(ledger_proxy.get("ledger_status")),
            }

        feature_row = build_structural_target_feature_row(
            question=question,
            candidate_trace=trace_text,
            candidate_code=code_text or None,
            candidate_answer=candidate_answer,
            execution_metadata=execution_metadata,
            support_count=max(1, int(round(support_count)) if support_count else 1),
        )
        role = _infer_candidate_role(
            candidate_answer=candidate_answer,
            baseline=baseline,
            selected_source=selected_source,
            row=row,
            action_summary=action_summary,
            transformed_focus=transformed_focus,
        )
        target_quantity_type = question_target_type if role != "intermediate" else "intermediate"
        source_kind = _candidate_source(candidate_answer, baseline, direct, frontier)
        source_rank = {"retry_candidate": 4, "our_candidate": 3, "baseline_candidate": 2, "pal_candidate": 1}.get(source_kind, 0)
        support_norm = min(1.0, support_count / 3.0) if support_count else 0.0
        confidence = max(
            0.0,
            min(
                1.0,
                0.45 * _safe_float(feature_row.get("structural_selector_score"), 0.0)
                + 0.30 * _safe_float(feature_row.get("target_alignment_score"), 0.0)
                + 0.15 * (1.0 - _safe_float(feature_row.get("intermediate_answer_penalty"), 0.0))
                + 0.05 * support_norm
                + 0.05 * (source_rank / 4.0),
            ),
        )
        combined_score = max(
            0.0,
            min(
                1.0,
                0.50 * _safe_float(feature_row.get("structural_selector_score"), 0.0)
                + 0.30 * _safe_float(feature_row.get("target_alignment_score"), 0.0)
                + 0.20 * (1.0 - _safe_float(feature_row.get("intermediate_answer_penalty"), 0.0)),
            ),
        )
        candidates.append(
            {
                "answer": candidate_answer,
                "source": source_kind,
                "source_rank": source_rank,
                "confidence": confidence,
                "target_quantity_type": target_quantity_type,
                "final_answer_role": role,
                "structural_selector_score": _safe_float(feature_row.get("structural_selector_score"), 0.0),
                "target_alignment_score": _safe_float(feature_row.get("target_alignment_score"), 0.0),
                "intermediate_answer_penalty": _safe_float(feature_row.get("intermediate_answer_penalty"), 0.0),
                "combined_proxy_score": combined_score,
                "support_count": support_count,
                "support_norm": support_norm,
                "candidate_trace": trace_text,
                "candidate_code": code_text,
                "selected_by_baseline": candidate_answer == baseline,
                "selected_by_direct": candidate_answer == direct,
                "selected_by_frontier": candidate_answer == frontier,
                "structural_row_present": bool(row),
                "structural_row": _jsonable(row) if row else {},
                "feature_row": _jsonable(feature_row),
            }
        )

    # keep the strongest candidate per answer
    deduped: dict[str, dict[str, Any]] = {}
    for cand in candidates:
        ans = cand["answer"]
        prev = deduped.get(ans)
        if prev is None or cand["combined_proxy_score"] > prev["combined_proxy_score"]:
            deduped[ans] = cand
    ordered = sorted(
        deduped.values(),
        key=lambda row: (
            -float(row.get("combined_proxy_score", 0.0)),
            -float(row.get("confidence", 0.0)),
            -int(row.get("source_rank", 0)),
            str(row.get("answer", "")),
        ),
    )
    return ordered


def _select_with_verifier(case: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    question = _stringify(case.get("question"))
    baseline = _norm_answer(case.get("model_final_prediction") or case.get("selector_metadata", {}).get("selected_answer"))
    case_trace = _case_trace_excerpt(case)
    verifier_features = final_target_verifier_features(question, candidate_answer_text=baseline, candidate_trace=case_trace)
    question_target_type = _question_target_type(question, verifier_features)
    selector_candidates = [
        {
            "answer": cand["answer"],
            "source": cand["source"],
            "confidence": cand["confidence"],
            "target_quantity_type": cand["target_quantity_type"],
        }
        for cand in candidates
    ]
    selector_meta: dict[str, Any] = {}
    verifier_choice = select_with_final_target_verifier_v1(selector_candidates, question, verifier_features, selector_meta)
    chosen_answer = _norm_answer(verifier_choice.get("selected_answer") or baseline)
    chosen_source = _stringify(verifier_choice.get("selected_source") or "baseline_candidate")
    chosen_candidate = next((cand for cand in candidates if cand["answer"] == chosen_answer), None)

    # Structural fallback: if the verifier keeps a weak baseline but another candidate
    # has a clearly stronger proxy score and no worse target alignment, use it.
    if chosen_candidate is None and candidates:
        chosen_candidate = candidates[0]

    if candidates:
        best_structural = candidates[0]
        baseline_candidate = next((cand for cand in candidates if cand["answer"] == baseline), None)
        if best_structural and baseline_candidate:
            if (
                best_structural["answer"] != baseline
                and best_structural["combined_proxy_score"] >= baseline_candidate["combined_proxy_score"]
                and best_structural["target_alignment_score"] >= baseline_candidate["target_alignment_score"]
            ):
                chosen_candidate = best_structural
                chosen_answer = best_structural["answer"]
                chosen_source = _stringify(best_structural["source"])

    if chosen_candidate is None:
        return {
            "verifier_selected_answer": baseline,
            "verifier_selected_source": "baseline_candidate",
            "verifier_selected_candidate": {},
            "verifier_selected_reason": "no_candidates",
            "question_target_type": question_target_type,
            "verifier_features": verifier_features,
            "selector_metadata": selector_meta,
        }

    return {
        "verifier_selected_answer": chosen_answer,
        "verifier_selected_source": chosen_source,
        "verifier_selected_candidate": chosen_candidate,
        "verifier_selected_reason": _stringify(verifier_choice.get("selection_reason") or "target_finalization"),
        "question_target_type": question_target_type,
        "verifier_features": verifier_features,
        "selector_metadata": selector_meta,
    }


def _retained_baseline_selection(
    case: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    selected_reason: str,
    verifier_features: dict[str, Any],
    question_target_type: str,
    selector_meta: dict[str, Any],
) -> dict[str, Any]:
    baseline = _norm_answer(case.get("model_final_prediction") or case.get("selector_metadata", {}).get("selected_answer"))
    baseline_candidate = next((cand for cand in candidates if cand["answer"] == baseline), None)
    if baseline_candidate is None and candidates:
        baseline_candidate = candidates[0]
    return {
        "verifier_selected_answer": baseline,
        "verifier_selected_source": "baseline_candidate",
        "verifier_selected_candidate": baseline_candidate or {},
        "verifier_selected_reason": selected_reason,
        "question_target_type": question_target_type,
        "verifier_features": verifier_features,
        "selector_metadata": selector_meta,
    }


def _select_with_verifier_calibrated_v1(case: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    chosen = _select_with_verifier(case, candidates)
    selected_answer = _norm_answer(chosen.get("verifier_selected_answer"))
    baseline = _norm_answer(case.get("model_final_prediction") or case.get("selector_metadata", {}).get("selected_answer"))
    selector_metadata = chosen.get("selector_metadata") or {}
    if selected_answer == baseline:
        return chosen

    chosen_candidate = chosen.get("verifier_selected_candidate") or {}
    selected_source = _stringify(chosen.get("verifier_selected_source"))
    question_target_type = _stringify(chosen.get("question_target_type"))
    baseline_source = _stringify(case.get("selector_metadata", {}).get("selected_source"))

    if (
        selected_source not in CALIBRATED_V1_ALLOWED_SOURCES
        or question_target_type not in CALIBRATED_V1_ALLOWED_TARGET_TYPES
        or _stringify(chosen_candidate.get("final_answer_role")) != "target"
        or (baseline_source == "repair_layer" and baseline == "1")
    ):
        return _retained_baseline_selection(
            case,
            candidates,
            selected_reason="calibrated_v1_baseline_retained",
            verifier_features=chosen.get("verifier_features") or {},
            question_target_type=question_target_type,
            selector_meta=selector_metadata,
        )

    return {
        **chosen,
        "verifier_selected_reason": "calibrated_v1_accept",
    }


def _packet_completeness_summary(case_rows: list[dict[str, Any]], *, min_completeness: float) -> dict[str, Any]:
    total = len(case_rows)
    subset_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    question_present = prediction_present = candidate_pool_present = action_trace_present = pal_execution_present = structural_present = 0
    empty_packet_count = 0

    def _action_present(summary: dict[str, Any]) -> bool:
        excerpt = summary.get("trace_excerpt") or []
        if isinstance(excerpt, list) and excerpt:
            return True
        return any(_stringify(v) for v in summary.values())

    def _pal_present(summary: dict[str, Any]) -> bool:
        return any(_stringify(v) for v in summary.values())

    for case in case_rows:
        subset = _stringify(case.get("primary_subset")) or "unknown"
        subset_counts[subset]["case_count"] += 1
        has_question = bool(_stringify(case.get("question")))
        has_prediction = bool(_stringify(case.get("model_final_prediction")))
        has_candidate_pool = bool(case.get("candidate_answers") or case.get("candidate_answer_groups") or case.get("selector_candidate_pool"))
        has_action = _action_present(case.get("action_trace_summary") or {})
        has_pal = _pal_present(case.get("pal_exec_summary") or {})
        has_structural = bool(case.get("structural_fields"))
        question_present += int(has_question)
        prediction_present += int(has_prediction)
        candidate_pool_present += int(has_candidate_pool)
        action_trace_present += int(has_action)
        pal_execution_present += int(has_pal)
        structural_present += int(has_structural)
        subset_counts[subset]["question_present_count"] += int(has_question)
        subset_counts[subset]["prediction_present_count"] += int(has_prediction)
        subset_counts[subset]["candidate_pool_present_count"] += int(has_candidate_pool)
        subset_counts[subset]["action_trace_present_count"] += int(has_action)
        subset_counts[subset]["pal_execution_present_count"] += int(has_pal)
        subset_counts[subset]["structural_fields_present_count"] += int(has_structural)
        if not any((has_question, has_prediction, has_candidate_pool, has_action, has_pal, has_structural)):
            empty_packet_count += 1
            subset_counts[subset]["empty_packet_count"] += 1

    def rate(count: int) -> float:
        return round(count / max(1, total), 6)

    per_subset: dict[str, dict[str, Any]] = {}
    for subset, counts in subset_counts.items():
        subset_total = counts.get("case_count", 0)
        per_subset[subset] = {
            "case_count": subset_total,
            "question_present_rate": round(counts.get("question_present_count", 0) / max(1, subset_total), 6),
            "prediction_present_rate": round(counts.get("prediction_present_count", 0) / max(1, subset_total), 6),
            "candidate_pool_present_rate": round(counts.get("candidate_pool_present_count", 0) / max(1, subset_total), 6),
            "action_trace_present_rate": round(counts.get("action_trace_present_count", 0) / max(1, subset_total), 6),
            "pal_execution_present_rate": round(counts.get("pal_execution_present_count", 0) / max(1, subset_total), 6),
            "structural_fields_present_rate": round(counts.get("structural_fields_present_count", 0) / max(1, subset_total), 6),
            "empty_packet_count": counts.get("empty_packet_count", 0),
        }

    warnings: list[str] = []
    if total:
        if rate(question_present) < min_completeness:
            warnings.append(f"question_present_rate={rate(question_present):.3f} is below min completeness {min_completeness:.3f}")
        if rate(prediction_present) < min_completeness:
            warnings.append(f"prediction_present_rate={rate(prediction_present):.3f} is below min completeness {min_completeness:.3f}")

    return {
        "case_count": total,
        "min_packet_completeness": round(min_completeness, 6),
        "question_present_rate": rate(question_present),
        "prediction_present_rate": rate(prediction_present),
        "candidate_pool_present_rate": rate(candidate_pool_present),
        "action_trace_present_rate": rate(action_trace_present),
        "pal_execution_present_rate": rate(pal_execution_present),
        "structural_fields_present_rate": rate(structural_present),
        "empty_packet_count": empty_packet_count,
        "per_subset": per_subset,
        "warnings": warnings,
    }


def _load_cases(trace_packets_path: Path) -> list[dict[str, Any]]:
    case_rows: list[dict[str, Any]] = []
    for packet in _read_jsonl_rows(trace_packets_path):
        if isinstance(packet.get("cases"), list):
            for case in packet["cases"]:
                if isinstance(case, dict):
                    case_rows.append(dict(case))
        elif isinstance(packet, dict) and packet.get("case_id"):
            case_rows.append(dict(packet))
    return case_rows


def _replay_case(case: dict[str, Any], *, variant: str = "v1") -> dict[str, Any]:
    question = _stringify(case.get("question"))
    baseline = _norm_answer(case.get("model_final_prediction") or case.get("selector_metadata", {}).get("selected_answer"))
    selected_source = _stringify(case.get("selector_metadata", {}).get("selected_source"))
    direct = _norm_answer(case.get("direct_reserve_answer"))
    frontier = _norm_answer(case.get("frontier_candidate_answer"))
    action_summary = case.get("action_trace_summary") or {}
    verifier_features = final_target_verifier_features(question, candidate_answer_text=baseline, candidate_trace=_case_trace_excerpt(case))
    transformed_focus = _looks_transformed_target_case(question, action_summary, verifier_features)
    focus_tag = _case_focus_tag(question, case.get("selector_metadata", {}) or {}, action_summary, verifier_features)
    candidates = _build_candidate_pool(case)
    if variant == "calibrated_v1":
        chosen = _select_with_verifier_calibrated_v1(case, candidates)
    else:
        chosen = _select_with_verifier(case, candidates)

    baseline_candidate = next((cand for cand in candidates if cand["answer"] == baseline), None)
    chosen_candidate = chosen.get("verifier_selected_candidate") or {}
    baseline_role = _stringify(baseline_candidate.get("final_answer_role")) if baseline_candidate else ""
    replay_role = _stringify(chosen_candidate.get("final_answer_role")) if chosen_candidate else ""
    baseline_score = _safe_float(baseline_candidate.get("combined_proxy_score"), 0.0) if baseline_candidate else 0.0
    replay_score = _safe_float(chosen_candidate.get("combined_proxy_score"), 0.0) if chosen_candidate else 0.0
    baseline_target_align = _safe_float(baseline_candidate.get("target_alignment_score"), 0.0) if baseline_candidate else 0.0
    replay_target_align = _safe_float(chosen_candidate.get("target_alignment_score"), 0.0) if chosen_candidate else 0.0
    baseline_intermediate_penalty = _safe_float(baseline_candidate.get("intermediate_answer_penalty"), 0.0) if baseline_candidate else 0.0
    replay_intermediate_penalty = _safe_float(chosen_candidate.get("intermediate_answer_penalty"), 0.0) if chosen_candidate else 0.0
    structural_choice = candidates[0] if candidates else {}
    structural_answer = _stringify(structural_choice.get("answer"))
    structural_score = _safe_float(structural_choice.get("combined_proxy_score"), 0.0) if structural_choice else 0.0

    return {
        "case_id": _stringify(case.get("case_id")),
        "primary_subset": _stringify(case.get("primary_subset")),
        "question": question,
        "question_target_type": _stringify(chosen.get("question_target_type")),
        "baseline_answer": baseline,
        "baseline_selected_source": selected_source,
        "verifier_answer": _stringify(chosen.get("verifier_selected_answer") or baseline),
        "verifier_selected_source": _stringify(chosen.get("verifier_selected_source") or ""),
        "combined_answer": _stringify(chosen.get("verifier_selected_answer") or baseline),
        "structural_best_answer": structural_answer,
        "candidate_count": len(candidates),
        "target_candidate_count": sum(1 for cand in candidates if _stringify(cand.get("final_answer_role")) == "target"),
        "intermediate_candidate_count": sum(1 for cand in candidates if _stringify(cand.get("final_answer_role")) == "intermediate"),
        "baseline_final_answer_role": baseline_role,
        "replay_final_answer_role": replay_role,
        "baseline_combined_proxy_score": baseline_score,
        "replay_combined_proxy_score": replay_score,
        "baseline_target_alignment_score": baseline_target_align,
        "replay_target_alignment_score": replay_target_align,
        "baseline_intermediate_answer_penalty": baseline_intermediate_penalty,
        "replay_intermediate_answer_penalty": replay_intermediate_penalty,
        "combined_replay_changed": baseline != _stringify(chosen.get("verifier_selected_answer") or baseline),
        "proxy_alignment_improved": replay_target_align > baseline_target_align + 1e-12,
        "proxy_score_improved": replay_score > baseline_score + 1e-12,
        "focus_tag": focus_tag,
        "transformed_focus": transformed_focus,
        "repair_layer_collapse_to_1": selected_source == "repair_layer" and baseline == "1",
        "selected_source": selected_source,
        "selection_variant": variant,
        "direct_reserve_answer": direct,
        "frontier_candidate_answer": frontier,
        "candidates": candidates,
        "verifier_features": _jsonable(verifier_features),
        "verifier_metadata": _jsonable(chosen.get("selector_metadata") or {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline replay for final-target binding failure patterns (no API calls).")
    parser.add_argument("--trace-packets", default=str(DEFAULT_TRACE_PACKETS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--min-packet-completeness", type=float, default=0.75)
    parser.add_argument("--case-limit", type=int, default=None)
    parser.add_argument("--variant", choices=("v1", "calibrated_v1"), default="v1")
    args = parser.parse_args()

    trace_packets_path = Path(args.trace_packets)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    min_packet_completeness = float(args.min_packet_completeness)
    if not (0.0 <= min_packet_completeness <= 1.0):
        raise SystemExit("--min-packet-completeness must be within [0, 1]")

    case_rows = _load_cases(trace_packets_path)
    if args.case_limit is not None:
        case_rows = case_rows[: max(0, int(args.case_limit))]
    packet_completeness = _packet_completeness_summary(case_rows, min_completeness=min_packet_completeness)

    replay_rows = [_replay_case(case, variant=args.variant) for case in case_rows]
    casebook_rows: list[dict[str, Any]] = []
    replay_jsonl_rows: list[dict[str, Any]] = []

    proxy_improved_count = 0
    proxy_score_improved_count = 0
    replay_changed_count = 0
    transformed_focus_count = 0
    transformed_focus_replay_changed = 0
    transformed_focus_proxy_improved = 0
    repair_layer_collapse_count = 0
    repair_layer_non_1_count = 0

    baseline_source_counts: Counter[str] = Counter()
    replay_source_counts: Counter[str] = Counter()
    focus_tag_counts: Counter[str] = Counter()

    for row in replay_rows:
        baseline_source_counts[_stringify(row.get("baseline_selected_source"))] += 1
        replay_source_counts[_stringify(row.get("verifier_selected_source"))] += 1
        focus_tag_counts[_stringify(row.get("focus_tag"))] += 1
        if row.get("proxy_alignment_improved"):
            proxy_improved_count += 1
        if row.get("proxy_score_improved"):
            proxy_score_improved_count += 1
        if row.get("combined_replay_changed"):
            replay_changed_count += 1
        if row.get("transformed_focus"):
            transformed_focus_count += 1
            if row.get("combined_replay_changed"):
                transformed_focus_replay_changed += 1
            if row.get("proxy_alignment_improved"):
                transformed_focus_proxy_improved += 1
        if row.get("repair_layer_collapse_to_1"):
            repair_layer_collapse_count += 1
            if _norm_answer(row.get("combined_answer")) != "1":
                repair_layer_non_1_count += 1

        casebook_row = {
            "case_id": row["case_id"],
            "primary_subset": row["primary_subset"],
            "focus_tag": row["focus_tag"],
            "question_target_type": row["question_target_type"],
            "baseline_answer": row["baseline_answer"],
            "verifier_answer": row["verifier_answer"],
            "combined_answer": row["combined_answer"],
            "structural_best_answer": row["structural_best_answer"],
            "baseline_selected_source": row["baseline_selected_source"],
            "verifier_selected_source": row["verifier_selected_source"],
            "baseline_final_answer_role": row["baseline_final_answer_role"],
            "replay_final_answer_role": row["replay_final_answer_role"],
            "candidate_count": row["candidate_count"],
            "target_candidate_count": row["target_candidate_count"],
            "intermediate_candidate_count": row["intermediate_candidate_count"],
            "baseline_combined_proxy_score": row["baseline_combined_proxy_score"],
            "replay_combined_proxy_score": row["replay_combined_proxy_score"],
            "baseline_target_alignment_score": row["baseline_target_alignment_score"],
            "replay_target_alignment_score": row["replay_target_alignment_score"],
            "baseline_intermediate_answer_penalty": row["baseline_intermediate_answer_penalty"],
            "replay_intermediate_answer_penalty": row["replay_intermediate_answer_penalty"],
            "combined_replay_changed": row["combined_replay_changed"],
            "proxy_alignment_improved": row["proxy_alignment_improved"],
            "proxy_score_improved": row["proxy_score_improved"],
            "repair_layer_collapse_to_1": row["repair_layer_collapse_to_1"],
            "transformed_focus": row["transformed_focus"],
        }
        casebook_rows.append(casebook_row)
        replay_jsonl_rows.append(row)

    baseline_top_role_rate = sum(1 for row in replay_rows if _stringify(row.get("baseline_final_answer_role")) == "target") / max(1, len(replay_rows))
    replay_top_role_rate = sum(1 for row in replay_rows if _stringify(row.get("replay_final_answer_role")) == "target") / max(1, len(replay_rows))

    summary = {
        "created_at_utc": _utc_stamp(),
        "trace_packets_path": str(trace_packets_path),
        "output_dir": str(output_dir),
        "case_count": len(replay_rows),
        "variant": args.variant,
        "packet_completeness_summary": packet_completeness,
        "baseline_target_role_rate": round(baseline_top_role_rate, 6),
        "replay_target_role_rate": round(replay_top_role_rate, 6),
        "proxy_alignment_improved_count": proxy_improved_count,
        "proxy_score_improved_count": proxy_score_improved_count,
        "replay_changed_count": replay_changed_count,
        "focus_tag_counts": dict(sorted(focus_tag_counts.items(), key=lambda item: (-item[1], item[0]))),
        "transformed_focus_count": transformed_focus_count,
        "transformed_focus_replay_changed_count": transformed_focus_replay_changed,
        "transformed_focus_proxy_improved_count": transformed_focus_proxy_improved,
        "repair_layer_collapse_count": repair_layer_collapse_count,
        "repair_layer_non_1_count": repair_layer_non_1_count,
        "baseline_selected_source_counts": dict(sorted(baseline_source_counts.items(), key=lambda item: (-item[1], item[0]))),
        "replay_selected_source_counts": dict(sorted(replay_source_counts.items(), key=lambda item: (-item[1], item[0]))),
        "notes": [
            "Selection is gold-free; any gold answer would only be used for optional external reporting, not replay decisions.",
            "This replay is diagnostic and does not claim improvement over external_l1_max.",
        ],
    }

    manifest = {
        "experiment_id": "final_target_verifier_offline_replay",
        "variant": args.variant,
        "created_at_utc": summary["created_at_utc"],
        "inputs": {
            "trace_packets": str(trace_packets_path),
            "case_limit": args.case_limit,
            "min_packet_completeness": min_packet_completeness,
        },
        "outputs": [
            "manifest.json",
            "replay_casebook.csv",
            "replay_casebook.jsonl",
            "replay_summary.json",
            "replay_report.md",
            "packet_completeness_summary.json",
        ],
        "no_api_calls": True,
        "gold_free_selection": True,
        "proxy_only_evaluation": True,
    }

    _write_json(output_dir / "manifest.json", manifest)
    _write_json(output_dir / "replay_summary.json", summary)
    _write_json(output_dir / "packet_completeness_summary.json", packet_completeness)
    _write_csv(output_dir / "replay_casebook.csv", casebook_rows)
    _write_jsonl(output_dir / "replay_casebook.jsonl", replay_jsonl_rows)

    report_lines = [
        "# Final-target verifier offline replay",
        "",
        f"- trace_packets: `{trace_packets_path}`",
        f"- output_dir: `{output_dir}`",
        f"- variant: `{args.variant}`",
        f"- cases: `{len(replay_rows)}`",
        f"- baseline_target_role_rate: `{summary['baseline_target_role_rate']}`",
        f"- replay_target_role_rate: `{summary['replay_target_role_rate']}`",
        f"- proxy_alignment_improved_count: `{proxy_improved_count}`",
        f"- proxy_score_improved_count: `{proxy_score_improved_count}`",
        f"- replay_changed_count: `{replay_changed_count}`",
        f"- transformed_focus_count: `{transformed_focus_count}`",
        f"- transformed_focus_replay_changed_count: `{transformed_focus_replay_changed}`",
        f"- transformed_focus_proxy_improved_count: `{transformed_focus_proxy_improved}`",
        f"- repair_layer_collapse_count: `{repair_layer_collapse_count}`",
        f"- repair_layer_non_1_count: `{repair_layer_non_1_count}`",
        "",
        "## Packet Completeness",
        f"- question_present_rate: `{packet_completeness['question_present_rate']}`",
        f"- prediction_present_rate: `{packet_completeness['prediction_present_rate']}`",
        f"- candidate_pool_present_rate: `{packet_completeness['candidate_pool_present_rate']}`",
        f"- action_trace_present_rate: `{packet_completeness['action_trace_present_rate']}`",
        f"- pal_execution_present_rate: `{packet_completeness['pal_execution_present_rate']}`",
        f"- structural_fields_present_rate: `{packet_completeness['structural_fields_present_rate']}`",
        f"- empty_packet_count: `{packet_completeness['empty_packet_count']}`",
        "",
        "## Claim Boundary",
        "- This replay is proxy-based and gold-free in the selection path.",
        "- It tests whether a final-target binding verifier can shift selections toward stronger final-target candidates.",
        "- It does not claim benchmark superiority or any improvement over `external_l1_max`.",
    ]
    if packet_completeness.get("warnings"):
        report_lines.extend(["", "## Warnings"] + [f"- {warning}" for warning in packet_completeness["warnings"]])
    (output_dir / "replay_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
