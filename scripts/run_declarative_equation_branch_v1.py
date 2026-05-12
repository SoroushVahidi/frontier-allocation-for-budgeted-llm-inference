#!/usr/bin/env python3
"""
Runner for declarative_equation_branch_v1.

Dry-run is default. Live mode requires --allow-api.
Gold labels are used only post-hoc when a casebook is supplied.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_bftc_executable_repair_v1 import eval_formula

EXPERIMENT_ID = "declarative_equation_branch_v1"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

_REQUIRED_FIELDS = [
    "requested_target",
    "target_variable",
    "target_unit",
    "process_state",
    "source_facts",
    "variables",
    "relations",
    "equations",
    "equation_rationale",
    "solve_for",
    "solution_formula",
    "final_answer",
    "uncertainty",
    "abstain_reason",
]
_FORBIDDEN_PROMPT_RE = [
    re.compile(r"\bgold_answer\b\s*[:=]", re.I),
    re.compile(r"\banswer_key\b\s*[:=]", re.I),
    re.compile(r"\bhidden[_ -]?labels?\b\s*[:=]", re.I),
    re.compile(r"\bgold\b\s*[:=]", re.I),
]
_IDENT_RE = re.compile(r"\b[a-z_][a-z0-9_]*\b")
_RESERVED_NAMES = {"round", "true", "false", "null"}
_ALLOWED_PROCESS_STATES = {"before", "after", "final", "original", "unknown"}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _parse_numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _normalize_answer(value: Any) -> str:
    number = _parse_numeric(value)
    if number is None:
        return str(value).strip()
    if abs(number - round(number)) <= 1e-9 and abs(number) < 1e12:
        return str(int(round(number)))
    return str(round(number, 6))


def _audit_prompt_for_gold(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _FORBIDDEN_PROMPT_RE)


def _extract_json(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text:
        return None, "empty_response"
    stripped = text.strip()
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj, "direct"
    except json.JSONDecodeError:
        pass
    fence = re.sub(r"```(?:json)?\s*", "", stripped)
    fence = re.sub(r"```\s*$", "", fence).strip()
    try:
        obj = json.loads(fence)
        if isinstance(obj, dict):
            return obj, "fence_stripped"
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj, "extracted"
        except json.JSONDecodeError:
            pass
    return None, "parse_failed"


def _load_provider_requests(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_gold_labels(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            case_id = str(row.get("case_id", "")).strip()
            if not case_id:
                continue
            value = row.get("gold_answer") or row.get("gold") or row.get("correct_answer") or row.get("structural_best_answer") or ""
            out[case_id] = _normalize_answer(value)
    return out


def _extract_identifiers(text: str) -> list[str]:
    seen: list[str] = []
    for name in _IDENT_RE.findall(text or ""):
        if name in _RESERVED_NAMES:
            continue
        if name not in seen:
            seen.append(name)
    return seen


def _variables_to_bindings(variables: Any) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    bindings: dict[str, dict[str, Any]] = {}
    duplicate_names: list[str] = []
    malformed_rows: list[str] = []
    if not isinstance(variables, list):
        return bindings, duplicate_names, ["variables_not_list"]
    for idx, row in enumerate(variables, start=1):
        if not isinstance(row, dict):
            malformed_rows.append(f"malformed_variable_row:{idx}")
            continue
        name = str(row.get("name", "")).strip()
        if not name:
            malformed_rows.append(f"missing_variable_name:{idx}")
            continue
        if name in bindings:
            duplicate_names.append(name)
        bindings[name] = {
            "value": row.get("value"),
            "description": str(row.get("description", "")),
            "unit": str(row.get("unit", "")),
        }
    return bindings, duplicate_names, malformed_rows


def _collect_unknown_names(items: Any, declared_names: set[str]) -> tuple[bool, list[str], list[str]]:
    present = isinstance(items, list) and any(str(item).strip() for item in items or [])
    strings = [str(item).strip() for item in items] if isinstance(items, list) else []
    unknown: list[str] = []
    for item in strings:
        for name in _extract_identifiers(item):
            if name not in declared_names and name not in unknown:
                unknown.append(name)
    return present, strings, unknown


def parse_declarative_response(obj: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    resolved: dict[str, Any] = {}

    for field in _REQUIRED_FIELDS:
        if field not in obj:
            issues.append(f"missing_field:{field}")
        else:
            resolved[field] = obj.get(field)

    requested_target = str(resolved.get("requested_target", "")).strip()[:300]
    target_variable = str(resolved.get("target_variable", "")).strip()
    solve_for = str(resolved.get("solve_for", "")).strip()
    target_unit = str(resolved.get("target_unit", "")).strip()
    process_state = str(resolved.get("process_state", "")).strip().lower()
    abstain_reason = str(resolved.get("abstain_reason", "") or "").strip()
    uncertainty = resolved.get("uncertainty")

    bindings, duplicate_names, malformed_variable_rows = _variables_to_bindings(resolved.get("variables"))
    declared_names = set(bindings.keys())
    for name in duplicate_names:
        issues.append(f"duplicate_variable_name:{name}")
    issues.extend(malformed_variable_rows)

    target_match = bool(target_variable) and target_variable == solve_for
    if not target_match:
        issues.append("target_variable_solve_for_mismatch")

    if process_state not in _ALLOWED_PROCESS_STATES:
        issues.append(f"invalid_process_state:{process_state}")

    if not isinstance(uncertainty, bool):
        issues.append("uncertainty_not_bool")

    relations_present, relation_strings, unknown_relation_vars = _collect_unknown_names(
        resolved.get("relations"),
        declared_names,
    )
    if not relations_present:
        issues.append("relations_missing_or_empty")
    for item in relation_strings:
        if "=" not in item and ":" not in item:
            issues.append("relation_missing_structure")
            break
    for name in unknown_relation_vars:
        issues.append(f"unknown_relation_variable:{name}")

    equation_present, equation_strings, unknown_equation_vars = _collect_unknown_names(
        resolved.get("equations"),
        declared_names,
    )
    if not equation_present:
        issues.append("equations_missing_or_empty")
    for item in equation_strings:
        if "=" not in item:
            issues.append("equation_missing_equals")
            break
    for name in unknown_equation_vars:
        issues.append(f"unknown_equation_variable:{name}")

    solution_formula = str(resolved.get("solution_formula", "") or "")
    if not solution_formula.strip():
        issues.append("empty_solution_formula")
    formula_eval = eval_formula(solution_formula, bindings if bindings else {})
    if solution_formula.strip() and not formula_eval["eval_ok"]:
        issues.append(f"formula_eval_error:{formula_eval['error_type']}")

    final_answer_raw = resolved.get("final_answer")
    final_answer_numeric = _parse_numeric(final_answer_raw)
    if final_answer_raw is not None and final_answer_numeric is None:
        issues.append(f"non_numeric_final_answer:{final_answer_raw!r}")
    if final_answer_raw is None and not bool(uncertainty) and not abstain_reason:
        issues.append("missing_numeric_final_answer_without_abstain")

    if bool(uncertainty) and not abstain_reason:
        issues.append("uncertain_without_abstain_reason")

    formula_matches_final_answer: bool | None = None
    if formula_eval["eval_ok"] and final_answer_numeric is not None:
        tolerance = max(abs(final_answer_numeric) * 1e-6, 1e-9)
        formula_matches_final_answer = abs(formula_eval["value"] - final_answer_numeric) <= tolerance
        if not formula_matches_final_answer:
            issues.append(
                f"final_answer_formula_mismatch:eval={formula_eval['value']:.6g},final={final_answer_numeric:.6g}"
            )

    hard_issue_prefixes = (
        "missing_field:",
        "variables_not_list",
        "malformed_variable_row:",
        "missing_variable_name:",
        "target_variable_solve_for_mismatch",
        "invalid_process_state:",
        "uncertainty_not_bool",
        "relations_missing_or_empty",
        "relation_missing_structure",
        "unknown_relation_variable:",
        "equations_missing_or_empty",
        "equation_missing_equals",
        "unknown_equation_variable:",
        "formula_eval_error:",
        "empty_solution_formula",
        "missing_numeric_final_answer_without_abstain",
    )
    schema_ok = not any(issue.startswith(hard_issue_prefixes) for issue in issues)

    return {
        "schema_ok": schema_ok,
        "issues": issues,
        "requested_target": requested_target,
        "target_variable": target_variable,
        "target_unit": target_unit,
        "solve_for": solve_for,
        "process_state": process_state,
        "uncertainty": bool(uncertainty) if isinstance(uncertainty, bool) else None,
        "abstain_reason": abstain_reason[:300],
        "target_variable_solve_for_match": target_match,
        "relation_present": relations_present,
        "relation_count": len(relation_strings),
        "relation_names": [name for item in relation_strings for name in _extract_identifiers(item)],
        "unknown_relation_vars": unknown_relation_vars,
        "equation_present": equation_present,
        "equation_count": len(equation_strings),
        "equation_names": [name for item in equation_strings for name in _extract_identifiers(item)],
        "unknown_equation_vars": unknown_equation_vars,
        "solution_formula": solution_formula[:500],
        "formula_eval_ok": formula_eval["eval_ok"],
        "formula_eval_value": formula_eval["value"],
        "formula_eval_error_type": formula_eval.get("error_type"),
        "formula_names_used": formula_eval.get("names_used", []),
        "formula_matches_final_answer": formula_matches_final_answer,
        "final_answer_numeric": final_answer_numeric,
        "final_answer_extracted": final_answer_numeric is not None,
    }


def _call_cohere(client: Any, model: str, prompt: str, max_tokens: int, temperature: float) -> tuple[str, dict[str, Any]]:
    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
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


def _process_case(
    *,
    req: dict[str, Any],
    gold_labels: dict[str, str],
    client: Any | None,
    model: str,
    max_tokens: int,
    temperature: float,
    call_index: int,
    dry_run: bool,
) -> tuple[dict[str, Any], int]:
    case_id = req.get("case_id", "")
    prompt_text = req.get("prompt_text", "")
    candidate_pool = req.get("candidate_pool", [])
    baseline_answer = str(req.get("baseline_answer", "")).strip()

    result: dict[str, Any] = {
        "call_index": call_index,
        "case_id": case_id,
        "baseline_answer": baseline_answer,
        "candidate_pool": candidate_pool,
        "prompt_text": prompt_text,
        "prompt_sha256": _sha256(prompt_text),
        "gold_in_prompt": _audit_prompt_for_gold(prompt_text),
    }

    if dry_run:
        result.update(
            {
                "call_ok": None,
                "api_call_made": False,
                "raw_response": None,
                "parse_ok": None,
                "schema_ok": None,
                "relation_present": None,
                "equation_present": None,
                "formula_eval_ok": None,
                "target_variable_solve_for_match": None,
                "final_answer_extracted": None,
                "executable_final_answer": None,
                "gold_recovered_final_answer": None,
                "gold_recovered_executable_answer": None,
                "issues": ["dry_run"],
            }
        )
        return result, 0

    result["api_call_made"] = True
    try:
        raw_text, usage = _call_cohere(client, model, prompt_text, max_tokens, temperature)
        result["raw_response"] = raw_text
        result["usage"] = usage
        result["call_ok"] = True
        result["call_error"] = None
    except Exception as exc:
        result.update(
            {
                "raw_response": "",
                "usage": {},
                "call_ok": False,
                "call_error": f"{type(exc).__name__}: {str(exc)[:200]}",
                "parse_ok": False,
                "schema_ok": False,
                "relation_present": False,
                "equation_present": False,
                "formula_eval_ok": False,
                "target_variable_solve_for_match": False,
                "final_answer_extracted": False,
                "executable_final_answer": None,
                "gold_recovered_final_answer": None,
                "gold_recovered_executable_answer": None,
                "issues": ["call_failed"],
            }
        )
        return result, 1

    obj, parse_method = _extract_json(result["raw_response"])
    result["parse_ok"] = obj is not None
    result["parse_method"] = parse_method
    if obj is None:
        result.update(
            {
                "schema_ok": False,
                "relation_present": False,
                "equation_present": False,
                "formula_eval_ok": False,
                "target_variable_solve_for_match": False,
                "final_answer_extracted": False,
                "executable_final_answer": None,
                "gold_recovered_final_answer": None,
                "gold_recovered_executable_answer": None,
                "issues": [f"json_parse_failed:{parse_method}"],
            }
        )
        return result, 1

    parsed = parse_declarative_response(obj)
    result.update(
        {
            "schema_ok": parsed["schema_ok"],
            "issues": parsed["issues"],
            "requested_target": parsed["requested_target"],
            "target_variable": parsed["target_variable"],
            "target_unit": parsed["target_unit"],
            "solve_for": parsed["solve_for"],
            "process_state": parsed["process_state"],
            "uncertainty": parsed["uncertainty"],
            "abstain_reason": parsed["abstain_reason"],
            "target_variable_solve_for_match": parsed["target_variable_solve_for_match"],
            "relation_present": parsed["relation_present"],
            "relation_count": parsed["relation_count"],
            "relation_names": parsed["relation_names"],
            "unknown_relation_vars": parsed["unknown_relation_vars"],
            "equation_present": parsed["equation_present"],
            "equation_count": parsed["equation_count"],
            "equation_names": parsed["equation_names"],
            "unknown_equation_vars": parsed["unknown_equation_vars"],
            "solution_formula": parsed["solution_formula"],
            "formula_eval_ok": parsed["formula_eval_ok"],
            "formula_eval_value": parsed["formula_eval_value"],
            "formula_eval_error_type": parsed["formula_eval_error_type"],
            "formula_names_used": parsed["formula_names_used"],
            "formula_matches_final_answer": parsed["formula_matches_final_answer"],
            "final_answer_numeric": parsed["final_answer_numeric"],
            "final_answer_extracted": parsed["final_answer_extracted"],
        }
    )

    executable_final = parsed["formula_eval_value"] if parsed["formula_eval_ok"] else parsed["final_answer_numeric"]
    result["executable_final_answer"] = executable_final
    result["executable_final_answer_source"] = "eval" if parsed["formula_eval_ok"] else "model_final_answer"
    executable_norm = _normalize_answer(executable_final) if executable_final is not None else ""
    candidate_pool_norms = {_normalize_answer(value) for value in candidate_pool}
    result["is_new_declarative_candidate"] = executable_norm not in candidate_pool_norms and executable_norm not in {"", "NA"}
    result["matches_baseline"] = executable_norm == _normalize_answer(baseline_answer)

    gold_norm = gold_labels.get(case_id, "")
    final_norm = _normalize_answer(parsed["final_answer_numeric"]) if parsed["final_answer_numeric"] is not None else ""
    if gold_norm:
        result["gold_recovered_final_answer"] = final_norm == gold_norm and final_norm not in {"", "NA"}
        result["gold_recovered_executable_answer"] = executable_norm == gold_norm and executable_norm not in {"", "NA"}
    else:
        result["gold_recovered_final_answer"] = None
        result["gold_recovered_executable_answer"] = None

    return result, 1


def _generate_report(results: list[dict[str, Any]], n_loaded: int, calls_attempted: int, args: argparse.Namespace, dry_run: bool) -> str:
    mode = "DRY RUN" if dry_run else "LIVE"
    n = len(results)
    issue_counts: Counter[str] = Counter()
    for row in results:
        for issue in row.get("issues", []):
            issue_counts[issue.split(":")[0]] += 1
    lines = [
        f"# Declarative Equation Branch v1 — {mode} Report",
        f"**Timestamp:** {_TS}",
        f"**Experiment:** {EXPERIMENT_ID}",
        f"**Mode:** {mode}",
        f"**Model:** {getattr(args, 'model', 'N/A')}",
        "",
        "## Call Results",
        f"- Cases in provider requests: {n_loaded}",
        f"- Cases processed: {n}",
        f"- Calls attempted: {calls_attempted}",
        f"- Calls succeeded: {sum(1 for row in results if row.get('call_ok') is True)}/{calls_attempted}" if calls_attempted else "- Calls succeeded: 0/0",
        f"- JSON parse ok: {sum(1 for row in results if row.get('parse_ok') is True)}/{n}",
        f"- Schema ok: {sum(1 for row in results if row.get('schema_ok') is True)}/{n}",
        f"- relations present: {sum(1 for row in results if row.get('relation_present') is True)}/{n}",
        f"- equations present: {sum(1 for row in results if row.get('equation_present') is True)}/{n}",
        f"- target_variable == solve_for: {sum(1 for row in results if row.get('target_variable_solve_for_match') is True)}/{n}",
        f"- formula eval ok: {sum(1 for row in results if row.get('formula_eval_ok') is True)}/{n}",
        "",
        "## Candidate Quality",
        f"- final_answer extracted: {sum(1 for row in results if row.get('final_answer_extracted') is True)}/{n}",
        f"- executable final_answer available: {sum(1 for row in results if row.get('executable_final_answer') is not None)}/{n}",
        f"- new executable candidates: {sum(1 for row in results if row.get('is_new_declarative_candidate') is True)}/{n}",
        "",
        "## Gold Recovery (post-hoc only)",
        f"- Gold recovered by model final_answer: {sum(1 for row in results if row.get('gold_recovered_final_answer') is True)}",
        f"- Gold recovered by executable answer: {sum(1 for row in results if row.get('gold_recovered_executable_answer') is True)}",
        "",
        "## Issue Summary",
    ]
    for issue, count in issue_counts.most_common():
        lines.append(f"- {issue}: {count}")
    lines += [
        "",
        "## Safe Claims",
        "- Gold was not included in prompts or provider requests.",
        "- solution_formula evaluation uses the existing AST-validated evaluator.",
        "- Schema-valid structure is not evidence of task correctness by itself.",
    ]
    return "\n".join(lines) + "\n"


def _build_raw_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "case_id": row["case_id"],
            "call_index": row["call_index"],
            "call_ok": row.get("call_ok"),
            "prompt_text": row.get("prompt_text", ""),
            "prompt_sha256": row.get("prompt_sha256", ""),
            "raw_response": row.get("raw_response"),
            "call_error": row.get("call_error"),
            "usage": row.get("usage", {}),
        }
        for row in results
    ]


def _build_parsed_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "case_id": row["case_id"],
            "call_index": row["call_index"],
            "parse_ok": row.get("parse_ok"),
            "parse_method": row.get("parse_method"),
            "schema_ok": row.get("schema_ok"),
            "requested_target": row.get("requested_target", ""),
            "target_variable": row.get("target_variable", ""),
            "target_unit": row.get("target_unit", ""),
            "process_state": row.get("process_state", ""),
            "solve_for": row.get("solve_for", ""),
            "uncertainty": row.get("uncertainty"),
            "relation_present": row.get("relation_present"),
            "relation_count": row.get("relation_count"),
            "unknown_relation_vars": row.get("unknown_relation_vars", []),
            "equation_present": row.get("equation_present"),
            "equation_count": row.get("equation_count"),
            "unknown_equation_vars": row.get("unknown_equation_vars", []),
            "target_variable_solve_for_match": row.get("target_variable_solve_for_match"),
            "solution_formula": row.get("solution_formula", ""),
            "formula_eval_ok": row.get("formula_eval_ok"),
            "formula_eval_value": row.get("formula_eval_value"),
            "formula_eval_error_type": row.get("formula_eval_error_type"),
            "final_answer_numeric": row.get("final_answer_numeric"),
            "formula_matches_final_answer": row.get("formula_matches_final_answer"),
            "abstain_reason": row.get("abstain_reason", ""),
            "issues": row.get("issues", []),
        }
        for row in results
    ]


def _build_candidate_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "case_id": row["case_id"],
            "final_answer_numeric": row.get("final_answer_numeric"),
            "executable_final_answer": row.get("executable_final_answer"),
            "executable_final_answer_source": row.get("executable_final_answer_source"),
            "is_new_declarative_candidate": row.get("is_new_declarative_candidate"),
            "matches_baseline": row.get("matches_baseline"),
            "gold_recovered_final_answer": row.get("gold_recovered_final_answer"),
            "gold_recovered_executable_answer": row.get("gold_recovered_executable_answer"),
            "candidate_pool": row.get("candidate_pool", []),
            "issues": row.get("issues", []),
        }
        for row in results
    ]


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = _parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    dry_run = not args.allow_api

    if not args.provider_requests.is_file():
        print(f"ERROR: provider requests not found: {args.provider_requests}", file=sys.stderr)
        sys.exit(1)

    reqs = _load_provider_requests(args.provider_requests)
    n_loaded = len(reqs)
    reqs.sort(key=lambda row: row.get("case_id", ""))
    reqs = reqs[: args.limit]

    gold_labels: dict[str, str] = {}
    if args.casebook and args.casebook.exists():
        gold_labels = _load_gold_labels(args.casebook)

    gold_in_any_prompt = any(_audit_prompt_for_gold(row.get("prompt_text", "")) for row in reqs)

    if dry_run:
        results = [
            _process_case(
                req=req,
                gold_labels={},
                client=None,
                model=args.model,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                call_index=idx,
                dry_run=True,
            )[0]
            for idx, req in enumerate(reqs, start=1)
        ]
        total_api_calls = 0
        report_name = "dry_run_report.md"
    else:
        api_key = os.environ.get("COHERE_API_KEY", "")
        if not api_key:
            print("ERROR: COHERE_API_KEY not set.", file=sys.stderr)
            sys.exit(1)
        try:
            import cohere  # type: ignore[import]
        except ImportError:
            print("ERROR: cohere SDK not installed.", file=sys.stderr)
            sys.exit(1)
        client = cohere.ClientV2(api_key=api_key)
        results = []
        total_api_calls = 0
        for idx, req in enumerate(reqs, start=1):
            result, n_calls = _process_case(
                req=req,
                gold_labels=gold_labels,
                client=client,
                model=args.model,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                call_index=idx,
                dry_run=False,
            )
            results.append(result)
            total_api_calls += n_calls
            if idx < len(reqs):
                time.sleep(0.5)
        report_name = "live_report.md"

    _write_jsonl(args.out_dir / "raw_responses.jsonl", _build_raw_rows(results))
    _write_jsonl(args.out_dir / "parsed_responses.jsonl", _build_parsed_rows(results))
    _write_jsonl(args.out_dir / "declarative_candidate_rows.jsonl", _build_candidate_rows(results))
    (args.out_dir / report_name).write_text(_generate_report(results, n_loaded, total_api_calls, args, dry_run), encoding="utf-8")

    issue_counts: Counter[str] = Counter()
    for row in results:
        for issue in row.get("issues", []):
            issue_counts[issue.split(":")[0]] += 1

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": _TS,
        "mode": "dry_run" if dry_run else "live",
        "model": args.model,
        "provider": "cohere",
        "provider_requests_input": str(args.provider_requests),
        "casebook_input": str(args.casebook) if args.casebook is not None else None,
        "cases_in_requests": n_loaded,
        "cases_attempted": len(results),
        "api_calls_made": total_api_calls,
        "calls_attempted": total_api_calls,
        "calls_succeeded": sum(1 for row in results if row.get("call_ok") is True),
        "json_parse_ok_count": sum(1 for row in results if row.get("parse_ok") is True),
        "schema_ok_count": sum(1 for row in results if row.get("schema_ok") is True),
        "relation_present_count": sum(1 for row in results if row.get("relation_present") is True),
        "equation_present_count": sum(1 for row in results if row.get("equation_present") is True),
        "target_solve_for_match_count": sum(1 for row in results if row.get("target_variable_solve_for_match") is True),
        "target_variable_solve_for_match_count": sum(1 for row in results if row.get("target_variable_solve_for_match") is True),
        "formula_eval_ok_count": sum(1 for row in results if row.get("formula_eval_ok") is True),
        "final_answer_extracted_count": sum(1 for row in results if row.get("final_answer_extracted") is True),
        "executable_final_answer_count": sum(1 for row in results if row.get("executable_final_answer") is not None),
        "gold_recovered_by_final_answer_count": sum(1 for row in results if row.get("gold_recovered_final_answer") is True),
        "gold_recovered_by_executable_answer_count": sum(1 for row in results if row.get("gold_recovered_executable_answer") is True),
        "gold_labels_available": len(gold_labels),
        "gold_in_any_prompt": gold_in_any_prompt,
        "issue_summary": dict(sorted(issue_counts.items())),
        "out_dir": str(args.out_dir),
        "outputs": [
            "manifest.json",
            "raw_responses.jsonl",
            "parsed_responses.jsonl",
            "declarative_candidate_rows.jsonl",
            "pilot_summary.json",
            report_name,
        ],
    }
    _write_json(args.out_dir / "pilot_summary.json", summary)
    _write_json(args.out_dir / "manifest.json", summary)
    print(f"Declarative equation branch run complete. {len(results)} cases. Output: {args.out_dir}", flush=True)
    return summary


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runner for declarative_equation_branch_v1.")
    parser.add_argument("--provider-requests", required=True, type=Path)
    parser.add_argument("--casebook", type=Path, default=None)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--model", default="command-r-plus-08-2024")
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--allow-api", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    main()
