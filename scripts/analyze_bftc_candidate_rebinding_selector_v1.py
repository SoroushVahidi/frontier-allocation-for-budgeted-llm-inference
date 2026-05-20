#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "bftc_candidate_rebinding_selector_v1"
DEFAULT_DOC_PATH = (
    REPO_ROOT / "docs" / "BFTC_CANDIDATE_REBINDING_SELECTOR_V1_ANALYSIS_20260512.md"
)
PROVENANCE_PRIORITY = {
    "bftc_only_final": 0,
    "exec_model_final": 1,
    "exec_formula_final": 2,
    "repaired_candidate": 3,
    "final_answer_field": 4,
    "answer_field": 5,
    "formula_variable": 6,
}
RELATION_SUSPICIOUS_AXES = {"relation_construction", "source_fact_extraction", "unit_scale"}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _normalize_numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().replace(",", "")
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


def _normalize_answer_str(value: Any) -> str:
    numeric = _normalize_numeric(value)
    if numeric is None:
        return str(value or "").strip()
    return _normalize_numeric_key(numeric)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _lexical_overlap_score(text: str, target: str) -> float:
    text_tokens = set(_tokenize(text))
    target_tokens = set(_tokenize(target))
    if not text_tokens or not target_tokens:
        return 0.0
    return len(text_tokens & target_tokens) / len(target_tokens)


def _extract_question(prompt_text: str) -> str:
    match = re.search(r"QUESTION:\n(.*?)\n\nEXISTING CANDIDATES", prompt_text, re.S)
    return match.group(1).strip() if match else ""


def _unit_match(unit: str, target_text: str, question: str) -> bool:
    unit = str(unit or "").strip().lower()
    if not unit:
        return False
    joined = f"{target_text} {question}".lower()
    if unit in {"$", "dollar", "dollars"}:
        return "$" in joined or "dollar" in joined or "money" in joined
    if unit == "%":
        return "%" in joined or "percent" in joined or "percentage" in joined
    return unit in joined


def _provenance_sort_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    min_priority = min(PROVENANCE_PRIORITY.get(p, 999) for p in candidate["provenance_types"])
    return (
        min_priority,
        not candidate.get("came_from_formula_variable", False),
        candidate["candidate_value"],
    )


def _choose_single(case_rows: list[dict[str, Any]], predicate) -> dict[str, Any]:
    matches = [row for row in case_rows if predicate(row)]
    pool = matches or case_rows
    return sorted(pool, key=_provenance_sort_key)[0]


def _choose_by_score(case_rows: list[dict[str, Any]], score_fn) -> dict[str, Any]:
    return max(
        case_rows,
        key=lambda row: (
            score_fn(row),
            row.get("candidate_from_target_suggesting_variable", False),
            row.get("came_from_exec_formula", False),
            row.get("came_from_bftc_only_final", False),
            -_provenance_sort_key(row)[0],
            -row["candidate_value"],
        ),
    )


def _selector_overlap_score(row: dict[str, Any]) -> float:
    return (
        row["max_variable_description_target_overlap"]
        + 0.75 * row["max_variable_name_target_overlap"]
        + 0.25 * float(row["unit_match_any"])
        + 0.15 * float(row["came_from_exec_formula"])
        - 0.2 * float(row["relation_category_suspicious"])
    )


def load_casebook(path: Path) -> dict[str, dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["case_id"]: row for row in csv.DictReader(handle) if row.get("case_id")}


def load_exec_postmortem(exec_dir: Path) -> dict[str, dict[str, Any]]:
    analysis_path = exec_dir / "bftc_executable_case_error_analysis.jsonl"
    if not analysis_path.exists():
        return {}
    return {row["case_id"]: row for row in _load_jsonl(analysis_path)}


def load_raw_exec_responses(exec_dir: Path) -> dict[str, dict[str, Any]]:
    raw_rows = {row["case_id"]: row for row in _load_jsonl(exec_dir / "raw_responses.jsonl")}
    out: dict[str, dict[str, Any]] = {}
    for case_id, row in raw_rows.items():
        parsed = {}
        raw_text = row.get("raw_response") or ""
        if raw_text:
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError:
                parsed = {}
        out[case_id] = {
            "prompt_text": row.get("prompt_text", ""),
            "question": _extract_question(row.get("prompt_text", "")),
            "response_obj": parsed,
        }
    return out


