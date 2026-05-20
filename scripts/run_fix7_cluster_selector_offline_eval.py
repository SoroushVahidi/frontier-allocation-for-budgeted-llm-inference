#!/usr/bin/env python3
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
from typing import Any

from experiments.cluster_answer_selector import (
    AnswerCluster,
    AnswerEvidence,
    apply_fix7_offline,
    canonicalize_answer_text,
    cluster_answers,
    compute_cluster_features,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = REPO_ROOT / "outputs"

FAILURE_PACKET_DIR = OUTPUTS / "latest_method_fix24_failure_packets_20260519_20260519T174500Z"
PRECISE_PATTERN_DIR = OUTPUTS / "fix24_precise_pattern_mining_20260519_20260519T184647Z"
DEEP_REASON_DIR = OUTPUTS / "fix24_deep_failure_reason_mining_20260520_20260520T003745Z"
PREV_RESOLUTION_DIR = OUTPUTS / "previous_failures_resolution_audit_fix24_20260519_20260519T180229Z"
POSTRUN_DIR = OUTPUTS / "overnight_fix5_postrun_eval_20260519_20260519T134633Z"
VALIDATION_DIR = OUTPUTS / "overnight_fix5_promotion_grade_validation_20260519T040621Z"

MAIN_PER_EXAMPLE = (
    VALIDATION_DIR
    / "runner_output"
    / "cohere_real_model_cost_normalized_validation_fix5_overnight_live_20260519T040621Z"
    / "per_example_records.jsonl"
)

DR_METHOD = "direct_reserve_semantic_frontier_v2"
L1_METHOD = "external_l1_max"
S1_METHOD = "external_s1_budget_forcing"
TALE_METHOD = "external_tale_prompt_budgeting"
EXT_METHODS = {L1_METHOD, S1_METHOD, TALE_METHOD}
METHODS_REQUIRED = [DR_METHOD, L1_METHOD, S1_METHOD, TALE_METHOD]


@dataclass(frozen=True)
class CaseKey:
    dataset: str
    example_id: str
    seed: int
    budget: int

    def as_tuple(self) -> tuple[str, str, int, int]:
        return (self.dataset, self.example_id, self.seed, self.budget)

    def as_id(self) -> str:
        return f"{self.dataset}::{self.example_id}::seed{self.seed}::b{self.budget}"


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _parse_pointer(pointer: str) -> tuple[Path, int] | None:
    pointer = str(pointer or "")
    if not pointer:
        return None
    parts = pointer.split(":")
    if len(parts) < 2:
        return None
    line_idx = None
    line_pos = None
    for i in range(len(parts) - 1, 0, -1):
        if parts[i].isdigit():
            line_idx = int(parts[i])
            line_pos = i
            break
    if line_idx is None or line_pos is None:
        return None
    file_path = ":".join(parts[:line_pos])
    p = Path(file_path)
    if not p.is_absolute():
        p = REPO_ROOT / file_path
    return p, line_idx


def _load_json_line(path: Path, one_based_line: int, line_cache: dict[Path, list[str]]) -> dict[str, Any] | None:
    if one_based_line <= 0:
        return None
    if path not in line_cache:
        if not path.exists():
            return None
        line_cache[path] = path.read_text(encoding="utf-8").splitlines()
    lines = line_cache[path]
    if one_based_line > len(lines):
        return None
    raw = lines[one_based_line - 1].strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _method_answer_canonical(row: dict[str, Any]) -> str | None:
    for key in ("final_answer_canonical", "selected_answer_canonical", "prediction_normalized"):
        v = row.get(key)
        if v not in (None, "", "None"):
            return str(v).strip()
    raw = row.get("final_answer_raw") or row.get("selected_answer_raw") or row.get("controller_final_answer_raw")
    can = canonicalize_answer_text(str(raw or "")).canonical_answer
    return can


def _method_answer_raw(row: dict[str, Any]) -> str:
    for key in ("final_answer_raw", "selected_answer_raw", "controller_final_answer_raw", "repair_answer_raw"):
        v = row.get(key)
        if v not in (None, ""):
            return str(v)
    return str(row.get("final_answer_canonical") or "")


def _group_key_from_row(row: dict[str, Any]) -> CaseKey:
    return CaseKey(
        dataset=str(row.get("dataset") or ""),
        example_id=str(row.get("example_id") or ""),
        seed=_safe_int(row.get("seed")),
        budget=_safe_int(row.get("budget")),
    )


def _build_main_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str, int, int], dict[str, dict[str, Any]]]:
    out: dict[tuple[str, str, int, int], dict[str, dict[str, Any]]] = {}
    for row in rows:
        key = _group_key_from_row(row).as_tuple()
        out.setdefault(key, {})[str(row.get("method") or "")] = row
    return out


def _high_disagreement(answer_map: dict[str, str | None]) -> bool:
    vals = {v for v in answer_map.values() if v}
    return len(vals) >= 3


def _is_low_depth(md: dict[str, Any]) -> bool:
    override_reason = str(md.get("override_reason") or "")
    if "single_weak_frontier_branch" in override_reason:
        return True
    if _safe_int(md.get("frontier_support"), 0) == 0 and _safe_int(md.get("candidate_pool_answer_group_count"), 0) >= 2:
        return True
    return False


