#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "missing_gold_topology_v1"
DEFAULT_TRACE_PACKETS = Path("/tmp/codex_pattern_mining_wrong_consensus_97_packets/trace_packets.jsonl")
DEFAULT_CASEBOOK = (
    REPO_ROOT
    / "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
)
DEFAULT_BFTC_DIR = REPO_ROOT / "outputs/bftc_live_pilot_v1_20cases_20260512T210634Z"
DEFAULT_EXEC_DIR = REPO_ROOT / "outputs/bftc_executable_repair_v1_live_20cases_20260512T221521Z"
DEFAULT_REBINDING_DIR = REPO_ROOT / "outputs/bftc_candidate_rebinding_selector_v1_20260512T224257Z"

MISSING_EDGE_TYPES = {
    "target_rebinding",
    "inverse_state_transition",
    "difference_to_total",
    "total_to_difference",
    "per_unit_to_total",
    "total_to_per_unit",
    "ratio_base_correction",
    "percentage_base_correction",
    "unit_conversion",
    "profit_to_sale_price",
    "sale_price_to_profit",
    "original_before_process",
    "final_after_process",
    "equation_setup_missing",
    "source_fact_missing",
    "relation_composition_missing",
    "arithmetic_precision",
    "prompt_gold_inconsistent",
    "selector_rebinding",
    "unknown",
}
NEEDED_BRANCH_FAMILIES = {
    "backward_from_target_check",
    "declarative_equation_branch",
    "target_variable_dict_pal",
    "unit_conversion_branch",
    "ratio_base_check",
    "inverse_relation_solver",
    "source_fact_extraction",
    "selector_rebinding",
    "relation_verifier",
    "other",
}
TREE_TOPOLOGY_LABELS = {
    "wrong_target_basin_collapse",
    "diverse_wrong_pool",
    "near_miss_pool",
    "missing_source_fact",
    "missing_relation_composition",
    "selector_only_failure",
    "prompt_gold_inconsistent",
    "unknown",
}
REQUIRED_API_FIELDS = {
    "closest_explored_node",
    "closest_candidate_value",
    "missing_edge_type",
    "missing_edge_description",
    "estimated_steps_from_closest_node_to_gold",
    "needed_branch_family",
    "tree_topology_label",
    "existing_tree_had_needed_facts",
    "deterministic_repair_possible",
    "new_generation_needed",
    "confidence",
    "rationale",
}
FORBIDDEN_PROMPT_PATTERNS = [
    re.compile(r"\bgold_answer\b\s*[:=]", re.I),
    re.compile(r"\banswer_key\b\s*[:=]", re.I),
    re.compile(r"\bhidden[_ -]?labels?\b\s*[:=]", re.I),
]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _normalize_numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _stringify(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_numeric_key(value: float) -> str:
    if abs(value - round(value)) <= 1e-9:
        return str(int(round(value)))
    return f"{value:.12g}"


def _normalize_answer(value: Any) -> str:
    numeric = _normalize_numeric(value)
    if numeric is None:
        return _stringify(value)
    return _normalize_numeric_key(numeric)


def _relative_distance(candidate: float, gold: float) -> float:
    denom = max(abs(gold), 1e-9)
    return abs(candidate - gold) / denom


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _lexical_overlap(a: str, b: str) -> float:
    tokens_a = set(_tokenize(a))
    tokens_b = set(_tokenize(b))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_b)


def _boolish(value: Any) -> bool:
    text = _stringify(value).lower()
    return text not in {"", "0", "0.0", "false", "no", "none", "nan", "unknown"}


def _contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _load_casebook(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["case_id"]: dict(row) for row in csv.DictReader(handle) if row.get("case_id")}


def _load_trace_packets(path: Path) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict) and isinstance(obj.get("cases"), list):
                for case in obj["cases"]:
                    if isinstance(case, dict) and _stringify(case.get("case_id")):
                        cases[_stringify(case["case_id"])] = case
            elif isinstance(obj, dict) and _stringify(obj.get("case_id")):
                cases[_stringify(obj["case_id"])] = obj
    return cases


