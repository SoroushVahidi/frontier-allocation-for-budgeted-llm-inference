from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any

TRACE_SCHEMA_VERSION = "branch_trace_v1"

TOP_LEVEL_FIELDS = [
    "example_id",
    "dataset",
    "provider",
    "model",
    "budget",
    "seed",
    "method",
    "question_hash",
    "gold_answer",
    "final_answer",
    "final_correct",
    "actions_used",
    "expansions",
    "verifications",
    "trace_available",
]

DIRECT_FIELDS = [
    "direct_reserve_answer",
    "direct_reserve_correct",
    "direct_reserve_source_method",
    "direct_reserve_attempts",
    "direct_reserve_agreement_count",
    "direct_reserve_num_attempts",
    "direct_reserve_confidence_proxy",
    "direct_reserve_parse_success",
    "direct_reserve_metadata",
]

FRONTIER_FIELDS = [
    "frontier_candidate_answer",
    "frontier_candidate_correct",
    "frontier_candidate_support",
    "frontier_candidate_maturity",
    "frontier_candidate_family_count",
    "frontier_candidate_depth_max",
    "frontier_candidate_depth_mean",
    "frontier_candidate_metadata",
]

OVERRIDE_FIELDS = [
    "reserve_used",
    "frontier_override_triggered",
    "override_margin",
    "override_reason",
    "direct_frontier_agree",
    "incumbent_support",
    "frontier_support",
    "support_margin",
    "maturity_margin",
    "override_thresholds",
    "guard_decision_inputs",
]

CANDIDATE_BRANCH_TABLE_FIELDS = [
    "example_id",
    "dataset",
    "provider",
    "model",
    "budget",
    "seed",
    "method",
    "branch_id",
    "parent_id",
    "depth",
    "family_id",
    "parsed_answer",
    "answer_group",
    "is_resolved",
    "is_selected",
    "is_expanded",
    "branch_score",
    "V",
    "A",
    "C",
    "R",
    "I",
    "text_hash",
    "metadata",
]

ANSWER_GROUP_TABLE_FIELDS = [
    "example_id",
    "dataset",
    "provider",
    "model",
    "budget",
    "seed",
    "method",
    "answer_group",
    "support_count",
    "maturity",
    "family_count",
    "depth_max",
    "depth_mean",
    "best_branch_score",
    "branch_ids",
    "family_counts",
    "metadata",
]

TRACE_INDEX_FIELDS = [
    "example_id",
    "dataset",
    "provider",
    "model",
    "budget",
    "seed",
    "method",
    "trace_path",
    "trace_available",
    "n_branches",
    "n_answer_groups",
]


def safe_hash(text: str | None) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]


def _norm_answer(value: Any) -> str:
    return str(value or "").strip() or "__unknown__"


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _answers_match(answer: Any, gold: Any) -> bool | None:
    if gold is None or str(gold).strip() == "" or answer is None or str(answer).strip() == "":
        return None
    return str(answer).strip().lower() == str(gold).strip().lower()


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(k): _jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_jsonable(v) for v in value]
        return str(value)