def _build_evidence_from_group(method_rows: dict[str, dict[str, Any]]) -> tuple[list[AnswerEvidence], list[dict[str, Any]]]:
    dr = method_rows[DR_METHOD]
    md = dr.get("result_metadata") or {}
    if isinstance(md, str):
        try:
            md = json.loads(md)
        except Exception:
            md = {}
    assert isinstance(md, dict)

    evidences: list[AnswerEvidence] = []
    parser_audit: list[dict[str, Any]] = []

    # Frontier selected answer.
    dr_raw = _method_answer_raw(dr)
    dr_can = canonicalize_answer_text(dr_raw, cue="frontier_selected", explicit=True)
    evidences.append(
        AnswerEvidence(
            source=DR_METHOD,
            source_kind="frontier_selected",
            raw_text=dr_raw,
            parser_confidence=dr_can.parser_confidence,
            canonical_answer=dr_can.canonical_answer,
            normalized_unit=dr_can.normalized_unit,
        )
    )

    # Frontier candidate answer when present.
    frontier_candidate = md.get("frontier_candidate_answer")
    if frontier_candidate not in (None, "", "None"):
        can = canonicalize_answer_text(str(frontier_candidate), cue="frontier_candidate", explicit=True)
        evidences.append(
            AnswerEvidence(
                source=DR_METHOD,
                source_kind="frontier_candidate",
                raw_text=str(frontier_candidate),
                parser_confidence=can.parser_confidence,
                canonical_answer=can.canonical_answer,
                normalized_unit=can.normalized_unit,
            )
        )

    # Selector pool candidates.
    selector_pool = md.get("selector_candidate_pool") or md.get("final_branch_states") or []
    if isinstance(selector_pool, list):
        for item in selector_pool:
            if not isinstance(item, dict):
                continue
            raw = (
                item.get("normalized_answer")
                or item.get("predicted_answer")
                or item.get("answer")
                or item.get("final_answer")
                or ""
            )
            if str(raw).strip() == "":
                continue
            can = canonicalize_answer_text(str(raw), cue="pool", explicit=False)
            evidences.append(
                AnswerEvidence(
                    source=str(item.get("source_family") or item.get("source") or DR_METHOD),
                    source_kind="frontier_pool",
                    raw_text=str(raw),
                    parser_confidence=can.parser_confidence,
                    canonical_answer=can.canonical_answer,
                    normalized_unit=can.normalized_unit,
                    branch_id=str(item.get("branch_id") or "") or None,
                )
            )

    # Final nodes.
    final_nodes = dr.get("final_nodes") or []
    if isinstance(final_nodes, list):
        for node in final_nodes:
            if not isinstance(node, dict):
                continue
            raw = node.get("predicted_answer") or node.get("final_answer") or ""
            if str(raw).strip() == "":
                continue
            can = canonicalize_answer_text(str(raw), cue="final_node", explicit=False)
            evidences.append(
                AnswerEvidence(
                    source=DR_METHOD,
                    source_kind="frontier_final_node",
                    raw_text=str(raw),
                    parser_confidence=can.parser_confidence,
                    canonical_answer=can.canonical_answer,
                    normalized_unit=can.normalized_unit,
                    branch_id=str(node.get("branch_id") or "") or None,
                )
            )

    # External method outputs.
    for method in (L1_METHOD, S1_METHOD, TALE_METHOD):
        row = method_rows.get(method)
        if not row:
            continue
        raw = _method_answer_raw(row)
        can = canonicalize_answer_text(raw, cue=method, explicit=True)
        evidences.append(
            AnswerEvidence(
                source=method,
                source_kind="external_method",
                raw_text=raw,
                parser_confidence=can.parser_confidence,
                canonical_answer=can.canonical_answer,
                normalized_unit=can.normalized_unit,
            )
        )

    # Parser audit: did robust parse differ from existing canonical field?
    existing_can = str(dr.get("final_answer_canonical") or "")
    if dr_can.canonical_answer and existing_can and dr_can.canonical_answer != existing_can:
        parser_audit.append(
            {
                "example_id": str(dr.get("example_id") or ""),
                "dataset": str(dr.get("dataset") or ""),
                "seed": str(dr.get("seed") or ""),
                "budget": str(dr.get("budget") or ""),
                "issue_type": "robust_parser_changed_frontier_canonical",
                "raw_answer": dr_raw,
                "existing_canonical": existing_can,
                "robust_canonical": dr_can.canonical_answer,
                "parser_confidence": dr_can.parser_confidence,
            }
        )
    if dr_can.ambiguous:
        parser_audit.append(
            {
                "example_id": str(dr.get("example_id") or ""),
                "dataset": str(dr.get("dataset") or ""),
                "seed": str(dr.get("seed") or ""),
                "budget": str(dr.get("budget") or ""),
                "issue_type": "frontier_parse_ambiguous",
                "raw_answer": dr_raw,
                "existing_canonical": existing_can,
                "robust_canonical": dr_can.canonical_answer or "",
                "parser_confidence": dr_can.parser_confidence,
            }
        )
    return evidences, parser_audit


