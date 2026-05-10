#!/usr/bin/env python3
"""Offline PAL Python code static audit (no API, no controllers, no selection wiring)."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]

PAL_JSONL_NAMES = (
    "all_results.jsonl",
    "results.jsonl",
    "pal_results.jsonl",
    "per_example_records.jsonl",
)

COHORT_GOLD_ABSENT = "gold_absent_discovery"
COHORT_PN = "present_not_selected"
COHORT_GUARDRAIL = "pal_correct_guardrail"
COHORT_PAL_WRONG = "pal_wrong_other"
COHORT_PILOT_B = "pilot_track_b"
COHORT_UNKNOWN = "unknown"

LABELED_COHORTS = frozenset(
    {
        COHORT_GOLD_ABSENT,
        COHORT_PN,
        COHORT_GUARDRAIL,
        COHORT_PAL_WRONG,
        COHORT_PILOT_B,
    }
)

PROMISING_TRIGGER_GROUP = (
    "temporal_no_state_no_sub",
    "rate_no_muldiv",
    "many_unused_final_sparse",
)

from experiments.gsm8k_structural_validate import (
    _exec_ok_from_metadata,
    _normalize_numeric_string,
    _normalized_value_in_haystack,
    _required_operation_cues,
    _salient_problem_norms,
    validate_gsm8k_candidate,
)
from experiments.output_layer_repair import canonicalize_answer

from scripts.evaluate_gsm8k_structural_validator import (
    PAL_METHOD,
    guardrail_case_ids,
    load_csv_rows,
    load_failure_cluster_map,
    load_pal_all_results,
    load_selected_failures,
)

DATASET = "openai/gsm8k"
DEFAULT_BUNDLE = (
    REPO_ROOT / "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z"
)
DEFAULT_OUT = REPO_ROOT / "outputs/gsm8k_structural_validator_eval_20260507"

STATE_NAME_RE = re.compile(
    r"\b(initial|before|after|remaining|left|final|total|start|end|prev|next)\b", re.I
)
RATE_NAME_RE = re.compile(
    r"\b(rate|each|per|speed|price|cost_per|mph|daily|weekly|hourly)\b", re.I
)


def _syntax_ok(code: str) -> bool:
    if not str(code).strip():
        return False
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _extract_pal_code_stdout(
    pal_row: dict[str, Any] | None,
    sf_row: dict[str, Any] | None,
) -> tuple[str, str, dict[str, Any]]:
    """Return (code, stdout_sanitized, pal_execution dict)."""
    px: dict[str, Any] = {}
    code = ""
    if pal_row:
        px = dict(pal_row.get("pal_execution") or {})
        code = str(px.get("pal_code") or "").strip()
    if sf_row:
        mr = sf_row.get("method_records") or {}
        if isinstance(mr, dict):
            pal_mr = mr.get(PAL_METHOD)
            if isinstance(pal_mr, dict):
                pe = pal_mr.get("pal_execution")
                if isinstance(pe, dict):
                    if not code:
                        code = str(pe.get("pal_code") or "").strip()
                    px = pe or px
    er = px.get("pal_execution_result") if isinstance(px.get("pal_execution_result"), dict) else {}
    stdout = str(er.get("pal_stdout") or "")[:4000]
    return code, stdout, px


def _collect_literals_and_ops(tree: ast.AST) -> tuple[set[str], Counter[str], int, int]:
    """Normalized numeric literal strings; op counts; subt/subtraction count; muldiv count."""
    literals: set[str] = set()
    ops: Counter[str] = Counter()
    sub_count = 0
    muldiv_count = 0

    class V(ast.NodeVisitor):
        def visit_Constant(self, node: ast.Constant) -> None:
            if isinstance(node.value, (int, float)):
                n = _normalize_numeric_string(str(node.value))
                if n:
                    literals.add(n)
            self.generic_visit(node)

        def visit_BinOp(self, node: ast.BinOp) -> None:
            nonlocal sub_count, muldiv_count
            if isinstance(node.op, ast.Sub):
                sub_count += 1
                ops["-"] += 1
            elif isinstance(node.op, ast.Add):
                ops["+"] += 1
            elif isinstance(node.op, ast.Mult):
                muldiv_count += 1
                ops["*"] += 1
            elif isinstance(node.op, ast.Div):
                muldiv_count += 1
                ops["/"] += 1
            elif isinstance(node.op, ast.FloorDiv):
                muldiv_count += 1
                ops["//"] += 1
            elif isinstance(node.op, ast.Mod):
                ops["%"] += 1
            self.generic_visit(node)

        def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
            if isinstance(node.op, ast.USub):
                ops["usub"] += 1
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Name) and node.func.id == "sum":
                ops["sum()"] += 1
            self.generic_visit(node)

    V().visit(tree)
    return literals, ops, sub_count, muldiv_count


def _collect_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()

    class N(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            names.add(node.id)
            self.generic_visit(node)

    N().visit(tree)
    return names


def _final_print_or_answer_expr(code: str) -> tuple[str, str]:
    """Heuristic: last print(...) call source slice or last assignment to answer.*"""
    if not _syntax_ok(code):
        return "", ""
    tree = ast.parse(code)
    last_snip = ""
    final_expr_kind = ""
    for stmt in reversed(tree.body):
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            fn = stmt.value.func
            if isinstance(fn, ast.Name) and fn.id == "print":
                try:
                    seg = ast.get_source_segment(code, stmt.value) or ""
                    last_snip = seg[:500]
                    final_expr_kind = "print"
                    break
                except Exception:
                    pass
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id == "answer":
                    try:
                        seg = ast.get_source_segment(code, stmt.value) or ""
                        last_snip = seg[:500]
                        final_expr_kind = "answer_assign"
                        break
                    except Exception:
                        pass
            if last_snip:
                break
    return last_snip, final_expr_kind


def _literals_in_source_fragment(src: str) -> set[str]:
    out: set[str] = set()
    if not src.strip():
        return out
    try:
        e = ast.parse(src, mode="eval")
        for node in ast.walk(e):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                n = _normalize_numeric_string(str(node.value))
                if n:
                    out.add(n)
    except SyntaxError:
        pass
    return out


def _opaque_single_expression(code: str) -> bool:
    """Heuristic: one dominant assignment/print line; body stmt count <= 3 non-comment."""
    if not code.strip():
        return True
    lines = [ln for ln in code.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if len(lines) <= 1:
        return True
    if not _syntax_ok(code):
        return False
    tree = ast.parse(code)
    real = [s for s in tree.body if not isinstance(s, ast.Import) and not isinstance(s, ast.ImportFrom)]
    return len(real) <= 2


def _entity_comment_signal(code: str) -> bool:
    return bool(re.search(r"#\s*[a-z]{4,}", code, re.I))


def _problem_quantity_coverage(code: str, problem: str, answer_for_cov: str) -> float | None:
    v = validate_gsm8k_candidate(
        problem_text=problem,
        candidate_answer=answer_for_cov or "0",
        candidate_trace=None,
        candidate_code=code or None,
        source_family="pal_code_audit",
        execution_metadata=None,
    )
    return v.get("quantity_coverage")


def audit_row(
    *,
    case_id: str,
    audit_cohort: str,
    question: str,
    gold_for_offline: str,
    pal_row: dict[str, Any] | None,
    sf_row: dict[str, Any] | None,
) -> dict[str, Any]:
    code, stdout, px = _extract_pal_code_stdout(pal_row, sf_row)
    empty_code = not bool(code.strip())
    syn = _syntax_ok(code)
    exec_ok = _exec_ok_from_metadata(
        {
            **px,
            **(
                px.get("pal_execution_result")
                if isinstance(px.get("pal_execution_result"), dict)
                else {}
            ),
        }
    )

    salient = _salient_problem_norms(question)
    hay = code.lower()
    unused = [n for n in salient if not _normalized_value_in_haystack(n, hay)]

    literals: set[str] = set()
    ops: Counter[str] = Counter()
    sub_n = 0
    muldiv_n = 0
    all_names: set[str] = set()
    if syn and code.strip():
        tree = ast.parse(code)
        literals, ops, sub_n, muldiv_n = _collect_literals_and_ops(tree)
        all_names = _collect_names(tree)

    matched_problem = sum(1 for n in salient if _normalized_value_in_haystack(n, hay))

    final_snip, final_kind = _final_print_or_answer_expr(code)
    final_lits = _literals_in_source_fragment(final_snip)
    qhay = question.lower().replace(",", "")
    ungrounded_final_literals = [
        lit for lit in final_lits if not _normalized_value_in_haystack(lit, qhay)
    ]

    state_hits = bool(STATE_NAME_RE.search(code))
    rate_hits = bool(RATE_NAME_RE.search(code))

    req_cues = _required_operation_cues(question)
    temporal_req = "temporal" in req_cues
    rate_req = "rate" in req_cues

    # Fewer quantities in final than in earlier code: compare literal counts
    body_lits = literals
    final_lit_count = len(final_lits) if final_snip else 0
    fewer_in_final = len(body_lits) > 0 and final_lit_count < max(1, len(body_lits) // 2)

    cov = _problem_quantity_coverage(code, question, stdout[:80] if stdout else "")

    pal_answer = ""
    if sf_row and isinstance(sf_row.get("method_records"), dict):
        pm = sf_row["method_records"].get(PAL_METHOD)
        if isinstance(pm, dict):
            pal_answer = str(pm.get("controller_final_answer_raw") or pm.get("final_answer_raw") or "")

    gold_match = False
    if gold_for_offline and pal_answer:
        ca = canonicalize_answer(pal_answer.strip(), dataset=DATASET)
        cg = canonicalize_answer(str(gold_for_offline).strip(), dataset=DATASET)
        gold_match = bool(ca and cg and ca == cg)

    return {
        "case_id": case_id,
        "audit_cohort": audit_cohort,
        "pal_code_len": len(code),
        "pal_code_empty": empty_code,
        "syntax_ok": syn,
        "exec_ok": exec_ok,
        "pal_stdout_preview": (stdout[:200].replace("\n", "\\n")),
        "n_numeric_literals_in_code": len(literals),
        "n_salient_problem_quantities": len(salient),
        "n_literals_match_problem_quantities": matched_problem,
        "n_unused_salient_quantities": len(unused),
        "unused_salient_quantities_json": json.dumps(unused[:30]),
        "operation_cues_required_json": json.dumps(req_cues),
        "temporal_cue_required": temporal_req,
        "rate_cue_required": rate_req,
        "final_expr_kind": final_kind,
        "final_expr_snippet": final_snip[:400],
        "final_expr_numeric_literals_json": json.dumps(sorted(final_lits)[:20]),
        "op_counts_json": json.dumps(dict(ops)),
        "subtraction_binop_count": sub_n,
        "mul_div_floor_count": muldiv_n,
        "state_like_name_signal": state_hits,
        "rate_like_name_signal": rate_hits,
        "opaque_one_expression_heuristic": _opaque_single_expression(code),
        "final_uses_fewer_quantities_than_body_heuristic": fewer_in_final,
        "code_has_comment_with_words": _entity_comment_signal(code),
        "quantity_coverage_validator": cov,
        "ungrounded_numeric_literals_in_final_expr_json": json.dumps(ungrounded_final_literals[:10]),
        "matches_gold_offline": gold_match,
    }


# --- Candidate static triggers (offline only) ---------------------------------

def trigger_temporal_no_state_no_sub(r: dict[str, Any]) -> bool:
    if not r.get("temporal_cue_required"):
        return False
    return (
        not r.get("state_like_name_signal")
        and int(r.get("subtraction_binop_count") or 0) == 0
    )


def trigger_rate_no_muldiv(r: dict[str, Any]) -> bool:
    if not r.get("rate_cue_required"):
        return False
    return int(r.get("mul_div_floor_count") or 0) == 0


def trigger_many_unused_and_final_sparse(r: dict[str, Any]) -> bool:
    try:
        fl = json.loads(r.get("final_expr_numeric_literals_json") or "[]")
    except json.JSONDecodeError:
        fl = []
    return int(r.get("n_unused_salient_quantities") or 0) >= 2 and len(fl) <= 1


def trigger_ungrounded_final_literal(r: dict[str, Any]) -> bool:
    u = json.loads(r.get("ungrounded_numeric_literals_in_final_expr_json") or "[]")
    return len(u) > 0


def trigger_syntax_exec_empty(r: dict[str, Any]) -> bool:
    if r.get("pal_code_empty"):
        return True
    if r.get("syntax_ok") is False:
        return True
    ex = r.get("exec_ok")
    return ex is False


def trigger_opaque_low_cov(r: dict[str, Any]) -> bool:
    cov = r.get("quantity_coverage_validator")
    if cov is None:
        return False
    return bool(r.get("opaque_one_expression_heuristic")) and float(cov) < 0.34


BASE_TRIGGER_FNS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "temporal_no_state_no_sub": trigger_temporal_no_state_no_sub,
    "rate_no_muldiv": trigger_rate_no_muldiv,
    "many_unused_final_sparse": trigger_many_unused_and_final_sparse,
    "ungrounded_final_literal": trigger_ungrounded_final_literal,
    "syntax_exec_or_empty": trigger_syntax_exec_empty,
    "opaque_one_expr_low_coverage": trigger_opaque_low_cov,
}

BASE_TRIGGER_SCHEMA: dict[str, str] = {
    "temporal_no_state_no_sub": "state-table retry",
    "rate_no_muldiv": "rate-equation retry",
    "many_unused_final_sparse": "quantity-grounding retry",
    "ungrounded_final_literal": "quantity-grounding retry",
    "syntax_exec_or_empty": "PAL repair / codegen retry",
    "opaque_one_expr_low_coverage": "aggregation / decomposition retry",
}

# Back-compat name for the original small audit path (base triggers only).
TRIGGER_FNS = BASE_TRIGGER_FNS
TRIGGER_SCHEMA = BASE_TRIGGER_SCHEMA


def _trigger_any_static_pal_suspicion(r: dict[str, Any]) -> bool:
    return any(BASE_TRIGGER_FNS[n](r) for n in PROMISING_TRIGGER_GROUP)


def _trigger_high_precision_static_pal_suspicion(r: dict[str, Any]) -> bool:
    return (
        BASE_TRIGGER_FNS["rate_no_muldiv"](r)
        or BASE_TRIGGER_FNS["many_unused_final_sparse"](r)
        or BASE_TRIGGER_FNS["syntax_exec_or_empty"](r)
    )


def _trigger_temporal_specific_retry_candidate(r: dict[str, Any]) -> bool:
    return BASE_TRIGGER_FNS["temporal_no_state_no_sub"](r)


def _trigger_rate_specific_retry_candidate(r: dict[str, Any]) -> bool:
    return BASE_TRIGGER_FNS["rate_no_muldiv"](r)


COMBINED_TRIGGER_FNS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "any_static_pal_suspicion": _trigger_any_static_pal_suspicion,
    "high_precision_static_pal_suspicion": _trigger_high_precision_static_pal_suspicion,
    "temporal_specific_retry_candidate": _trigger_temporal_specific_retry_candidate,
    "rate_specific_retry_candidate": _trigger_rate_specific_retry_candidate,
}

COMBINED_TRIGGER_SCHEMA: dict[str, str] = {
    "any_static_pal_suspicion": "OR(temporal, rate_no_muldiv, many_unused_final_sparse)",
    "high_precision_static_pal_suspicion": "OR(rate_no_muldiv, many_unused_final_sparse, syntax_exec_or_empty)",
    "temporal_specific_retry_candidate": "temporal_no_state_no_sub only",
    "rate_specific_retry_candidate": "rate_no_muldiv only",
}

SCALED_TRIGGER_FNS: dict[str, Callable[[dict[str, Any]], bool]] = {
    **BASE_TRIGGER_FNS,
    **COMBINED_TRIGGER_FNS,
}
SCALED_TRIGGER_SCHEMA: dict[str, str] = {**BASE_TRIGGER_SCHEMA, **COMBINED_TRIGGER_SCHEMA}


def _bundle_track_b_pilot(bundle: Path) -> bool:
    return "track_b_ab_pilot" in bundle.name


def _read_csv_header(path: Path) -> list[str]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as fp:
        r = csv.DictReader(fp)
        return list(r.fieldnames or [])


def _load_bundle_casebook_maps(bundle: Path) -> tuple[dict[str, dict[str, str]], str]:
    for name, style in (
        ("all_casebook.csv", "collect_casebook"),
        ("paired_casebook.csv", "paired_casebook"),
    ):
        p = bundle / name
        if not p.is_file():
            continue
        rows = load_csv_rows(p)
        by_id = {r["case_id"]: r for r in rows if r.get("case_id")}
        return by_id, style
    return {}, "none"


def _present_not_selected_ids(bundle: Path) -> set[str]:
    p = bundle / "present_not_selected_replay_table.csv"
    if not p.is_file():
        return set()
    rows = load_csv_rows(p)
    return {r["case_id"] for r in rows if r.get("case_id")}


def _assign_scaled_cohort(
    *,
    bundle: Path,
    case_id: str,
    casebook_by_id: dict[str, dict[str, str]],
    casebook_style: str,
    ft_map: dict[str, str],
    pn_ids: set[str],
) -> str:
    if _bundle_track_b_pilot(bundle):
        return COHORT_PILOT_B
    cb = casebook_by_id.get(case_id)

    if casebook_style == "collect_casebook":
        if ft_map.get(case_id) == "gold_absent_discovery":
            return COHORT_GOLD_ABSENT
        if case_id in pn_ids:
            return COHORT_PN
        if cb and cb.get("pal_correct") == "1" and cb.get("best_external_correct") == "1":
            return COHORT_GUARDRAIL
        if cb and cb.get("pal_correct") == "0":
            return COHORT_PAL_WRONG
        return COHORT_UNKNOWN

    if casebook_style == "paired_casebook" and cb:
        hdr = _read_csv_header(bundle / "paired_casebook.csv")
        if "track_b_exact_match" in hdr or "baseline_exact_match" in hdr:
            return COHORT_PILOT_B
        if "pal_gold_absent" in cb or "pal_present_not_selected" in cb:
            if cb.get("pal_gold_absent") == "1":
                return COHORT_GOLD_ABSENT
            if cb.get("pal_present_not_selected") == "1":
                return COHORT_PN
            if cb.get("both_correct") == "1":
                return COHORT_GUARDRAIL
            if cb.get("pal_exact") == "0":
                return COHORT_PAL_WRONG
            return COHORT_UNKNOWN
        if "best_external_correct" in cb:
            if cb.get("pal_correct") == "1" and cb.get("best_external_correct") == "1":
                return COHORT_GUARDRAIL
            if cb.get("pal_correct") == "0":
                return COHORT_PAL_WRONG
            return COHORT_UNKNOWN

    return COHORT_UNKNOWN


def _raw_pal_execution_dict(raw: dict[str, Any]) -> dict[str, Any] | None:
    pe = raw.get("pal_execution")
    if not isinstance(pe, dict):
        pe = None
    if not pe or not str(pe.get("pal_code") or "").strip():
        rm = raw.get("result_metadata")
        if isinstance(rm, dict):
            pe2 = rm.get("pal_execution")
            if isinstance(pe2, dict):
                pe = pe2
    if not isinstance(pe, dict) or not str(pe.get("pal_code") or "").strip():
        return None
    return pe


def normalize_pal_jsonl_row(raw: dict[str, Any]) -> dict[str, Any] | None:
    pe = _raw_pal_execution_dict(raw)
    if pe is None:
        return None
    out = dict(raw)
    out["pal_execution"] = pe
    return out


def discover_output_bundle_dirs(repo: Path) -> list[Path]:
    out = repo / "outputs"
    if not out.is_dir():
        return []
    roots: list[Path] = []
    for d in sorted(out.iterdir()):
        if not d.is_dir():
            continue
        if any((d / name).is_file() for name in PAL_JSONL_NAMES):
            roots.append(d)
    return roots


def iter_bundle_pal_records(bundle: Path) -> Iterator[tuple[dict[str, Any], str]]:
    """Yield (normalized_row, jsonl_basename) for PAL rows with non-empty pal_code."""
    for name in PAL_JSONL_NAMES:
        path = bundle / name
        if not path.is_file():
            continue
        with path.open(encoding="utf-8", errors="replace") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("method") != PAL_METHOD:
                    continue
                norm = normalize_pal_jsonl_row(d)
                if norm is None:
                    continue
                yield norm, name


def _policy_label(*, n_ga: int, n_gr: int, ga_rate: float, gr_rate: float) -> str:
    if n_ga < 10 or n_gr < 15:
        return "inconclusive"
    if gr_rate > 0.10 or ga_rate <= 0.10:
        return "weak"
    if ga_rate >= 0.20 and gr_rate <= 0.05:
        return "promising"
    return "mixed"


def _trigger_metrics_scaled(
    *,
    label: str,
    fn: Callable[[dict[str, Any]], bool],
    rows: list[dict[str, Any]],
    cohort_counts: dict[str, int],
) -> dict[str, Any]:
    fired = [r for r in rows if fn(r)]
    by_cohort: Counter[str] = Counter()
    for r in fired:
        by_cohort[r["audit_cohort"]] += 1

    def rate(cohort: str) -> float:
        d = cohort_counts.get(cohort, 0)
        return by_cohort[cohort] / d if d else 0.0

    n_ga = cohort_counts.get(COHORT_GOLD_ABSENT, 0)
    n_gr = cohort_counts.get(COHORT_GUARDRAIL, 0)
    ga_f = by_cohort[COHORT_GOLD_ABSENT]
    gr_f = by_cohort[COHORT_GUARDRAIL]
    pn_f = by_cohort[COHORT_PN]
    policy = _policy_label(
        n_ga=n_ga,
        n_gr=n_gr,
        ga_rate=ga_f / n_ga if n_ga else 0.0,
        gr_rate=gr_f / n_gr if n_gr else 0.0,
    )

    labeled_fires = sum(by_cohort[c] for c in LABELED_COHORTS)
    precision_like = ga_f / labeled_fires if labeled_fires else 0.0
    disc_den = ga_f + gr_f + pn_f + by_cohort[COHORT_PAL_WRONG]
    precision_like_excl_pilot = ga_f / disc_den if disc_den else 0.0

    top = sorted(
        fired,
        key=lambda r: (
            0 if r["audit_cohort"] == COHORT_GOLD_ABSENT else 1,
            r["case_id"],
        ),
    )[:20]

    bundle_bd: Counter[str] = Counter(str(r.get("bundle_slug") or "") for r in fired)

    return {
        "actionable_retry_schema_hint": SCALED_TRIGGER_SCHEMA.get(label, ""),
        "fires_by_cohort": dict(by_cohort),
        "cohort_sizes": dict(cohort_counts),
        "rates": {
            COHORT_GOLD_ABSENT: rate(COHORT_GOLD_ABSENT),
            COHORT_GUARDRAIL: rate(COHORT_GUARDRAIL),
            COHORT_PN: rate(COHORT_PN),
            COHORT_PAL_WRONG: rate(COHORT_PAL_WRONG),
            COHORT_PILOT_B: rate(COHORT_PILOT_B),
            COHORT_UNKNOWN: rate(COHORT_UNKNOWN),
        },
        "fires_gold_absent_discovery": ga_f,
        "fires_pal_correct_guardrail": gr_f,
        "fires_present_not_selected": pn_f,
        "fires_pal_wrong_other": by_cohort[COHORT_PAL_WRONG],
        "fires_pilot_track_b": by_cohort[COHORT_PILOT_B],
        "fires_unknown_cohort": by_cohort[COHORT_UNKNOWN],
        "precision_like_among_labeled_fires": precision_like,
        "precision_like_ga_over_discovery_guardrail_pn_wrong_fires": precision_like_excl_pilot,
        "policy_usefulness": policy,
        "top_cases": [
            {
                "case_id": r["case_id"],
                "bundle_slug": r.get("bundle_slug"),
                "audit_cohort": r["audit_cohort"],
            }
            for r in top
        ],
        "bundle_breakdown_fires": dict(bundle_bd),
    }


def run_all_available_audit(repo: Path, out_dir: Path) -> None:
    bundles = discover_output_bundle_dirs(repo)
    dedup: dict[tuple[str, str, str], dict[str, Any]] = {}

    for bundle in bundles:
        casebook_by_id, casebook_style = _load_bundle_casebook_maps(bundle)
        ft_map = load_failure_cluster_map(bundle / "failure_cluster_summary.csv")
        pn_ids = _present_not_selected_ids(bundle)
        sf_by_case = load_selected_failures(bundle / "selected_failure_cases.jsonl")

        for raw_row, src_jsonl in iter_bundle_pal_records(bundle):
            cid = str(raw_row.get("case_id") or raw_row.get("example_id") or "").strip()
            if not cid:
                continue
            method = str(raw_row.get("method") or PAL_METHOD)
            key = (cid, bundle.name, method)
            if key in dedup:
                continue

            cohort = _assign_scaled_cohort(
                bundle=bundle,
                case_id=cid,
                casebook_by_id=casebook_by_id,
                casebook_style=casebook_style,
                ft_map=ft_map,
                pn_ids=pn_ids,
            )
            cb = casebook_by_id.get(cid)
            gold = (cb.get("gold_answer") or "") if cb else ""
            q = (cb.get("question") or "") if cb else ""
            sf = sf_by_case.get(cid)
            if not q:
                q = str(raw_row.get("question") or "")
            if not q and sf:
                q = str(sf.get("question") or "")
            if not gold:
                gold = str(raw_row.get("gold_answer") or "")
            if not gold and sf:
                gold = str(sf.get("gold_answer") or "")

            base = audit_row(
                case_id=cid,
                audit_cohort=cohort,
                question=q,
                gold_for_offline=gold,
                pal_row=raw_row,
                sf_row=sf,
            )
            base["bundle_slug"] = bundle.name
            base["source_jsonl"] = src_jsonl
            base["pal_method"] = method
            dedup[key] = base

    rows = sorted(dedup.values(), key=lambda r: (r["bundle_slug"], r["case_id"]))
    cohort_counts = Counter(str(r["audit_cohort"]) for r in rows)
    cohort_counts_full = {
        COHORT_GOLD_ABSENT: cohort_counts.get(COHORT_GOLD_ABSENT, 0),
        COHORT_PN: cohort_counts.get(COHORT_PN, 0),
        COHORT_GUARDRAIL: cohort_counts.get(COHORT_GUARDRAIL, 0),
        COHORT_PAL_WRONG: cohort_counts.get(COHORT_PAL_WRONG, 0),
        COHORT_PILOT_B: cohort_counts.get(COHORT_PILOT_B, 0),
        COHORT_UNKNOWN: cohort_counts.get(COHORT_UNKNOWN, 0),
    }

    trig_out: dict[str, Any] = {}
    for tname, fn in SCALED_TRIGGER_FNS.items():
        trig_out[tname] = _trigger_metrics_scaled(
            label=tname,
            fn=fn,
            rows=rows,
            cohort_counts=dict(cohort_counts_full),
        )

    summary = {
        "mode": "all_available_scaled",
        "repo": str(repo),
        "bundles_scanned": [b.name for b in bundles],
        "n_bundles_with_pal_code_rows": len({r["bundle_slug"] for r in rows}),
        "n_rows_after_dedup": len(rows),
        "dedup_key": ["case_id", "bundle_slug", "pal_method"],
        "cohort_counts": cohort_counts_full,
        "labeling_coverage": {
            "rows_with_offline_stratification": sum(
                cohort_counts_full[c] for c in LABELED_COHORTS if c != COHORT_UNKNOWN
            ),
            "note": (
                "Rates and policy on gold_absent_discovery / pal_correct_guardrail use cohort_counts as "
                "denominators; most PAL-code rows are unknown without a paired casebook / failure cluster."
            ),
        },
        "triggers": trig_out,
        "cohort_priority_notes": (
            "Mutually exclusive: pilot_track_b (bundle name) first; "
            "else collect-style or paired-casebook labels from offline fields only."
        ),
        "notes": {
            "gold_used_only_offline": True,
            "validator_validate_gsm8k_candidate_used_for_quantity_coverage_only": True,
            "no_api": True,
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    if rows:
        fields = list(rows[0].keys())
        with (out_dir / "pal_code_static_audit_scaled.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in rows:
                w.writerow(row)
    (out_dir / "pal_code_static_audit_scaled_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    (out_dir / "pal_code_static_audit_scaled_report.md").write_text(
        _markdown_report_scaled(summary),
        encoding="utf-8",
    )
    print(f"Wrote scaled PAL code audit to {out_dir}")


def _markdown_report_scaled(summary: dict[str, Any]) -> str:
    tr = summary["triggers"]
    cc = summary["cohort_counts"]
    promising = [n for n, s in tr.items() if s.get("policy_usefulness") == "promising"]
    weak = [n for n, s in tr.items() if s.get("policy_usefulness") == "weak"]
    inconc = [n for n, s in tr.items() if s.get("policy_usefulness") == "inconclusive"]

    lines = [
        "# PAL code static audit — scaled (all local bundles)",
        "",
        "Offline only — **no** API, **no** controllers, **no** selection changes.",
        "",
        "## Cohort counts (offline labels)",
        "",
        summary.get("labeling_coverage", {}).get("note", ""),
        "",
        "```json",
        json.dumps(cc, indent=2),
        "```",
        "",
        "## Trigger metrics",
        "",
        "| Trigger | GA fires / rate | Guardrail fires / rate | PN fires / rate | "
        "Precision-like (labeled fires) | Policy |",
        "|---------|-----------------|------------------------|-----------------|"
        "--------------------------------|--------|",
    ]
    for name in sorted(tr.keys()):
        s = tr[name]
        n_ga = s["cohort_sizes"].get(COHORT_GOLD_ABSENT, 0)
        n_gr = s["cohort_sizes"].get(COHORT_GUARDRAIL, 0)
        ga_f = s["fires_gold_absent_discovery"]
        gr_f = s["fires_pal_correct_guardrail"]
        pn_f = s["fires_present_not_selected"]
        rga = ga_f / n_ga if n_ga else 0.0
        rgr = gr_f / n_gr if n_gr else 0.0
        rpn = pn_f / s["cohort_sizes"].get(COHORT_PN, 1) if s["cohort_sizes"].get(COHORT_PN, 0) else 0.0
        lines.append(
            f"| `{name}` | {ga_f} / {rga:.3f} | {gr_f} / {rgr:.3f} | {pn_f} / {rpn:.3f} | "
            f"**{s['precision_like_among_labeled_fires']:.3f}** | **{s['policy_usefulness']}** |"
        )

    lines.extend(
        [
            "",
            "### Policy buckets",
            "",
            f"- **Promising:** ≥20% of `gold_absent_discovery` **and** ≤5% of `pal_correct_guardrail`, "
            f"with cohort denominators n_ga≥10 and n_gr≥15; else **inconclusive** if too small. "
            f"**Weak:** ≤10% GA **or** >10% guardrail.",
            "",
            f"- **Promising triggers now:** {', '.join(f'`{x}`' for x in promising) or '_(none)_'}",
            f"- **Weak / noisy:** {', '.join(f'`{x}`' for x in weak) or '_(none)_'}",
            f"- **Inconclusive (small denominators):** {', '.join(f'`{x}`' for x in inconc) or '_(none)_'}",
            "",
            "## Bundle coverage",
            "",
            f"- Bundles scanned: **{summary['n_bundles_with_pal_code_rows']}** with ≥1 PAL-code row.",
            f"- Total deduped rows: **{summary['n_rows_after_dedup']}**.",
            "",
            "## Top fired cases (per trigger, first 20 in JSON)",
            "",
            "See `pal_code_static_audit_scaled_summary.json` → `triggers.*.top_cases` and "
            "`bundle_breakdown_fires`.",
            "",
            "## Track A retry / TRCE path",
            "",
            _scaled_track_a_verdict(promising),
            "",
            "**API:** not required for this audit.",
        ]
    )
    return "\n".join(lines)


def _scaled_track_a_verdict(promising: list[str]) -> str:
    if not promising:
        return (
            "**Verdict:** No trigger met the **promising** thresholds on this scaled offline slice. "
            "**Static PAL-code triggers are not yet strong enough** to justify implementing Track A "
            "retry/TRCE policy — **pause** this direction until richer offline pools or stronger signals."
        )
    return (
        f"**Verdict:** Triggers {', '.join(f'`{p}`' for p in promising)} look **promising** under the stated "
        "thresholds — a **targeted** Track A prototype (flag-guarded retries mapped to those schemas) may "
        "be worth implementing; validate on additional held-out PAL bundles before any live default."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--all-available",
        action="store_true",
        help="Scan outputs/* bundles for PAL JSONL rows with code; write scaled artifacts under out-dir/pal_code_static_audit_scaled/.",
    )
    args = ap.parse_args()
    repo = REPO_ROOT
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.all_available:
        scaled_dir = out_dir / "pal_code_static_audit_scaled"
        run_all_available_audit(repo, scaled_dir)
        return

    random.seed(args.seed)
    bundle = args.bundle_dir.resolve()

    ft_map = load_failure_cluster_map(bundle / "failure_cluster_summary.csv")
    ga_ids = sorted(cid for cid, ft in ft_map.items() if ft == "gold_absent_discovery")

    casebook_rows = load_csv_rows(bundle / "all_casebook.csv")
    casebook_by_id = {r["case_id"]: r for r in casebook_rows if r.get("case_id")}
    guard_ids = sorted(guardrail_case_ids(casebook_rows))
    guard_sample = random.sample(guard_ids, min(25, len(guard_ids)))

    replay_rows = load_csv_rows(bundle / "present_not_selected_replay_table.csv")
    pn_ids = sorted({r["case_id"] for r in replay_rows if r.get("case_id")})
    pn_sample = random.sample(pn_ids, min(10, len(pn_ids)))

    pal_by_case = load_pal_all_results(bundle / "all_results.jsonl")
    sf_by_case = load_selected_failures(bundle / "selected_failure_cases.jsonl")

    rows: list[dict[str, Any]] = []

    def run_case(cid: str, cohort: str) -> None:
        cb = casebook_by_id.get(cid)
        gold = (cb.get("gold_answer") or "") if cb else ""
        q = (cb.get("question") or "") if cb else ""
        sf = sf_by_case.get(cid)
        if not q and sf:
            q = str(sf.get("question") or "")
        if not gold and sf:
            gold = str(sf.get("gold_answer") or "")
        pal_row = pal_by_case.get(cid)
        if not q and pal_row:
            q = str(pal_row.get("question") or "")
        if not gold and pal_row:
            gold = str(pal_row.get("gold_answer") or "")
        rows.append(
            audit_row(
                case_id=cid,
                audit_cohort=cohort,
                question=q,
                gold_for_offline=gold,
                pal_row=pal_row,
                sf_row=sf,
            )
        )

    for cid in ga_ids:
        run_case(cid, "gold_absent_discovery")
    for cid in guard_sample:
        run_case(cid, "guardrail_correct_sample")
    for cid in pn_sample:
        run_case(cid, "present_not_selected_sample")

    # Trigger statistics
    def bucket(r: dict[str, Any]) -> str:
        c = r["audit_cohort"]
        if c == "gold_absent_discovery":
            return "gold_absent"
        if c == "guardrail_correct_sample":
            return "guardrail"
        if c == "present_not_selected_sample":
            return "present_not_selected"
        return "other"

    stats: dict[str, Any] = {}
    buckets = {"gold_absent": [], "guardrail": [], "present_not_selected": []}
    for r in rows:
        b = bucket(r)
        if b in buckets:
            buckets[b].append(r)

    for tname, fn in TRIGGER_FNS.items():
        ga_f = sum(1 for r in buckets["gold_absent"] if fn(r))
        gr_f = sum(1 for r in buckets["guardrail"] if fn(r))
        pn_f = sum(1 for r in buckets["present_not_selected"] if fn(r))
        tot = ga_f + gr_f + pn_f
        n_ga = len(buckets["gold_absent"])
        n_gr = len(buckets["guardrail"])
        stats[tname] = {
            "actionable_retry_schema_hint": TRIGGER_SCHEMA[tname],
            "fires_gold_absent": ga_f,
            "rate_gold_absent": ga_f / max(n_ga, 1),
            "fires_guardrail": gr_f,
            "rate_guardrail_fp": gr_f / max(n_gr, 1),
            "fires_present_not_selected": pn_f,
            "fires_total": tot,
            "precision_like_ga_given_fired": ga_f / tot if tot else 0.0,
        }

    # Aggregate comparisons
    def mean(xs: list[float]) -> float:
        return sum(xs) / max(len(xs), 1)

    ga_cov = [float(r["quantity_coverage_validator"]) for r in buckets["gold_absent"] if r["quantity_coverage_validator"] is not None]
    gr_cov = [float(r["quantity_coverage_validator"]) for r in buckets["guardrail"] if r["quantity_coverage_validator"] is not None]

    summary = {
        "bundle": str(bundle),
        "cases": {
            "gold_absent_discovery": len(ga_ids),
            "guardrail_sampled": len(guard_sample),
            "present_not_selected_sampled": len(pn_sample),
        },
        "cohort_comparison": {
            "mean_quantity_coverage_gold_absent": mean(ga_cov) if ga_cov else None,
            "mean_quantity_coverage_guardrail": mean(gr_cov) if gr_cov else None,
            "mean_unused_salient_gold_absent": mean(
                [float(r["n_unused_salient_quantities"]) for r in buckets["gold_absent"]]
            ),
            "mean_unused_salient_guardrail": mean(
                [float(r["n_unused_salient_quantities"]) for r in buckets["guardrail"]]
            ),
            "mean_opaque_one_expr_gold_absent": mean(
                [1.0 if r["opaque_one_expression_heuristic"] else 0.0 for r in buckets["gold_absent"]]
            ),
            "mean_opaque_one_expr_guardrail": mean(
                [1.0 if r["opaque_one_expression_heuristic"] else 0.0 for r in buckets["guardrail"]]
            ),
        },
        "static_triggers": stats,
        "notes": {
            "gold_used_only_offline": True,
            "validator_validate_gsm8k_candidate_used_for_quantity_coverage_only": True,
        },
    }

    if rows:
        fields = list(rows[0].keys())
        with (out_dir / "pal_code_static_audit.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in sorted(rows, key=lambda x: (x["audit_cohort"], x["case_id"])):
                w.writerow(row)

    (out_dir / "pal_code_static_audit_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = _markdown_report(summary, buckets)
    (out_dir / "pal_code_static_audit_report.md").write_text(report, encoding="utf-8")
    print(f"Wrote PAL code audit to {out_dir}")


def _markdown_report(summary: dict[str, Any], buckets: dict[str, list]) -> str:
    st = summary["static_triggers"]
    cc = summary["cohort_comparison"]
    lines = [
        "# PAL code static audit (Track A diagnostic)",
        "",
        "Offline only — **no** API, **no** controllers, **no** selection.",
        "",
        "## A. Why broad validator triggers were insufficient",
        "",
        "Coarse regex cues (`temporal_cue_gap`, etc.) achieved **low recall** on gold-absent rows and **material guardrail FPs**. "
        "This audit inspects **PAL Python** directly for structural patterns (ops, literals vs problem quantities, opacity).",
        "",
        "## B. PAL-code audit method",
        "",
        "- Sources: `all_results.jsonl` + `selected_failure_cases.jsonl` (`pal_execution.pal_code`, stdout preview).",
        "- **Problem quantities**: `_salient_problem_norms` (same as structural validator) — **no gold as checker input**.",
        "- **Quantity coverage**: `validate_gsm8k_candidate` called with **problem + code + stdout preview** for the coverage field only.",
        "- AST: literals, `+ - * / //`, `sum()`, subtraction binops, final `print`/`answer` snippet heuristics.",
        "",
        "## C. Gold-absent vs guardrail code-feature comparison",
        "",
        "```json",
        json.dumps(cc, indent=2),
        "```",
        "",
        "## D. Candidate static triggers",
        "",
        "| Trigger | GA rate | Guardrail FP rate | Precision-like | Retry schema |",
        "|---------|---------|-------------------|----------------|--------------|",
    ]
    for name, s in sorted(st.items()):
        lines.append(
            f"| `{name}` | **{s['rate_gold_absent']:.3f}** | **{s['rate_guardrail_fp']:.3f}** "
            f"| **{s['precision_like_ga_given_fired']:.3f}** | {s['actionable_retry_schema_hint']} |"
        )

    best = max(st.items(), key=lambda kv: kv[1]["precision_like_ga_given_fired"] if kv[1]["fires_total"] else -1)
    worst_fp = max(st.items(), key=lambda kv: kv[1]["rate_guardrail_fp"])

    lines.extend(
        [
            "",
            "## E. Promising / rejected triggers",
            "",
            f"- **Highest precision-like (among fired):** `{best[0]}` (~**{best[1]['precision_like_ga_given_fired']:.2f}**).",
            f"- **Highest guardrail FP rate:** `{worst_fp[0]}` (~**{worst_fp[1]['rate_guardrail_fp']:.2f}** on this sample).",
            "",
            _verdict(st),
            "",
            "## F. Examples worth manual inspection",
            "",
            _examples_section(buckets),
            "",
            "## G. Relationship to Combinatorial Opt Agent verification",
            "",
            "Same philosophy: **cheap structural checks** on candidate artifacts before expensive reasoning — here applied to **PAL code shape**.",
            "",
            "## H. Whether to continue Track A PAL-code validator direction",
            "",
            _continue_verdict(st),
            "",
            "## I. Exact next implementation query",
            "",
            "> If any static trigger keeps precision-like **>** ~0.35 **and** guardrail FP **<** ~0.15 on **large** slices "
            "with **≥30** aggregate fires, prototype optional retry templates behind flags. "
            "On this tiny audit, **do not** enable automatic triggers.",
            "",
            "**API:** not required.",
        ]
    )
    return "\n".join(lines)


def _verdict(st: dict[str, Any]) -> str:
    max_single = max(v["fires_total"] for v in st.values())
    best_name, best_st = max(st.items(), key=lambda kv: kv[1]["precision_like_ga_given_fired"])
    if max_single <= 10:
        return (
            "**Verdict:** Even the busiest trigger fires **≤10** times total here — too few events to claim a clear "
            "algorithmic win over coarse validator cues. Treat **`rate_no_muldiv`** precision-like (~0.60) as "
            "**hypothesis only**. **Pause** automatic Track A triggers until a larger PAL-code audit."
        )
    return (
        f"**Verdict:** Best precision-like **~{best_st['precision_like_ga_given_fired']:.2f}** (`{best_name}`) — "
        "still validate on larger slices before runtime hooks."
    )


def _continue_verdict(st: dict[str, Any]) -> str:
    max_single = max(v["fires_total"] for v in st.values())
    if max_single <= 10:
        return (
            "**The static-analysis trigger path does not yet produce enough fired events** on this bundle to justify "
            "continuing toward runtime Track A policy — **pause** automation; optional **manual** review of `pal_code_static_audit.csv`."
        )
    return "**Continue** only with a **scaled** PAL-code audit (more cases, fixed triggers)."


def _examples_section(buckets: dict[str, list]) -> str:
    ga = buckets["gold_absent"]
    lines = []
    # suspicious: high unused salient + opaque
    susp = sorted(
        ga,
        key=lambda r: (-int(r["n_unused_salient_quantities"]), -int(r["pal_code_len"])),
    )[:5]
    for r in susp:
        lines.append(
            f"- **`{r['case_id']}`:** unused_salient={r['n_unused_salient_quantities']}, "
            f"opaque={r['opaque_one_expression_heuristic']}, cov={r['quantity_coverage_validator']}"
        )
    if not lines:
        return "(none)"
    return "\n".join(lines)


if __name__ == "__main__":
    main()