def _branch_rows_from_metadata(metadata: dict[str, Any], selected_group: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    final_states = metadata.get("final_branch_states") or metadata.get("candidate_branch_rows") or []
    if not isinstance(final_states, list):
        final_states = []
    expanded_ids = {
        str(r.get("branch_id", ""))
        for r in metadata.get("action_trace", [])
        if isinstance(r, dict) and str(r.get("action", "")) in {"expand", "direct_reserve"}
    }
    for idx, raw in enumerate(final_states):
        if not isinstance(raw, dict):
            continue
        branch_id = str(raw.get("branch_id") or f"branch_{idx}")
        answer = raw.get("predicted_answer", raw.get("parsed_answer", ""))
        group = str(raw.get("group_key") or raw.get("answer_group") or _norm_answer(answer))
        steps = raw.get("steps") if isinstance(raw.get("steps"), list) else []
        trace_events = raw.get("trace_events") if isinstance(raw.get("trace_events"), list) else []
        latest_text = ""
        if trace_events and isinstance(trace_events[-1], dict):
            latest_text = str(trace_events[-1].get("reasoning_text") or trace_events[-1].get("response_text") or "")
        elif steps:
            latest_text = "\n".join(str(s) for s in steps[-3:])
        rows.append(
            {
                "branch_id": branch_id,
                "parent_id": str(raw.get("parent_branch_id") or raw.get("parent_id") or ""),
                "depth": _as_int(raw.get("branch_depth", raw.get("depth", len(steps)))),
                "family_id": str(raw.get("strategy_family") or raw.get("family_id") or raw.get("source") or ""),
                "parsed_answer": "" if answer is None else str(answer),
                "answer_group": group,
                "is_resolved": bool(raw.get("is_done", raw.get("is_terminal", bool(answer)))),
                "is_selected": bool(raw.get("selected", raw.get("is_selected", group == selected_group))),
                "is_expanded": bool(branch_id in expanded_ids or int(raw.get("is_expanded", 0)) == 1),
                "branch_score": _as_float(raw.get("score", raw.get("branch_score", 0.0))),
                "V": raw.get("V"),
                "A": raw.get("A"),
                "C": raw.get("C"),
                "R": raw.get("R"),
                "I": raw.get("I"),
                "text_hash": safe_hash(latest_text) if latest_text else "",
                "metadata": {
                    "source": raw.get("source", ""),
                    "trace_event_count": len(trace_events),
                },
            }
        )
    return rows


def _answer_group_rows(metadata: dict[str, Any], branch_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    support_counts = metadata.get("answer_group_support_counts") or metadata.get("frontier_answer_group_counts") or {}
    if not isinstance(support_counts, dict):
        support_counts = {}
    family_counts = metadata.get("answer_group_strategy_family_counts") or {}
    if not isinstance(family_counts, dict):
        family_counts = {}
    best_scores = metadata.get("answer_group_best_branch_scores") or metadata.get("family_best_branch_scores_by_answer_group") or {}
    if not isinstance(best_scores, dict):
        best_scores = {}

    groups = sorted(set(str(k) for k in support_counts) | {str(r["answer_group"]) for r in branch_rows})
    rows: list[dict[str, Any]] = []
    for group in groups:
        members = [r for r in branch_rows if str(r["answer_group"]) == group]
        depths = [_as_int(r.get("depth")) for r in members]
        families = sorted({str(r.get("family_id") or "") for r in members if str(r.get("family_id") or "")})
        score_values = [_as_float(r.get("branch_score")) for r in members]
        raw_best = best_scores.get(group)
        if isinstance(raw_best, dict):
            raw_best = max((_as_float(v) for v in raw_best.values()), default=0.0)
        rows.append(
            {
                "answer_group": group,
                "support_count": _as_int(support_counts.get(group), len(members)),
                "maturity": len(members),
                "family_count": len(families),
                "depth_max": max(depths) if depths else 0,
                "depth_mean": float(mean(depths)) if depths else 0.0,
                "best_branch_score": _as_float(raw_best, max(score_values) if score_values else 0.0),
                "branch_ids": [str(r["branch_id"]) for r in members],
                "family_counts": family_counts.get(group, {}),
                "metadata": {},
            }
        )
    return rows


def build_branch_trace(
    *,
    result: Any,
    example_id: str,
    dataset: str = "",
    provider: str = "",
    model: str = "",
    budget: int | None = None,
    seed: int | None = None,
    method: str | None = None,
    question: str = "",
    gold_answer: str | None = None,
) -> dict[str, Any]:
    metadata = dict(getattr(result, "metadata", {}) or {})
    final_answer = getattr(result, "prediction", None)
    selected_group = str(metadata.get("selected_answer_group") or metadata.get("selected_group") or _norm_answer(final_answer))
    branches = _branch_rows_from_metadata(metadata, selected_group)
    groups = _answer_group_rows(metadata, branches)
    direct_answer = metadata.get("direct_reserve_answer")
    frontier_answer = metadata.get("frontier_candidate_answer", getattr(result, "prediction", None))
    frontier_group = _norm_answer(frontier_answer)
    frontier_group_row = next((g for g in groups if str(g["answer_group"]) == frontier_group), {})
    incumbent_support = metadata.get("incumbent_support")
    frontier_support = metadata.get("frontier_support", frontier_group_row.get("support_count"))
    direct_counts = metadata.get("direct_answer_group_counts") if isinstance(metadata.get("direct_answer_group_counts"), dict) else {}

    trace = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "top_level": {
            "example_id": example_id,
            "dataset": dataset,
            "provider": provider,
            "model": model,
            "budget": budget,
            "seed": seed,
            "method": method or getattr(result, "method", ""),
            "question_hash": safe_hash(question),
            "gold_answer": gold_answer,
            "final_answer": final_answer,
            "final_correct": getattr(result, "is_correct", None) if gold_answer is not None else None,
            "actions_used": getattr(result, "actions_used", None),
            "expansions": getattr(result, "expansions", None),
            "verifications": getattr(result, "verifications", None),
            "trace_available": True,
        },
        "direct_reserve": {
            "direct_reserve_answer": direct_answer,
            "direct_reserve_correct": _answers_match(direct_answer, gold_answer),
            "direct_reserve_source_method": metadata.get("direct_reserve_source_method", "direct_reserve"),
            "direct_reserve_attempts": metadata.get("direct_reserve_attempts", metadata.get("direct_action_trace", [])),
            "direct_reserve_agreement_count": metadata.get(
                "direct_reserve_agreement_count",
                max((_as_int(v) for v in direct_counts.values()), default=0),
            ),
            "direct_reserve_num_attempts": metadata.get(
                "direct_reserve_num_attempts",
                metadata.get("direct_reserve_attempts_executed", len(metadata.get("direct_action_trace", []))),
            ),
            "direct_reserve_confidence_proxy": metadata.get(
                "direct_reserve_confidence_proxy",
                metadata.get("direct_top_support"),
            ),
            "direct_reserve_parse_success": metadata.get(
                "direct_reserve_parse_success",
                direct_answer is not None and str(direct_answer).strip() != "",
            ),
            "direct_reserve_metadata": metadata.get("direct_reserve_metadata", {}),
        },
        "frontier_candidate": {
            "frontier_candidate_answer": frontier_answer,
            "frontier_candidate_correct": _answers_match(frontier_answer, gold_answer),
            "frontier_candidate_support": frontier_support,
            "frontier_candidate_maturity": metadata.get("frontier_candidate_maturity", frontier_group_row.get("maturity")),
            "frontier_candidate_family_count": metadata.get("frontier_candidate_family_count", frontier_group_row.get("family_count")),
            "frontier_candidate_depth_max": metadata.get("frontier_candidate_depth_max", frontier_group_row.get("depth_max")),
            "frontier_candidate_depth_mean": metadata.get("frontier_candidate_depth_mean", frontier_group_row.get("depth_mean")),
            "frontier_candidate_metadata": metadata.get("frontier_candidate_metadata", metadata.get("frontier_metadata", {})),
        },
        "answer_groups": {
            "answer_group_support_counts": metadata.get("answer_group_support_counts", {}),
            "answer_group_maturity": {str(g["answer_group"]): g["maturity"] for g in groups},
            "answer_group_family_counts": metadata.get("answer_group_strategy_family_counts", {}),
            "answer_group_depth_stats": {
                str(g["answer_group"]): {"depth_max": g["depth_max"], "depth_mean": g["depth_mean"]} for g in groups
            },
            "answer_group_best_branch_score": {str(g["answer_group"]): g["best_branch_score"] for g in groups},
            "answer_group_branch_ids": {str(g["answer_group"]): g["branch_ids"] for g in groups},
        },
        "branches": branches,
        "override_gating": {
            "reserve_used": metadata.get("reserve_used"),
            "frontier_override_triggered": metadata.get("frontier_override_triggered"),
            "override_margin": metadata.get("override_margin"),
            "override_reason": metadata.get("override_reason"),
            "direct_frontier_agree": metadata.get("direct_frontier_agree"),
            "incumbent_support": incumbent_support,
            "frontier_support": frontier_support,
            "support_margin": metadata.get("support_margin", metadata.get("override_margin")),
            "maturity_margin": metadata.get("maturity_margin"),
            "override_thresholds": metadata.get("override_thresholds", {}),
            "guard_decision_inputs": metadata.get("guard_decision_inputs", {}),
        },
        "raw_metadata": _jsonable(metadata),
    }
    return fill_missing_trace_fields(trace)


def fill_missing_trace_fields(trace: dict[str, Any]) -> dict[str, Any]:
    out = dict(trace)
    out.setdefault("schema_version", TRACE_SCHEMA_VERSION)
    for section, fields in (
        ("top_level", TOP_LEVEL_FIELDS),
        ("direct_reserve", DIRECT_FIELDS),
        ("frontier_candidate", FRONTIER_FIELDS),
        ("override_gating", OVERRIDE_FIELDS),
    ):
        payload = dict(out.get(section) or {})
        for field in fields:
            payload.setdefault(field, None)
        out[section] = payload
    out.setdefault("answer_groups", {})
    for field in [
        "answer_group_support_counts",
        "answer_group_maturity",
        "answer_group_family_counts",
        "answer_group_depth_stats",
        "answer_group_best_branch_score",
        "answer_group_branch_ids",
    ]:
        out["answer_groups"].setdefault(field, {})
    out.setdefault("branches", [])
    out.setdefault("raw_metadata", {})
    return out


def trace_to_table_rows(trace: dict[str, Any], trace_path: str = "") -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    top = trace["top_level"]
    branch_rows: list[dict[str, Any]] = []
    for branch in trace.get("branches", []):
        row = {k: top.get(k) for k in ("example_id", "dataset", "provider", "model", "budget", "seed", "method")}
        row.update(branch)
        branch_rows.append(row)

    group_rows: list[dict[str, Any]] = []
    support_counts = trace["answer_groups"].get("answer_group_support_counts", {})
    maturity = trace["answer_groups"].get("answer_group_maturity", {})
    family_counts = trace["answer_groups"].get("answer_group_family_counts", {})
    depth_stats = trace["answer_groups"].get("answer_group_depth_stats", {})
    best_scores = trace["answer_groups"].get("answer_group_best_branch_score", {})
    branch_ids = trace["answer_groups"].get("answer_group_branch_ids", {})
    for group in sorted(set(support_counts) | set(maturity) | set(branch_ids)):
        stats = depth_stats.get(group, {}) if isinstance(depth_stats, dict) else {}
        fam = family_counts.get(group, {}) if isinstance(family_counts, dict) else {}
        row = {k: top.get(k) for k in ("example_id", "dataset", "provider", "model", "budget", "seed", "method")}
        row.update(
            {
                "answer_group": group,
                "support_count": _as_int(support_counts.get(group), len(branch_ids.get(group, []))),
                "maturity": _as_int(maturity.get(group), len(branch_ids.get(group, []))),
                "family_count": len(fam) if isinstance(fam, dict) else 0,
                "depth_max": stats.get("depth_max", 0) if isinstance(stats, dict) else 0,
                "depth_mean": stats.get("depth_mean", 0.0) if isinstance(stats, dict) else 0.0,
                "best_branch_score": best_scores.get(group, 0.0) if isinstance(best_scores, dict) else 0.0,
                "branch_ids": branch_ids.get(group, []),
                "family_counts": fam,
                "metadata": {},
            }
        )
        group_rows.append(row)
    index_row = {k: top.get(k) for k in ("example_id", "dataset", "provider", "model", "budget", "seed", "method")}
    index_row.update(
        {
            "trace_path": trace_path,
            "trace_available": top.get("trace_available", True),
            "n_branches": len(branch_rows),
            "n_answer_groups": len(group_rows),
        }
    )
    return branch_rows, group_rows, index_row


def write_trace_package(output_dir: Path, traces: list[dict[str, Any]]) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_dir = output_dir / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    all_branches: list[dict[str, Any]] = []
    all_groups: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []
    for trace in traces:
        top = trace["top_level"]
        safe_example = str(top.get("example_id") or "example").replace("/", "_").replace(" ", "_")
        safe_method = str(top.get("method") or "method").replace("/", "_").replace(" ", "_")
        path = trace_dir / f"{safe_example}_{safe_method}.json"
        path.write_text(json.dumps(_jsonable(trace), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rel = str(path.relative_to(output_dir))
        branches, groups, index = trace_to_table_rows(trace, rel)
        all_branches.extend(branches)
        all_groups.extend(groups)
        index_rows.append(index)
    _write_csv(output_dir / "candidate_branch_table.csv", all_branches, CANDIDATE_BRANCH_TABLE_FIELDS)
    _write_csv(output_dir / "answer_group_table.csv", all_groups, ANSWER_GROUP_TABLE_FIELDS)
    _write_csv(output_dir / "per_case_trace_index.csv", index_rows, TRACE_INDEX_FIELDS)
    return {"n_traces": len(traces), "n_branches": len(all_branches), "n_answer_groups": len(all_groups)}


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            normalized = {}
            for field in fields:
                value = row.get(field, "")
                if isinstance(value, (dict, list)):
                    value = json.dumps(_jsonable(value), sort_keys=True)
                normalized[field] = value
            w.writerow(normalized)
