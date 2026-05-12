#!/usr/bin/env python3
"""
run_bftc_executable_repair_v1.py

Live runner for bftc_executable_repair_v1.

Parses BFTC+executable-repair JSON responses, evaluates solution_formula
using a safe AST-based evaluator, and uses the executed result as
executable_final_answer when valid. Post-hoc gold scoring via casebook.

Gold is NEVER placed in prompts or provider request fields.

Usage (dry-run):
    python scripts/run_bftc_executable_repair_v1.py \\
        --provider-requests /tmp/bftcx_preflight/provider_requests_dry_run.jsonl \\
        --out-dir /tmp/bftcx_dry_run

Usage (live — requires --allow-api):
    ... same plus --allow-api --casebook <path>
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
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

EXPERIMENT_ID = "bftc_executable_repair_v1"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

_REQUIRED_CANONICAL = [
    "requested_target",
    "source_facts",
    "reverse_derivation",
    "failed_relation",
    "repair_operation",
    "formula_variables",
    "solution_formula",
    "final_answer",
    "confidence",
]

_FIELD_SYNONYMS: dict[str, list[str]] = {
    "requested_target": ["requested_target", "target_identified", "target_quantity", "target"],
    "source_facts": ["source_facts", "key_facts", "given_facts", "facts"],
    "reverse_derivation": ["reverse_derivation", "backward_check_steps", "check_steps", "steps"],
    "failed_relation": ["failed_relation", "failure_relation", "error_relation"],
    "repair_operation": ["repair_operation", "repair", "correction"],
    "formula_variables": ["formula_variables", "variables", "var_map"],
    "solution_formula": ["solution_formula", "formula", "arithmetic_expression"],
    "final_answer": ["final_answer", "repaired_candidate", "answer"],
    "confidence": ["confidence", "confidence_level"],
}

_MAX_FORMULA_LEN = 500
_MAX_EXPONENT = 100
_ALLOWED_CALL_NAMES = {"round"}
_MAX_ROUND_PRECISION = 10

_FORBIDDEN_PROMPT_RE = [
    re.compile(r"\bgold_answer\b\s*[:=]", re.I),
    re.compile(r"\banswer_key\b\s*[:=]", re.I),
    re.compile(r"\bhidden[_ -]?labels?\b\s*[:=]", re.I),
    re.compile(r"\bgold\b\s*[:=]", re.I),
]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_numeric(v: Any) -> float | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _normalize_answer(v: Any) -> str:
    n = _parse_numeric(v)
    if n is None:
        return str(v).strip()
    if n == int(n) and abs(n) < 1e12:
        return str(int(n))
    return str(round(n, 6))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _audit_prompt_for_gold(text: str) -> bool:
    return any(p.search(text) for p in _FORBIDDEN_PROMPT_RE)


# ---------------------------------------------------------------------------
# Safe AST formula evaluator
# ---------------------------------------------------------------------------

_ALLOWED_BINOP = (
    ast.Add, ast.Sub, ast.Mult, ast.Div,
    ast.FloorDiv, ast.Mod, ast.Pow,
)
_ALLOWED_UNARYOP = (ast.USub, ast.UAdd)


class _SafeFormulaError(Exception):
    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message


def _check_node(node: ast.AST, allowed_names: set[str]) -> None:
    """Recursively validate an AST node. Raises _SafeFormulaError on rejection."""
    if isinstance(node, ast.Expression):
        _check_node(node.body, allowed_names)

    elif isinstance(node, ast.BinOp):
        if not isinstance(node.op, _ALLOWED_BINOP):
            raise _SafeFormulaError("unsafe_operator", f"Operator {type(node.op).__name__} not allowed")
        if isinstance(node.op, ast.Pow):
            if isinstance(node.right, ast.Constant):
                if not isinstance(node.right.value, (int, float)):
                    raise _SafeFormulaError("unsafe_exponent", "Exponent must be numeric")
                if abs(node.right.value) > _MAX_EXPONENT:
                    raise _SafeFormulaError("huge_exponent", f"Exponent {node.right.value} > {_MAX_EXPONENT}")
            else:
                raise _SafeFormulaError("unsafe_exponent", "Exponent must be a numeric constant")
        _check_node(node.left, allowed_names)
        _check_node(node.right, allowed_names)

    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _ALLOWED_UNARYOP):
            raise _SafeFormulaError("unsafe_unary_op", f"Unary op {type(node.op).__name__} not allowed")
        _check_node(node.operand, allowed_names)

    elif isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise _SafeFormulaError("string_constant", f"String/non-numeric constant not allowed: {node.value!r}")

    elif isinstance(node, ast.Name):
        if node.id not in allowed_names:
            raise _SafeFormulaError("unknown_variable", f"Variable {node.id!r} not in formula_variables")

    elif isinstance(node, ast.Call):
        # Only allow round(x) or round(x, n)
        if not isinstance(node.func, ast.Name):
            raise _SafeFormulaError("unsafe_call", "Only bare-name calls allowed")
        if node.func.id not in _ALLOWED_CALL_NAMES:
            raise _SafeFormulaError("unsafe_call", f"Call to {node.func.id!r} not allowed")
        if node.keywords:
            raise _SafeFormulaError("unsafe_call", "Keyword arguments in calls not allowed")
        if len(node.args) > 2:
            raise _SafeFormulaError("unsafe_call", "round() takes at most 2 arguments")
        if len(node.args) == 2:
            prec_node = node.args[1]
            if not isinstance(prec_node, ast.Constant) or not isinstance(prec_node.value, int):
                raise _SafeFormulaError("unsafe_call", "round() precision must be a non-negative integer constant")
            if prec_node.value < 0 or prec_node.value > _MAX_ROUND_PRECISION:
                raise _SafeFormulaError("unsafe_call", f"round() precision must be 0–{_MAX_ROUND_PRECISION}")
        for arg in node.args:
            _check_node(arg, allowed_names)

    else:
        raise _SafeFormulaError(
            "unsafe_ast_node",
            f"AST node type {type(node).__name__} not allowed",
        )


def _eval_checked_node(node: ast.AST, bindings: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _eval_checked_node(node.body, bindings)

    if isinstance(node, ast.BinOp):
        left = _eval_checked_node(node.left, bindings)
        right = _eval_checked_node(node.right, bindings)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise _SafeFormulaError("unsafe_operator", f"Operator {type(node.op).__name__} not allowed")

    if isinstance(node, ast.UnaryOp):
        operand = _eval_checked_node(node.operand, bindings)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise _SafeFormulaError("unsafe_unary_op", f"Unary op {type(node.op).__name__} not allowed")

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise _SafeFormulaError("string_constant", f"String/non-numeric constant not allowed: {node.value!r}")
        return float(node.value)

    if isinstance(node, ast.Name):
        if node.id not in bindings:
            raise _SafeFormulaError("unknown_variable", f"Variable {node.id!r} not in formula_variables")
        return bindings[node.id]

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id != "round":
            raise _SafeFormulaError("unsafe_call", "Only round() calls are allowed")
        evaluated_args = [_eval_checked_node(arg, bindings) for arg in node.args]
        if len(evaluated_args) == 1:
            return float(round(evaluated_args[0]))
        if len(evaluated_args) == 2:
            precision = node.args[1]
            if not isinstance(precision, ast.Constant) or not isinstance(precision.value, int):
                raise _SafeFormulaError("unsafe_call", "round() precision must be a non-negative integer constant")
            return float(round(evaluated_args[0], precision.value))
        raise _SafeFormulaError("unsafe_call", "round() takes at most 2 arguments")

    raise _SafeFormulaError("unsafe_ast_node", f"AST node type {type(node).__name__} not allowed")


def _collect_names_in_order(node: ast.AST, names_used: list[str]) -> None:
    if isinstance(node, ast.Name):
        if node.id not in names_used:
            names_used.append(node.id)
        return
    for child in ast.iter_child_nodes(node):
        _collect_names_in_order(child, names_used)


def eval_formula(
    formula: str,
    formula_variables: dict[str, Any],
) -> dict[str, Any]:
    """Safely evaluate a formula string using only allowed AST nodes.

    Args:
        formula: arithmetic expression string
        formula_variables: mapping of variable name → {value, description, unit}

    Returns:
        dict with keys: eval_ok, value, error_type, error_message, names_used
    """
    if not isinstance(formula, str) or not formula.strip():
        return {
            "eval_ok": False, "value": None,
            "error_type": "empty_formula", "error_message": "Formula is empty or not a string",
            "names_used": [],
        }

    if len(formula) > _MAX_FORMULA_LEN:
        return {
            "eval_ok": False, "value": None,
            "error_type": "formula_too_long",
            "error_message": f"Formula length {len(formula)} exceeds {_MAX_FORMULA_LEN}",
            "names_used": [],
        }

    # Extract numeric bindings from formula_variables
    bindings: dict[str, float] = {}
    if isinstance(formula_variables, dict):
        for name, entry in formula_variables.items():
            if isinstance(entry, dict):
                raw = entry.get("value")
            else:
                raw = entry
            n = _parse_numeric(raw)
            if n is not None:
                bindings[name] = n

    allowed_names = set(bindings.keys())

    # Parse
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as exc:
        return {
            "eval_ok": False, "value": None,
            "error_type": "syntax_error", "error_message": str(exc),
            "names_used": [],
        }

    # Collect names used
    names_used: list[str] = []
    _collect_names_in_order(tree, names_used)

    # Validate AST
    try:
        _check_node(tree, allowed_names)
    except _SafeFormulaError as exc:
        return {
            "eval_ok": False, "value": None,
            "error_type": exc.error_type, "error_message": exc.message,
            "names_used": names_used,
        }

    # Execute through manual AST evaluation after validation.
    try:
        result = _eval_checked_node(tree, bindings)
    except ZeroDivisionError:
        return {
            "eval_ok": False, "value": None,
            "error_type": "division_by_zero", "error_message": "Division by zero in formula",
            "names_used": names_used,
        }
    except Exception as exc:
        return {
            "eval_ok": False, "value": None,
            "error_type": "runtime_error", "error_message": str(exc)[:200],
            "names_used": names_used,
        }

    if not isinstance(result, (int, float)) or isinstance(result, bool):
        return {
            "eval_ok": False, "value": None,
            "error_type": "non_numeric_result", "error_message": f"Result type {type(result).__name__} is not numeric",
            "names_used": names_used,
        }

    if not math.isfinite(result):
        return {
            "eval_ok": False, "value": None,
            "error_type": "non_finite_result", "error_message": "Formula produced a non-finite value",
            "names_used": names_used,
        }

    return {
        "eval_ok": True, "value": float(result),
        "error_type": None, "error_message": None,
        "names_used": names_used,
    }


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> tuple[dict | None, str]:
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
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj, "extracted"
        except json.JSONDecodeError:
            pass
    return None, "parse_failed"


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _resolve_field(obj: dict, canonical: str) -> tuple[Any, str | None]:
    for key in _FIELD_SYNONYMS.get(canonical, [canonical]):
        if key in obj:
            return obj[key], key
    return None, None


def parse_bftcx_response(obj: dict) -> dict[str, Any]:
    """Parse and validate a BFTC+executable-repair JSON response."""
    issues: list[str] = []
    resolved: dict[str, Any] = {}

    for canonical in _REQUIRED_CANONICAL:
        val, key = _resolve_field(obj, canonical)
        if val is None:
            issues.append(f"missing_field:{canonical}")
        else:
            resolved[canonical] = val
            if key != canonical:
                issues.append(f"synonym_used:{canonical}={key!r}")

    # final_answer numeric
    fa = resolved.get("final_answer")
    fa_numeric = _parse_numeric(fa)
    if fa is not None and fa_numeric is None:
        issues.append(f"non_numeric_final_answer:{fa!r}")

    # formula_variables shape
    fvars = resolved.get("formula_variables")
    formula_variables_ok = isinstance(fvars, dict) and bool(fvars)
    if not formula_variables_ok and fvars is not None:
        issues.append("formula_variables_not_dict_or_empty")

    # solution_formula: evaluate
    formula_str = resolved.get("solution_formula", "")
    eval_result: dict[str, Any] = {"eval_ok": False, "value": None, "error_type": "no_formula", "error_message": "", "names_used": []}
    formula_matches_model_fa = None

    if formula_str and isinstance(formula_str, str):
        eval_result = eval_formula(formula_str, fvars or {})
        if not eval_result["eval_ok"]:
            issues.append(f"formula_eval_error:{eval_result['error_type']}")
        elif fa_numeric is not None:
            tol = max(abs(fa_numeric) * 1e-6, 1e-9)
            formula_matches_model_fa = abs(eval_result["value"] - fa_numeric) <= tol
            if not formula_matches_model_fa:
                issues.append(
                    f"formula_result_mismatch:eval={eval_result['value']:.6g},model_fa={fa_numeric:.6g}"
                )
    else:
        issues.append("missing_field:solution_formula" if "missing_field:solution_formula" not in issues else "")
        issues = [i for i in issues if i]

    # reverse_derivation: count steps
    steps = resolved.get("reverse_derivation")
    steps_count = 0
    all_consistent = True
    if isinstance(steps, list):
        steps_count = len(steps)
        for step in steps:
            if isinstance(step, dict) and step.get("consistent_with_target") is False:
                all_consistent = False

    # confidence
    confidence = str(resolved.get("confidence", "")).lower().strip()
    if confidence not in ("high", "medium", "low", ""):
        issues.append(f"unexpected_confidence:{confidence!r}")

    schema_hard_failures = [
        i for i in issues
        if (i.startswith("missing_field:") or i.startswith("non_numeric_final_answer"))
    ]

    return {
        "schema_ok": len(schema_hard_failures) == 0,
        "issues": issues,
        "requested_target": str(resolved.get("requested_target", ""))[:300],
        "steps_count": steps_count,
        "all_steps_consistent": all_consistent,
        "formula_variables_ok": formula_variables_ok,
        "solution_formula": str(formula_str)[:500] if formula_str else "",
        "eval_ok": eval_result["eval_ok"],
        "eval_value": eval_result["value"],
        "eval_error_type": eval_result.get("error_type"),
        "names_used": eval_result.get("names_used", []),
        "formula_matches_model_fa": formula_matches_model_fa,
        "fa_numeric": fa_numeric,
        "fa_bare": fa_numeric is not None,
        "confidence": confidence,
        "failed_relation": str(resolved.get("failed_relation", ""))[:200],
        "repair_operation": str(resolved.get("repair_operation", ""))[:200],
    }


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_provider_requests(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_gold_labels(path: Path) -> dict[str, str]:
    gold: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if not cid:
                continue
            val = (
                row.get("gold_answer")
                or row.get("gold")
                or row.get("correct_answer")
                or row.get("structural_best_answer")
                or ""
            )
            gold[cid] = _normalize_answer(val)
    return gold


# ---------------------------------------------------------------------------
# Cohere API
# ---------------------------------------------------------------------------

def _call_cohere(client: Any, model: str, prompt: str, max_tokens: int, temperature: float) -> tuple[str, dict]:
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


# ---------------------------------------------------------------------------
# Per-case processing
# ---------------------------------------------------------------------------

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
    prompt = req.get("prompt_text", "")
    candidate_pool = req.get("candidate_pool", [])
    baseline_answer = str(req.get("baseline_answer", "")).strip()
    gold_absent = req.get("gold_absent")

    result: dict[str, Any] = {
        "call_index": call_index,
        "case_id": case_id,
        "baseline_answer": baseline_answer,
        "candidate_pool": candidate_pool,
        "gold_absent": gold_absent,
        "prompt_text": prompt,
        "prompt_sha256": _sha256(prompt),
        "gold_in_prompt": _audit_prompt_for_gold(prompt),
    }

    if dry_run:
        result.update({
            "call_ok": None,
            "api_call_made": False,
            "raw_response": None,
            "parse_ok": None,
            "schema_ok": None,
            "eval_ok": None,
            "eval_value": None,
            "formula_matches_model_fa": None,
            "executable_final_answer": None,
            "is_new_executable_candidate": None,
            "gold_recovered_model_fa": None,
            "gold_recovered_executable_fa": None,
            "issues": ["dry_run"],
        })
        return result, 0

    # Live call
    result["api_call_made"] = True
    try:
        raw_text, usage = _call_cohere(client, model, prompt, max_tokens, temperature)
        result["raw_response"] = raw_text
        result["usage"] = usage
        result["call_ok"] = True
        result["call_error"] = None
    except Exception as exc:
        result.update({
            "raw_response": "",
            "usage": {},
            "call_ok": False,
            "call_error": f"{type(exc).__name__}: {str(exc)[:200]}",
            "parse_ok": False,
            "schema_ok": False,
            "eval_ok": False,
            "eval_value": None,
            "formula_matches_model_fa": None,
            "executable_final_answer": None,
            "is_new_executable_candidate": False,
            "gold_recovered_model_fa": None,
            "gold_recovered_executable_fa": None,
            "issues": ["call_failed"],
        })
        return result, 1

    # Parse
    obj, parse_method = _extract_json(raw_text)
    result["parse_ok"] = obj is not None
    result["parse_method"] = parse_method

    if obj is None:
        result.update({
            "schema_ok": False,
            "eval_ok": False,
            "eval_value": None,
            "formula_matches_model_fa": None,
            "executable_final_answer": None,
            "is_new_executable_candidate": False,
            "gold_recovered_model_fa": None,
            "gold_recovered_executable_fa": None,
            "issues": [f"json_parse_failed:{parse_method}"],
        })
        return result, 1

    # Validate + eval formula
    val = parse_bftcx_response(obj)
    result.update({
        "schema_ok": val["schema_ok"],
        "issues": val["issues"],
        "requested_target": val["requested_target"],
        "steps_count": val["steps_count"],
        "all_steps_consistent": val["all_steps_consistent"],
        "solution_formula": val["solution_formula"],
        "eval_ok": val["eval_ok"],
        "eval_value": val["eval_value"],
        "eval_error_type": val["eval_error_type"],
        "names_used": val["names_used"],
        "formula_matches_model_fa": val["formula_matches_model_fa"],
        "fa_numeric": val["fa_numeric"],
        "fa_bare": val["fa_bare"],
        "confidence": val["confidence"],
        "failed_relation": val["failed_relation"],
        "repair_operation": val["repair_operation"],
    })

    # Determine executable_final_answer
    exec_fa: float | None = val["eval_value"] if val["eval_ok"] else val["fa_numeric"]
    exec_fa_str = _normalize_answer(exec_fa) if exec_fa is not None else ""
    result["executable_final_answer"] = exec_fa
    result["executable_final_answer_source"] = "eval" if val["eval_ok"] else "model_fa"

    # New candidate check
    pool_norms = {_normalize_answer(a) for a in candidate_pool}
    result["is_new_executable_candidate"] = (
        exec_fa_str not in pool_norms and exec_fa_str not in ("", "NA")
    )
    result["matches_baseline"] = exec_fa_str == _normalize_answer(baseline_answer)

    # Post-hoc gold scoring
    gold_norm = gold_labels.get(case_id, "")
    model_fa_str = _normalize_answer(val["fa_numeric"]) if val["fa_numeric"] is not None else ""
    if gold_norm:
        result["gold_recovered_model_fa"] = model_fa_str == gold_norm and model_fa_str not in ("", "NA")
        result["gold_recovered_executable_fa"] = exec_fa_str == gold_norm and exec_fa_str not in ("", "NA")
    else:
        result["gold_recovered_model_fa"] = None
        result["gold_recovered_executable_fa"] = None

    return result, 1


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _generate_report(
    results: list[dict[str, Any]],
    n_loaded: int,
    calls_attempted: int,
    args: argparse.Namespace,
    dry_run: bool,
) -> str:
    n = len(results)
    mode = "DRY RUN" if dry_run else "LIVE"

    calls_succeeded = sum(1 for r in results if r.get("call_ok") is True)
    parse_ok = sum(1 for r in results if r.get("parse_ok") is True)
    schema_ok = sum(1 for r in results if r.get("schema_ok") is True)
    eval_ok = sum(1 for r in results if r.get("eval_ok") is True)
    formula_mismatch = sum(1 for r in results if r.get("formula_matches_model_fa") is False)
    new_exec = sum(1 for r in results if r.get("is_new_executable_candidate") is True)
    gold_model = sum(1 for r in results if r.get("gold_recovered_model_fa") is True)
    gold_exec = sum(1 for r in results if r.get("gold_recovered_executable_fa") is True)
    gold_scored = sum(1 for r in results if r.get("gold_recovered_executable_fa") is not None)

    issue_counts: Counter = Counter()
    for r in results:
        for issue in r.get("issues", []):
            issue_counts[issue.split(":")[0]] += 1

    lines = [
        f"# BFTC Executable Repair v1 — {mode} Report",
        f"**Timestamp:** {_TS}",
        f"**Experiment:** {EXPERIMENT_ID}",
        f"**Mode:** {mode}",
        f"**Model:** {getattr(args, 'model', 'N/A')}",
        "",
        "## Call Results",
        f"- Cases in provider requests: {n_loaded}",
        f"- Cases processed: {n}",
        f"- Calls attempted: {calls_attempted}",
        f"- Calls succeeded: {calls_succeeded}/{calls_attempted}" if calls_attempted else "- Calls succeeded: 0/0",
        f"- JSON parse ok: {parse_ok}/{n}",
        f"- Schema ok: {schema_ok}/{n}",
        f"- formula eval ok: {eval_ok}/{n}",
        f"- formula result ≠ model final_answer: {formula_mismatch}",
        "",
        "## Answer Quality",
        f"- New executable candidates: {new_exec}/{n}",
        "",
        "## Gold Recovery (post-hoc only)",
        f"- Cases with gold labels: {gold_scored}/{n}",
        f"- Gold recovered by model final_answer: {gold_model}/{gold_scored}" if gold_scored else "- Gold recovery: N/A",
        f"- Gold recovered by executable final_answer: {gold_exec}/{gold_scored}" if gold_scored else "",
        "",
        "## Issue Summary",
        "",
    ]
    for issue, cnt in issue_counts.most_common():
        if not issue.startswith("synonym_used"):
            lines.append(f"- {issue}: {cnt}")

    lines += [
        "",
        "## Safe Claims",
        "- Gold was not included in any prompt or provider request field.",
        "- solution_formula was evaluated using an ast-based safe evaluator (no exec/eval of arbitrary code).",
        "- Schema compliance does not equal accuracy on the underlying math task.",
    ]
    return "\n".join(l for l in lines if l is not None) + "\n"


def _build_raw_response_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "case_id": r["case_id"],
            "call_index": r["call_index"],
            "call_ok": r.get("call_ok"),
            "prompt_text": r.get("prompt_text", ""),
            "prompt_sha256": r.get("prompt_sha256", ""),
            "raw_response": r.get("raw_response"),
            "call_error": r.get("call_error"),
            "usage": r.get("usage", {}),
        }
        for r in results
    ]


def _build_parsed_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "case_id": r["case_id"],
            "call_index": r["call_index"],
            "parse_ok": r.get("parse_ok"),
            "parse_method": r.get("parse_method"),
            "schema_ok": r.get("schema_ok"),
            "eval_ok": r.get("eval_ok"),
            "eval_value": r.get("eval_value"),
            "eval_error_type": r.get("eval_error_type"),
            "solution_formula": r.get("solution_formula", ""),
            "formula_matches_model_fa": r.get("formula_matches_model_fa"),
            "requested_target": r.get("requested_target", ""),
            "steps_count": r.get("steps_count"),
            "all_steps_consistent": r.get("all_steps_consistent"),
            "fa_numeric": r.get("fa_numeric"),
            "confidence": r.get("confidence", ""),
            "issues": r.get("issues", []),
        }
        for r in results
    ]


def _build_executable_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "case_id": r["case_id"],
            "executable_final_answer": r.get("executable_final_answer"),
            "executable_final_answer_source": r.get("executable_final_answer_source"),
            "is_new_executable_candidate": r.get("is_new_executable_candidate"),
            "matches_baseline": r.get("matches_baseline"),
            "gold_recovered_model_fa": r.get("gold_recovered_model_fa"),
            "gold_recovered_executable_fa": r.get("gold_recovered_executable_fa"),
            "formula_matches_model_fa": r.get("formula_matches_model_fa"),
            "candidate_pool": r.get("candidate_pool", []),
            "baseline_answer": r.get("baseline_answer", ""),
            "issues": r.get("issues", []),
        }
        for r in results
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = _parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    dry_run = not args.allow_api

    if not args.provider_requests.exists():
        print(f"ERROR: provider requests not found: {args.provider_requests}", file=sys.stderr)
        sys.exit(1)

    all_reqs = _load_provider_requests(args.provider_requests)
    n_loaded = len(all_reqs)
    all_reqs.sort(key=lambda r: r.get("case_id", ""))
    reqs = all_reqs[: args.limit]

    gold_labels: dict[str, str] = {}
    if args.casebook and args.casebook.exists():
        gold_labels = _load_gold_labels(args.casebook)

    gold_in_any_prompt = any(_audit_prompt_for_gold(r.get("prompt_text", "")) for r in reqs)

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
        _write_jsonl(args.out_dir / "raw_responses.jsonl", _build_raw_response_rows(results))
        _write_jsonl(args.out_dir / "parsed_responses.jsonl", _build_parsed_rows(results))
        _write_jsonl(
            args.out_dir / "executable_candidate_rows.jsonl",
            _build_executable_rows(results),
        )
        report = _generate_report(results, n_loaded, total_api_calls, args, dry_run=True)
        (args.out_dir / "dry_run_report.md").write_text(report, encoding="utf-8")

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

        results: list[dict[str, Any]] = []
        total_api_calls = 0
        consecutive_auth_errors = 0

        for idx, req in enumerate(reqs, start=1):
            case_id = req.get("case_id", "")
            print(f"  [{idx}/{len(reqs)}] {case_id} ...", end=" ", flush=True)
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

            if result.get("call_ok"):
                consecutive_auth_errors = 0
                exec_fa = result.get("executable_final_answer")
                eval_ok = result.get("eval_ok")
                new = result.get("is_new_executable_candidate")
                print(f"ok | eval_ok={eval_ok} exec_fa={exec_fa} new={new}", flush=True)
            else:
                err = result.get("call_error", "")
                print(f"FAIL: {err[:80]}", flush=True)
                if "401" in err or "AuthenticationError" in err or "Unauthorized" in err:
                    consecutive_auth_errors += 1
                    if consecutive_auth_errors >= 2:
                        print("ERROR: consecutive auth failures — stopping.", file=sys.stderr)
                        break

            if idx < len(reqs):
                time.sleep(0.5)

        _write_jsonl(args.out_dir / "raw_responses.jsonl", _build_raw_response_rows(results))
        _write_jsonl(args.out_dir / "parsed_responses.jsonl", _build_parsed_rows(results))
        _write_jsonl(
            args.out_dir / "executable_candidate_rows.jsonl",
            _build_executable_rows(results),
        )
        report = _generate_report(results, n_loaded, total_api_calls, args, dry_run=False)
        (args.out_dir / "live_report.md").write_text(report, encoding="utf-8")

    # Summary
    n = len(results)
    issue_counts_all: Counter = Counter()
    for r in results:
        for issue in r.get("issues", []):
            issue_counts_all[issue.split(":")[0]] += 1
    issue_summary = dict(sorted(issue_counts_all.items()))

    summary: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": _TS,
        "mode": "dry_run" if dry_run else "live",
        "model": args.model,
        "provider": "cohere",
        "provider_requests_input": str(args.provider_requests),
        "casebook_input": str(args.casebook) if args.casebook is not None else None,
        "cases_in_requests": n_loaded,
        "cases_attempted": n,
        "api_calls_made": total_api_calls,
        "calls_attempted": total_api_calls,
        "calls_succeeded": sum(1 for r in results if r.get("call_ok") is True),
        "calls_ok": sum(1 for r in results if r.get("call_ok") is True),
        "json_parse_ok_count": sum(1 for r in results if r.get("parse_ok") is True),
        "schema_ok_count": sum(1 for r in results if r.get("schema_ok") is True),
        "formula_present_count": sum(1 for r in results if r.get("solution_formula")),
        "formula_eval_ok_count": sum(1 for r in results if r.get("eval_ok") is True),
        "formula_eval_error_count": sum(1 for r in results if r.get("eval_ok") is False and r.get("parse_ok") is True),
        "formula_matches_model_final_answer_count": sum(1 for r in results if r.get("formula_matches_model_fa") is True),
        "executable_final_answer_count": sum(1 for r in results if r.get("executable_final_answer") is not None),
        "gold_recovered_by_model_final_answer_count": sum(1 for r in results if r.get("gold_recovered_model_fa") is True),
        "gold_recovered_by_executable_final_answer_count": sum(1 for r in results if r.get("gold_recovered_executable_fa") is True),
        "gold_labels_available": len(gold_labels),
        "gold_in_any_prompt": gold_in_any_prompt,
        "call_failed": issue_counts_all.get("call_failed", 0),
        "invalid_json": issue_counts_all.get("json_parse_failed", 0),
        "issue_summary": issue_summary,
        "out_dir": str(args.out_dir),
        "outputs": [
            "manifest.json", "raw_responses.jsonl", "parsed_responses.jsonl",
            "executable_candidate_rows.jsonl", "pilot_summary.json",
            "dry_run_report.md" if dry_run else "live_report.md",
        ],
    }
    _write_json(args.out_dir / "pilot_summary.json", summary)
    _write_json(args.out_dir / "manifest.json", summary)

    print(
        f"\nBFTC executable repair {'dry-run' if dry_run else 'live'} complete."
        f" {n} cases. Output: {args.out_dir}",
        flush=True,
    )
    return summary


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BFTC executable repair v1 runner.")
    p.add_argument("--provider-requests", required=True, type=Path)
    p.add_argument("--casebook", type=Path, default=None)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--max-tokens", type=int, default=2048)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--allow-api", action="store_true")
    return p.parse_args(argv)


if __name__ == "__main__":
    main()
