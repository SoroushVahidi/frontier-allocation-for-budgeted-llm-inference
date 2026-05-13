#!/usr/bin/env python3
"""
Build an offline RelationReady_v0 dataset from existing 20-case artifacts.

No APIs are used. Gold labels are used only post-hoc for supervised labels.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "relation_ready_v0_dataset"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

DEFAULT_RELATION_VERIFIER_CASE_ANALYSIS = (
    REPO_ROOT / "outputs/relation_verifier_v1_live_20cases_20260513T013951Z/relation_verifier_v1_case_error_analysis.csv"
)
DEFAULT_RELATION_VERIFIER_FALSE_ACCEPT_SUMMARY = (
    REPO_ROOT / "outputs/relation_verifier_v1_live_20cases_20260513T013951Z/relation_verifier_v1_false_accept_summary.json"
)
DEFAULT_RELATION_VERIFIER_ROWS = (
    REPO_ROOT / "outputs/relation_verifier_v1_live_20cases_20260513T013951Z/relation_verifier_rows.jsonl"
)
DEFAULT_DECLARATIVE_V1 = (
    REPO_ROOT / "outputs/declarative_equation_branch_v1_live_20cases_20260513T001028Z/declarative_case_error_analysis.csv"
)
DEFAULT_DECLARATIVE_V2 = (
    REPO_ROOT / "outputs/declarative_equation_branch_v2_live_20cases_20260513T004717Z/declarative_v2_case_error_analysis.csv"
)
DEFAULT_BFTC = REPO_ROOT / "outputs/bftc_live_pilot_v1_20cases_20260512T210634Z/bftc_case_error_analysis.csv"
DEFAULT_BFTC_EXEC = (
    REPO_ROOT / "outputs/bftc_executable_repair_v1_live_20cases_20260512T221521Z/bftc_executable_case_error_analysis.csv"
)
DEFAULT_TOPOLOGY = REPO_ROOT / "outputs/missing_gold_topology_v1_20260512T231758Z/missing_gold_topology_rows.jsonl"
DEFAULT_CASEBOOK = (
    REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
)

TRUE_TOKENS = {"1", "true", "t", "yes", "y"}
FALSE_TOKENS = {"0", "false", "f", "no", "n"}
SEMANTIC_ERROR_AXES = {
    "wrong_relation",
    "wrong_target_variable",
    "missing_source_fact",
    "wrong_process_state",
    "unit_scale_error",
    "prompt_gold_inconsistent",
    "equation_semantically_wrong",
    "formula_semantically_wrong",
}
RELATION_VERIFIER_ERROR_TYPES = [
    "none",
    "wrong_relation",
    "wrong_target_variable",
    "missing_source_fact",
    "wrong_process_state",
    "unit_scale_error",
    "arithmetic_error",
    "format_error",
    "uncertain",
]
CANDIDATE_SOURCES = [
    "bftc_only",
    "bftc_executable",
    "declarative_v1",
    "declarative_v2",
    "relation_verifier_v1_primary",
]
TOPOLOGY_ONEHOT_LABELS = [
    "relation_composition_missing",
    "final_after_process",
    "arithmetic_precision",
    "unit_conversion",
    "prompt_gold_inconsistent",
]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _safe_bool(value: Any) -> bool | None:
    text = _stringify(value).lower()
    if not text:
        return None
    if text in TRUE_TOKENS:
        return True
    if text in FALSE_TOKENS:
        return False
    return None


def _safe_float(value: Any) -> float | None:
    text = _stringify(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _normalize_number_text(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return _stringify(value)
    if number.is_integer():
        return str(int(number))
    return ("%f" % number).rstrip("0").rstrip(".")


def _normalize_case_id(value: Any) -> str:
    text = _stringify(value)
    if not text:
        return ""
    if text.startswith("openai_gsm8k_"):
        return "gsm8k_" + text.split("openai_gsm8k_", 1)[1]
    return text


def _stable_split(normalized_case_id: str) -> str:
    if not normalized_case_id:
        return "train"
    bucket = int(hashlib.sha256(normalized_case_id.encode("utf-8")).hexdigest()[:8], 16) % 20
    if bucket < 14:
        return "train"
    if bucket < 17:
        return "val"
    return "test"


def _compare_answers(value: Any, gold: Any) -> bool:
    value_text = _stringify(value)
    gold_text = _stringify(gold)
    if not value_text or not gold_text:
        return False
    value_num = _safe_float(value_text)
    gold_num = _safe_float(gold_text)
    if value_num is not None and gold_num is not None:
        return abs(value_num - gold_num) <= 1e-9
    return _normalize_number_text(value_text) == _normalize_number_text(gold_text)


def _read_csv_optional(path: Path, warnings: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        warnings.append(f"missing_optional_file:{path}")
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_jsonl_optional(path: Path, warnings: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        warnings.append(f"missing_optional_file:{path}")
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _read_json_optional(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"missing_optional_file:{path}")
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _index_rows_by_case(rows: list[dict[str, Any]], *, case_field: str = "case_id") -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = _stringify(row.get(case_field))
        if case_id:
            indexed[_normalize_case_id(case_id)] = row
    return indexed


def _gold_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        case_id = _normalize_case_id(row.get("case_id"))
        if not case_id:
            continue
        gold = row.get("gold_answer") or row.get("gold") or row.get("correct_answer") or ""
        out[case_id] = _stringify(gold)
    return out


def _bool_field(row: dict[str, Any], key: str) -> bool | None:
    return _safe_bool(row.get(key))


def _base_row(case_id: str, candidate_source: str, topology: dict[str, Any], gold_value: str) -> dict[str, Any]:
    topology_label = _stringify(topology.get("missing_edge_type") or topology.get("topology_label"))
    prompt_gold_consistency = _stringify(
        topology.get("prompt_gold_consistency") or topology.get("prompt_gold_consistency_flag")
    ).lower()
    prompt_gold_inconsistent = prompt_gold_consistency == "inconsistent" or topology_label == "prompt_gold_inconsistent"
    normalized_case_id = _normalize_case_id(case_id)
    return {
        "case_id": case_id,
        "normalized_case_id": normalized_case_id,
        "candidate_id": f"{candidate_source}:{case_id}",
        "candidate_source": candidate_source,
        "topology_label": topology_label,
        "prompt_gold_inconsistent_flag": prompt_gold_inconsistent,
        "gold_value_posthoc": gold_value,
        "final_answer": "",
        "executable_final_answer": "",
        "exact_final_answer_posthoc": False,
        "exact_executable_answer_posthoc": False,
        "any_prior_exact_posthoc": False,
        "relation_verifier_error_type": "",
        "relation_verifier_accept": None,
        "relation_verifier_false_accept": False,
        "target_relation_correct": None,
        "target_variable_correct": None,
        "source_facts_sufficient": None,
        "equations_match_source_facts": None,
        "process_state_correct": None,
        "unit_scale_correct": None,
        "arithmetic_executable": None,
        "target_variable_ok": None,
        "target_binding_ok": None,
        "source_facts_ok": None,
        "process_state_ok": None,
        "unit_scale_ok": None,
        "equation_semantics_ok": None,
        "formula_executable_ok": None,
        "first_error_axis": "unknown",
        "relation_ready_label": None,
        "relation_ready_source": "",
        "label_confidence": "low",
        "notes": "",
        "has_formula": False,
        "has_executable_answer": False,
        "formula_eval_ok": None,
        "final_answer_formula_mismatch": None,
        "target_solve_for_match": None,
        "solve_for_declared": None,
        "equation_strict_ok": None,
        "formula_strict_ok": None,
        "numeric_variable_value_ok": None,
        "relation_verifier_accept_bool": False,
        "suggested_split": _stable_split(normalized_case_id),
    }


def _attach_relation_verifier_fields(
    row: dict[str, Any],
    verifier_case: dict[str, Any] | None,
    verifier_row: dict[str, Any] | None,
) -> None:
    if not verifier_case:
        return
    row["relation_verifier_error_type"] = _stringify(verifier_case.get("verifier_error_type"))
    row["relation_verifier_accept"] = _safe_bool(_stringify(verifier_case.get("verifier_error_type")) == "none")
    row["relation_verifier_accept_bool"] = row["relation_verifier_accept"] is True
    row["relation_verifier_false_accept"] = _bool_field(verifier_case, "false_accept") is True
    row["target_relation_correct"] = _bool_field(verifier_case, "verifier_target_relation_correct")
    row["target_variable_correct"] = _bool_field(verifier_case, "verifier_target_variable_correct")
    row["source_facts_sufficient"] = _bool_field(verifier_case, "verifier_source_facts_sufficient")
    row["equations_match_source_facts"] = _bool_field(verifier_case, "verifier_equations_match_source_facts")
    row["process_state_correct"] = _bool_field(verifier_case, "verifier_process_state_correct")
    row["unit_scale_correct"] = _bool_field(verifier_case, "verifier_unit_scale_correct")
    row["arithmetic_executable"] = _bool_field(verifier_case, "verifier_arithmetic_executable")
    if verifier_row:
        notes = []
        primary_source = _stringify(verifier_row.get("primary_candidate_source"))
        if primary_source:
            notes.append(f"relation_verifier_primary_source={primary_source}")
        extraction_source = _stringify(verifier_row.get("extraction_source"))
        if extraction_source:
            notes.append(f"verifier_extraction_source={extraction_source}")
        if notes:
            row["notes"] = "; ".join(filter(None, [row["notes"], *notes])).strip("; ")


def _derive_first_error_axis(row: dict[str, Any]) -> str:
    if row["prompt_gold_inconsistent_flag"]:
        return "prompt_gold_inconsistent"
    error_type = _stringify(row.get("relation_verifier_error_type"))
    if error_type and error_type != "none":
        return error_type
    if row.get("exact_final_answer_posthoc") or row.get("exact_executable_answer_posthoc"):
        return "no_issue"
    notes_blob = " ".join(
        [
            _stringify(row.get("notes")),
            _stringify(row.get("diagnosis")),
            _stringify(row.get("primary_category")),
            _stringify(row.get("failure_axis")),
            _stringify(row.get("topology_label")),
        ]
    ).lower()
    if "target" in notes_blob and "variable" in notes_blob:
        return "wrong_target_variable"
    if "unit" in notes_blob or "convert" in notes_blob or row.get("topology_label") == "unit_conversion":
        return "unit_scale_error"
    if "process" in notes_blob or row.get("topology_label") == "final_after_process":
        return "wrong_process_state"
    if "missing source fact" in notes_blob or "underspecified" in notes_blob:
        return "missing_source_fact"
    if "semantic" in notes_blob and "formula" in notes_blob:
        return "formula_semantically_wrong"
    if "semantic" in notes_blob and "equation" in notes_blob:
        return "equation_semantically_wrong"
    if "relation" in notes_blob or row.get("topology_label") == "relation_composition_missing":
        return "wrong_relation"
    if "arith" in notes_blob or row.get("topology_label") == "arithmetic_precision":
        return "arithmetic_error"
    return "unknown"


def _derive_relation_ready_label(row: dict[str, Any]) -> tuple[bool | None, str, str]:
    blocker = row["prompt_gold_inconsistent_flag"] or row["relation_verifier_false_accept"]
    first_error = _stringify(row.get("first_error_axis"))
    if first_error in SEMANTIC_ERROR_AXES:
        blocker = True
    if first_error in {"arithmetic_error", "format_error"} and not (
        row.get("exact_final_answer_posthoc") or row.get("exact_executable_answer_posthoc")
    ):
        blocker = True
    if blocker:
        return False, "conservative_blocker", "high"
    if row.get("exact_final_answer_posthoc") or row.get("exact_executable_answer_posthoc"):
        return True, "posthoc_exact_no_blocker", "medium"
    if row.get("relation_verifier_accept") is True and not row.get("relation_verifier_false_accept"):
        return None, "accepted_but_not_exact", "low"
    return None, "insufficient_evidence", "low"


def _add_onehot_features(row: dict[str, Any]) -> None:
    rv_type = _stringify(row.get("relation_verifier_error_type"))
    for label in RELATION_VERIFIER_ERROR_TYPES:
        row[f"relation_verifier_error_type_onehot__{label}"] = rv_type == label
    topology_label = _stringify(row.get("topology_label"))
    for label in TOPOLOGY_ONEHOT_LABELS:
        row[f"topology_label_onehot__{label}"] = topology_label == label
    row["topology_label_onehot__other"] = bool(topology_label) and topology_label not in TOPOLOGY_ONEHOT_LABELS
    candidate_source = _stringify(row.get("candidate_source"))
    for label in CANDIDATE_SOURCES:
        row[f"candidate_source_onehot__{label}"] = candidate_source == label


def _load_artifact_maps(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    rv_cases = _index_rows_by_case(_read_csv_optional(args.relation_verifier_case_analysis, warnings))
    rv_rows = _index_rows_by_case(_read_jsonl_optional(args.relation_verifier_rows, warnings))
    decl_v1 = _index_rows_by_case(_read_csv_optional(args.declarative_v1_case_analysis, warnings))
    decl_v2 = _index_rows_by_case(_read_csv_optional(args.declarative_v2_case_analysis, warnings))
    bftc = _index_rows_by_case(_read_csv_optional(args.bftc_case_analysis, warnings))
    bftc_exec = _index_rows_by_case(_read_csv_optional(args.bftc_executable_case_analysis, warnings))
    topology = _index_rows_by_case(_read_jsonl_optional(args.topology_rows, warnings))
    casebook_rows = _read_csv_optional(args.casebook, warnings)
    false_accept_summary = _read_json_optional(args.relation_verifier_false_accept_summary, warnings)
    return (
        {
            "relation_verifier_cases": rv_cases,
            "relation_verifier_rows": rv_rows,
            "declarative_v1": decl_v1,
            "declarative_v2": decl_v2,
            "bftc": bftc,
            "bftc_exec": bftc_exec,
            "topology": topology,
            "casebook_gold": _gold_map(casebook_rows),
            "false_accept_summary": false_accept_summary,
        },
        warnings,
    )


def _build_rows(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[str]]:
    maps, warnings = _load_artifact_maps(args)
    all_case_ids = sorted(
        {
            *maps["relation_verifier_cases"].keys(),
            *maps["relation_verifier_rows"].keys(),
            *maps["declarative_v1"].keys(),
            *maps["declarative_v2"].keys(),
            *maps["bftc"].keys(),
            *maps["bftc_exec"].keys(),
            *maps["topology"].keys(),
            *maps["casebook_gold"].keys(),
        }
    )
    rows: list[dict[str, Any]] = []

    for normalized_case_id in all_case_ids:
        topology = maps["topology"].get(normalized_case_id, {})
        case_id = _stringify(
            topology.get("case_id")
            or maps["declarative_v2"].get(normalized_case_id, {}).get("case_id")
            or maps["declarative_v1"].get(normalized_case_id, {}).get("case_id")
            or maps["bftc_exec"].get(normalized_case_id, {}).get("case_id")
            or maps["bftc"].get(normalized_case_id, {}).get("case_id")
            or maps["relation_verifier_cases"].get(normalized_case_id, {}).get("case_id")
            or maps["relation_verifier_rows"].get(normalized_case_id, {}).get("case_id")
        )
        if not case_id:
            continue
        gold_value = _stringify(maps["casebook_gold"].get(normalized_case_id) or topology.get("gold"))
        rv_case = maps["relation_verifier_cases"].get(normalized_case_id)
        rv_row = maps["relation_verifier_rows"].get(normalized_case_id)
        d1 = maps["declarative_v1"].get(normalized_case_id)
        d2 = maps["declarative_v2"].get(normalized_case_id)
        bftc = maps["bftc"].get(normalized_case_id)
        bftc_exec = maps["bftc_exec"].get(normalized_case_id)

        if bftc:
            row = _base_row(case_id, "bftc_only", topology, gold_value)
            row["final_answer"] = _stringify(bftc.get("fa"))
            row["exact_final_answer_posthoc"] = _compare_answers(row["final_answer"], gold_value)
            row["target_variable_ok"] = _bool_field(bftc, "target_correct")
            row["target_binding_ok"] = row["target_variable_ok"]
            row["notes"] = _stringify(bftc.get("failed_relation") or bftc.get("diagnosis"))
            row["diagnosis"] = _stringify(bftc.get("diagnosis"))
            row["primary_category"] = _stringify(bftc.get("error_category"))
            row["formula_executable_ok"] = None
            row["equation_semantics_ok"] = False if "wrong" in _stringify(bftc.get("error_category")).lower() else None
            rows.append(row)

        if bftc_exec:
            row = _base_row(case_id, "bftc_executable", topology, gold_value)
            row["final_answer"] = _stringify(bftc_exec.get("model_final_answer"))
            row["executable_final_answer"] = _stringify(bftc_exec.get("executable_final_answer"))
            row["exact_final_answer_posthoc"] = _bool_field(bftc_exec, "model_final_recovered") is True
            row["exact_executable_answer_posthoc"] = _bool_field(bftc_exec, "executable_recovered") is True
            row["has_formula"] = bool(_stringify(bftc_exec.get("solution_formula")))
            row["has_executable_answer"] = bool(row["executable_final_answer"])
            row["formula_eval_ok"] = _bool_field(bftc_exec, "formula_eval_ok")
            row["formula_executable_ok"] = row["formula_eval_ok"]
            row["final_answer_formula_mismatch"] = _bool_field(
                bftc_exec, "formula_result_mismatched_model_final_answer"
            )
            row["target_variable_ok"] = bool(_stringify(bftc_exec.get("bftc_only_target_identified")))
            row["target_binding_ok"] = row["target_variable_ok"]
            row["source_facts_ok"] = None
            row["equation_semantics_ok"] = False if "semantic" in _stringify(bftc_exec.get("diagnosis")).lower() else None
            row["notes"] = _stringify(bftc_exec.get("minimal_fix") or bftc_exec.get("diagnosis"))
            row["diagnosis"] = _stringify(bftc_exec.get("diagnosis"))
            row["failure_axis"] = _stringify(bftc_exec.get("failure_axis"))
            rows.append(row)

        if d1:
            row = _base_row(case_id, "declarative_v1", topology, gold_value)
            row["final_answer"] = _stringify(d1.get("final_answer"))
            row["executable_final_answer"] = _stringify(d1.get("executable_final_answer"))
            row["exact_final_answer_posthoc"] = _bool_field(d1, "final_exact") is True
            row["exact_executable_answer_posthoc"] = _bool_field(d1, "executable_exact") is True
            row["has_formula"] = _bool_field(d1, "equation_present") is True
            row["has_executable_answer"] = bool(row["executable_final_answer"])
            row["formula_eval_ok"] = _bool_field(d1, "formula_eval_ok")
            row["formula_executable_ok"] = row["formula_eval_ok"]
            row["target_solve_for_match"] = _bool_field(d1, "target_solve_for_match")
            row["equation_strict_ok"] = _bool_field(d1, "equation_strict_ok")
            row["formula_strict_ok"] = _bool_field(d1, "formula_strict_ok")
            row["target_variable_ok"] = row["target_solve_for_match"]
            row["target_binding_ok"] = row["target_solve_for_match"]
            row["equation_semantics_ok"] = None
            row["notes"] = _stringify(d1.get("diagnosis") or d1.get("recommended_fix_category"))
            row["diagnosis"] = _stringify(d1.get("diagnosis"))
            rows.append(row)

        if d2:
            row = _base_row(case_id, "declarative_v2", topology, gold_value)
            row["final_answer"] = _stringify(d2.get("v2_final_answer"))
            row["executable_final_answer"] = _stringify(d2.get("v2_executable_answer"))
            row["exact_final_answer_posthoc"] = _compare_answers(row["final_answer"], gold_value)
            row["exact_executable_answer_posthoc"] = _compare_answers(row["executable_final_answer"], gold_value)
            row["has_formula"] = True
            row["has_executable_answer"] = bool(row["executable_final_answer"])
            row["formula_eval_ok"] = _bool_field(d2, "v2_formula_eval_ok")
            row["formula_executable_ok"] = row["formula_eval_ok"]
            row["target_solve_for_match"] = _bool_field(d2, "v2_target_solve_for_match")
            row["solve_for_declared"] = _bool_field(d2, "v2_solve_for_declared")
            row["numeric_variable_value_ok"] = _bool_field(d2, "v2_numeric_variable_value_ok")
            row["target_variable_ok"] = row["target_solve_for_match"]
            row["target_binding_ok"] = row["target_solve_for_match"] and row["solve_for_declared"] is True
            primary_label = _stringify(d2.get("primary_label"))
            row["equation_semantics_ok"] = False if "semantic" in primary_label else None
            row["notes"] = _stringify(d2.get("normalization_note") or d2.get("comparison_note"))
            row["diagnosis"] = primary_label
            row["equation_strict_ok"] = _bool_field(d2, "v2_schema_ok")
            row["formula_strict_ok"] = _bool_field(d2, "v2_schema_ok")
            _attach_relation_verifier_fields(row, rv_case, rv_row)
            rows.append(row)

        if rv_case:
            row = _base_row(case_id, "relation_verifier_v1_primary", topology, gold_value)
            if d2:
                row["final_answer"] = _stringify(d2.get("v2_final_answer"))
                row["executable_final_answer"] = _stringify(d2.get("v2_executable_answer"))
                row["exact_final_answer_posthoc"] = _compare_answers(row["final_answer"], gold_value)
                row["exact_executable_answer_posthoc"] = _compare_answers(row["executable_final_answer"], gold_value)
                row["has_formula"] = True
                row["has_executable_answer"] = bool(row["executable_final_answer"])
                row["formula_eval_ok"] = _bool_field(d2, "v2_formula_eval_ok")
                row["formula_executable_ok"] = row["formula_eval_ok"]
            _attach_relation_verifier_fields(row, rv_case, rv_row)
            row["target_variable_ok"] = row["target_variable_correct"]
            row["target_binding_ok"] = (
                row["target_variable_correct"] is True and row["target_relation_correct"] is True
            )
            row["source_facts_ok"] = row["source_facts_sufficient"]
            row["process_state_ok"] = row["process_state_correct"]
            row["unit_scale_ok"] = row["unit_scale_correct"]
            row["equation_semantics_ok"] = row["equations_match_source_facts"]
            row["diagnosis"] = _stringify(rv_case.get("diagnosis"))
            rows.append(row)

    prior_exact_by_case: dict[str, bool] = {}
    for row in rows:
        if row["candidate_source"] == "relation_verifier_v1_primary":
            continue
        if row["exact_final_answer_posthoc"] or row["exact_executable_answer_posthoc"]:
            prior_exact_by_case[row["normalized_case_id"]] = True

    for row in rows:
        row["any_prior_exact_posthoc"] = prior_exact_by_case.get(row["normalized_case_id"], False)
        if row["source_facts_ok"] is None:
            row["source_facts_ok"] = row["source_facts_sufficient"]
        if row["process_state_ok"] is None:
            row["process_state_ok"] = row["process_state_correct"]
        if row["unit_scale_ok"] is None:
            row["unit_scale_ok"] = row["unit_scale_correct"]
        if row["first_error_axis"] == "unknown":
            row["first_error_axis"] = _derive_first_error_axis(row)
        label, label_source, confidence = _derive_relation_ready_label(row)
        row["relation_ready_label"] = label
        row["relation_ready_source"] = label_source
        row["label_confidence"] = confidence
        _add_onehot_features(row)

    return rows, warnings


def _serialize_scalar(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, str)):
        return value
    return _stringify(value)


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    preferred = [
        "case_id",
        "normalized_case_id",
        "candidate_id",
        "candidate_source",
        "topology_label",
        "prompt_gold_inconsistent_flag",
        "final_answer",
        "executable_final_answer",
        "exact_final_answer_posthoc",
        "exact_executable_answer_posthoc",
        "any_prior_exact_posthoc",
        "relation_verifier_error_type",
        "relation_verifier_accept",
        "relation_verifier_false_accept",
        "target_relation_correct",
        "target_variable_correct",
        "source_facts_sufficient",
        "equations_match_source_facts",
        "process_state_correct",
        "unit_scale_correct",
        "arithmetic_executable",
        "target_variable_ok",
        "target_binding_ok",
        "source_facts_ok",
        "process_state_ok",
        "unit_scale_ok",
        "equation_semantics_ok",
        "formula_executable_ok",
        "first_error_axis",
        "relation_ready_label",
        "relation_ready_source",
        "label_confidence",
        "notes",
    ]
    fieldnames = list(preferred)
    extra = sorted({key for row in rows for key in row.keys() if key not in fieldnames})
    fieldnames.extend(extra)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _serialize_scalar(row.get(key)) for key in fieldnames})


def _build_summary(rows: list[dict[str, Any]], warnings: list[str], meta: dict[str, Any]) -> dict[str, Any]:
    by_source = Counter(_stringify(row.get("candidate_source")) for row in rows)
    by_topology = Counter(_stringify(row.get("topology_label")) for row in rows)
    by_error = Counter(_stringify(row.get("first_error_axis")) for row in rows)
    by_label = Counter("null" if row.get("relation_ready_label") is None else str(row["relation_ready_label"]).lower() for row in rows)
    by_split = Counter(_stringify(row.get("suggested_split")) for row in rows)
    return {
        "experiment_id": EXPERIMENT_ID,
        "row_count": len(rows),
        "case_count": len({_stringify(row.get("normalized_case_id")) for row in rows}),
        "candidate_source_counts": dict(by_source),
        "topology_label_counts": dict(by_topology),
        "first_error_axis_counts": dict(by_error),
        "relation_ready_label_counts": dict(by_label),
        "suggested_split_counts": dict(by_split),
        "warnings": warnings,
        "false_accept_summary_loaded": bool(meta.get("false_accept_summary")),
        "train_val_test_note": "Suggested split is stable by normalized_case_id only; no model training is performed here.",
    }


def _write_report(path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    preview = rows[:5]
    lines = [
        f"# {EXPERIMENT_ID} Report",
        "",
        f"- rows: `{summary['row_count']}`",
        f"- cases: `{summary['case_count']}`",
        f"- candidate sources: `{summary['candidate_source_counts']}`",
        f"- topology labels: `{summary['topology_label_counts']}`",
        f"- first error axis: `{summary['first_error_axis_counts']}`",
        f"- relation_ready_label: `{summary['relation_ready_label_counts']}`",
        f"- suggested split counts: `{summary['suggested_split_counts']}`",
        "",
        "## Warnings",
    ]
    if summary["warnings"]:
        lines.extend([f"- `{warning}`" for warning in summary["warnings"]])
    else:
        lines.append("- none")
    lines.extend(["", "## Preview", ""])
    for row in preview:
        lines.append(
            f"- `{row['candidate_id']}` label=`{row['relation_ready_label']}` "
            f"first_error_axis=`{row['first_error_axis']}` source=`{row['candidate_source']}`"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _default_out_dir() -> Path:
    return REPO_ROOT / "outputs" / f"relation_ready_v0_dataset_{_TS}"


def build_dataset(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = args.out_dir
    rows, warnings = _build_rows(args)
    meta, _ = _load_artifact_maps(args)
    summary = _build_summary(rows, warnings, meta)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "relation_ready_rows.jsonl", rows)
    _write_csv(out_dir / "relation_ready_rows.csv", rows)
    _write_json(out_dir / "relation_ready_summary.json", summary)
    _write_report(out_dir / "relation_ready_report.md", summary, rows)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relation-verifier-case-analysis", type=Path, default=DEFAULT_RELATION_VERIFIER_CASE_ANALYSIS)
    parser.add_argument(
        "--relation-verifier-false-accept-summary", type=Path, default=DEFAULT_RELATION_VERIFIER_FALSE_ACCEPT_SUMMARY
    )
    parser.add_argument("--relation-verifier-rows", type=Path, default=DEFAULT_RELATION_VERIFIER_ROWS)
    parser.add_argument("--declarative-v1-case-analysis", type=Path, default=DEFAULT_DECLARATIVE_V1)
    parser.add_argument("--declarative-v2-case-analysis", type=Path, default=DEFAULT_DECLARATIVE_V2)
    parser.add_argument("--bftc-case-analysis", type=Path, default=DEFAULT_BFTC)
    parser.add_argument("--bftc-executable-case-analysis", type=Path, default=DEFAULT_BFTC_EXEC)
    parser.add_argument("--topology-rows", type=Path, default=DEFAULT_TOPOLOGY)
    parser.add_argument("--casebook", type=Path, default=DEFAULT_CASEBOOK)
    parser.add_argument("--out-dir", type=Path, default=_default_out_dir())
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    return build_dataset(args)


if __name__ == "__main__":
    main()