def build_candidate_rows(
    *,
    bftc_only_dir: Path,
    exec_dir: Path,
    exec_postmortem: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    bftc_rows = {row["case_id"]: row for row in _load_jsonl(bftc_only_dir / "candidate_rows.jsonl")}
    bftc_parsed = {row["case_id"]: row for row in _load_jsonl(bftc_only_dir / "parsed_responses.jsonl")}
    exec_parsed = {row["case_id"]: row for row in _load_jsonl(exec_dir / "parsed_responses.jsonl")}
    exec_rows = {row["case_id"]: row for row in _load_jsonl(exec_dir / "executable_candidate_rows.jsonl")}
    raw_exec = load_raw_exec_responses(exec_dir)

    all_rows: list[dict[str, Any]] = []

    for case_id in sorted(exec_rows):
        question = raw_exec.get(case_id, {}).get("question", "")
        response_obj = raw_exec.get(case_id, {}).get("response_obj", {})
        formula_vars = response_obj.get("formula_variables") or {}
        requested_target = exec_parsed[case_id].get("requested_target", "")
        bftc_target = bftc_parsed[case_id].get("target_identified", "")
        target_text = requested_target or bftc_target
        postmortem = exec_postmortem.get(case_id, {})
        prompt_gold_inconsistent = postmortem.get("prompt_gold_consistency") == "definite_mismatch"
        relation_category_suspicious = postmortem.get("failure_axis") in RELATION_SUSPICIOUS_AXES
        candidate_map: dict[str, dict[str, Any]] = {}

        def add_candidate(
            value: Any,
            provenance: str,
            *,
            variable_name: str = "",
            variable_description: str = "",
            variable_unit: str = "",
        ) -> None:
            numeric = _normalize_numeric(value)
            if numeric is None:
                return
            key = _normalize_numeric_key(numeric)
            row = candidate_map.setdefault(
                key,
                {
                    "case_id": case_id,
                    "question": question,
                    "requested_target": requested_target,
                    "bftc_target_identified": bftc_target,
                    "target_text": target_text,
                    "candidate_value": numeric,
                    "candidate_value_normalized": key,
                    "provenance_types": [],
                    "provenance_count": 0,
                    "variable_names": [],
                    "variable_descriptions": [],
                    "variable_units": [],
                    "relation_category_suspicious": relation_category_suspicious,
                    "postmortem_primary_category": postmortem.get("primary_category", ""),
                    "prompt_gold_inconsistent": prompt_gold_inconsistent,
                },
            )
            if provenance not in row["provenance_types"]:
                row["provenance_types"].append(provenance)
            if variable_name and variable_name not in row["variable_names"]:
                row["variable_names"].append(variable_name)
            if variable_description and variable_description not in row["variable_descriptions"]:
                row["variable_descriptions"].append(variable_description)
            if variable_unit and variable_unit not in row["variable_units"]:
                row["variable_units"].append(variable_unit)
            row["provenance_count"] = len(row["provenance_types"])

        add_candidate(bftc_rows[case_id].get("fa_numeric"), "bftc_only_final")
        add_candidate(exec_parsed[case_id].get("fa_numeric"), "exec_model_final")
        add_candidate(exec_rows[case_id].get("executable_final_answer"), "exec_formula_final")

        for raw_field in ("repaired_candidate", "final_answer", "answer"):
            if raw_field in response_obj:
                provenance = (
                    "repaired_candidate"
                    if raw_field == "repaired_candidate"
                    else ("final_answer_field" if raw_field == "final_answer" else "answer_field")
                )
                add_candidate(response_obj.get(raw_field), provenance)

        if isinstance(formula_vars, dict):
            for name, info in formula_vars.items():
                if isinstance(info, dict):
                    add_candidate(
                        info.get("value"),
                        "formula_variable",
                        variable_name=name,
                        variable_description=str(info.get("description", "")),
                        variable_unit=str(info.get("unit", "")),
                    )
                else:
                    add_candidate(info, "formula_variable", variable_name=name)

        for row in candidate_map.values():
            row["provenance_types"] = sorted(
                row["provenance_types"], key=lambda p: PROVENANCE_PRIORITY.get(p, 999)
            )
            row["provenance_types_joined"] = "|".join(row["provenance_types"])
            row["came_from_bftc_only_final"] = "bftc_only_final" in row["provenance_types"]
            row["came_from_exec_model_final"] = "exec_model_final" in row["provenance_types"]
            row["came_from_exec_formula"] = "exec_formula_final" in row["provenance_types"]
            row["came_from_repaired_candidate"] = "repaired_candidate" in row["provenance_types"]
            row["came_from_formula_variable"] = "formula_variable" in row["provenance_types"]
            row["candidate_equals_any_formula_variable"] = row["came_from_formula_variable"]
            row["max_variable_name_target_overlap"] = max(
                [_lexical_overlap_score(name, target_text) for name in row["variable_names"]] or [0.0]
            )
            row["max_variable_description_target_overlap"] = max(
                [
                    _lexical_overlap_score(description, target_text)
                    for description in row["variable_descriptions"]
                ]
                or [0.0]
            )
            row["unit_match_any"] = any(
                _unit_match(unit, target_text, question) for unit in row["variable_units"]
            )
            row["candidate_from_target_suggesting_variable"] = (
                row["max_variable_name_target_overlap"] > 0
                or row["max_variable_description_target_overlap"] > 0
                or row["unit_match_any"]
            )
            row["selector_overlap_score"] = round(_selector_overlap_score(row), 6)
            row["case_has_gold_in_candidate_set"] = False
            row["oracle_recoverable"] = False
            row["candidate_matches_gold"] = False
            all_rows.append(row)

    return all_rows


def attach_posthoc_gold_labels(
    candidate_rows: list[dict[str, Any]],
    gold_map: dict[str, float],
) -> list[dict[str, Any]]:
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        by_case[row["case_id"]].append(row)

    labeled: list[dict[str, Any]] = []
    for case_id, rows in by_case.items():
        gold = gold_map.get(case_id)
        has_gold = False
        for row in rows:
            if gold is not None and math_isclose(row["candidate_value"], gold):
                has_gold = True
                break
        for row in rows:
            new_row = dict(row)
            new_row["candidate_matches_gold"] = bool(
                gold is not None and math_isclose(row["candidate_value"], gold)
            )
            new_row["case_has_gold_in_candidate_set"] = has_gold
            new_row["oracle_recoverable"] = has_gold
            labeled.append(new_row)
    return labeled


def math_isclose(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9


def _selector_choice(case_rows: list[dict[str, Any]], selector_name: str) -> dict[str, Any]:
    if selector_name == "prefer_bftc_only_final":
        return _choose_single(case_rows, lambda row: row["came_from_bftc_only_final"])
    if selector_name == "prefer_exec_formula_final":
        return _choose_single(case_rows, lambda row: row["came_from_exec_formula"])
    if selector_name == "prefer_model_final":
        return _choose_single(case_rows, lambda row: row["came_from_exec_model_final"])
    if selector_name == "prefer_variable_with_target_overlap":
        variable_rows = [row for row in case_rows if row["came_from_formula_variable"]]
        if variable_rows:
            return _choose_by_score(
                variable_rows,
                lambda row: (
                    row["candidate_from_target_suggesting_variable"],
                    row["max_variable_description_target_overlap"],
                    row["max_variable_name_target_overlap"],
                    row["unit_match_any"],
                ),
            )
        return _choose_single(case_rows, lambda row: row["came_from_bftc_only_final"])
    if selector_name == "prefer_non_prompt_inconsistent_best_target_overlap":
        if case_rows[0]["prompt_gold_inconsistent"]:
            return _choose_single(case_rows, lambda row: row["came_from_bftc_only_final"])
        return _choose_by_score(case_rows, lambda row: row["selector_overlap_score"])
    if selector_name == "oracle_upper_bound":
        oracle_rows = [row for row in case_rows if row["candidate_matches_gold"]]
        if oracle_rows:
            return sorted(oracle_rows, key=_provenance_sort_key)[0]
        return _choose_single(case_rows, lambda row: row["came_from_bftc_only_final"])
    raise ValueError(f"Unknown selector: {selector_name}")


def evaluate_selectors(candidate_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        by_case[row["case_id"]].append(row)

    selector_names = [
        "prefer_bftc_only_final",
        "prefer_exec_formula_final",
        "prefer_model_final",
        "prefer_variable_with_target_overlap",
        "prefer_non_prompt_inconsistent_best_target_overlap",
        "oracle_upper_bound",
    ]
    selector_results: list[dict[str, Any]] = []
    case_choices: list[dict[str, Any]] = []

    for selector_name in selector_names:
        correct = 0
        prompt_inconsistent_correct = 0
        prompt_inconsistent_total = 0
        for case_id in sorted(by_case):
            rows = by_case[case_id]
            choice = _selector_choice(rows, selector_name)
            case_choices.append(
                {
                    "selector": selector_name,
                    "case_id": case_id,
                    "chosen_candidate": choice["candidate_value"],
                    "chosen_candidate_normalized": choice["candidate_value_normalized"],
                    "chosen_provenance": choice["provenance_types_joined"],
                    "candidate_matches_gold": choice["candidate_matches_gold"],
                    "oracle_recoverable": choice["oracle_recoverable"],
                    "prompt_gold_inconsistent": choice["prompt_gold_inconsistent"],
                }
            )
            correct += int(choice["candidate_matches_gold"])
            if choice["prompt_gold_inconsistent"]:
                prompt_inconsistent_total += 1
                prompt_inconsistent_correct += int(choice["candidate_matches_gold"])

        total = len(by_case)
        selector_results.append(
            {
                "selector": selector_name,
                "correct_count": correct,
                "accuracy": correct / total if total else 0.0,
                "prompt_inconsistent_correct_count": prompt_inconsistent_correct,
                "prompt_inconsistent_case_count": prompt_inconsistent_total,
            }
        )

    return selector_results, case_choices


def build_summary(
    candidate_rows: list[dict[str, Any]],
    selector_results: list[dict[str, Any]],
    case_choices: list[dict[str, Any]],
) -> dict[str, Any]:
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        by_case[row["case_id"]].append(row)

    prompt_inconsistent_cases = sorted(
        {case_id for case_id, rows in by_case.items() if rows[0]["prompt_gold_inconsistent"]}
    )
    gold_in_candidate_cases = sorted(
        {case_id for case_id, rows in by_case.items() if rows[0]["case_has_gold_in_candidate_set"]}
    )
    variable_rebinding_cases = sorted(
        {
            case_id
            for case_id, rows in by_case.items()
            if any(
                row["candidate_matches_gold"]
                and row["came_from_formula_variable"]
                and not row["came_from_exec_formula"]
                for row in rows
            )
        }
    )
    variable_gold_examples = []
    for case_id, rows in by_case.items():
        if any(
            row["candidate_matches_gold"]
            and row["came_from_formula_variable"]
            and not row["came_from_exec_formula"]
            for row in rows
        ):
            chosen_exec = _selector_choice(rows, "prefer_exec_formula_final")
            if not chosen_exec["candidate_matches_gold"]:
                gold_rows = [
                    row for row in rows if row["candidate_matches_gold"] and row["came_from_formula_variable"]
                ]
                variable_gold_examples.append(
                    {
                        "case_id": case_id,
                        "exec_formula_final": chosen_exec["candidate_value"],
                        "gold_variable_candidates": [
                            {
                                "candidate_value": row["candidate_value"],
                                "variable_names": row["variable_names"],
                                "variable_descriptions": row["variable_descriptions"],
                            }
                            for row in gold_rows
                        ],
                    }
                )

    prompt_inconsistent_recoverable = sorted(
        {
            case_id
            for case_id in prompt_inconsistent_cases
            if by_case[case_id][0]["case_has_gold_in_candidate_set"]
        }
    )
    prompt_inconsistent_unrecoverable = sorted(
        set(prompt_inconsistent_cases) - set(prompt_inconsistent_recoverable)
    )

    selector_map = {row["selector"]: row for row in selector_results}
    candidate_counts = [len(rows) for rows in by_case.values()]

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": _utc_stamp(),
        "case_count": len(by_case),
        "candidate_row_count": len(candidate_rows),
        "candidate_count_mean": statistics.mean(candidate_counts) if candidate_counts else 0.0,
        "candidate_count_median": statistics.median(candidate_counts) if candidate_counts else 0.0,
        "candidate_pool_union_recovery_count": len(gold_in_candidate_cases),
        "candidate_pool_union_recovery_rate": len(gold_in_candidate_cases) / len(by_case)
        if by_case
        else 0.0,
        "gold_in_candidate_set_case_ids": gold_in_candidate_cases,
        "prompt_gold_inconsistent_case_ids": prompt_inconsistent_cases,
        "prompt_gold_inconsistent_recoverable_case_ids": prompt_inconsistent_recoverable,
        "prompt_gold_inconsistent_unrecoverable_case_ids": prompt_inconsistent_unrecoverable,
        "variable_rebinding_recoverable_case_ids": variable_rebinding_cases,
        "variable_rebinding_recoverable_count": len(variable_rebinding_cases),
        "formula_variable_gold_examples": variable_gold_examples,
        "selectors": selector_results,
        "oracle_upper_bound_count": selector_map["oracle_upper_bound"]["correct_count"],
        "oracle_upper_bound_rate": selector_map["oracle_upper_bound"]["accuracy"],
        "provenance_counts": dict(
            Counter(
                provenance
                for row in candidate_rows
                for provenance in row["provenance_types"]
            )
        ),
    }


def write_case_report(
    out_dir: Path,
    summary: dict[str, Any],
    case_choices: list[dict[str, Any]],
) -> None:
    selector_lines = []
    for row in summary["selectors"]:
        selector_lines.append(
            f"- `{row['selector']}`: {row['correct_count']}/{summary['case_count']}"
        )
    example_lines = []
    for item in summary["formula_variable_gold_examples"][:5]:
        example_lines.append(
            f"- `{item['case_id']}`: exec formula chose {item['exec_formula_final']}, "
            f"but a formula-variable candidate matched gold."
        )
    lines = [
        "# BFTC Candidate Rebinding Selector v1 — Case Report",
        "",
        "## Summary",
        f"- Cases: {summary['case_count']}",
        f"- Candidate rows: {summary['candidate_row_count']}",
        f"- Gold in combined candidate set: {summary['candidate_pool_union_recovery_count']}/{summary['case_count']}",
        f"- Variable rebinding recoverable: {summary['variable_rebinding_recoverable_count']}",
        "",
        "## Selector Accuracy",
        *selector_lines,
        "",
        "## Prompt/Gold Inconsistency",
        f"- Inconsistent cases: {len(summary['prompt_gold_inconsistent_case_ids'])}",
        f"- Inconsistent but recoverable: {len(summary['prompt_gold_inconsistent_recoverable_case_ids'])}",
        f"- Inconsistent and unrecoverable: {len(summary['prompt_gold_inconsistent_unrecoverable_case_ids'])}",
        "",
        "## Formula Variable Gold Examples",
        *(example_lines or ["- none"]),
    ]
    (out_dir / "case_selector_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_doc(
    *,
    doc_path: Path,
    out_dir: Path,
    summary: dict[str, Any],
) -> None:
    selector_lines = []
    for row in summary["selectors"]:
        selector_lines.append(
            f"| `{row['selector']}` | `{row['correct_count']}/{summary['case_count']}` |"
        )
    doc_lines = [
        "# BFTC Candidate Rebinding Selector v1 Analysis",
        "**Date:** 2026-05-12  ",
        f"**Output directory:** `{out_dir}`  ",
        "**Mode:** offline / no-API",
        "",
        "## Motivation",
        "",
        "The BFTC executable-repair pilot showed that formulas executed safely but usually encoded the wrong relation or variable binding. This analysis asks a narrower offline question: if we union the candidates already available from BFTC-only, executable-repair finals, executable formula outputs, and formula-variable values, how much selector headroom is present without another model call?",
        "",
        "## Input Pilots",
        "",
        "- `outputs/bftc_live_pilot_v1_20cases_20260512T210634Z`",
        "- `outputs/bftc_executable_repair_v1_live_20cases_20260512T221521Z`",
        "- `docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv`",
        "- `outputs/bftc_executable_repair_v1_live_20cases_20260512T221521Z/bftc_executable_case_error_analysis.jsonl`",
        "",
        "## Candidate Set Construction",
        "",
        "Per case, the candidate set unions:",
        "",
        "- BFTC-only final answer",
        "- executable-repair model final answer",
        "- executable formula final answer",
        "- numeric values from `formula_variables`",
        "- any top-level repaired-candidate / final-answer fields that were numeric",
        "",
        "Candidates are deduplicated numerically, while provenance is preserved.",
        "",
        "## Feature Definitions",
        "",
        "For each candidate, the analysis records:",
        "",
        "- provenance type(s)",
        "- whether the candidate equals a formula-variable value",
        "- lexical overlap between variable name/description and the requested target",
        "- unit match between variable unit and target/question text",
        "- whether the candidate came from the executable formula",
        "- whether the candidate came from the BFTC-only final",
        "- whether the postmortem marks the relation category as suspicious",
        "- whether the case is prompt/gold inconsistent",
        "",
        "Gold is attached only after candidate construction for offline labels and reporting.",
        "",
        "## Selector Results",
        "",
        "| Selector | Exact |",
        "|---|---:|",
        *selector_lines,
        "",
        "## Oracle Upper Bound",
        "",
        f"- Gold appears somewhere in the combined candidate set for `{summary['candidate_pool_union_recovery_count']}/{summary['case_count']}` cases.",
        f"- Oracle upper bound: `{summary['oracle_upper_bound_count']}/{summary['case_count']}`",
        f"- Variable-rebinding recoverable without another model call: `{summary['variable_rebinding_recoverable_count']}` cases",
        "",
        "## Prompt/Gold Inconsistency Effect",
        "",
        f"- Prompt/gold inconsistent cases: `{len(summary['prompt_gold_inconsistent_case_ids'])}`",
        f"- Inconsistent but still oracle-recoverable: `{len(summary['prompt_gold_inconsistent_recoverable_case_ids'])}`",
        f"- Inconsistent and unrecoverable/misleading: `{len(summary['prompt_gold_inconsistent_unrecoverable_case_ids'])}`",
        "",
        "This means the 20-case slice should not be reused as a clean live gating set without first separating provenance-clean cases from prompt/gold mismatches.",
        "",
        "## Recommendation",
        "",
        "- Do not build the current heuristic rebinding selector directly into runtime yet.",
        "- Clean or quarantine the 6 prompt/gold inconsistent cases before more live tests.",
        "- The next live candidate should be `relation-verifier + formula-verifier`, not a prompt-only rerun.",
        "- A rebinding selector is still worth building offline, because the combined candidate pool exceeds the 4/20 union recovered by direct system outputs alone whenever gold lands in a formula-variable value.",
    ]
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")


def run_analysis(
    *,
    bftc_only_dir: Path,
    exec_dir: Path,
    casebook_path: Path,
    out_dir: Path,
    doc_path: Path,
) -> dict[str, Any]:
    exec_postmortem = load_exec_postmortem(exec_dir)
    candidate_rows = build_candidate_rows(
        bftc_only_dir=bftc_only_dir,
        exec_dir=exec_dir,
        exec_postmortem=exec_postmortem,
    )
    casebook = load_casebook(casebook_path)
    gold_map = {
        case_id: float(row["gold"])
        for case_id, row in casebook.items()
        if _normalize_numeric(row.get("gold")) is not None
    }
    labeled_rows = attach_posthoc_gold_labels(candidate_rows, gold_map)
    selector_results, case_choices = evaluate_selectors(labeled_rows)
    summary = build_summary(labeled_rows, selector_results, case_choices)

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "selector_summary.json", summary)
    _write_jsonl(out_dir / "candidate_set_rows.jsonl", labeled_rows)
    csv_rows = []
    for row in labeled_rows:
        csv_row = dict(row)
        csv_row["provenance_types"] = json.dumps(row["provenance_types"])
        csv_row["variable_names"] = json.dumps(row["variable_names"])
        csv_row["variable_descriptions"] = json.dumps(row["variable_descriptions"])
        csv_row["variable_units"] = json.dumps(row["variable_units"])
        csv_rows.append(csv_row)
    _write_csv(out_dir / "candidate_set_rows.csv", csv_rows)
    write_case_report(out_dir, summary, case_choices)
    write_doc(doc_path=doc_path, out_dir=out_dir, summary=summary)
    return summary


def _default_out_dir() -> Path:
    return REPO_ROOT / "outputs" / f"{EXPERIMENT_ID}_{_utc_stamp()}"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline BFTC candidate rebinding selector analysis.")
    parser.add_argument("--bftc-only-dir", required=True, type=Path)
    parser.add_argument("--exec-dir", required=True, type=Path)
    parser.add_argument("--casebook", required=True, type=Path)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = _parse_args(argv)
    out_dir = args.out_dir or _default_out_dir()
    summary = run_analysis(
        bftc_only_dir=args.bftc_only_dir,
        exec_dir=args.exec_dir,
        casebook_path=args.casebook,
        out_dir=out_dir,
        doc_path=args.doc_path,
    )
    print(out_dir)
    return summary


if __name__ == "__main__":
    main()