def _build_group_payload(method_rows: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    dr = method_rows[DR_METHOD]
    md = dr.get("result_metadata") or {}
    if isinstance(md, str):
        try:
            md = json.loads(md)
        except Exception:
            md = {}
    if not isinstance(md, dict):
        md = {}

    answer_map = {
        DR_METHOD: _method_answer_canonical(method_rows[DR_METHOD]),
        L1_METHOD: _method_answer_canonical(method_rows[L1_METHOD]),
        S1_METHOD: _method_answer_canonical(method_rows[S1_METHOD]),
        TALE_METHOD: _method_answer_canonical(method_rows[TALE_METHOD]),
    }
    baseline_answer = answer_map[DR_METHOD]

    evidences, parser_audit = _build_evidence_from_group(method_rows)
    clusters: list[AnswerCluster] = cluster_answers(evidences)

    low_depth = _is_low_depth(md)
    high_disagreement = _high_disagreement(answer_map)
    support_margin = md.get("support_margin")
    support_margin_f = _safe_float(support_margin, 0.0) if support_margin is not None else None
    override_reason = str(md.get("override_reason") or "")

    cluster_features: list[dict[str, Any]] = []
    for cl in clusters:
        feat = compute_cluster_features(
            cl,
            baseline_answer=baseline_answer,
            frontier_answer=answer_map[DR_METHOD],
            l1_answer=answer_map[L1_METHOD],
            s1_answer=answer_map[S1_METHOD],
            tale_answer=answer_map[TALE_METHOD],
            low_depth_flag=low_depth,
            high_disagreement_flag=high_disagreement,
            support_margin=support_margin_f,
            override_reason=override_reason,
        )
        cluster_features.append(feat)

    # top-2 support margin at group level.
    by_support = sorted(cluster_features, key=lambda x: int(x.get("support_mass", 0)), reverse=True)
    top2_margin = 0
    if len(by_support) >= 2:
        top2_margin = int(by_support[0].get("support_mass", 0)) - int(by_support[1].get("support_mass", 0))
    elif len(by_support) == 1:
        top2_margin = int(by_support[0].get("support_mass", 0))
    for feat in cluster_features:
        feat["top2_support_margin"] = top2_margin

    gold_raw = dr.get("gold_answer_canonical") or dr.get("gold_answer")
    gold_can = canonicalize_answer_text(str(gold_raw or "")).canonical_answer

    payload = {
        "case_key": _group_key_from_row(dr).as_id(),
        "dataset": str(dr.get("dataset") or ""),
        "example_id": str(dr.get("example_id") or ""),
        "seed": _safe_int(dr.get("seed")),
        "budget": _safe_int(dr.get("budget")),
        "baseline_answer": baseline_answer,
        "frontier_answer": answer_map[DR_METHOD],
        "l1_answer": answer_map[L1_METHOD],
        "s1_answer": answer_map[S1_METHOD],
        "tale_answer": answer_map[TALE_METHOD],
        "offline_gold_answer": gold_can,
        "cluster_features": cluster_features,
        "runtime_flags": {
            "low_depth_flag": low_depth,
            "high_disagreement_flag": high_disagreement,
            "support_margin_runtime": support_margin_f,
            "override_reason": override_reason,
        },
        "metadata_question_hash": str((dr.get("result_metadata") or {}).get("question_hash", "")),
    }
    return payload, parser_audit


def _cluster_by_id(group: dict[str, Any], cid: str | None) -> dict[str, Any] | None:
    if not cid:
        return None
    for c in group["cluster_features"]:
        if str(c.get("cluster_id")) == str(cid):
            return c
    return None


def _baseline_cluster(group: dict[str, Any]) -> dict[str, Any] | None:
    for c in group["cluster_features"]:
        if c.get("contains_fix24_answer"):
            return c
    return None


def _fallback_baseline_decision(group: dict[str, Any]) -> dict[str, Any]:
    base = _baseline_cluster(group)
    return {
        "rule": "R0_keep_fix24",
        "selected_cluster_id": None if not base else str(base.get("cluster_id")),
        "selected_answer": group.get("baseline_answer"),
        "override": False,
        "trigger_reason": "keep_baseline",
    }


def _pick_challenger(
    group: dict[str, Any],
    *,
    min_external_count: int = 0,
    require_realized_frontier: bool = False,
    require_non_low_depth: bool = False,
    require_parser_high_vs_base_low: bool = False,
) -> dict[str, Any] | None:
    base = _baseline_cluster(group)
    if not base:
        return None
    if require_non_low_depth and bool(base.get("low_depth_flag")):
        return None
    out: list[dict[str, Any]] = []
    for c in group["cluster_features"]:
        if c.get("cluster_id") == base.get("cluster_id"):
            continue
        if int(c.get("external_count", 0)) < min_external_count:
            continue
        if require_realized_frontier and int(c.get("frontier_count", 0)) <= 0:
            continue
        if require_parser_high_vs_base_low:
            if float(c.get("parser_confidence_mean", 0.0)) < 2.0:
                continue
            if float(base.get("parser_confidence_mean", 0.0)) > 1.0:
                continue
        out.append(c)
    if not out:
        return None
    out.sort(
        key=lambda c: (
            int(c.get("external_count", 0)),
            int(c.get("frontier_count", 0)) + int(c.get("independent_path_count", 0)),
            float(c.get("parser_confidence_mean", 0.0)),
            int(c.get("support_mass", 0)),
        ),
        reverse=True,
    )
    return out[0]


def _rule_r1(group: dict[str, Any], threshold: int) -> dict[str, Any]:
    base = _baseline_cluster(group)
    if not base:
        return _fallback_baseline_decision(group)
    top2_margin = int(base.get("top2_support_margin", 0))
    if top2_margin < threshold:
        return _fallback_baseline_decision(group) | {"rule": f"R1_margin{threshold}", "trigger_reason": "margin_below_threshold"}

    candidates: list[dict[str, Any]] = []
    base_frontier_support = int(base.get("frontier_count", 0)) + int(base.get("independent_path_count", 0))
    base_ext = int(base.get("external_count", 0))
    base_conf = float(base.get("parser_confidence_mean", 0.0))
    for c in group["cluster_features"]:
        if c.get("cluster_id") == base.get("cluster_id"):
            continue
        c_frontier_support = int(c.get("frontier_count", 0)) + int(c.get("independent_path_count", 0))
        if c_frontier_support <= base_frontier_support:
            continue
        if int(c.get("external_count", 0)) < base_ext:
            continue
        if float(c.get("parser_confidence_mean", 0.0)) < base_conf:
            continue
        candidates.append(c)
    if not candidates:
        return _fallback_baseline_decision(group) | {"rule": f"R1_margin{threshold}", "trigger_reason": "no_safe_challenger"}

    candidates.sort(
        key=lambda c: (
            int(c.get("frontier_count", 0)) + int(c.get("independent_path_count", 0)),
            int(c.get("support_mass", 0)),
            int(c.get("external_count", 0)),
        ),
        reverse=True,
    )
    top = candidates[0]
    return {
        "rule": f"R1_margin{threshold}",
        "selected_cluster_id": str(top.get("cluster_id")),
        "selected_answer": top.get("canonical_answer"),
        "override": True,
        "trigger_reason": "higher_frontier_support_with_margin",
    }


def _rule_r2(group: dict[str, Any], name: str, *, min_ext: int, non_low_depth: bool, require_realized: bool, parser_guard: bool) -> dict[str, Any]:
    base = _baseline_cluster(group)
    if not base:
        return _fallback_baseline_decision(group) | {"rule": name}
    chal = _pick_challenger(
        group,
        min_external_count=min_ext,
        require_realized_frontier=require_realized,
        require_non_low_depth=non_low_depth,
        require_parser_high_vs_base_low=parser_guard,
    )
    if not chal:
        return _fallback_baseline_decision(group) | {"rule": name, "trigger_reason": "no_r2_challenger"}

    # Guard: challenger must either be frontier-realized or parser-guarded.
    base_conf = float(base.get("parser_confidence_mean", 0.0))
    chal_conf = float(chal.get("parser_confidence_mean", 0.0))
    realized = int(chal.get("frontier_count", 0)) > 0
    if not realized and not (chal_conf >= 2.0 and base_conf <= 1.0):
        return _fallback_baseline_decision(group) | {"rule": name, "trigger_reason": "not_realized_or_parser_guard"}

    return {
        "rule": name,
        "selected_cluster_id": str(chal.get("cluster_id")),
        "selected_answer": chal.get("canonical_answer"),
        "override": True,
        "trigger_reason": "external_majority_realized_or_parser_guard",
    }


def _rule_r3(group: dict[str, Any]) -> dict[str, Any]:
    base = _baseline_cluster(group)
    if not base:
        return _fallback_baseline_decision(group) | {"rule": "R3_present_not_selected"}
    margin = group["runtime_flags"].get("support_margin_runtime")
    margin_f = float(margin) if margin is not None else 0.0
    if margin_f > 0.5:
        return _fallback_baseline_decision(group) | {"rule": "R3_present_not_selected", "trigger_reason": "baseline_margin_not_low"}

    candidates: list[dict[str, Any]] = []
    for c in group["cluster_features"]:
        if c.get("cluster_id") == base.get("cluster_id"):
            continue
        if float(c.get("parser_confidence_mean", 0.0)) < 2.0:
            continue
        ext_support = int(c.get("external_count", 0))
        path_support = int(c.get("frontier_count", 0)) + int(c.get("independent_path_count", 0))
        base_path = int(base.get("frontier_count", 0)) + int(base.get("independent_path_count", 0))
        if ext_support <= 0 and path_support <= base_path:
            continue
        candidates.append(c)
    if not candidates:
        return _fallback_baseline_decision(group) | {"rule": "R3_present_not_selected", "trigger_reason": "no_alt_support"}

    candidates.sort(
        key=lambda c: (
            int(c.get("external_count", 0)),
            int(c.get("frontier_count", 0)) + int(c.get("independent_path_count", 0)),
            int(c.get("support_mass", 0)),
        ),
        reverse=True,
    )
    top = candidates[0]
    return {
        "rule": "R3_present_not_selected",
        "selected_cluster_id": str(top.get("cluster_id")),
        "selected_answer": top.get("canonical_answer"),
        "override": True,
        "trigger_reason": "low_margin_with_alt_support",
    }


def _rule_r4(group: dict[str, Any]) -> dict[str, Any]:
    base = _baseline_cluster(group)
    if not base:
        return _fallback_baseline_decision(group) | {"rule": "R4_parser_confidence_correction"}
    if float(base.get("parser_confidence_mean", 0.0)) > 1.0:
        return _fallback_baseline_decision(group) | {"rule": "R4_parser_confidence_correction", "trigger_reason": "baseline_parser_not_low"}

    candidates = []
    for c in group["cluster_features"]:
        if c.get("cluster_id") == base.get("cluster_id"):
            continue
        if float(c.get("parser_confidence_mean", 0.0)) < 2.0:
            continue
        if int(c.get("external_count", 0)) < int(base.get("external_count", 0)):
            continue
        unit_mismatch = str(c.get("normalized_unit") or "") != str(base.get("normalized_unit") or "")
        if not unit_mismatch and int(c.get("support_mass", 0)) < int(base.get("support_mass", 0)):
            continue
        candidates.append(c)
    if not candidates:
        return _fallback_baseline_decision(group) | {"rule": "R4_parser_confidence_correction", "trigger_reason": "no_parser_correction_candidate"}

    candidates.sort(
        key=lambda c: (
            int(c.get("external_count", 0)),
            float(c.get("parser_confidence_mean", 0.0)),
            int(c.get("support_mass", 0)),
        ),
        reverse=True,
    )
    top = candidates[0]
    return {
        "rule": "R4_parser_confidence_correction",
        "selected_cluster_id": str(top.get("cluster_id")),
        "selected_answer": top.get("canonical_answer"),
        "override": True,
        "trigger_reason": "baseline_low_conf_alt_high_conf",
    }


def _rule_r5(group: dict[str, Any]) -> dict[str, Any]:
    # Ordered guards: parser correction -> strict 3/3 realized non-low-depth -> strict R1 margin2
    r4 = _rule_r4(group)
    if r4.get("override"):
        return r4 | {"rule": "R5_combined_v0", "trigger_reason": f"r4::{r4.get('trigger_reason')}"}

    r2 = _rule_r2(
        group,
        "R2_3of3_realized_nonlowdepth",
        min_ext=3,
        non_low_depth=True,
        require_realized=True,
        parser_guard=False,
    )
    if r2.get("override"):
        return r2 | {"rule": "R5_combined_v0", "trigger_reason": f"r2::{r2.get('trigger_reason')}"}

    r1 = _rule_r1(group, threshold=2)
    if r1.get("override"):
        return r1 | {"rule": "R5_combined_v0", "trigger_reason": f"r1::{r1.get('trigger_reason')}"}

    # Also include default module decision for compatibility.
    dflt = apply_fix7_offline(group)
    if dflt.override_applied:
        return {
            "rule": "R5_combined_v0",
            "selected_cluster_id": dflt.selected_cluster_id,
            "selected_answer": dflt.selected_answer,
            "override": True,
            "trigger_reason": f"default::{dflt.override_reason}",
        }
    return _fallback_baseline_decision(group) | {"rule": "R5_combined_v0", "trigger_reason": "no_safe_rule"}


def _evaluate_rules_for_group(group: dict[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    rules.append(_fallback_baseline_decision(group))
    rules.append(_rule_r1(group, threshold=1))
    rules.append(_rule_r1(group, threshold=2))
    rules.append(_rule_r2(group, "R2_3of3_only", min_ext=3, non_low_depth=False, require_realized=False, parser_guard=False))
    rules.append(_rule_r2(group, "R2_2of3_only", min_ext=2, non_low_depth=False, require_realized=False, parser_guard=False))
    rules.append(_rule_r2(group, "R2_2of3_nonlowdepth", min_ext=2, non_low_depth=True, require_realized=False, parser_guard=False))
    rules.append(_rule_r2(group, "R2_2of3_realized", min_ext=2, non_low_depth=False, require_realized=True, parser_guard=False))
    rules.append(_rule_r2(group, "R2_2of3_parser_guard", min_ext=2, non_low_depth=False, require_realized=False, parser_guard=True))
    rules.append(_rule_r3(group))
    rules.append(_rule_r4(group))
    rules.append(_rule_r5(group))
    return rules


def _score_decision(gold: str | None, baseline: str | None, selected: str | None) -> tuple[int | None, int | None]:
    if not gold:
        return None, None
    return int(baseline == gold), int(selected == gold)


def _build_dataset_a(main_index: dict[tuple[str, str, int, int], dict[str, dict[str, Any]]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    failure_packets = _read_jsonl(FAILURE_PACKET_DIR / "fix24_failure_case_packets.jsonl")
    counterexamples = _read_csv(FAILURE_PACKET_DIR / "fix24_failure_counterexample_pool.csv")
    groups: list[dict[str, Any]] = []
    bucket_map: dict[str, str] = {}
    seen: set[tuple[str, str, int, int]] = set()

    for pkt in failure_packets:
        ident = pkt.get("identity") or {}
        key = (
            str(ident.get("dataset") or ""),
            str(ident.get("example_id") or ""),
            _safe_int(ident.get("seed")),
            _safe_int(ident.get("budget")),
        )
        method_rows = main_index.get(key)
        if not method_rows or not all(m in method_rows for m in METHODS_REQUIRED):
            continue
        payload, _ = _build_group_payload(method_rows)
        payload["dataset_split"] = "A_failure_packet"
        payload["offline_bucket"] = str(pkt.get("primary_root_label") or "failure")
        payload["offline_gold_answer"] = canonicalize_answer_text(str((pkt.get("offline_labels") or {}).get("gold_answer") or payload.get("offline_gold_answer") or "")).canonical_answer
        payload["metadata_failure_packet_source"] = "latest_method_fix24_failure_packets_20260519_20260519T174500Z"
        groups.append(payload)
        seen.add(key)
        bucket_map[payload["case_key"]] = payload["offline_bucket"]

    # Take up to 60 counterexamples.
    for row in counterexamples[:60]:
        key = (
            str(row.get("dataset") or ""),
            str(row.get("example_id") or ""),
            _safe_int(row.get("seed")),
            _safe_int(row.get("budget")),
        )
        if key in seen:
            continue
        method_rows = main_index.get(key)
        if not method_rows or not all(m in method_rows for m in METHODS_REQUIRED):
            continue
        payload, _ = _build_group_payload(method_rows)
        payload["dataset_split"] = "A_counterexample_pool"
        payload["offline_bucket"] = "counterexample_pool"
        payload["offline_gold_answer"] = canonicalize_answer_text(str(row.get("offline_gold_answer") or payload.get("offline_gold_answer") or "")).canonical_answer
        groups.append(payload)
        seen.add(key)
        bucket_map[payload["case_key"]] = payload["offline_bucket"]

    return groups, bucket_map


def _build_dataset_b(main_index: dict[tuple[str, str, int, int], dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for key, method_rows in main_index.items():
        if not all(m in method_rows for m in METHODS_REQUIRED):
            continue
        payload, _ = _build_group_payload(method_rows)
        payload["dataset_split"] = "B_main300"
        payload["offline_bucket"] = "main300"
        groups.append(payload)
    return groups


def _build_dataset_c(line_cache: dict[Path, list[str]]) -> list[dict[str, Any]]:
    replay_rows = _read_csv(PREV_RESOLUTION_DIR / "fix24_replayable_cases.csv")
    groups: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in replay_rows:
        pointers = str(row.get("source_row_pointers") or "").split("|")
        method_rows: dict[str, dict[str, Any]] = {}
        for ptxt in pointers:
            parsed = _parse_pointer(ptxt)
            if not parsed:
                continue
            p, ln = parsed
            if p.name != "per_example_records.jsonl":
                continue
            rec = _load_json_line(p, ln, line_cache)
            if not rec:
                continue
            method = str(rec.get("method") or "")
            if method in METHODS_REQUIRED and method not in method_rows:
                method_rows[method] = rec
        if not all(m in method_rows for m in METHODS_REQUIRED):
            continue
        payload, _ = _build_group_payload(method_rows)
        payload["dataset_split"] = "C_previous_replayable"
        payload["offline_bucket"] = "previous_replayable"
        payload["offline_gold_answer"] = canonicalize_answer_text(str(row.get("offline_gold_answer") or payload.get("offline_gold_answer") or "")).canonical_answer
        payload["metadata_case_key"] = str(row.get("case_key") or "")
        if payload["case_key"] in seen_ids:
            continue
        seen_ids.add(payload["case_key"])
        groups.append(payload)
    return groups


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and not fieldnames:
        fieldnames = ["empty"]
        rows = [{"empty": ""}]
    if not fieldnames:
        fields: set[str] = set()
        for r in rows:
            fields.update(r.keys())
        fieldnames = sorted(fields)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m20T%H%M%SZ")
    out_root = OUTPUTS / f"fix7_cluster_selector_offline_eval_20260520_{ts}"
    out_root.mkdir(parents=True, exist_ok=True)

    line_cache: dict[Path, list[str]] = {}
    main_rows = _read_jsonl(MAIN_PER_EXAMPLE)
    main_index = _build_main_index(main_rows)

    dataset_a, bucket_map = _build_dataset_a(main_index)
    dataset_b = _build_dataset_b(main_index)
    dataset_c = _build_dataset_c(line_cache)

    all_sets = {
        "A": dataset_a,
        "B": dataset_b,
        "C": dataset_c,
    }

    all_cluster_rows: list[dict[str, Any]] = []
    all_decisions: list[dict[str, Any]] = []
    parser_audit_rows: list[dict[str, Any]] = []
    recovery_cases: list[dict[str, Any]] = []
    override_cases: list[dict[str, Any]] = []
    regression_cases: list[dict[str, Any]] = []
    pattern_rows: list[dict[str, Any]] = []

    for split_name, groups in all_sets.items():
        for g in groups:
            # collect cluster feature rows.
            for cf in g["cluster_features"]:
                all_cluster_rows.append(
                    {
                        "dataset_split": split_name,
                        "case_key": g["case_key"],
                        "example_id": g["example_id"],
                        "seed": g["seed"],
                        "budget": g["budget"],
                        **cf,
                    }
                )

            decisions = _evaluate_rules_for_group(g)
            for d in decisions:
                selected = d.get("selected_answer")
                base = g.get("baseline_answer")
                gold = g.get("offline_gold_answer")
                base_ok, sel_ok = _score_decision(gold, base, selected)
                rec = {
                    "dataset_split": split_name,
                    "case_key": g["case_key"],
                    "example_id": g["example_id"],
                    "seed": g["seed"],
                    "budget": g["budget"],
                    "rule": d.get("rule"),
                    "selected_cluster_id": d.get("selected_cluster_id"),
                    "baseline_answer": base,
                    "selected_answer": selected,
                    "offline_gold_answer": gold,
                    "baseline_correct_offline": base_ok,
                    "rule_correct_offline": sel_ok,
                    "override": int(bool(d.get("override"))),
                    "trigger_reason": d.get("trigger_reason"),
                    "offline_bucket": g.get("offline_bucket"),
                }
                all_decisions.append(rec)
                if rec["override"]:
                    override_cases.append(rec)
                if base_ok == 1 and sel_ok == 0:
                    regression_cases.append(rec)
                if base_ok == 0 and sel_ok == 1:
                    recovery_cases.append(
                        {
                            **rec,
                            "cluster_features": g["cluster_features"],
                            "runtime_flags": g["runtime_flags"],
                        }
                    )
                if split_name == "A":
                    pattern_rows.append(
                        {
                            "rule": rec["rule"],
                            "offline_bucket": rec["offline_bucket"],
                            "override": rec["override"],
                            "baseline_correct_offline": rec["baseline_correct_offline"],
                            "rule_correct_offline": rec["rule_correct_offline"],
                        }
                    )

    # parser audit data from all groups
    for split_name, groups in all_sets.items():
        for g in groups:
            method_rows = main_index.get((g["dataset"], g["example_id"], g["seed"], g["budget"]))
            if method_rows and all(m in method_rows for m in METHODS_REQUIRED):
                _, audits = _build_group_payload(method_rows)
                for a in audits:
                    parser_audit_rows.append({"dataset_split": split_name, **a})

    # Aggregate metrics.
    metrics: dict[str, Any] = {
        "output_root": str(out_root),
        "datasets": {},
        "rules": {},
    }
    by_rule_split: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in all_decisions:
        by_rule_split.setdefault((row["dataset_split"], row["rule"]), []).append(row)

    for (split, rule), rows in sorted(by_rule_split.items()):
        valid = [r for r in rows if r["rule_correct_offline"] is not None and r["baseline_correct_offline"] is not None]
        if not valid:
            continue
        n = len(valid)
        acc = sum(int(r["rule_correct_offline"]) for r in valid) / n
        base_acc = sum(int(r["baseline_correct_offline"]) for r in valid) / n
        rec = sum(1 for r in valid if r["baseline_correct_offline"] == 0 and r["rule_correct_offline"] == 1)
        reg = sum(1 for r in valid if r["baseline_correct_offline"] == 1 and r["rule_correct_offline"] == 0)
        over = sum(int(r["override"]) for r in valid)
        metrics["rules"].setdefault(rule, {})[split] = {
            "n": n,
            "baseline_accuracy": base_acc,
            "rule_accuracy": acc,
            "delta_vs_baseline": acc - base_acc,
            "recoveries": rec,
            "regressions": reg,
            "net_gain": rec - reg,
            "overrides": over,
        }

    # Candidate rule summary on stress-test A.
    stress_rows = [r for r in all_decisions if r["dataset_split"] == "A"]
    by_rule_stress: dict[str, list[dict[str, Any]]] = {}
    for r in stress_rows:
        by_rule_stress.setdefault(r["rule"], []).append(r)
    candidate_rule_rows: list[dict[str, Any]] = []
    for rule, rows in sorted(by_rule_stress.items()):
        valid = [r for r in rows if r["rule_correct_offline"] is not None and r["baseline_correct_offline"] is not None]
        if not valid:
            continue
        rec = sum(1 for r in valid if r["baseline_correct_offline"] == 0 and r["rule_correct_offline"] == 1)
        reg = sum(1 for r in valid if r["baseline_correct_offline"] == 1 and r["rule_correct_offline"] == 0)
        changed = [r for r in valid if r["override"] == 1]
        precision = (rec / len(changed)) if changed else 0.0
        candidate_rule_rows.append(
            {
                "rule": rule,
                "support_failures_captured": rec,
                "counterexamples_regressed": reg,
                "net_gain": rec - reg,
                "trigger_count": len(changed),
                "precision_estimate": round(precision, 4),
                "inference_available": "yes",
                "uses_offline_only_labels_as_trigger": "no",
                "implementation_complexity": "low" if rule in {"R0_keep_fix24", "R2_3of3_only"} else "medium",
            }
        )

    # Pattern bucket eval.
    pattern_bucket_eval: list[dict[str, Any]] = []
    bucket_grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in pattern_rows:
        bucket_grouped.setdefault((r["rule"], r["offline_bucket"]), []).append(r)
    for (rule, bucket), rows in sorted(bucket_grouped.items()):
        valid = [r for r in rows if r["rule_correct_offline"] is not None and r["baseline_correct_offline"] is not None]
        if not valid:
            continue
        rec = sum(1 for r in valid if r["baseline_correct_offline"] == 0 and r["rule_correct_offline"] == 1)
        reg = sum(1 for r in valid if r["baseline_correct_offline"] == 1 and r["rule_correct_offline"] == 0)
        pattern_bucket_eval.append(
            {
                "rule": rule,
                "pattern_bucket": bucket,
                "n": len(valid),
                "recoveries": rec,
                "regressions": reg,
                "net_gain": rec - reg,
            }
        )

    # Counterexample stress test table (A counterexample subset only).
    cx_rows = [r for r in all_decisions if r["dataset_split"] == "A" and r["offline_bucket"] == "counterexample_pool"]
    cx_by_rule: dict[str, list[dict[str, Any]]] = {}
    for r in cx_rows:
        cx_by_rule.setdefault(r["rule"], []).append(r)
    counterexample_eval: list[dict[str, Any]] = []
    for rule, rows in sorted(cx_by_rule.items()):
        valid = [r for r in rows if r["rule_correct_offline"] is not None and r["baseline_correct_offline"] is not None]
        if not valid:
            continue
        regressions = [r for r in valid if r["baseline_correct_offline"] == 1 and r["rule_correct_offline"] == 0]
        recoveries = [r for r in valid if r["baseline_correct_offline"] == 0 and r["rule_correct_offline"] == 1]
        counterexample_eval.append(
            {
                "rule": rule,
                "n_counterexamples": len(valid),
                "recoveries": len(recoveries),
                "regressions": len(regressions),
                "net_gain": len(recoveries) - len(regressions),
                "false_positive_example_ids": "|".join(r["example_id"] for r in regressions[:20]),
                "risk_level": "high" if len(regressions) >= 3 else ("medium" if len(regressions) >= 1 else "low"),
            }
        )

    # Choose best rule on stress set (excluding R0).
    deploy_candidates = [r for r in candidate_rule_rows if r["rule"] != "R0_keep_fix24"]
    deploy_candidates.sort(
        key=lambda r: (
            int(r["net_gain"]),
            -int(r["counterexamples_regressed"]),
            float(r["precision_estimate"]),
        ),
        reverse=True,
    )
    best_rule = deploy_candidates[0]["rule"] if deploy_candidates else "R0_keep_fix24"
    best_row = deploy_candidates[0] if deploy_candidates else None

    # Conservative decision gate.
    if best_row and int(best_row["net_gain"]) >= 3 and int(best_row["counterexamples_regressed"]) == 0:
        recommendation = "D"
        decision_rationale = "tight external-majority realized-in-pool rule shows low-risk positive net on offline stress set"
    else:
        recommendation = "B"
        decision_rationale = "offline gains are not strong enough / low-risk enough for promotion before independent final validation"

    # Policy definition JSON.
    policy_definition = {
        "policy_name": "fix7_cluster_selector_v0_offline",
        "runtime_label_only": True,
        "base_policy_kept": "FIX-2+FIX-4",
        "rules": {
            "R0_keep_fix24": "Keep baseline selection.",
            "R1_margin_grid": "Override when challenger has stronger frontier/path support and sufficient top2 support margin.",
            "R2_external_majority_variants": "Override with 2/3 or 3/3 external agreement under realization/parser guards.",
            "R3_present_not_selected": "Override only for low-margin baseline and strong alternate support.",
            "R4_parser_confidence_correction": "Override low-confidence baseline with high-confidence parser alternative.",
            "R5_combined_v0": "Ordered conservative union: R4 -> strict R2 -> strict R1.",
        },
        "guard_order_for_R5": [
            "R4_parser_confidence_correction",
            "R2_3of3_realized_nonlowdepth",
            "R1_margin2",
            "else_keep_baseline",
        ],
        "forbidden_runtime_features": ["gold_answer", "exact_match", "correctness", "example_id", "artifact_path"],
    }

    next_decision = {
        "decision": recommendation,
        "recommendation_code": recommendation,
        "recommended_best_rule": best_rule,
        "reason": decision_rationale,
        "promotion_ready": bool(recommendation in {"A", "D"}),
        "safety_notes": [
            "offline-only prototype",
            "no provider/API calls used",
            "keep FIX-2+FIX-4 as deployed policy until independent confirmation",
        ],
    }

    # Report markdown.
    lines = [
        "# FIX-7 Offline Evaluation Report",
        "",
        f"- Output root: `{out_root}`",
        "- Scope: offline-only prototype of cluster-level selector + robust parser arbitration.",
        "- Runtime policy unchanged: FIX-2+FIX-4 remains deployed baseline.",
        "",
        "## Datasets",
        f"- A (failure+counterexample stress): {len(dataset_a)} groups",
        f"- B (main 300 validation, seed=41): {len(dataset_b)} groups",
        f"- C (previous replayable cases, reliable subset): {len(dataset_c)} groups",
        "",
        "## Best Offline Rule (Stress A)",
        f"- best_rule: `{best_rule}`",
    ]
    if best_row:
        lines.extend(
            [
                f"- recoveries: {best_row['support_failures_captured']}",
                f"- regressions: {best_row['counterexamples_regressed']}",
                f"- net_gain: {best_row['net_gain']}",
                f"- precision_estimate: {best_row['precision_estimate']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Decision",
            f"- recommendation: **{recommendation}**",
            f"- rationale: {decision_rationale}",
            "- claim scope: no promotion claim; offline evidence only.",
            "",
            "## Safety Confirmation",
            "- no API/provider calls",
            "- no use of in-progress final validation outputs for evaluation",
            "- no output deletion/overwrite",
            "- gold/exact used only as offline labels for scoring",
            "",
        ]
    )

    # Write required files.
    (out_root / "fix7_offline_eval_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_root / "fix7_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    _write_csv(out_root / "fix7_cluster_feature_table.csv", all_cluster_rows)
    _write_csv(out_root / "fix7_case_decisions.csv", all_decisions)
    _write_csv(out_root / "fix7_override_cases.csv", override_cases)
    _write_csv(out_root / "fix7_regression_cases.csv", regression_cases)
    with (out_root / "fix7_recovery_cases.jsonl").open("w", encoding="utf-8") as f:
        for row in recovery_cases:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    _write_csv(out_root / "fix7_parser_audit_cases.csv", parser_audit_rows)
    _write_csv(out_root / "fix7_pattern_bucket_eval.csv", pattern_bucket_eval)
    _write_csv(out_root / "fix7_counterexample_stress_test.csv", counterexample_eval)
    (out_root / "fix7_policy_definition.json").write_text(json.dumps(policy_definition, indent=2) + "\n", encoding="utf-8")
    _write_csv(out_root / "fix7_candidate_rules.csv", candidate_rule_rows)
    (out_root / "fix7_next_decision.json").write_text(json.dumps(next_decision, indent=2) + "\n", encoding="utf-8")

    print(str(out_root))


if __name__ == "__main__":
    main()
