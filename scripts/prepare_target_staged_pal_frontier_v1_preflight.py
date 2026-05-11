#!/usr/bin/env python3
"""No-API preflight scaffold for target_staged_pal_frontier_v1."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.gsm8k_structural_validate import validate_gsm8k_candidate
from experiments.selector_error_features import build_structural_target_feature_row

EXPERIMENT_ID = "target_staged_pal_frontier_v1"
ALIAS = "ts_pal_frontier_v1"
DEFAULT_TIMESTAMP = "20260511"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs"
DEFAULT_MANIFEST_PATH = (
    REPO_ROOT / "manifests" / "target_staged_pal_frontier_v1_preflight_20260511.json"
)
DEFAULT_PROMPT_DIR = REPO_ROOT / "prompts" / "target_staged_pal_frontier_v1"
DEFAULT_BUDGET = 6
PROMPT_TEMPLATE_IDS = (
    "target_schema_prepass",
    "target_first_reasoning",
    "entity_unit_ledger_reasoning",
    "equation_first_reasoning",
    "pal_code_with_required_target_variable",
    "backward_from_target_check",
)
BRANCH_TEMPLATE_IDS = PROMPT_TEMPLATE_IDS[1:]
CASE_SPECS = (
    ("primary", "wrong_supported_consensus_97"),
    ("secondary", "direct_l1_anchor_potential_43"),
    ("guardrail", "four_way_pilot_30"),
    ("caution", "direct_l1_strong_seed_15"),
)
TEMPLATE_PATHS = {
    tid: DEFAULT_PROMPT_DIR / f"{tid}.md" for tid in PROMPT_TEMPLATE_IDS
}
FORBIDDEN_PROMPT_PATTERNS = (
    re.compile(r"\bgold_answer\b\s*[:=]", re.I),
    re.compile(r"\banswer_key\b\s*[:=]", re.I),
    re.compile(r"\bhidden[_ -]?labels?\b\s*[:=]", re.I),
    re.compile(r"\bgold\b\s*[:=]", re.I),
)

_TARGET_SURFACE_RE = re.compile(
    r"(?:what is(?: the)?|how many|how much|find(?: the)?|calculate|determine|express(?: the)?)\s+(.+?)(?:\?|$)",
    re.I,
)
_MONEY_RE = re.compile(r"[\$£€]|\b(dollars?|cents?|cost(?:s|ing)?|price(?:s)?|revenue|profit|money)\b", re.I)
_COUNT_RE = re.compile(r"\b(how many|number of|count|counts)\b", re.I)
_RATE_RE = re.compile(r"\b(per|each|every|mph|/hour|per hour|per day|per minute|rate)\b", re.I)
_DIFF_RE = re.compile(r"\b(more than|less than|difference|remaining|left|compare)\b", re.I)
_RATIO_RE = re.compile(r"\b(percent|percentage|ratio|fraction|proportion|out of)\b", re.I)
_TIME_RE = re.compile(r"\b(now|today|after|before|from now|initial|final|remaining|left)\b", re.I)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _load_csv_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append({str(k): ("" if v is None else str(v)) for k, v in row.items()})
    return rows


def _flatten_for_csv(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    if value is None:
        return ""
    return value


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
            writer.writerow({k: _flatten_for_csv(row.get(k)) for k in fieldnames})


def parse_target_schema(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TypeError("target schema must be a mapping")
    out = {
        "target_variable": _stringify(raw.get("target_variable")),
        "entity": _stringify(raw.get("entity")),
        "unit": _stringify(raw.get("unit")),
        "time_or_state": _stringify(raw.get("time_or_state")),
        "operation_goal": _stringify(raw.get("operation_goal")),
        "known_quantities": [],
        "required_relations": [],
        "uncertainty": bool(raw.get("uncertainty", False)),
    }
    known_quantities = raw.get("known_quantities")
    if isinstance(known_quantities, list):
        for idx, item in enumerate(known_quantities, start=1):
            if not isinstance(item, dict):
                continue
            out["known_quantities"].append(
                {
                    "name": _stringify(item.get("name") or f"quantity_{idx}"),
                    "value": _stringify(item.get("value")),
                    "unit": _stringify(item.get("unit")),
                }
            )
    required_relations = raw.get("required_relations")
    if isinstance(required_relations, list):
        out["required_relations"] = [_stringify(item) for item in required_relations if _stringify(item)]
    return out


def serialize_target_schema(schema: dict[str, Any]) -> str:
    return json.dumps(parse_target_schema(schema), sort_keys=True, ensure_ascii=False)


def _extract_target_surface(question: str) -> str:
    match = _TARGET_SURFACE_RE.search(question or "")
    if not match:
        return ""
    surface = re.sub(r"\s+", " ", match.group(1)).strip(" .")
    return surface[:120]


def _infer_unit(question: str) -> str:
    q = (question or "").lower()
    if _MONEY_RE.search(q):
        return "money"
    if _COUNT_RE.search(q):
        return "count"
    if _RATE_RE.search(q):
        return "rate"
    if _DIFF_RE.search(q):
        return "difference"
    if _RATIO_RE.search(q):
        return "ratio"
    if re.search(r"\b(minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years|second|seconds)\b", q):
        return "time"
    return "unknown"


def _infer_time_or_state(question: str) -> str:
    q = (question or "").lower()
    if "before" in q or "after" in q:
        return "before_after"
    if "from now" in q:
        return "future_state"
    if "now" in q:
        return "current_state"
    if "final" in q:
        return "final_state"
    if _TIME_RE.search(q):
        return "time_marker"
    return "unknown"


def _infer_operation_goal(question: str) -> str:
    q = (question or "").lower()
    if any(tok in q for tok in ("total", "altogether", "in all", "combined", "sum")):
        return "add"
    if any(tok in q for tok in ("left", "remaining", "difference", "less than", "more than")):
        return "subtract"
    if any(tok in q for tok in ("per", "each", "every", "rate", "times", "product")):
        return "multiply_or_divide"
    if any(tok in q for tok in ("ratio", "percent", "percentage", "fraction", "proportion")):
        return "ratio"
    if any(tok in q for tok in ("convert", "conversion", "hours to minutes", "minutes to hours")):
        return "convert"
    if any(tok in q for tok in ("equation", "solve for", "find x", "variable")):
        return "equation"
    return "solve"


def _infer_quantity_unit(context: str) -> str:
    q = (context or "").lower()
    if _MONEY_RE.search(q):
        return "money"
    if re.search(r"\b(minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years|second|seconds)\b", q):
        return "time"
    if _RATIO_RE.search(q):
        return "ratio"
    if _RATE_RE.search(q):
        return "rate"
    if _COUNT_RE.search(q):
        return "count"
    return "unknown"


def _extract_known_quantities(question: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for idx, match in enumerate(re.finditer(r"(?<!\w)(-?\d+(?:\.\d+)?)(?!\w)", question or ""), start=1):
        start = max(0, match.start() - 40)
        end = min(len(question), match.end() + 40)
        context = question[start:end]
        out.append(
            {
                "name": f"quantity_{idx}",
                "value": match.group(1),
                "unit": _infer_quantity_unit(context),
            }
        )
    return out


def build_target_schema(question: str, *, case_id: str = "", slice_name: str = "") -> dict[str, Any]:
    target_surface = _extract_target_surface(question)
    unit = _infer_unit(question)
    target_variable = target_surface or "final_target"
    entity = target_surface or target_variable
    known_quantities = _extract_known_quantities(question)
    operation_goal = _infer_operation_goal(question)
    relations = [f"bind_target:{target_variable}"]
    if operation_goal != "solve":
        relations.append(f"apply_{operation_goal}")
    if unit != "unknown":
        relations.append("preserve_unit_consistency")
    if any(tok in (question or "").lower() for tok in (" or ", "either", "uncertain", "maybe")):
        relations.append("handle_ambiguity")
    uncertainty = bool(
        not target_surface
        or unit == "unknown"
        or not known_quantities
        or any(tok in (question or "").lower() for tok in (" or ", "either", "maybe"))
    )
    if case_id or slice_name:
        relations.append(f"preflight_case:{slice_name or 'unknown'}")
    return parse_target_schema(
        {
            "target_variable": target_variable,
            "entity": entity,
            "unit": unit,
            "time_or_state": _infer_time_or_state(question),
            "operation_goal": operation_goal,
            "known_quantities": known_quantities,
            "required_relations": relations,
            "uncertainty": uncertainty,
        }
    )


def _schema_to_ledger(schema: dict[str, Any]) -> list[dict[str, str]]:
    entity = _stringify(schema.get("entity")) or _stringify(schema.get("target_variable"))
    ledger: list[dict[str, str]] = []
    for idx, item in enumerate(schema.get("known_quantities") or [], start=1):
        if not isinstance(item, dict):
            continue
        ledger.append(
            {
                "entity": entity,
                "quantity_name": _stringify(item.get("name") or f"quantity_{idx}"),
                "quantity_value": _stringify(item.get("value")),
                "unit": _stringify(item.get("unit") or schema.get("unit")),
            }
        )
    return ledger


def _sanitize_identifier(text: str) -> str:
    ident = re.sub(r"[^0-9a-zA-Z_]+", "_", _stringify(text)).strip("_")
    if not ident:
        return "target_value"
    if ident[0].isdigit():
        ident = f"target_{ident}"
    return ident


def _pal_stub_code(schema: dict[str, Any], *, branch_slot: int) -> str:
    target = _sanitize_identifier(schema.get("target_variable") or "target_value")
    return f"{target} = {int(branch_slot)}\nprint({target})"


def _prompt_template_path(template_id: str) -> Path:
    if template_id not in TEMPLATE_PATHS:
        raise KeyError(f"unknown prompt template: {template_id}")
    return TEMPLATE_PATHS[template_id]


def render_prompt(template_id: str, *, question: str, target_schema: dict[str, Any] | None = None) -> str:
    template = _prompt_template_path(template_id).read_text(encoding="utf-8")
    rendered = template.replace("{{question}}", question)
    schema_json = serialize_target_schema(target_schema or {})
    rendered = rendered.replace("{{target_schema_json}}", schema_json)
    if "{{" in rendered or "}}" in rendered:
        raise ValueError(f"unresolved placeholder in {template_id}")
    return rendered


def _contains_forbidden_prompt_markers(prompt: str) -> list[str]:
    hits: list[str] = []
    for pattern in FORBIDDEN_PROMPT_PATTERNS:
        if pattern.search(prompt or ""):
            hits.append(pattern.pattern)
    return hits


def _load_question_bank() -> dict[str, str]:
    bank: dict[str, str] = {}
    reference_paths = [
        REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl",
        REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl",
        REPO_ROOT / "docs/project_handoff_20260510/target_audit_diagnostic_cases.jsonl",
    ]
    for path in reference_paths:
        for row in _load_jsonl_rows(path):
            cid = _stringify(row.get("example_id") or row.get("case_id"))
            question = _stringify(row.get("question") or row.get("problem_text"))
            if cid and question:
                bank[cid] = question
    return bank


def _synthetic_question(case_id: str, slice_name: str, ordinal: int, source_row: dict[str, Any]) -> str:
    base = 3 + (ordinal % 5)
    extra = 2 + (ordinal % 4)
    label = _stringify(source_row.get("failure_family") or source_row.get("question_type") or source_row.get("error_type") or "unknown")
    return (
        f"Synthetic preflight placeholder for case {case_id} in the {slice_name} slice "
        f"({label}). There are {base} items and {extra} more items. What is the final total?"
    )


def _select_case_rows(
    *,
    manifest: dict[str, Any],
    question_bank: dict[str, str],
    case_source: str,
    max_cases_per_slice: int | None,
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    slice_defs = manifest.get("slice_definitions") or {}
    for slice_name, _label in CASE_SPECS:
        spec = dict(slice_defs.get(slice_name) or {})
        source_path = REPO_ROOT / _stringify(spec.get("source_path"))
        case_count = int(spec.get("case_count") or 0)
        limit = case_count
        if max_cases_per_slice is not None:
            limit = min(limit, max_cases_per_slice)

        if source_path.suffix.lower() == ".jsonl":
            rows = _load_jsonl_rows(source_path)
        else:
            rows = _load_csv_rows(source_path)

        if not rows:
            continue

        seen_case_ids: set[str] = set()
        selected_for_slice = 0
        for ordinal, row in enumerate(rows, start=1):
            case_id = _stringify(row.get("case_id") or row.get("example_id"))
            if not case_id or case_id in seen_case_ids:
                continue
            seen_case_ids.add(case_id)
            if selected_for_slice >= limit:
                break

            real_question = _stringify(row.get("question") or row.get("problem_text"))
            if case_source == "synthetic":
                question = _synthetic_question(case_id, slice_name, ordinal, row)
                question_source = "synthetic_placeholder"
            else:
                if real_question:
                    question = real_question
                    question_source = "source_row_question"
                elif case_id in question_bank:
                    question = question_bank[case_id]
                    question_source = "reference_question_bank"
                else:
                    question = _synthetic_question(case_id, slice_name, ordinal, row)
                    question_source = "synthetic_placeholder"

            resolved.append(
                {
                    "slice_name": slice_name,
                    "slice_label": _label,
                    "case_id": case_id,
                    "case_ordinal": ordinal,
                    "case_count_target": case_count,
                    "case_source": case_source,
                    "question_source": question_source,
                    "question": question,
                    "source_path": str(source_path.relative_to(REPO_ROOT)),
                    "source_metadata": {
                        k: v
                        for k, v in row.items()
                        if k not in {"question", "problem_text"}
                    },
                }
            )
            selected_for_slice += 1
            if selected_for_slice >= limit:
                break
    return resolved


def validate_manifest(manifest: dict[str, Any]) -> None:
    if _stringify(manifest.get("experiment_id")) != EXPERIMENT_ID:
        raise ValueError("manifest experiment_id mismatch")
    if _stringify(manifest.get("alias")) != ALIAS:
        raise ValueError("manifest alias mismatch")
    if _stringify(manifest.get("mode")) != "dry_run_only":
        raise ValueError("manifest mode must be dry_run_only")
    if manifest.get("runtime_defaults_changed") is not False:
        raise ValueError("manifest must not change runtime defaults")
    if manifest.get("api_calls_allowed") is not False:
        raise ValueError("manifest must not allow API calls")
    branches = list(manifest.get("branch_families") or [])
    if branches != list(BRANCH_TEMPLATE_IDS):
        raise ValueError("manifest branch_families mismatch")
    slices = manifest.get("slice_definitions")
    if not isinstance(slices, dict):
        raise ValueError("manifest slice_definitions must be a mapping")
    for slice_name, label in CASE_SPECS:
        spec = dict(slices.get(slice_name) or {})
        if _stringify(spec.get("label")) != label:
            raise ValueError(f"manifest slice label mismatch for {slice_name}")
        if int(spec.get("case_count") or 0) <= 0:
            raise ValueError(f"manifest slice case_count missing for {slice_name}")
    out_files = list(manifest.get("expected_output_files") or [])
    required_outputs = {
        "manifest.resolved.json",
        "call_plan.jsonl",
        "traces.jsonl",
        "candidate_feature_rows.csv",
        "candidate_feature_rows.jsonl",
        "replay_summary.json",
        "replay_report.md",
    }
    if not required_outputs.issubset(set(out_files)):
        raise ValueError("manifest expected_output_files mismatch")


def build_call_plan(
    *,
    manifest: dict[str, Any],
    case_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    call_plan_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    resolved_budget = int(manifest.get("resolved_total_action_budget") or DEFAULT_BUDGET)

    for case_idx, case in enumerate(case_rows, start=1):
        question = _stringify(case.get("question"))
        case_id = _stringify(case.get("case_id"))
        slice_name = _stringify(case.get("slice_name"))
        target_schema = build_target_schema(question, case_id=case_id, slice_name=slice_name)
        target_schema_json = json.dumps(target_schema, indent=2, sort_keys=True, ensure_ascii=False)
        roundtrip_ok = parse_target_schema(json.loads(serialize_target_schema(target_schema))) == target_schema
        ledger = _schema_to_ledger(target_schema)
        source_meta = dict(case.get("source_metadata") or {})

        for branch_slot, template_id in enumerate(PROMPT_TEMPLATE_IDS):
            branch_family = "schema_prepass" if template_id == "target_schema_prepass" else template_id
            prompt = render_prompt(template_id, question=question, target_schema=target_schema)
            render_ok = ("{{" not in prompt) and ("}}" not in prompt) and question in prompt
            forbidden_hits = _contains_forbidden_prompt_markers(prompt)
            no_gold_leak_ok = len(forbidden_hits) == 0
            candidate_role = "unknown" if template_id == "target_schema_prepass" else "target"
            candidate_answer = "" if template_id == "target_schema_prepass" else str(branch_slot)
            candidate_code = _pal_stub_code(target_schema, branch_slot=branch_slot) if template_id == "pal_code_with_required_target_variable" else None
            execution_metadata = {
                "candidate_role": candidate_role,
                "reasoning_role": branch_family,
                "source_family": template_id,
                "target_variable": target_schema.get("target_variable", ""),
                "target_entity": target_schema.get("entity", ""),
                "target_unit": target_schema.get("unit", ""),
                "entity_ledger": ledger,
                "unit_consistency_status": "unknown",
                "branch_family": branch_family,
            }
            validation = validate_gsm8k_candidate(
                problem_text=question,
                candidate_answer=candidate_answer,
                candidate_trace=prompt,
                candidate_code=candidate_code,
                source_family=template_id,
                execution_metadata=execution_metadata,
            )
            structural = build_structural_target_feature_row(
                question=question,
                candidate_trace=prompt,
                candidate_code=candidate_code,
                candidate_answer=candidate_answer,
                execution_metadata=execution_metadata,
                support_count=1,
            )
            trace_compat_ok = (
                validation.get("target_tuple") == structural.get("target_tuple")
                and validation.get("structural_selector_score") == structural.get("structural_selector_score")
            )
            call_plan_id = f"{ALIAS}:{slice_name}:{case_id}:{template_id}:{branch_slot}"
            base_row = {
                "experiment_id": EXPERIMENT_ID,
                "alias": ALIAS,
                "slice_name": slice_name,
                "slice_label": case.get("slice_label"),
                "case_id": case_id,
                "case_index": case_idx,
                "case_ordinal": case.get("case_ordinal"),
                "question_source": case.get("question_source"),
                "source_path": case.get("source_path"),
                "case_source": case.get("case_source"),
                "question": question,
                "target_schema": target_schema,
                "target_schema_json": target_schema_json,
                "target_variable": target_schema.get("target_variable", ""),
                "entity": target_schema.get("entity", ""),
                "unit": target_schema.get("unit", ""),
                "time_or_state": target_schema.get("time_or_state", ""),
                "operation_goal": target_schema.get("operation_goal", ""),
                "known_quantities": target_schema.get("known_quantities", []),
                "required_relations": target_schema.get("required_relations", []),
                "uncertainty": target_schema.get("uncertainty", False),
                "plan_stage": "schema_prepass" if template_id == "target_schema_prepass" else "branch_generation",
                "branch_family": branch_family,
                "branch_slot": branch_slot,
                "schema_slot_reserved": bool(template_id == "pal_code_with_required_target_variable"),
                "prompt_template_id": template_id,
                "prompt_template_path": str(_prompt_template_path(template_id).relative_to(REPO_ROOT)),
                "call_plan_id": call_plan_id,
                "budget_total": resolved_budget,
                "budget_cost": 1,
                "schema_roundtrip_ok": roundtrip_ok,
                "parse_ok": roundtrip_ok,
                "render_ok": render_ok,
                "no_gold_leak_ok": no_gold_leak_ok,
                "trace_compat_ok": trace_compat_ok,
                "forbidden_prompt_patterns": forbidden_hits,
                "candidate_role": candidate_role,
                "candidate_answer": candidate_answer,
                "candidate_code": candidate_code or "",
                "candidate_trace": prompt,
                "execution_metadata": execution_metadata,
                "validator": validation,
                "structural_features": structural,
            }
            call_plan_rows.append(base_row)
            trace_rows.append(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "alias": ALIAS,
                    "call_plan_id": call_plan_id,
                    "slice_name": slice_name,
                    "case_id": case_id,
                    "prompt_template_id": template_id,
                    "branch_family": branch_family,
                    "branch_slot": branch_slot,
                    "question_source": case.get("question_source"),
                    "rendered_prompt": prompt,
                    "render_ok": render_ok,
                    "no_gold_leak_ok": no_gold_leak_ok,
                    "schema_roundtrip_ok": roundtrip_ok,
                    "trace_compat_ok": trace_compat_ok,
                    "candidate_answer": candidate_answer,
                    "candidate_code": candidate_code or "",
                    "validation": validation,
                }
            )
            feature_row = {
                "experiment_id": EXPERIMENT_ID,
                "alias": ALIAS,
                "slice_name": slice_name,
                "slice_label": case.get("slice_label"),
                "case_id": case_id,
                "call_plan_id": call_plan_id,
                "prompt_template_id": template_id,
                "branch_family": branch_family,
                "branch_slot": branch_slot,
                "question_source": case.get("question_source"),
                "source_path": case.get("source_path"),
                "candidate_answer": candidate_answer,
                "candidate_code": candidate_code or "",
                "candidate_trace": prompt,
                "target_schema": target_schema,
                "target_tuple": validation.get("target_tuple"),
                "entity_unit_ledger_proxy": validation.get("entity_unit_ledger_proxy"),
                "final_answer_role": validation.get("final_answer_role"),
                "last_operation_family": validation.get("last_operation_family"),
                "target_alignment_score": validation.get("target_alignment_score"),
                "intermediate_answer_penalty": validation.get("intermediate_answer_penalty"),
                "duplicate_wrong_signature": validation.get("duplicate_wrong_signature"),
                "structural_selector_score": validation.get("structural_selector_score"),
                "structural_score": validation.get("structural_score"),
                "quantity_coverage": validation.get("quantity_coverage"),
                "operation_cues_required": validation.get("operation_cues_required"),
                "operation_cues_found": validation.get("operation_cues_found"),
                "target_question_type": validation.get("target_question_type"),
                "target_type_match": validation.get("target_type_match"),
                "code_syntax_ok": validation.get("code_syntax_ok"),
                "exec_ok": validation.get("exec_ok"),
                "errors": validation.get("errors"),
                "warnings": validation.get("warnings"),
                "abstain_reasons": validation.get("abstain_reasons"),
                "parse_ok": roundtrip_ok,
                "render_ok": render_ok,
                "no_gold_leak_ok": no_gold_leak_ok,
                "trace_compat_ok": trace_compat_ok,
            }
            feature_rows.append(feature_row)
    return call_plan_rows, trace_rows, feature_rows


def _summarize_rows(
    *,
    manifest: dict[str, Any],
    case_rows: list[dict[str, Any]],
    call_plan_rows: list[dict[str, Any]],
    trace_rows: list[dict[str, Any]],
    feature_rows: list[dict[str, Any]],
    output_dir: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    per_slice_counts = Counter(str(row.get("slice_name") or "") for row in case_rows)
    question_sources = Counter(str(row.get("question_source") or "") for row in case_rows)
    template_counts = Counter(str(row.get("prompt_template_id") or "") for row in call_plan_rows)
    branch_counts = Counter(str(row.get("branch_family") or "") for row in call_plan_rows)
    bool_counts = {
        "parse_ok": sum(1 for row in call_plan_rows if row.get("parse_ok")),
        "render_ok": sum(1 for row in call_plan_rows if row.get("render_ok")),
        "no_gold_leak_ok": sum(1 for row in call_plan_rows if row.get("no_gold_leak_ok")),
        "trace_compat_ok": sum(1 for row in call_plan_rows if row.get("trace_compat_ok")),
    }
    all_ok = all(v == len(call_plan_rows) for v in bool_counts.values()) if call_plan_rows else False
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "alias": ALIAS,
        "manifest_path": str(manifest_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "case_count": len(case_rows),
        "call_plan_row_count": len(call_plan_rows),
        "trace_row_count": len(trace_rows),
        "candidate_feature_row_count": len(feature_rows),
        "budget_total": manifest.get("resolved_total_action_budget", DEFAULT_BUDGET),
        "slice_counts": dict(per_slice_counts),
        "question_source_counts": dict(question_sources),
        "prompt_template_counts": dict(template_counts),
        "branch_family_counts": dict(branch_counts),
        "validation_counts": bool_counts,
        "all_validation_flags_ok": all_ok,
        "schema_roundtrip_ok": all_ok,
        "prompt_render_ok": all_ok,
        "no_gold_leakage_ok": all_ok,
        "dry_run_only": True,
        "trace_compatibility_ok": all_ok,
        "no_api_clients_constructed": True,
        "output_files": [
            "manifest.resolved.json",
            "call_plan.jsonl",
            "traces.jsonl",
            "candidate_feature_rows.csv",
            "candidate_feature_rows.jsonl",
            "validation_summary.json",
            "replay_summary.json",
            "dry_run_report.md",
            "replay_report.md",
        ],
    }
    return summary


def _render_report(title: str, summary: dict[str, Any], *, include_replay: bool) -> str:
    lines = [
        f"# {title}",
        "",
        f"- experiment_id: `{summary['experiment_id']}`",
        f"- alias: `{summary['alias']}`",
        f"- output_dir: `{summary['output_dir']}`",
        f"- cases: `{summary['case_count']}`",
        f"- call_plan_rows: `{summary['call_plan_row_count']}`",
        f"- trace_rows: `{summary['trace_row_count']}`",
        f"- candidate_feature_rows: `{summary['candidate_feature_row_count']}`",
        f"- budget_total: `{summary['budget_total']}`",
        "",
        "## Slice Counts",
    ]
    for key, value in sorted((summary.get("slice_counts") or {}).items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Question Sources",
        ]
    )
    for key, value in sorted((summary.get("question_source_counts") or {}).items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Validation",
        ]
    )
    for key, value in (summary.get("validation_counts") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            f"- all_validation_flags_ok: `{summary['all_validation_flags_ok']}`",
            f"- no_api_clients_constructed: `{summary['no_api_clients_constructed']}`",
        ]
    )
    if include_replay:
        lines.extend(
            [
                "",
                "## Branch Families",
            ]
        )
        for key, value in sorted((summary.get("branch_family_counts") or {}).items()):
            lines.append(f"- {key}: `{value}`")
        lines.extend(
            [
                "",
                "## Prompt Templates",
            ]
        )
        for key, value in sorted((summary.get("prompt_template_counts") or {}).items()):
            lines.append(f"- {key}: `{value}`")
        lines.extend(
            [
                "",
                "## Output Files",
            ]
        )
        for item in summary.get("output_files") or []:
            lines.append(f"- `{item}`")
    lines.append("")
    if include_replay:
        lines.append("This is a no-API dry-run. It is trace-compatible with the current structural replay feature layer, but it is not an accuracy claim.")
    else:
        lines.append("This is a no-API preflight. It does not change runtime defaults or call any model API.")
    lines.append("")
    return "\n".join(lines)


def run(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT / "target_staged_pal_frontier_v1_preflight")
    parser.add_argument("--timestamp", type=str, default="")
    parser.add_argument("--case-source", choices=("auto", "synthetic"), default="auto")
    parser.add_argument("--max-cases-per-slice", type=int, default=0)
    args = parser.parse_args(argv)

    manifest = _json_load(args.manifest.resolve())
    validate_manifest(manifest)
    question_bank = _load_question_bank()
    case_rows = _select_case_rows(
        manifest=manifest,
        question_bank=question_bank,
        case_source=args.case_source,
        max_cases_per_slice=args.max_cases_per_slice or None,
    )

    stamp = _stringify(args.timestamp) or _utc_stamp()
    output_dir = args.output_root / f"{EXPERIMENT_ID}_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    call_plan_rows, trace_rows, feature_rows = build_call_plan(manifest=manifest, case_rows=case_rows)
    summary = _summarize_rows(
        manifest=manifest,
        case_rows=case_rows,
        call_plan_rows=call_plan_rows,
        trace_rows=trace_rows,
        feature_rows=feature_rows,
        output_dir=output_dir,
        manifest_path=args.manifest,
    )

    resolved_manifest = dict(manifest)
    resolved_manifest["resolved_timestamp"] = stamp
    resolved_manifest["resolved_output_dir"] = str(output_dir.resolve())
    resolved_manifest["resolved_case_count"] = len(case_rows)
    resolved_manifest["resolved_case_rows"] = case_rows
    resolved_manifest["resolved_call_plan_row_count"] = len(call_plan_rows)
    resolved_manifest["resolved_trace_row_count"] = len(trace_rows)
    resolved_manifest["resolved_candidate_feature_row_count"] = len(feature_rows)
    resolved_manifest["resolved_case_source_mode"] = args.case_source
    resolved_manifest["resolved_max_cases_per_slice"] = args.max_cases_per_slice or 0
    resolved_manifest["resolved_total_action_budget"] = manifest.get("resolved_total_action_budget", DEFAULT_BUDGET)

    _write_jsonl(output_dir / "call_plan.jsonl", call_plan_rows)
    _write_jsonl(output_dir / "traces.jsonl", trace_rows)
    _write_jsonl(output_dir / "candidate_feature_rows.jsonl", feature_rows)
    _write_csv(output_dir / "candidate_feature_rows.csv", feature_rows)
    (output_dir / "manifest.resolved.json").write_text(
        json.dumps(resolved_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "validation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "replay_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "dry_run_report.md").write_text(
        _render_report("Target-Staged PAL Frontier v1 Dry Run", summary, include_replay=False),
        encoding="utf-8",
    )
    (output_dir / "replay_report.md").write_text(
        _render_report("Target-Staged PAL Frontier v1 Replay-Compatible Summary", summary, include_replay=True),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    summary = run()
    print(f"Wrote preflight artifacts to {summary['output_dir']}")


if __name__ == "__main__":
    main()