def _group_jsonl_by_case(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    return {row["case_id"]: row for row in _load_jsonl(path) if row.get("case_id")}


def _load_bftc_bundle(path: Path | None) -> dict[str, dict[str, dict[str, Any]]]:
    if path is None or not path.is_dir():
        return {"candidate_rows": {}, "parsed": {}, "raw": {}, "analysis": {}}
    return {
        "candidate_rows": _group_jsonl_by_case(path / "candidate_rows.jsonl"),
        "parsed": _group_jsonl_by_case(path / "parsed_responses.jsonl"),
        "raw": _group_jsonl_by_case(path / "raw_responses.jsonl"),
        "analysis": _group_jsonl_by_case(path / "bftc_case_error_analysis.jsonl"),
    }


def _parse_json_object_text(text: str) -> dict[str, Any] | None:
    stripped = _stringify(text)
    if not stripped:
        return None
    try:
        obj = json.loads(stripped)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", stripped, re.S)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _load_exec_bundle(path: Path | None) -> dict[str, dict[str, dict[str, Any]]]:
    if path is None or not path.is_dir():
        return {"candidate_rows": {}, "parsed": {}, "raw": {}, "analysis": {}, "response_json": {}}
    raw = _group_jsonl_by_case(path / "raw_responses.jsonl")
    response_json: dict[str, dict[str, Any]] = {}
    for case_id, row in raw.items():
        parsed = _parse_json_object_text(row.get("raw_response"))
        if parsed is not None:
            response_json[case_id] = parsed
    return {
        "candidate_rows": _group_jsonl_by_case(path / "executable_candidate_rows.jsonl"),
        "parsed": _group_jsonl_by_case(path / "parsed_responses.jsonl"),
        "raw": raw,
        "analysis": _group_jsonl_by_case(path / "bftc_executable_case_error_analysis.jsonl"),
        "response_json": response_json,
    }


def _load_rebinding_bundle(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_dir():
        return {"candidate_rows": {}, "summary": {}}
    candidate_rows = defaultdict(list)
    for row in _load_jsonl(path / "candidate_set_rows.jsonl"):
        case_id = _stringify(row.get("case_id"))
        if case_id:
            candidate_rows[case_id].append(row)
    summary = json.loads((path / "selector_summary.json").read_text(encoding="utf-8")) if (path / "selector_summary.json").is_file() else {}
    return {"candidate_rows": dict(candidate_rows), "summary": summary}


def _new_candidate_entry(value: float) -> dict[str, Any]:
    return {
        "value": value,
        "value_normalized": _normalize_numeric_key(value),
        "provenance_types": set(),
        "branch_families": set(),
        "source_texts": [],
        "support_count": 0.0,
        "occurrence_count": 0,
        "variable_names": set(),
        "variable_descriptions": set(),
        "variable_units": set(),
    }


def _append_text(row: dict[str, Any], text: str) -> None:
    text = _stringify(text)
    if text and text not in row["source_texts"]:
        row["source_texts"].append(text[:600])


def add_candidate_record(
    candidate_map: dict[str, dict[str, Any]],
    value: Any,
    *,
    provenance: str,
    branch_family: str = "",
    source_text: str = "",
    support_count: float = 0.0,
    variable_name: str = "",
    variable_description: str = "",
    variable_unit: str = "",
) -> None:
    numeric = _normalize_numeric(value)
    if numeric is None:
        return
    key = _normalize_numeric_key(numeric)
    row = candidate_map.setdefault(key, _new_candidate_entry(numeric))
    row["provenance_types"].add(provenance)
    if branch_family:
        row["branch_families"].add(branch_family)
    row["support_count"] += float(support_count or 0.0)
    row["occurrence_count"] += 1
    if variable_name:
        row["variable_names"].add(variable_name)
    if variable_description:
        row["variable_descriptions"].add(variable_description)
    if variable_unit:
        row["variable_units"].add(variable_unit)
    _append_text(row, source_text)


def _extract_trace_candidates(trace_case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    candidate_map: dict[str, dict[str, Any]] = {}
    for value in trace_case.get("candidate_answers") or []:
        add_candidate_record(candidate_map, value, provenance="trace_candidate_answers")
    for value in trace_case.get("selector_candidate_pool") or []:
        add_candidate_record(candidate_map, value, provenance="selector_candidate_pool")
    add_candidate_record(candidate_map, trace_case.get("direct_reserve_answer"), provenance="direct_reserve_answer")
    add_candidate_record(candidate_map, trace_case.get("frontier_candidate_answer"), provenance="frontier_candidate_answer")
    add_candidate_record(candidate_map, trace_case.get("model_final_prediction"), provenance="model_final_prediction")
    add_candidate_record(
        candidate_map,
        ((trace_case.get("pal_exec_summary") or {}).get("pal_answer")),
        provenance="pal_exec_answer",
    )
    for row in trace_case.get("candidate_answer_groups") or []:
        add_candidate_record(
            candidate_map,
            row.get("candidate_answer"),
            provenance="candidate_answer_group",
            branch_family=_stringify(row.get("source_family")),
            support_count=float(_normalize_numeric(row.get("support_count")) or 0.0),
        )
    structural_rows = ((trace_case.get("structural_fields") or {}).get("candidate_rows")) or []
    for row in structural_rows:
        add_candidate_record(
            candidate_map,
            row.get("candidate_answer"),
            provenance="structural_candidate",
            branch_family=_stringify(row.get("branch_family")),
            source_text=_stringify(row.get("candidate_trace")),
            support_count=float(_normalize_numeric(row.get("structural_selector_score")) or 0.0),
        )
    return candidate_map


def _extract_exec_formula_variables(case_id: str, exec_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    parsed = exec_bundle["response_json"].get(case_id, {})
    formula_variables = parsed.get("formula_variables")
    rows: list[dict[str, Any]] = []
    if isinstance(formula_variables, dict):
        for name, meta in formula_variables.items():
            if not isinstance(meta, dict):
                continue
            rows.append(
                {
                    "name": _stringify(name),
                    "value": meta.get("value"),
                    "description": _stringify(meta.get("description")),
                    "unit": _stringify(meta.get("unit")),
                }
            )
    analysis_row = exec_bundle["analysis"].get(case_id, {})
    if not rows and _stringify(analysis_row.get("formula_variables_json")):
        try:
            meta_obj = json.loads(_stringify(analysis_row["formula_variables_json"]))
        except json.JSONDecodeError:
            meta_obj = {}
        if isinstance(meta_obj, dict):
            for name, meta in meta_obj.items():
                if not isinstance(meta, dict):
                    continue
                rows.append(
                    {
                        "name": _stringify(name),
                        "value": meta.get("value"),
                        "description": _stringify(meta.get("description")),
                        "unit": _stringify(meta.get("unit")),
                    }
                )
    return rows


def _combine_candidates(
    *,
    case_id: str,
    trace_case: dict[str, Any],
    bftc_bundle: dict[str, Any],
    exec_bundle: dict[str, Any],
    rebinding_bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    candidate_map = _extract_trace_candidates(trace_case)

    bftc_candidate_row = bftc_bundle["candidate_rows"].get(case_id, {})
    add_candidate_record(candidate_map, bftc_candidate_row.get("fa_numeric"), provenance="bftc_only_final")
    for value in bftc_candidate_row.get("candidate_pool") or []:
        add_candidate_record(candidate_map, value, provenance="bftc_candidate_pool")

    exec_candidate_row = exec_bundle["candidate_rows"].get(case_id, {})
    add_candidate_record(candidate_map, exec_candidate_row.get("executable_final_answer"), provenance="exec_formula_final")
    for value in exec_candidate_row.get("candidate_pool") or []:
        add_candidate_record(candidate_map, value, provenance="exec_candidate_pool")

    exec_analysis_row = exec_bundle["analysis"].get(case_id, {})
    add_candidate_record(candidate_map, exec_analysis_row.get("model_final_answer"), provenance="exec_model_final")
    add_candidate_record(candidate_map, exec_analysis_row.get("bftc_only_final_answer"), provenance="bftc_only_final")

    exec_raw = exec_bundle["response_json"].get(case_id, {})
    add_candidate_record(candidate_map, exec_raw.get("final_answer"), provenance="final_answer_field")
    add_candidate_record(candidate_map, exec_analysis_row.get("closest_formula_variable_value"), provenance="closest_formula_variable")

    for variable in _extract_exec_formula_variables(case_id, exec_bundle):
        add_candidate_record(
            candidate_map,
            variable.get("value"),
            provenance="formula_variable",
            variable_name=_stringify(variable.get("name")),
            variable_description=_stringify(variable.get("description")),
            variable_unit=_stringify(variable.get("unit")),
        )

    for row in rebinding_bundle.get("candidate_rows", {}).get(case_id, []):
        add_candidate_record(
            candidate_map,
            row.get("candidate_value"),
            provenance="rebinding_candidate_set",
            variable_name="|".join(row.get("variable_names") or []),
            variable_description="|".join(row.get("variable_descriptions") or []),
            variable_unit="|".join(row.get("variable_units") or []),
        )

    out: list[dict[str, Any]] = []
    for row in candidate_map.values():
        out.append(
            {
                "value": row["value"],
                "value_normalized": row["value_normalized"],
                "provenance_types": sorted(row["provenance_types"]),
                "branch_families": sorted(row["branch_families"]),
                "source_texts": row["source_texts"][:4],
                "support_count": row["support_count"],
                "occurrence_count": row["occurrence_count"],
                "variable_names": sorted(row["variable_names"]),
                "variable_descriptions": sorted(row["variable_descriptions"]),
                "variable_units": sorted(row["variable_units"]),
            }
        )
    out.sort(key=lambda row: (row["value"], row["value_normalized"]))
    return out


def select_closest_numeric_candidate(candidates: list[dict[str, Any]], gold: float) -> dict[str, Any] | None:
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda row: (
            abs(row["value"] - gold),
            -row.get("occurrence_count", 0),
            -row.get("support_count", 0.0),
            len(row.get("provenance_types", [])),
            row["value"],
        ),
    )


def _unit_match_any(units: list[str], question: str, target: str) -> bool:
    joined = f"{question} {target}".lower()
    for unit in units:
        unit_l = unit.lower()
        if not unit_l:
            continue
        if unit_l in {"$", "dollar", "dollars"} and ("$" in joined or "dollar" in joined):
            return True
        if unit_l in {"%", "percent", "percentage"} and ("%" in joined or "percent" in joined or "percentage" in joined):
            return True
        if unit_l in joined:
            return True
    return False


def _semantic_score(candidate: dict[str, Any], question: str, target: str, gold: float) -> float:
    score = 0.0
    texts = candidate.get("variable_descriptions", []) + candidate.get("variable_names", []) + candidate.get("source_texts", [])
    for text in texts:
        score = max(score, _lexical_overlap(text, target))
    if _unit_match_any(candidate.get("variable_units", []), question, target):
        score += 0.2
    if candidate.get("branch_families"):
        if any("target" in family or "relation" in family for family in candidate["branch_families"]):
            score += 0.1
    score -= min(_relative_distance(candidate["value"], gold), 4.0) * 0.1
    return score


def select_closest_semantic_candidate(
    candidates: list[dict[str, Any]],
    question: str,
    target: str,
    gold: float,
) -> dict[str, Any] | None:
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            _semantic_score(row, question, target, gold),
            -abs(row["value"] - gold),
            row["value"],
        ),
    )


def build_candidate_cluster_structure(candidates: list[dict[str, Any]], gold: float) -> dict[str, Any]:
    numerics = sorted(candidates, key=lambda row: row["value"])
    if not numerics:
        return {
            "num_distinct_numeric_clusters": 0,
            "dominant_wrong_cluster": "",
            "branches_collapsed_around_one_wrong_answer": False,
        }
    clusters: list[list[dict[str, Any]]] = []
    for candidate in numerics:
        if not clusters:
            clusters.append([candidate])
            continue
        previous = clusters[-1][-1]["value"]
        tolerance = max(1.0, abs(previous) * 0.05, abs(candidate["value"]) * 0.05)
        if abs(candidate["value"] - previous) <= tolerance:
            clusters[-1].append(candidate)
        else:
            clusters.append([candidate])

    def cluster_weight(rows: list[dict[str, Any]]) -> float:
        return sum(max(1, row.get("occurrence_count", 0)) + row.get("support_count", 0.0) for row in rows)

    cluster_summaries: list[dict[str, Any]] = []
    for rows in clusters:
        center = sum(row["value"] for row in rows) / len(rows)
        cluster_summaries.append(
            {
                "center": center,
                "members": [_normalize_numeric_key(row["value"]) for row in rows],
                "weight": cluster_weight(rows),
                "contains_gold": any(abs(row["value"] - gold) <= 1e-9 for row in rows),
            }
        )
    wrong_clusters = [row for row in cluster_summaries if not row["contains_gold"]]
    dominant = max(wrong_clusters or cluster_summaries, key=lambda row: (row["weight"], len(row["members"])))
    total_weight = sum(row["weight"] for row in cluster_summaries) or 1.0
    return {
        "num_distinct_numeric_clusters": len(cluster_summaries),
        "dominant_wrong_cluster": json.dumps(
            {
                "center": _normalize_numeric_key(dominant["center"]),
                "members": dominant["members"],
                "weight": round(dominant["weight"], 3),
            },
            ensure_ascii=False,
        ),
        "branches_collapsed_around_one_wrong_answer": dominant["weight"] / total_weight >= 0.6,
    }


def has_selector_rebinding_signal(
    baseline_selected_answer: str,
    gold: float,
    candidates: list[dict[str, Any]],
    rebinding_rows: list[dict[str, Any]],
) -> bool:
    gold_key = _normalize_numeric_key(gold)
    baseline_key = _normalize_answer(baseline_selected_answer)
    if baseline_key == gold_key:
        return False
    if any(_boolish(row.get("candidate_matches_gold")) for row in rebinding_rows):
        return True
    return any(row["value_normalized"] == gold_key for row in candidates)


def assign_missing_edge_type(
    *,
    question: str,
    target_text: str,
    question_type: str,
    prompt_gold_consistency: str,
    selector_rebinding_signal: bool,
    primary_category: str,
    previous_category: str,
    failure_axis: str,
    diagnosis: str,
    minimal_fix: str,
    target_correct: bool | None,
    relative_distance: float | None,
) -> str:
    if prompt_gold_consistency == "definite_mismatch":
        return "prompt_gold_inconsistent"
    if selector_rebinding_signal:
        return "selector_rebinding"

    blob = " ".join(
        [
            question.lower(),
            target_text.lower(),
            question_type.lower(),
            prompt_gold_consistency.lower(),
            primary_category.lower(),
            previous_category.lower(),
            failure_axis.lower(),
            diagnosis.lower(),
            minimal_fix.lower(),
        ]
    )

    if (
        "unit conversion" in blob
        or "unit_or_scale" in blob
        or "unit_scale" in blob
        or "feet" in blob
        or "inches" in blob
        or "meters" in blob
        or "centimeters" in blob
    ):
        return "unit_conversion"
    if "profit" in target_text.lower():
        return "sale_price_to_profit"
    if "sale price" in target_text.lower():
        return "profit_to_sale_price"
    if "before" in target_text.lower() or "original" in target_text.lower():
        return "original_before_process"
    if "after" in target_text.lower() or "final state" in target_text.lower():
        return "final_after_process"
    if "state_before_after" in blob or "inverse" in blob:
        return "inverse_state_transition"
    if "ratio_or_percentage" in blob or "circular %" in blob or "%" in question or "percent" in question.lower():
        return "percentage_base_correction"
    if "ratio" in blob or "proportion" in blob:
        return "ratio_base_correction"
    if "difference" in blob and _contains_any(target_text, ["total", "combined", "altogether", "in total"]):
        return "difference_to_total"
    if _contains_any(question, ["how many more", "how much more", "difference"]) and not _contains_any(target_text, ["total", "combined", "altogether", "in total"]):
        return "total_to_difference"
    if _contains_any(blob, ["per pair", "each", "per-unit", "per unit", "share"]) and _contains_any(
        target_text,
        ["total", "altogether", "in total", "amount", "used", "spent"],
    ):
        return "per_unit_to_total"
    if _contains_any(blob, ["average", "each", "per-unit", "per unit"]) and _contains_any(
        target_text,
        ["each", "average", "per"],
    ):
        return "total_to_per_unit"
    if "source_fact" in blob or "dropped" in blob or "missed one category" in blob:
        return "source_fact_missing"
    if "relation_construction" in blob or "wrong relation" in blob or "wrong variable binding" in blob:
        return "relation_composition_missing"
    if "equation" in blob or "sympy" in blob or "solve the two equations" in blob:
        return "equation_setup_missing"
    if relative_distance is not None and relative_distance <= 0.2:
        return "arithmetic_precision"
    if target_correct is False or "wrong target" in blob or "requested_target" in blob:
        return "target_rebinding"
    return "unknown"


def estimate_steps_from_closest_node(
    *,
    gold_present: bool,
    missing_edge_type: str,
    deterministic_repair_possible: bool,
    new_generation_needed: bool,
) -> int:
    if gold_present:
        return 0
    if missing_edge_type in {
        "selector_rebinding",
        "unit_conversion",
        "ratio_base_correction",
        "percentage_base_correction",
        "difference_to_total",
        "total_to_difference",
        "per_unit_to_total",
        "total_to_per_unit",
        "sale_price_to_profit",
        "profit_to_sale_price",
        "original_before_process",
        "final_after_process",
        "inverse_state_transition",
        "arithmetic_precision",
    }:
        return 1 if deterministic_repair_possible else 2
    if missing_edge_type in {"equation_setup_missing", "relation_composition_missing", "target_rebinding"}:
        return 2 if deterministic_repair_possible else 3
    if missing_edge_type == "source_fact_missing":
        return 3
    if new_generation_needed:
        return 4
    return 2


def map_needed_branch_family(missing_edge_type: str) -> str:
    mapping = {
        "selector_rebinding": "selector_rebinding",
        "unit_conversion": "unit_conversion_branch",
        "ratio_base_correction": "ratio_base_check",
        "percentage_base_correction": "ratio_base_check",
        "original_before_process": "inverse_relation_solver",
        "final_after_process": "inverse_relation_solver",
        "inverse_state_transition": "inverse_relation_solver",
        "difference_to_total": "backward_from_target_check",
        "total_to_difference": "backward_from_target_check",
        "per_unit_to_total": "backward_from_target_check",
        "total_to_per_unit": "backward_from_target_check",
        "sale_price_to_profit": "backward_from_target_check",
        "profit_to_sale_price": "backward_from_target_check",
        "equation_setup_missing": "declarative_equation_branch",
        "relation_composition_missing": "relation_verifier",
        "source_fact_missing": "source_fact_extraction",
        "target_rebinding": "target_variable_dict_pal",
        "arithmetic_precision": "declarative_equation_branch",
        "prompt_gold_inconsistent": "other",
        "unknown": "other",
    }
    return mapping.get(missing_edge_type, "other")


def map_tree_topology_label(
    *,
    missing_edge_type: str,
    prompt_gold_consistency: str,
    selector_rebinding_signal: bool,
    relative_distance: float | None,
    cluster_structure: dict[str, Any],
) -> str:
    if prompt_gold_consistency == "definite_mismatch":
        return "prompt_gold_inconsistent"
    if selector_rebinding_signal:
        return "selector_only_failure"
    if missing_edge_type == "source_fact_missing":
        return "missing_source_fact"
    if missing_edge_type in {"equation_setup_missing", "relation_composition_missing"}:
        return "missing_relation_composition"
    if relative_distance is not None and relative_distance <= 0.2:
        return "near_miss_pool"
    if cluster_structure.get("num_distinct_numeric_clusters", 0) > 2:
        return "diverse_wrong_pool"
    if cluster_structure.get("branches_collapsed_around_one_wrong_answer"):
        return "wrong_target_basin_collapse"
    return "unknown"


def _analysis_packet(
    *,
    case_id: str,
    question: str,
    gold: float,
    allow_gold: bool,
    baseline_selected_answer: str,
    target_text: str,
    candidate_rows: list[dict[str, Any]],
    bftc_analysis: dict[str, Any],
    exec_analysis: dict[str, Any],
    rebinding_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    packet = {
        "case_id": case_id,
        "question": question,
        "baseline_selected_answer": baseline_selected_answer,
        "target_text": target_text,
        "explored_candidates": [
            {
                "value": row["value_normalized"],
                "provenance_types": row["provenance_types"],
                "branch_families": row["branch_families"],
                "variable_names": row["variable_names"],
                "variable_descriptions": row["variable_descriptions"],
            }
            for row in candidate_rows[:12]
        ],
        "bftc_summary": {
            "answer": bftc_analysis.get("fa"),
            "error_category": bftc_analysis.get("error_category"),
            "failed_relation": bftc_analysis.get("failed_relation"),
            "repair_operation": bftc_analysis.get("repair_operation"),
            "deterministic_repair_possible": bftc_analysis.get("deterministic_repair_possible"),
        },
        "executable_summary": {
            "model_final_answer": exec_analysis.get("model_final_answer"),
            "executable_final_answer": exec_analysis.get("executable_final_answer"),
            "primary_category": exec_analysis.get("primary_category"),
            "failure_axis": exec_analysis.get("failure_axis"),
            "formula_variables_assessment": exec_analysis.get("formula_variables_assessment"),
            "closest_formula_variable_name": exec_analysis.get("closest_formula_variable_name"),
            "closest_formula_variable_value": exec_analysis.get("closest_formula_variable_value"),
            "minimal_fix": exec_analysis.get("minimal_fix"),
        },
        "candidate_rebinding_summary": {
            "oracle_recoverable": sum(1 for row in rebinding_rows if _boolish(row.get("candidate_matches_gold"))) > 0,
            "top_overlap_candidates": [
                {
                    "value": row.get("candidate_value_normalized"),
                    "overlap_score": row.get("selector_overlap_score"),
                    "candidate_matches_gold": row.get("candidate_matches_gold"),
                }
                for row in rebinding_rows[:5]
            ],
        },
        "prompt_gold_consistency": exec_analysis.get("prompt_gold_consistency") or "unknown",
    }
    if allow_gold:
        packet["gold_answer"] = _normalize_numeric_key(gold)
    return packet


def build_api_prompt(packet: dict[str, Any], allow_gold: bool) -> str:
    gold_line = ""
    if allow_gold:
        gold_line = f'gold_answer: "{packet.get("gold_answer", "")}"\n'
    return (
        "ANALYSIS MODE ONLY. This prompt is for offline diagnostic labeling only.\n"
        "Do not solve the problem from scratch. Classify the missing-edge topology using the explored artifacts.\n"
        "This output is not for runtime, not for provider-request reuse, and not for candidate generation.\n\n"
        "Return a single strict JSON object with exactly these keys:\n"
        "{\n"
        '  "closest_explored_node": "...",\n'
        '  "closest_candidate_value": "...",\n'
        '  "missing_edge_type": "...",\n'
        '  "missing_edge_description": "...",\n'
        '  "estimated_steps_from_closest_node_to_gold": 0,\n'
        '  "needed_branch_family": "...",\n'
        '  "tree_topology_label": "...",\n'
        '  "existing_tree_had_needed_facts": true,\n'
        '  "deterministic_repair_possible": true,\n'
        '  "new_generation_needed": true,\n'
        '  "confidence": 0.0,\n'
        '  "rationale": "short"\n'
        "}\n\n"
        "Allowed missing_edge_type values:\n"
        + ", ".join(sorted(MISSING_EDGE_TYPES))
        + "\n\nAllowed needed_branch_family values:\n"
        + ", ".join(sorted(NEEDED_BRANCH_FAMILIES))
        + "\n\nAllowed tree_topology_label values:\n"
        + ", ".join(sorted(TREE_TOPOLOGY_LABELS))
        + "\n\n"
        f'case_id: "{packet["case_id"]}"\n'
        f'question: "{packet["question"]}"\n'
        + gold_line
        + f'baseline_selected_answer: "{packet["baseline_selected_answer"]}"\n'
        f'target_text: "{packet["target_text"]}"\n'
        f"analysis_packet_json:\n{json.dumps(packet, ensure_ascii=False, indent=2)}\n"
    )


def _audit_prompt(prompt_text: str, case_id: str, allow_gold: bool) -> dict[str, Any]:
    violations: list[str] = []
    for pattern in FORBIDDEN_PROMPT_PATTERNS:
        if allow_gold and pattern.pattern == r"\bgold_answer\b\s*[:=]":
            continue
        if pattern.search(prompt_text):
            violations.append(pattern.pattern)
    gold_in_prompt = '"gold_answer"' in prompt_text
    return {
        "case_id": case_id,
        "prompt_sha256": _sha256(prompt_text),
        "gold_in_prompt": gold_in_prompt,
        "gold_free": (not gold_in_prompt) if not allow_gold else False,
        "analysis_only_gold_conditioned": allow_gold,
        "not_for_runtime": True,
        "not_for_provider_request_reuse": True,
        "violations": violations,
    }


def parse_api_label_response(text: str) -> tuple[dict[str, Any] | None, str]:
    payload = _parse_json_object_text(text)
    if payload is None:
        return None, "json_parse_failed"
    missing = sorted(REQUIRED_API_FIELDS - set(payload))
    if missing:
        return None, f"missing_fields:{','.join(missing)}"
    if _stringify(payload.get("missing_edge_type")) not in MISSING_EDGE_TYPES:
        return None, "invalid_missing_edge_type"
    if _stringify(payload.get("needed_branch_family")) not in NEEDED_BRANCH_FAMILIES:
        return None, "invalid_needed_branch_family"
    if _stringify(payload.get("tree_topology_label")) not in TREE_TOPOLOGY_LABELS:
        return None, "invalid_tree_topology_label"
    try:
        steps = int(payload.get("estimated_steps_from_closest_node_to_gold"))
    except (TypeError, ValueError):
        return None, "invalid_steps"
    if steps < 0:
        return None, "invalid_steps"
    try:
        confidence = float(payload.get("confidence"))
    except (TypeError, ValueError):
        return None, "invalid_confidence"
    if confidence < 0.0 or confidence > 1.0:
        return None, "invalid_confidence"
    for key in (
        "existing_tree_had_needed_facts",
        "deterministic_repair_possible",
        "new_generation_needed",
    ):
        if not isinstance(payload.get(key), bool):
            return None, f"invalid_bool:{key}"
    payload["estimated_steps_from_closest_node_to_gold"] = steps
    payload["confidence"] = confidence
    return payload, ""


def _load_cohere_client() -> Any:
    import cohere  # type: ignore

    api_key = os.environ.get("COHERE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is not set.")
    return cohere.ClientV2(api_key=api_key)


def _call_api(
    *,
    provider: str,
    client: Any,
    model: str,
    prompt_text: str,
    max_tokens: int,
    temperature: float,
) -> tuple[str, dict[str, Any]]:
    if provider != "cohere":
        raise ValueError(f"Unsupported provider: {provider}")
    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt_text}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    text = ""
    if hasattr(response, "message") and response.message:
        content = response.message.content
        if content and hasattr(content[0], "text"):
            text = content[0].text or ""
    usage: dict[str, Any] = {}
    if hasattr(response, "usage") and response.usage:
        try:
            usage = json.loads(json.dumps(response.usage, default=str))
        except Exception:
            usage = {"raw": str(response.usage)}
    return text, usage


def build_summary(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    missing_edge_counts = Counter(row["missing_edge_type"] for row in rows)
    branch_counts = Counter(row["needed_branch_family"] for row in rows)
    topology_counts = Counter(row["tree_topology_label"] for row in rows)
    step_counts = Counter(str(row["estimated_steps_from_closest_node_to_gold"]) for row in rows)
    label_source_counts = Counter(row["label_source"] for row in rows)
    summary = {
        "manifest": manifest,
        "case_count": len(rows),
        "missing_edge_type_counts": dict(sorted(missing_edge_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "needed_branch_family_counts": dict(sorted(branch_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "tree_topology_label_counts": dict(sorted(topology_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "distance_to_gold_step_counts": dict(sorted(step_counts.items(), key=lambda kv: (int(kv[0]), kv[0]))),
        "label_source_counts": dict(sorted(label_source_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "selector_rebinding_cases": sum(1 for row in rows if row["missing_edge_type"] == "selector_rebinding"),
        "prompt_gold_inconsistent_cases": sum(1 for row in rows if row["missing_edge_type"] == "prompt_gold_inconsistent"),
        "deterministic_local_repair_possible_cases": sum(1 for row in rows if row["deterministic_local_repair_possible"]),
        "new_model_generation_needed_cases": sum(1 for row in rows if row["new_model_generation_edge_needed"]),
        "existing_information_sufficient_cases": sum(1 for row in rows if row["existing_information_sufficient"]),
    }
    return summary


def build_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    top_edges = summary["missing_edge_type_counts"]
    top_families = summary["needed_branch_family_counts"]
    step_counts = summary["distance_to_gold_step_counts"]
    lines = [
        "# Missing Gold Topology v1 Report",
        "",
        f"- case_count: `{summary['case_count']}`",
        f"- selector_rebinding_cases: `{summary['selector_rebinding_cases']}`",
        f"- prompt_gold_inconsistent_cases: `{summary['prompt_gold_inconsistent_cases']}`",
        f"- deterministic_local_repair_possible_cases: `{summary['deterministic_local_repair_possible_cases']}`",
        f"- new_model_generation_needed_cases: `{summary['new_model_generation_needed_cases']}`",
        "",
        "## Missing Edge Counts",
    ]
    for key, value in top_edges.items():
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Needed Branch Families"]
    for key, value in top_families.items():
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Distance To Gold"]
    for key, value in step_counts.items():
        lines.append(f"- `{key}` step(s): {value}")
    lines += ["", "## Sample Cases"]
    for row in rows[:5]:
        lines.append(
            f"- `{row['case_id']}`: edge=`{row['missing_edge_type']}`, "
            f"steps={row['estimated_steps_from_closest_node_to_gold']}, "
            f"topology=`{row['tree_topology_label']}`"
        )
    return "\n".join(lines) + "\n"


def _csv_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (list, dict)):
            out[key] = json.dumps(value, ensure_ascii=False)
        else:
            out[key] = value
    return out


def _default_out_dir() -> Path:
    return REPO_ROOT / "outputs" / f"{EXPERIMENT_ID}_{_utc_stamp()}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze missing-edge topology for gold-absent cases.")
    parser.add_argument("--trace-packets", type=Path, default=DEFAULT_TRACE_PACKETS)
    parser.add_argument("--casebook", type=Path, default=DEFAULT_CASEBOOK)
    parser.add_argument("--bftc-dir", type=Path, default=DEFAULT_BFTC_DIR)
    parser.add_argument("--exec-dir", type=Path, default=DEFAULT_EXEC_DIR)
    parser.add_argument("--rebinding-dir", type=Path, default=DEFAULT_REBINDING_DIR)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--provider", default="cohere")
    parser.add_argument("--model", default="command-r-plus-08-2024")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--allow-api-diagnostic-labeling", action="store_true")
    parser.add_argument("--allow-gold-in-analysis-api", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=2048)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    out_dir = args.out_dir or _default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.trace_packets.is_file():
        raise FileNotFoundError(f"Missing trace packets: {args.trace_packets}")
    if not args.casebook.is_file():
        raise FileNotFoundError(f"Missing casebook: {args.casebook}")
    if args.allow_gold_in_analysis_api and not args.allow_api_diagnostic_labeling:
        raise ValueError("--allow-gold-in-analysis-api requires --allow-api-diagnostic-labeling.")

    casebook = _load_casebook(args.casebook)
    trace_cases = _load_trace_packets(args.trace_packets)
    bftc_bundle = _load_bftc_bundle(args.bftc_dir if args.bftc_dir and args.bftc_dir.is_dir() else None)
    exec_bundle = _load_exec_bundle(args.exec_dir if args.exec_dir and args.exec_dir.is_dir() else None)
    rebinding_bundle = _load_rebinding_bundle(args.rebinding_dir if args.rebinding_dir and args.rebinding_dir.is_dir() else None)

    preferred_ids = (
        sorted(bftc_bundle["candidate_rows"])
        or sorted(exec_bundle["candidate_rows"])
        or sorted(trace_cases)
    )
    case_ids: list[str] = []
    for case_id in preferred_ids:
        if case_id in casebook and case_id in trace_cases and case_id not in case_ids:
            case_ids.append(case_id)
    for case_id in sorted(trace_cases):
        if case_id in casebook and case_id not in case_ids:
            case_ids.append(case_id)
    if args.limit > 0:
        case_ids = case_ids[: args.limit]

    client = None
    if args.allow_api_diagnostic_labeling:
        client = _load_cohere_client()

    rows: list[dict[str, Any]] = []
    prompt_audit_per_case: list[dict[str, Any]] = []
    api_prompt_rows: list[dict[str, Any]] = []
    api_raw_rows: list[dict[str, Any]] = []
    api_parsed_rows: list[dict[str, Any]] = []

    for index, case_id in enumerate(case_ids, start=1):
        casebook_row = casebook[case_id]
        trace_case = trace_cases[case_id]
        gold = float(_normalize_numeric(casebook_row.get("gold")) or 0.0)
        question = _stringify(trace_case.get("question") or casebook_row.get("question"))
        baseline_selected_answer = _stringify(
            ((trace_case.get("selector_metadata") or {}).get("selected_answer"))
            or trace_case.get("model_final_prediction")
            or trace_case.get("frontier_candidate_answer")
            or trace_case.get("direct_reserve_answer")
        )
        target_text = _stringify(
            exec_bundle["analysis"].get(case_id, {}).get("bftc_only_target_identified")
            or bftc_bundle["parsed"].get(case_id, {}).get("target_identified")
            or casebook_row.get("question_type")
        )
        candidate_rows = _combine_candidates(
            case_id=case_id,
            trace_case=trace_case,
            bftc_bundle=bftc_bundle,
            exec_bundle=exec_bundle,
            rebinding_bundle=rebinding_bundle,
        )
        closest_numeric = select_closest_numeric_candidate(candidate_rows, gold)
        closest_semantic = select_closest_semantic_candidate(candidate_rows, question, target_text, gold)
        cluster_structure = build_candidate_cluster_structure(candidate_rows, gold)
        exec_analysis = exec_bundle["analysis"].get(case_id, {})
        bftc_analysis = bftc_bundle["analysis"].get(case_id, {})
        rebinding_rows = rebinding_bundle.get("candidate_rows", {}).get(case_id, [])
        selector_signal = has_selector_rebinding_signal(
            baseline_selected_answer=baseline_selected_answer,
            gold=gold,
            candidates=candidate_rows,
            rebinding_rows=rebinding_rows,
        )
        closest_distance = abs((closest_numeric or {"value": gold})["value"] - gold) if closest_numeric else None
        relative_distance = _relative_distance((closest_numeric or {"value": gold})["value"], gold) if closest_numeric else None
        prompt_gold_consistency = _stringify(exec_analysis.get("prompt_gold_consistency") or "unknown")
        target_correct = None
        if "target_correct" in bftc_analysis:
            target_correct = bool(bftc_analysis.get("target_correct"))

        deterministic_repair_possible = bool(
            bftc_analysis.get("deterministic_repair_possible")
            or _stringify(exec_analysis.get("formula_variables_assessment")) == "enough"
            or (relative_distance is not None and relative_distance <= 0.2)
        )
        existing_info_sufficient = bool(
            _stringify(exec_analysis.get("formula_variables_assessment")) == "enough"
            or selector_signal
            or deterministic_repair_possible
        )

        heuristic_edge = assign_missing_edge_type(
            question=question,
            target_text=target_text,
            question_type=_stringify(casebook_row.get("question_type")),
            prompt_gold_consistency=prompt_gold_consistency,
            selector_rebinding_signal=selector_signal,
            primary_category=_stringify(exec_analysis.get("primary_category")),
            previous_category=_stringify(
                exec_analysis.get("bftc_only_prev_category") or bftc_analysis.get("error_category")
            ),
            failure_axis=_stringify(exec_analysis.get("failure_axis")),
            diagnosis=_stringify(exec_analysis.get("diagnosis") or bftc_analysis.get("diagnosis")),
            minimal_fix=_stringify(exec_analysis.get("minimal_fix") or bftc_analysis.get("repair_operation")),
            target_correct=target_correct,
            relative_distance=relative_distance,
        )
        new_generation_needed = not existing_info_sufficient and not selector_signal
        heuristic_steps = estimate_steps_from_closest_node(
            gold_present=selector_signal,
            missing_edge_type=heuristic_edge,
            deterministic_repair_possible=deterministic_repair_possible,
            new_generation_needed=new_generation_needed,
        )
        heuristic_topology = map_tree_topology_label(
            missing_edge_type=heuristic_edge,
            prompt_gold_consistency=prompt_gold_consistency,
            selector_rebinding_signal=selector_signal,
            relative_distance=relative_distance,
            cluster_structure=cluster_structure,
        )
        heuristic_branch_family = map_needed_branch_family(heuristic_edge)
        confidence = min(
            0.95,
            0.4
            + (0.15 if exec_analysis else 0.0)
            + (0.15 if bftc_analysis else 0.0)
            + (0.1 if selector_signal else 0.0)
            + (0.05 if prompt_gold_consistency == "definite_mismatch" else 0.0)
            + (0.1 if deterministic_repair_possible else 0.0),
        )

        row = {
            "case_id": case_id,
            "question": question,
            "gold": _normalize_numeric_key(gold),
            "baseline_selected_answer": baseline_selected_answer,
            "all_explored_numeric_candidates": [_normalize_numeric_key(c["value"]) for c in candidate_rows],
            "candidate_provenance": [
                {
                    "value": c["value_normalized"],
                    "provenance_types": c["provenance_types"],
                    "branch_families": c["branch_families"],
                }
                for c in candidate_rows
            ],
            "closest_numeric_candidate_to_gold": closest_numeric["value_normalized"] if closest_numeric else "",
            "numeric_distance_to_gold": round(float(closest_distance or 0.0), 6),
            "relative_distance_to_gold": round(float(relative_distance or 0.0), 6),
            "candidate_cluster_structure": cluster_structure,
                "closest_semantic_candidate": {
                    "candidate_value": closest_semantic["value_normalized"] if closest_semantic else "",
                    "candidate_text": (
                        ((closest_semantic or {}).get("source_texts") or [""])[0] if closest_semantic else ""
                    ),
                    "variable_descriptions": (closest_semantic or {}).get("variable_descriptions", []),
                    "source_branch_family": (closest_semantic or {}).get("branch_families", [""])[0] if closest_semantic and closest_semantic.get("branch_families") else "",
                },
            "missing_edge_type": heuristic_edge,
            "missing_edge_description": _stringify(
                exec_analysis.get("minimal_fix")
                or bftc_analysis.get("repair_operation")
                or exec_analysis.get("diagnosis")
                or bftc_analysis.get("diagnosis")
                or "No concrete missing-edge description was available."
            )[:240],
            "estimated_steps_from_closest_node_to_gold": heuristic_steps,
            "needed_branch_family": heuristic_branch_family,
            "tree_topology_label": heuristic_topology,
            "existing_information_sufficient": existing_info_sufficient,
            "deterministic_local_repair_possible": deterministic_repair_possible,
            "new_model_generation_edge_needed": new_generation_needed,
            "confidence": round(confidence, 3),
            "label_source": "heuristic",
            "prompt_gold_consistency": prompt_gold_consistency,
            "heuristic_rationale": _stringify(exec_analysis.get("diagnosis") or bftc_analysis.get("diagnosis")),
        }

        if args.allow_api_diagnostic_labeling:
            packet = _analysis_packet(
                case_id=case_id,
                question=question,
                gold=gold,
                allow_gold=args.allow_gold_in_analysis_api,
                baseline_selected_answer=baseline_selected_answer,
                target_text=target_text,
                candidate_rows=candidate_rows,
                bftc_analysis=bftc_analysis,
                exec_analysis=exec_analysis,
                rebinding_rows=rebinding_rows,
            )
            prompt_text = build_api_prompt(packet, args.allow_gold_in_analysis_api)
            prompt_audit = _audit_prompt(prompt_text, case_id, args.allow_gold_in_analysis_api)
            prompt_audit_per_case.append(prompt_audit)
            api_prompt_rows.append(
                {
                    "case_id": case_id,
                    "prompt_text": prompt_text,
                    "prompt_sha256": prompt_audit["prompt_sha256"],
                    "analysis_only_gold_conditioned": args.allow_gold_in_analysis_api,
                    "not_for_runtime": True,
                    "not_for_provider_request_reuse": True,
                }
            )
            raw_text = ""
            usage: dict[str, Any] = {}
            parse_error = ""
            parsed_label = None
            try:
                raw_text, usage = _call_api(
                    provider=args.provider,
                    client=client,
                    model=args.model,
                    prompt_text=prompt_text,
                    max_tokens=args.max_tokens,
                    temperature=args.temperature,
                )
                parsed_label, parse_error = parse_api_label_response(raw_text)
            except Exception as exc:
                parse_error = f"api_error:{type(exc).__name__}"
            api_raw_rows.append(
                {
                    "case_id": case_id,
                    "raw_response": raw_text,
                    "parse_error": parse_error,
                    "usage": usage,
                }
            )
            api_parsed_rows.append(
                {
                    "case_id": case_id,
                    "parse_ok": parsed_label is not None,
                    "parse_error": parse_error,
                    "parsed_label": parsed_label or {},
                }
            )
            if parsed_label is not None:
                row["closest_numeric_candidate_to_gold"] = _stringify(parsed_label.get("closest_candidate_value")) or row["closest_numeric_candidate_to_gold"]
                row["missing_edge_type"] = _stringify(parsed_label["missing_edge_type"])
                row["missing_edge_description"] = _stringify(parsed_label["missing_edge_description"])[:240]
                row["estimated_steps_from_closest_node_to_gold"] = int(parsed_label["estimated_steps_from_closest_node_to_gold"])
                row["needed_branch_family"] = _stringify(parsed_label["needed_branch_family"])
                row["tree_topology_label"] = _stringify(parsed_label["tree_topology_label"])
                row["existing_information_sufficient"] = bool(parsed_label["existing_tree_had_needed_facts"])
                row["deterministic_local_repair_possible"] = bool(parsed_label["deterministic_repair_possible"])
                row["new_model_generation_edge_needed"] = bool(parsed_label["new_generation_needed"])
                row["confidence"] = round(float(parsed_label["confidence"]), 3)
                row["label_source"] = "heuristic_plus_api"
                row["api_rationale"] = _stringify(parsed_label["rationale"])
                row["closest_semantic_candidate"]["candidate_text"] = _stringify(parsed_label["closest_explored_node"])
            if index < len(case_ids):
                time.sleep(0.5)

        rows.append(row)

    prompt_audit = {
        "api_diagnostic_mode": args.allow_api_diagnostic_labeling,
        "allow_gold_in_analysis_api": args.allow_gold_in_analysis_api,
        "all_gold_free": (not args.allow_gold_in_analysis_api),
        "all_not_for_runtime": True,
        "all_not_for_provider_request_reuse": True,
        "analysis_only_gold_conditioned_prompts": sum(1 for row in prompt_audit_per_case if row["analysis_only_gold_conditioned"]),
        "violations": [v for row in prompt_audit_per_case for v in row.get("violations", [])],
        "per_case": prompt_audit_per_case,
    }

    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "trace_packets": str(args.trace_packets),
        "casebook": str(args.casebook),
        "bftc_dir": str(args.bftc_dir) if args.bftc_dir else "",
        "exec_dir": str(args.exec_dir) if args.exec_dir else "",
        "rebinding_dir": str(args.rebinding_dir) if args.rebinding_dir else "",
        "provider": args.provider,
        "model": args.model,
        "limit": args.limit,
        "allow_api_diagnostic_labeling": args.allow_api_diagnostic_labeling,
        "allow_gold_in_analysis_api": args.allow_gold_in_analysis_api,
        "case_ids": case_ids,
        "out_dir": str(out_dir),
    }
    summary = build_summary(rows, manifest)

    _write_json(out_dir / "missing_gold_topology_summary.json", summary)
    _write_jsonl(out_dir / "missing_gold_topology_rows.jsonl", rows)
    _write_csv(out_dir / "missing_gold_topology_rows.csv", [_csv_row(row) for row in rows])
    (out_dir / "missing_gold_topology_report.md").write_text(build_report(summary, rows), encoding="utf-8")
    _write_json(out_dir / "prompt_audit.json", prompt_audit)

    if args.allow_api_diagnostic_labeling:
        _write_jsonl(out_dir / "api_diagnostic_prompts.jsonl", api_prompt_rows)
        _write_jsonl(out_dir / "api_diagnostic_raw_responses.jsonl", api_raw_rows)
        _write_jsonl(out_dir / "api_diagnostic_parsed_labels.jsonl", api_parsed_rows)

    print(f"{EXPERIMENT_ID} complete: {len(rows)} cases -> {out_dir}")
    return summary


if __name__ == "__main__":
    main()
